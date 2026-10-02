# Uptime Kuma na VPS

`playbooks/uptime-kuma.yml` instala o Uptime Kuma na VPS da Hetzner
(`hetzner` na tailnet). Ele roda fora de casa de propósito: se o Pi, o Proxmox
ou a internet de casa caírem, o monitor continua de pé e avisa.

| O quê | Como |
|---|---|
| Acesso | `https://uptime.lab.nextlevelcode.pro`, pelo Caddy da VPS, só da tailnet |
| Container | `louislam/uptime-kuma:2`, ouvindo só em `127.0.0.1:3001` |
| Dados | `/opt/uptime-kuma/data` (SQLite: monitores, avisos, histórico) |
| Backup | Borg no repositório compartilhado, prefixo `uptime-kuma-*`, 03:00 |
| Docker | instalado pelo `geerlingguy.docker`, **sem** o usuário `hetzner` no grupo `docker` (use `sudo docker`) |

Ele é servido pelo Caddy **da VPS**, não pelo do Proxmox: se o Proxmox cai, o
monitor continua acessível. O nome `uptime.lab` tem um registro A próprio na
Cloudflare, apontando para o IP Tailscale da VPS; o curinga `*.lab` continua no
Caddy do Proxmox. O Caddy da VPS só aceita conexões da tailnet nesse site.

## Aplicação

1. **Registro na Cloudflare** (zona `nextlevelcode.pro`): tipo `A`, nome
   `uptime.lab`, valor `<ip-tailscale-da-vps>` (IP Tailscale da VPS), **DNS only**
   (nuvem cinza). Manual porque o DNS público não é gerido por este repo.

   Confira: `dig +short @1.1.1.1 uptime.lab.nextlevelcode.pro` devolve
   `<ip-tailscale-da-vps>`, e `jellyfin.lab` continua devolvendo o IP do Caddy do
   Proxmox.

2. **ACL do Tailscale** (console):

   | De | Para | Portas | Para quê |
   |---|---|---|---|
   | seus dispositivos | VPS (`hetzner`) | `tcp:443` | abrir o Uptime Kuma |
   | VPS (`hetzner`) | `tag:caddy` | `tcp:443` | monitorar os `*.lab` |
   | VPS (`hetzner`) | Pi | `udp:53`, `tcp:53` | monitorar o DNS do AdGuard |

   Acrescente o que mais for monitorar por porta (ex.: `forgejo-lxc:2222`).

3. **Caddy da VPS.** Antes, o token da Cloudflare da VPS (separado do do
   Proxmox) vai para o vault:

   ```bash
   ssh hetzner@hetzner.<tailnet>.ts.net sudo grep CLOUDFLARE_API_TOKEN /etc/caddy/cf-token.env
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   O valor vai em `vault_caddy_vps_cloudflare_token`. Na primeira vez:
   - o binário custom passa a ficar fora do caminho do `apt` (`dpkg-divert`).
     Antes, ele tinha sido copiado por cima do `/usr/bin/caddy` do pacote, e um
     `apt upgrade` o trocaria pelo oficial, sem o plugin da Cloudflare;
   - o Caddy sobe para a última versão e **reinicia**: o
     `forge.nextlevelcode.pro` pisca por alguns segundos;
   - o `cf-token.env` passa de `644` para `640 root:caddy`.

   ```bash
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ```

   Confira: `curl -s -o /dev/null -w '%{http_code}\n' https://forge.nextlevelcode.pro`
   responde como antes.

4. **Uptime Kuma.** Na primeira vez instala o Docker na VPS:

   ```bash
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Os erros "No package matching 'docker-ce'" no `--check` são esperados (o
   repositório do Docker só é adicionado na execução real) e aparecem como
   `...ignoring`.

   Confira:

   ```bash
   ssh hetzner@hetzner.<tailnet>.ts.net 'sudo docker ps --filter name=uptime-kuma; id -nG'
   curl -s -o /dev/null -w '%{http_code}\n' https://uptime.lab.nextlevelcode.pro/
   ```

   O `id -nG` não deve listar `docker`.

5. **Primeiro acesso** em `https://uptime.lab.nextlevelcode.pro`: o Uptime Kuma
   pede para criar o usuário admin. É manual porque ele não aceita esse
   usuário por variável de ambiente.

6. **Aviso por e-mail** (*Settings → Notifications → Setup Notification →
   SMTP*):

   - host `smtp.protonmail.ch`, porta `587`, segurança STARTTLS;
   - usuário e senha: um **token SMTP** da Proton (em *Settings → IMAP/SMTP →
     SMTP tokens*), de preferência para um endereço só do monitor;
   - marque *Default enabled* e *Apply on all existing monitors*;
   - *Test* tem que chegar na sua caixa.

7. **Primeiro backup:**

   ```bash
   ssh -t hetzner@hetzner.<tailnet>.ts.net 'cd ~ && sudo /usr/local/bin/backup-uptime-kuma.sh'
   ```

## O que monitorar

Sugestão de partida (*Add New Monitor*):

| Monitor | Tipo | Alvo |
|---|---|---|
| Caddy + serviços | HTTP(s) | `https://jellyfin.lab.nextlevelcode.pro`, `immich.lab`, `nextcloud.lab/status.php`, `vault.lab/alive`, `searxng.lab`, `adguard.lab`, `fmd.lab` |
| Forgejo público | HTTP(s) | `https://forge.nextlevelcode.pro` |
| FMD (Funnel) | HTTP(s) | `https://fmd.<tailnet>.ts.net` |
| DNS do AdGuard | DNS | servidor `<ts_ip>`, nome `nextlevelcode.pro` |
| Pi | Ping | `nextlevelcode.<tailnet>.ts.net` |
| Proxmox | Ping | `proxmox.<tailnet>.ts.net` |

Um monitor HTTP que retorna 302 (tela de login) conta como "up"; ajuste
*Accepted Status Codes* se precisar.

## Restore

Não há role de restore. À mão, com o container parado: `borg extract` do
archive `uptime-kuma-*` mais recente para `/opt/uptime-kuma/data` e subir de
novo.
