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

`ansible.cfg` aponta para o diretório `inventory/`, que junta duas fontes:

| Arquivo | Onde rodam | Grupos |
|---|---|---|
| `static.ini` | hosts fixos (`pve`, `rpi5.local`) | `proxmox`, `raspberry` |
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
| `playbooks/forgejo.yml` | `forgejo` | stack do Forgejo |

A config base (em `lxc.yml`) é `common` → `tailscale` → `geerlingguy.docker`,
aplicada ao grupo `lxc` inteiro. Serviços específicos entram em playbook
próprio, como o Forgejo já faz. **Caddy e Vaultwarden ainda não têm serviço
configurado** — só recebem a base.

## Roles

| Role | O que é |
|---|---|
| `common` | timezone + NTP de máquina física |
| `tailscale` | instala e sobe na tailnet, com `--ssh` |
| `lxc_flags` | exceção: aplica flags do container (ver abaixo) |
| `forgejo` | compose do Forgejo + Postgres |
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
- **Fatos com prefixo `ansible_` estão depreciados.** Use
  `ansible_facts.virtualization_type`; a forma antiga sai no ansible-core 2.24.
- **`tailscale up` precisa de `no_log: true`**, senão a auth key aparece no
  output da execução.
- **Uma mesma auth key serve para os três containers.** Se ela for efêmera ou
  de uso único, só o primeiro host sobe.

## Segredos

Em `inventory/group_vars/all/vault.yml` (cifrado, fora do git): token do
Proxmox, auth key do Tailscale e senha do Postgres do Forgejo. O template do
que vai lá é `vault.yml.example`.

Todo runbook manual vai em arquivo `.md` no repo, em ordem de execução, com o
comando literal e como conferir que funcionou.
