# VPS (Hetzner)

A VPS fica fora de casa e serve duas coisas:

- o **Caddy público** (`*.nextlevelcode.pro`, hoje o `forge` e o `status`) e os **sites
  privados** que moram nela (`uptime.lab`, só da tailnet), pelo
  `playbooks/caddy-vps.yml`;
- o **Anubis** na frente do `forge` (`playbooks/anubis.yml`, ver `docs/anubis.md`);
- o **Uptime Kuma** (`playbooks/uptime-kuma.yml`, ver `docs/uptime-kuma.md`).

## Base

Na frente da VM fica o **firewall da Hetzner Cloud** (`vps-publica`, do
`terraform/hetzner/`): só `80`/`443` TCP, `41641` UDP (Tailscale direto) e
ICMP chegam nela. Ele vale mesmo com o UFW desligado, e é ele que deixa a 22
fechada desde o boot.

Dentro dela, todo playbook da VPS aplica antes o role `vps_host` (e o
`playbooks/vps.yml` aplica só ele):

- **UFW:** entrada negada por padrão; abertos só `80` e `443` para a internet
  (IPv4 e IPv6) e tudo que chega pela `tailscale0`. Na tailnet, quem filtra é
  a ACL (`tailscale/policy.hujson`). A porta 22 pública fica fechada.
- **sshd endurecido** (`/etc/ssh/sshd_config.d/00-nextlevelcode.conf`): sem
  senha e sem root. É segunda camada: a administração é pelo Tailscale SSH.
- **unattended-upgrades** ligado, só atualização de segurança e sem reboot
  automático. O `reboot-watch` avisa no Uptime Kuma quando o reboot fica
  pendente há mais de 3 dias, o unattended-upgrades falha ou um repositório
  do apt para de responder (`docs/uptime-kuma.md`).
- **fail2ban** no jail do sshd, ignorando a tailnet. Com a 22 fechada ele não
  vê nada: é fallback para o dia em que o UFW cair.
- **Log do Docker com rotação** (10 MB × 3 por container,
  `docker_daemon_options` em `group_vars/vps`), aplicado pelo role que instala
  o Docker. Só vale para container recriado depois da mudança.
- timezone, pelo role `common`.

## Atualizar

Atualização de **segurança** do Ubuntu entra sozinha (unattended-upgrades,
acima). O resto é sob demanda (ADR 0003), quando você puder ficar de olho:
pacotes que não são de segurança (os do `-updates` do Ubuntu e os dos
repositórios de terceiros, como o do Docker) e as imagens das stacks.

```bash
ansible-playbook playbooks/vps-atualizar.yml --ask-vault-pass
```

Faz, nesta ordem: `apt dist-upgrade`, `pull` das imagens de cada stack
(Anubis e Uptime Kuma), `up -d` de cada uma (recria só o container cuja
imagem mudou) e apaga as imagens antigas. Só troca imagem: config nova
continua sendo o playbook do serviço. Imagem com versão exata (Anubis,
AutoKuma) não muda aqui; sobe trocando a variável (`docs/anubis.md` e
`docs/uptime-kuma.md`, "Atualizar").

Quando o pacote do Docker atualiza, o `dockerd` reinicia e todo container da
VPS cai por alguns segundos, o Uptime Kuma junto: os monitores podem mandar
um aviso de queda e de volta.

No fim, mostra o que mudou por container e grava o log completo em
`/var/log/atualizar/<data>.log`, com o digest de antes para voltar uma
imagem (`docs/pi.md`, "Atualizar", tem o como).

Confira:

```bash
ssh hetzner@hetzner 'sudo docker ps --format "{{.Names}} {{.Status}}" | grep -v "Up"'
```

Sem saída, nenhum container está parado ou reiniciando.

Não reinicia: se o SO pedir reboot, o playbook avisa no fim. A VPS não tem
LUKS, então o reboot é só esperar um minuto, sem o Uptime Kuma e os domínios
públicos nesse tempo:

```bash
ssh hetzner@hetzner sudo reboot
```

Confira: `ssh hetzner@hetzner uptime` mostra o boot novo, e o monitor
*Atualizações VPS* fica verde (`sudo systemctl start reboot-watch.service`
para não esperar a hora cheia).

Porta publicada pelo Docker passa por cima do UFW: compose na VPS publica
sempre em `127.0.0.1:`, e o Caddy chega por localhost.

IPv6: o firewall já aceita 80/443, mas nenhum domínio tem registro AAAA, então
ninguém chega por IPv6. Para ligar, basta o AAAA na Cloudflare.

Regra criada à mão fica no UFW (o Ansible só acrescenta): confira com
`sudo ufw status verbose` e apague o que não estiver no role.

Segredos vêm do vault: o token da Cloudflare **próprio da VPS**
(`vault_caddy_vps_cloudflare_token`, separado do do Proxmox) e o acesso ao Borg. O Docker roda com `sudo`: o
usuário `hetzner` não fica no grupo `docker`.

## VPS nova (ou reinstalada)

O que vem antes de o Ansible conseguir entrar, mais o DNS público:

1. **Criar a VPS** (Ubuntu 26.04) com o usuário `hetzner` e sudo sem senha.
   Reinstalar (*Rebuild* no console, depois de desligar a `rebuild_protection`)
   mantém o mesmo servidor, então o firewall da Hetzner continua na frente.
   VPS nova é outro servidor: o `terraform/hetzner/` ainda não sabe criá-la
   (infra#16), e até ela entrar no Terraform não tem firewall da Hetzner.

   O sudo sem senha:

   ```bash
   echo 'hetzner ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/hetzner
   sudo chmod 440 /etc/sudoers.d/hetzner
   ```

2. **Tailscale no host.** Remova antes o nó `hetzner` antigo no console, para
   o nome ficar livre. É por aqui que o Ansible entra (Tailscale SSH):

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh --hostname=hetzner
   tailscale ip -4
   ```

   Confira, do seu computador: `ssh hetzner@hetzner.<tailnet>.ts.net true`.
   A tag da VPS e a policy do Tailscale SSH precisam permitir o usuário
   `hetzner`.

3. **Cloudflare** (zona `nextlevelcode.pro`, DNS only):

   | Nome | Tipo | Valor |
   |---|---|---|
   | `*` | A | IP público novo da VPS |
   | `uptime.lab` | A | IP Tailscale novo (o do passo 2) |

   O curinga `*.lab` fica como está (Caddy do Proxmox; na contingência,
   Caddy reserva do Pi, `docs/pi-recuperacao.md`). A VPS não atende o `*.lab`.

4. **Base, antes de tudo:** o primeiro playbook liga o UFW, o sshd endurecido
   e o resto da base:

   ```bash
   ansible-playbook playbooks/vps.yml --ask-vault-pass
   ```

   Confira na VPS: `sudo ufw status verbose` mostra `deny (incoming)`, 80,
   443 e a `tailscale0`. De fora da tailnet,
   `nc -zv -w 5 <IP público> 22` tem que falhar (timeout).

5. **Aplicar os serviços:**

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   O Anubis vem antes: o Caddy aponta o `forge` para ele, e sem ele o `forge`
   dá 502.

   Confira: `forge.nextlevelcode.pro` e `uptime.lab.nextlevelcode.pro`
   respondem.

6. **Dados do Uptime Kuma** (monitores, avisos, histórico), se quiser recuperar
   em vez de configurar de novo: com o container parado, `borg extract` do
   archive `uptime-kuma-*` mais recente para `/opt/uptime-kuma/data`, e subir.
