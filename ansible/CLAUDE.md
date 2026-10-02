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

`ansible.cfg` aponta para o diretório `inventory/`, que junta três fontes:

| Arquivo | Onde rodam | Grupos |
|---|---|---|
| `static.ini` | Proxmox (`pve`) | `proxmox` |
| `pi.yml` | Raspberry Pi 5 (`nextlevelcode`, user `ubuntu`) e o grupo das máquinas que se passam por ele | `pi_hosts` → `rpi`, `pi_staging` |
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
| `playbooks/caddy.yml` | `caddy` | binário custom com plugin DNS-01 + Caddyfile + drop-in |
| `playbooks/forgejo.yml` | `forgejo` | stack do Forgejo + backup Borg |
| `playbooks/vaultwarden.yml` | `vaultwarden` | stack do Vaultwarden + backup Borg |
| `playbooks/pi.yml` | `pi_hosts` | base do Pi (LUKS, Docker, redes, disk-guard) |
| `playbooks/gluetun.yml` | `pi_hosts` | gateway VPN do Pi |
| `playbooks/arr-stack.yml` | `pi_hosts` | stack Arr do Pi + backup Borg |
| `playbooks/searxng.yml` | `pi_hosts` | SearXNG do Pi (sai pela VPN do gluetun) |
| `playbooks/immich.yml` | `pi_hosts` | Immich do Pi + backup Borg em repo próprio (omarchy) |
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
`--limit pi_staging`) estão em `docs/pi.md`.

O Ansible configura o Pi inteiro, menos o que exige a passphrase do LUKS ou
login interativo (Tailscale no host, `luksFormat`, `secure-unlock` a cada
boot) — esses passos estão em `docs/pi.md`.

O Caddy do homelab atende `*.lab.nextlevelcode.pro`, acessível via Tailscale
split DNS dentro da tailnet. O Caddy público (VPS) é o que serve os
domínios voltados para a internet — está fora deste repo.

## Roles

| Role | O que é |
|---|---|
| `common` | timezone + NTP de máquina física |
| `artis3n.tailscale.machine` | instala e sobe na tailnet, com `--ssh` |
| `lxc_flags` | exceção: aplica flags do container (ver abaixo) |
| `caddy` | binário custom (DNS-01) + Caddyfile + systemd drop-in |
| `forgejo` | compose do Forgejo + Postgres |
| `vaultwarden` | compose do Vaultwarden |
| `pi_host` | base do Pi: LUKS no crypttab/fstab, `secure-unlock`, Docker com data-root cifrado, redes, disk-guard |
| `secure_links` | symlinks de caminhos antigos para o LUKS (o `bin/link-data`); recebe `secure_links_paths` |
| `borg_client` | Borg + chave + senha + known_hosts; dependência de todo role com backup/restore |
| `gluetun` | gateway VPN do Pi (compose do `self-hosted/gluetun`) |
| `arr_stack` | stack Arr do Pi (compose do `self-hosted/arr`) |
| `searxng` | SearXNG do Pi; `settings.yml` renderizado, porta publicada pelo gluetun |
| `immich` | Immich do Pi; sidecar Tailscale opcional, backup no omarchy |
| `*_restore` | restore Borg do serviço, exige `-e <svc>_restore_confirmation` |
| `geerlingguy.docker` | vendido, instala o engine |
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
- **O `validate` de `copy`/`template` não passa por shell.** O Ansible faz
  `shlex.split` + `execvp`, então `VAR=x comando` falha com
  `No such file or directory: 'VAR=x'` (procura um binário com esse nome).
  Para env var inline use `/usr/bin/env VAR=x comando`.

## Segredos

Borg é um repositório só, com prefixo por serviço. O que não é segredo
(caminho da chave, passcommand, opções de SSH, retenção, compressão) fica em
`borg_*` no `group_vars/all/vars.yml`; o vault guarda só repo, senha, chave
e known_host (ainda com o nome histórico `vault_forgejo_borg_*`).

Em `inventory/group_vars/all/vault.yml` (cifrado, fora do git): token do
Proxmox, auth key do Tailscale e senha do Postgres do Forgejo. O template do
que vai lá é `vault.yml.example`.

Todo runbook manual vai em arquivo `.md` no repo, em ordem de execução, com o
comando literal e como conferir que funcionou.
