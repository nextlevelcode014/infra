# CLAUDE.md

Configuração das máquinas do homelab. **Criar container é o repo `terraform`;
aqui só se configura o que roda dentro da máquina.**

## Comandos

```bash
ansible-playbook site.yml --ask-vault-pass
```

Todo comando Ansible pede a senha do vault, mesmo para hosts que não usam
segredo nenhum: o Ansible carrega **todos** os arquivos de
`inventory/group_vars/all/`, incluindo o `vault.yml` cifrado. Não é bug do
inventário — é assim mesmo. Para automatizar, existe a linha
`vault_password_file` comentada em `ansible.cfg`.

## Inventário

`ansible.cfg` aponta para o diretório `inventory/`, que junta quatro fontes:

| Arquivo | Onde rodam | Grupos |
|---|---|---|
| `static.ini` | Proxmox (`pve`) | `proxmox` |
| `pi.yml` | Raspberry Pi 5 (`nextlevelcode`, user `ubuntu`) e o grupo das máquinas que se passam por ele | `pi_hosts` → `rpi`, `pi_staging` |
| `vps.yml` | VPS da Hetzner (`hetzner`, user `hetzner`, Tailscale SSH) | `vps` |
| `terraform.yml` | plugin `cloud.terraform`, lendo o state do terraform | `lxc` |

Os containers **não** estão em arquivo nenhum: aparecem como recursos
`ansible_host` dentro do `terraform.tfstate`. Sem `terraform apply` o grupo
`lxc` fica vazio e os playbooks não acham ninguém.

Cada host do grupo `lxc` chega com `ansible_host` (IP fixo da LAN),
`ansible_user=root`, `ansible_ssh_private_key_file` e `lxc_vmid` — os três
primeiros definidos em `inventory.tf`, no repo terraform.

`requirements.yml` traz collections que hoje não são usadas por nenhum
playbook (`community.proxmox`, `geerlingguy.pip`). Ficam de propósito: serão
usadas depois.

## O papel de cada playbook

| Playbook | Hosts | Faz |
|---|---|---|
| `playbooks/lxc.yml` | `proxmox`, depois `lxc` | flags do container, depois a config base de todos |
| `playbooks/proxmox.yml` | `proxmox` | host do Proxmox (o notebook): modo de carga da bateria (`docs/proxmox.md`) |
| `playbooks/caddy.yml` | `caddy` | binário custom com plugin DNS-01 + Caddyfile + drop-in |
| `playbooks/forgejo.yml` | `forgejo` | stack do Forgejo + backup Borg |
| `playbooks/vaultwarden.yml` | `vaultwarden` | stack do Vaultwarden + backup Borg |
| `playbooks/pi.yml` | `pi_hosts` | base do Pi (LUKS, Docker, redes, disk-guard) |
| `playbooks/gluetun.yml` | `pi_hosts` | gateway VPN do Pi |
| `playbooks/arr-stack.yml` | `pi_hosts` | stack Arr do Pi + backup Borg |
| `playbooks/searxng.yml` | `pi_hosts` | SearXNG do Pi (sai pela VPN do gluetun) |
| `playbooks/pi-recuperacao.yml` | `pi_hosts` | Forgejo e Vaultwarden em standby no Pi (parados, prontos para o restore); com `proxmox_fora: true`, no ar e com backup |
| `playbooks/adguard.yml` | `pi_hosts` | AdGuard do Pi: DNS na LAN e na tailnet, web pelo Caddy, backup Borg |
| `playbooks/fmd.yml` | `pi_hosts` | FMD do Pi: Funnel público para emergência (atrás do Anubis) + fmd.lab pelo Caddy, backup Borg |
| `playbooks/exit-node.yml` | `rpi` | exit node Tailscale saindo pela ProtonVPN (nunca no pi-lab) |
| `playbooks/nextcloud.yml` | `rpi` | mastercontainer do Nextcloud AIO + coturn + `tailscale serve` do host |
| `playbooks/vps.yml` | `vps` | base da VPS: UFW, sshd endurecido, atualização automática, fail2ban; os playbooks da VPS já a aplicam |
| `playbooks/caddy-pi.yml` | `pi_hosts` | Caddy reserva do `*.lab` no Pi: sempre no ar, só no IP Tailscale; atende quando o `*.lab` da Cloudflare aponta para o Pi |
| `playbooks/caddy-vps.yml` | `vps` | Caddy da VPS: domínios públicos (forge, status page do Uptime Kuma) + sites privados em `*.lab` que moram nela |
| `playbooks/anubis.yml` | `vps` | Anubis (prova de trabalho anti-bot) na frente dos domínios públicos da VPS; aplicar antes do `caddy-vps.yml` |
| `playbooks/uptime-kuma.yml` | `vps` | Uptime Kuma na VPS (fora de casa), em `uptime.lab` pelo Caddy da VPS |
| `playbooks/immich.yml` | `pi_hosts` | Immich do Pi (backup Borg pronto, desligado até ampliar a cota) |
| `playbooks/pi-completo.yml` | `pi_hosts` | Pi inteiro na ordem certa; com `-e pi_restaurar_tudo=RESTAURAR_PI` traz os dados do Borg antes (`docs/pi-reconstrucao.md`) |
| `playbooks/pi-atualizar.yml` | `pi_hosts` | atualização sob demanda: `apt dist-upgrade` + pull + `up -d` das stacks + dependentes do gluetun + prune; só imagem, sem config; não reinicia, avisa se o SO pedir |
| `playbooks/pi-lab-limpar.yml` | `pi_staging` | depois de um ensaio: derruba as stacks, apaga os dados restaurados e as credenciais do Borg do pi-lab |
| `playbooks/*-restore.yml` | o grupo do serviço | restore Borg explícito (ver `docs/`) |

