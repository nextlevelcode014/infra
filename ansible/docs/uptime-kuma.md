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
| Monitores e aviso | **AutoKuma** (`ghcr.io/bigboot/autokuma:2.0.0`), a partir de `inventory/group_vars/vps/monitors.yml` |
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
   | VPS (`hetzner`) | Pi, Proxmox | `icmp` | os monitores de ping |
   | VPS (`hetzner`) | `forgejo-lxc` | `tcp:2222` | o SSH do Forgejo |

   Monitor novo de ping ou porta para outro host precisa da regra
   correspondente; os HTTP pelos `*.lab` já passam pela regra do `tag:caddy`.

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

5. **Primeiro acesso** em `https://uptime.lab.nextlevelcode.pro`: escolha
   **SQLite** e crie o usuário admin. É manual porque o Uptime Kuma não aceita
   esse usuário por variável de ambiente. Use o mesmo usuário e senha que vão
   para o vault (passo 6): o AutoKuma entra com eles.

6. **Vault e AutoKuma.** O aviso por e-mail e os monitores são criados pelo
   AutoKuma, a partir de arquivos que o Ansible gera:

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   | Chave | O quê |
   |---|---|
   | `vault_uptime_kuma_username` / `_password` | o admin do passo 5 |
   | `vault_uptime_kuma_smtp_username` | o endereço Proton que envia (ex.: `monitor@nextlevelcode.pro`) |
   | `vault_uptime_kuma_smtp_password` | um **token SMTP** da Proton (*Settings → IMAP/SMTP → SMTP tokens*) |
   | `vault_uptime_kuma_smtp_to` | quem recebe |

   ```bash
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Confira na interface: os grupos (Raspberry Pi, Proxmox, VPS), os
   monitores da lista e o aviso **E-mail** ligado em todos. Em
   *Settings → Notifications*, clique em *Test* no **E-mail**: tem que chegar
   (no formato **● AVISO**, porque o teste não traz o estado). Se você criou
   um aviso à mão antes, apague-o: ficaria duplicado.

7. **Primeiro backup:**

   ```bash
   ssh -t hetzner@hetzner.<tailnet>.ts.net 'cd ~ && sudo borgmatic -c /etc/borgmatic/uptime-kuma.yaml --verbosity 1 --stats'
   ```

## O que monitorar

A lista fica em `inventory/group_vars/vps/monitors.yml`. Cada item vira um
arquivo `.json` em `/opt/uptime-kuma/autokuma/monitors`, e o AutoKuma cria ou
atualiza o monitor. Para acrescentar um serviço:

```yaml
- {id: meu-servico, group: pi, type: http, name: Meu serviço, url: "https://meu-servico.lab.nextlevelcode.pro"}
```

e reaplicar `playbooks/uptime-kuma.yml`. Item que sai da lista tem o monitor
**apagado**. Os tipos usados são `http`, `dns`, `ping` e `port` (campos em
<https://autokuma.bigboot.dev/dev/entity-types/>).

- O container resolve por **DNS público** (Quad9 e Cloudflare), não pelo
  MagicDNS: assim o monitor do Funnel vê o que a internet vê. Por isso ping e
  porta usam o IP Tailscale; os `*.lab` são públicos e resolvem normalmente.
- Sonarr, Radarr e Prowlarr usam `/ping`: a raiz redireciona para
  `http://…/login` (eles não sabem que estão atrás de HTTPS), na porta 80, que
  a VPS não alcança.
- Todo monitor tem `max_retries: 2` (`uptime_kuma_monitor_defaults`): um
  container parado alguns segundos pelo backup não vira e-mail.
- **Não edite pela interface os monitores do AutoKuma:** a próxima
  sincronização desfaz a mudança. Monitor criado à mão fica, e o AutoKuma não
  mexe nele.

## Atualizações: reboot pendente

O role `reboot_watch` (dependência do `vps_host` e do `pi_host`) põe em cada
host um timer de hora em hora que empurra um monitor push do grupo
*Atualizações*:

| Situação no host | Monitor |
|---|---|
| tudo certo | up |
| `/var/run/reboot-required` com mais de 3 dias (`reboot_watch_grace_days`) | down, com os pacotes que pediram o reboot |
| `apt-daily-upgrade.service` (quem roda o unattended-upgrades) em `failed` | down, com o motivo |
| host fora ou timer parado | down quando passa 2 h sem push |

Os 3 dias evitam e-mail a cada kernel novo: o aviso só sai quando o reboot já
ficou esquecido. O reboot apaga o `/var/run/reboot-required` (tmpfs), e o
próximo push já volta a up. Para não esperar a hora cheia:

```bash
sudo systemctl start reboot-watch.service
```

O token sai da senha do Borg + `reboot-<host>`, como o do backup
(`reboot_watch_push_token` em `group_vars/all`). Host novo: uma linha em
`uptime_kuma_reboot_watch` (`group_vars/vps/monitors.yml`), com o
`inventory_hostname` dele. LXC não entra: o kernel é o do Proxmox.

Confira depois de aplicar, no host:

```bash
systemctl list-timers reboot-watch.timer   # próxima execução marcada
sudo systemctl start reboot-watch.service && systemctl status reboot-watch.service --no-pager
```

O status tem que terminar em `Deactivated successfully` (o `curl` falha a
unit se o Uptime Kuma recusar o push), e o monitor fica verde.

## Status page pública

`https://status.nextlevelcode.pro` mostra a status page de slug `infra` para a
internet. O Caddy da VPS só deixa passar os caminhos da página (lista em
`Caddyfile.vps.j2`); login, painel e `/socket.io` dão 404, e o painel completo
continua só em `uptime.lab`, pela tailnet. O DNS já está coberto pelo curinga
`*.nextlevelcode.pro`, que aponta para o IP público da VPS.

1. **Criar a página** em `https://uptime.lab.nextlevelcode.pro` (*Status Pages
   → New Status Page*), slug `infra`, e adicionar os monitores. É manual porque
   o AutoKuma 2.0.0 só cria status page, não atualiza, e referencia os
   monitores pelo id numérico. A página fica no `kuma.db`, que vai para o Borg.
   Monitor novo no `monitors.yml` **não** entra na página sozinho: adicione-o
   aqui também. Trocar o slug pede trocar `caddy_vps_status_page_slug` em
   `inventory/group_vars/vps/vars.yml`.

2. **Aplicar o Caddy da VPS:**

   ```bash
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ```

   Confira (de qualquer lugar; o nome resolve para o IP público):

   ```bash
   for p in / /status/infra /api/status-page/infra /api/status-page/heartbeat/infra /dashboard /socket.io/ /metrics /api/badge/1/status; do
     printf '%-36s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' https://status.nextlevelcode.pro$p)"
   done
   ```

   `/` dá `302`; os três da página, `200`; os quatro últimos, `404`.

## Restore

Não há role de restore. À mão, com o container parado: `borg extract` do
archive `uptime-kuma-*` mais recente para `/opt/uptime-kuma/data` e subir de
novo.