A config base (em `lxc.yml`) é `common` → `artis3n.tailscale.machine` →
`geerlingguy.docker`, aplicada ao grupo `lxc` menos `pi_hosts`. O `pi-lab` é
LXC mas se passa pelo Pi: do `lxc.yml` recebe só as flags. Serviços específicos
entram em playbook próprio, como Caddy, Forgejo e Vaultwarden já fazem.

O Pi não passa pela base de `lxc.yml`: é host físico com LUKS em
`/mnt/secure`. A base dele é o role `pi_host`, e **todo role de serviço do Pi
o declara em `meta/main.yml`** junto com `borg_client` e, se precisar,
`secure_links`. Assim cada playbook de serviço prepara o host sozinho. A
receita para um serviço novo e o staging (`pi-lab`, sempre com
`--limit pi_staging`) estão em `docs/pi.md`. Ensaio com dados de produção
termina sempre com `playbooks/pi-lab-limpar.yml`.

O Ansible configura o Pi inteiro, menos o que exige a passphrase do LUKS ou
login interativo (Tailscale no host, `luksFormat`, `secure-unlock` a cada
boot) — esses passos estão em `docs/pi.md`.

O Caddy do homelab atende `*.lab.nextlevelcode.pro`, acessível via Tailscale
split DNS dentro da tailnet. O Caddy público (VPS) é o que serve os
domínios voltados para a internet, e também é gerido aqui
(`playbooks/caddy-vps.yml`, `Caddyfile.vps.j2`): os domínios públicos e os
sites privados que moram na VPS. Todo playbook da VPS põe o role `vps_host`
antes do serviço, como o Pi faz com o `pi_host`. Um site privado na VPS
precisa de um registro A específico na Cloudflare apontando para o IP
Tailscale dela, porque o curinga `*.lab` aponta para o Caddy do Proxmox. VPS nova: `docs/vps.md`.

**Contingência (Proxmox fora):** `proxmox_fora: true` em `group_vars/all`
põe o Forgejo e o Vaultwarden do Pi no ar com backup e o Anubis do `forge` no
Pi. O `*.lab` não é variável: o Pi tem um **Caddy reserva** sempre no ar
(`playbooks/caddy-pi.yml`, só no IP Tailscale), e quem decide se ele atende é
o registro `*.lab` da Cloudflare. A VPS não atende o `*.lab`. As rotas que vão
para o Pi ficam em `caddy_lab_pi_routes`, lidas pelo Caddy do Proxmox e pelo
reserva: serviço novo do Pi entra ali, não no Caddyfile. Ida e volta em
`docs/pi-recuperacao.md`.

## Roles

| Role | O que é |
|---|---|
| `common` | timezone + NTP de máquina física |
| `artis3n.tailscale.machine` | instala e sobe na tailnet, com `--ssh` |
| `proxmox_host` | base do notebook do Proxmox: bateria em `Long_Life` (conservation mode) |
| `lxc_flags` | exceção: aplica flags do container (ver abaixo) |
| `caddy` | binário custom (DNS-01) + Caddyfile + systemd drop-in; `caddy_caddyfile_template` escolhe o Caddyfile do host (Proxmox, VPS ou Pi); binário amd64 ou arm64 pela arquitetura |
| `forgejo` | compose do Forgejo + Postgres |
| `vaultwarden` | compose do Vaultwarden |
| `pi_host` | base do Pi: LUKS no crypttab/fstab, `secure-unlock`, Docker com data-root cifrado, redes, disk-guard |
| `secure_links` | symlinks de caminhos antigos para o LUKS (o `bin/link-data`); recebe `secure_links_paths` |
| `borg_client` | Borg + chave + senha + known_hosts + borgmatic com um timer por host; dependência de todo role com backup/restore. `tasks_from: backup` gera o config de um serviço (`docs/backup.md`) |
| `gluetun` | gateway VPN do Pi (compose do `self-hosted/gluetun`) |
| `arr_stack` | stack Arr do Pi (compose do `self-hosted/arr`) |
| `searxng` | SearXNG do Pi; `settings.yml` renderizado, porta publicada pelo gluetun |
| `adguard` | AdGuard do Pi; DNS em `lan_ip` e `ts_ip`, sem sidecar |
| `fmd` | FMD do Pi; sidecar com Funnel opcional (`fmd_tailscale_sidecar`), Anubis no caminho do Funnel (`fmd_anubis`) |
| `exit_node` | exit node `vpn-exit` (compose do `self-hosted/exit-node`, sem mudança) |
| `nextcloud` | mastercontainer do AIO (os outros containers são do próprio AIO), coturn e o serve do host |
| `anubis` | Anubis da VPS, uma instância por serviço (`anubis_instances`); `tasks_from: policy` só renderiza a política, para um Anubis em outra stack (FMD) |
| `vps_host` | base de toda VPS: UFW (só 80/443 + `tailscale0`), sshd sem senha nem root, unattended-upgrades, fail2ban de fallback |
| `reboot_watch` | timer de hora em hora que avisa um monitor push quando o reboot está pendente há 3+ dias ou o `apt-daily-upgrade` falhou; dependência do `vps_host` e do `pi_host`, pula LXC |
| `uptime_kuma` | Uptime Kuma + AutoKuma + Docker na VPS, sem o usuário no grupo `docker`; monitores em `group_vars/vps/monitors.yml` |
| `immich` | Immich do Pi, acesso só pelo Caddy; `immich_backup_enabled` liga o backup |
| `borg_restore` | miolo de todos os restores: escolhe o archive (prefixo + máquina de origem), extrai (no Pi, dentro do LUKS) e valida |
| `*_restore` | restore Borg do serviço, exige `-e <svc>_restore_confirmation`; `-e restore_on_pi=true` restaura no Pi de recuperação |
| `geerlingguy.docker` | vendido, instala o engine |
| `borgbase.ansible_role_borgbackup` | vendido, usado só pelo `borg_client`: instala o borgmatic, renderiza cada config e o timer |
| `geerlingguy.pip`, `geerlingguy.security` | vendidos, sem uso ainda |

`lxc_flags` é o único que foge da regra deste repo: ele **provisiona**, não
configura. Existe porque o Proxmox reserva `keyctl` e o device passthrough ao
`root@pam`, e o Terraform usa token. Detalhes em `roles/lxc_flags/README.md`.

## Armadilhas já encontradas

Vale não repetir:

- **`community.general.timezone` usa `name`**, não `timezone`. Passando errado o
  erro sai genérico: `one of the following is required: hwclock, name`.
- **NTP dentro de LXC não existe.** O template Ubuntu 26.04 não traz
  `systemd-timesyncd`, e mesmo trouxesse não funcionaria: o relógio é o do
  kernel do host. As tasks de NTP do role `common` só rodam fora de container.
- **Ubuntu 26.04 usa chrony, não timesyncd.** No Pi o NTP é o chrony com NTS
  (autenticado) nos servidores da Canonical. O `common` só configura o
  timesyncd onde ele existe; o chrony fica como a distro entregou.
- **Fatos com prefixo `ansible_` estão depreciados.** Use
  `ansible_facts.virtualization_type`; a forma antiga sai no ansible-core 2.24.
- **Uma mesma auth key serve para os três containers.** Se ela for efêmera
  ou de uso único, só o primeiro host sobe. O role `artis3n.tailscale.machine`
  já cuida do `no_log`; não precisa repetir.
- **O Compose interpola `$` no `.env` e no `env_file`.** Uma senha com `$v7`
  vira a variável `v7` (vazia) e chega cortada, com só um aviso ("The "v7"
  variable is not set"). Em template que gera `.env` ou valor do compose, use
  `| replace('$', '$$')`. Já pegou o `ADMIN_TOKEN` do Vaultwarden e a senha do
  admin do Uptime Kuma (AutoKuma com `authIncorrectCreds`).
- **O AutoKuma trata todo valor como template Tera** (mesma sintaxe `{% %}` /
  `{{ }}` do Liquid e do Jinja). Valor com essa sintaxe precisa ir em
  `{% raw %}…{% endraw %}`; senão a entidade falha ao parsear e o AutoKuma
  **despeja o arquivo inteiro no log, com segredos**. Pegou o corpo do e-mail
  (Liquid) e vazou o token SMTP.
- **O AutoKuma compara o `config` do aviso pela contagem de campos.** Campo que
  o Uptime Kuma acrescenta sozinho e o arquivo não tem (o `applyExisting`, que
  ele grava sempre como `false`) faz o aviso ser regravado a cada 5 s, para
  sempre. E a mescla é rasa: o `config` do arquivo substitui o do banco
  inteiro, então tirar um campo do arquivo o **apaga** no Uptime Kuma.
- **O Anubis responde 500 sem o IP do cliente.** Ele exige `X-Real-Ip` (ou um
  `X-Forwarded-For` com IP público): no Caddy, `header_up X-Real-Ip
  {remote_host}`. IP da tailnet (`100.64.0.0/10`) ele descarta sempre, então
  quem chega pela tailnet a um Anubis atrás do `tailscale serve` leva 500: lá
  vai `USE_REMOTE_ADDRESS=true`, e a tailnet se separa do Funnel pelo header
  `Tailscale-Funnel-Request` (o FMD faz assim). E a
  página de desafio responde **200**: monitor apontado para a raiz fica verde
  com o serviço fora do ar; aponte para um caminho liberado na política.
- **`redir` do Caddy com um argumento só que começa com `/`** lê o caminho como
  matcher e falha no `adapt`. Use `redir * /destino`.
- **O role da borgbase pensa em um config por host.** Com
  `config.create: true`, o timer roda só o último config gravado. Por isso o
  `borg_client` cria o timer com `config.create: false` e `-c /etc/borgmatic`
  nas flags, e cada serviço grava o seu com `timer.type: none`. Na v2.1.0, o
  `ssh.create: false` ainda exige `_borgbackup_ssh_key_path` definido; sem
  ele, o configure falha com `'_borgbackup_ssh_key_path' is undefined`.
- **O `validate` de `copy`/`template` não passa por shell.** O Ansible faz
  `shlex.split` + `execvp`, então `VAR=x comando` falha com
  `No such file or directory: 'VAR=x'` (procura um binário com esse nome).
  Para env var inline use `/usr/bin/env VAR=x comando`.
- **Handler de reload antes do de restart quebra host novo.** O `apt install
  caddy` já sobe o Caddy do pacote, sem o plugin da Cloudflare; o reload
  manda o Caddyfile novo para esse processo e ele recusa com `unknown module:
  dns.providers.cloudflare`, e o restart nunca roda. No role `caddy` o
  restart vem primeiro: com os dois notificados, o reload depois é inócuo.
- **`sshd -t` falha com `Missing privilege separation directory: /run/sshd`**
  no Ubuntu com `ssh.socket`: o `ssh.service` só sobe na primeira conexão e é
  ele que cria o diretório. Com acesso só pelo Tailscale SSH, ele nunca subiu.
  O `vps_host` cria o `/run/sshd` antes do `validate` e reinicia com
  `systemctl try-restart` (não liga o serviço parado).

## ACL do Tailscale

`tailscale/policy.hujson` é a cópia revisada da política da tailnet; quem
aplica é o console, colando à mão depois do merge (`tailscale/README.md`).
Serviço novo com porta fora da 443, ou rota nova no Caddy, quase sempre pede um
grant lá — sem ele o serviço sobe e fica inacessível sem erro.

## Segredos

Borg é um repositório só, com prefixo por serviço; quem faz backup é o
borgmatic, e cada backup avisa um monitor push no Uptime Kuma, com token
derivado da senha do Borg (`docs/backup.md`). O que não é segredo
(caminho da chave, passcommand, opções de SSH, retenção, compressão, horário
de cada host) fica em `borg_*` no `group_vars/all/vars.yml`; o vault guarda
só repo, senha, chave e known_host (ainda com o nome histórico `vault_forgejo_borg_*`).

Em `inventory/group_vars/all/vault.yml` (cifrado, fora do git): token do
Proxmox, auth key do Tailscale e senha do Postgres do Forgejo. O template do
que vai lá é `vault.yml.example`.

Todo runbook manual vai em arquivo `.md` no repo, em ordem de execução, com o
comando literal e como conferir que funcionou. O padrão dos docs (um por
serviço, um de restore por playbook de restore, as seções e as regras) e o
índice estão em `docs/README.md`: doc novo ou reescrito segue o modelo de lá.
