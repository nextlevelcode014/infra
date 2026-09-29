# CLAUDE.md

Provisionamento dos containers LXC do homelab no Proxmox. **Aqui só se cria
infra; configurar o que roda dentro é o repo `ansible`.**

Proxmox só é alcançável pela Tailscale — sem ela nada aqui funciona.

## Comandos

```bash
terraform init
terraform plan      # sempre olhar o diff antes de aplicar
terraform apply
```

Valores locais ficam em `terraform.tfvars` (fora do git; ver
`terraform.tfvars.example`).

## Convenção — VMID 200-299

Todo container gerenciado aqui usa a **faixa 200-299**, e hostname, VMID e
último octeto do IP são o **mesmo número**:

| Hostname | VMID | IP | Uso |
|---|---|---|---|
| caddy | 200 | 192.168.50.200 | reverse proxy |
| forgejo | 201 | 192.168.50.201 | git + CI |
| vaultwarden | 202 | 192.168.50.202 | senhas |

O módulo `lxc` **valida** a faixa e falha o plano se você sair dela. Próximo
container livre: `203`.

Rede padrão: bridge `vmbr0`, gateway `192.168.50.1`, DNS `192.168.50.1`,
datastore `local-lvm`, template Ubuntu 26.04.

`destroy` apaga o container **e os discos** (`purge_on_destroy`). Só há dados
 descartáveis aqui, mas confirme antes de destruir em produção.

## Como adicionar um container

1. Bloco novo em `containers.tf`, chamando `./modules/lxc` com o próximo número
   livre da faixa (hostname, `vm_id` e IP batendo).
2. Bloco novo em `inventory.tf`: recurso `ansible_host` com `groups = ["lxc"]`,
   `depends_on = [module.<nome>]` e as vars `ansible_host`, `ansible_user`,
   `ansible_ssh_private_key_file` e `lxc_vmid`.
3. `terraform apply`.
4. Ir no repo `ansible` e escrever o role do serviço.

Passo 2 é obrigatório: é o recurso `ansible_host` gravado no state que o
plugin `cloud.terraform` lê como inventário. Sem ele o Ansible não vê a máquina.

## O que NÃO dá para fazer aqui

O provider autentica com um token (`terraform@pve!provider`). O Proxmox reserva
duas coisas ao usuário `root@pam`, e **nenhuma role resolve** — a checagem é
literal (`$authuser ne 'root@pam'`, em `PVE::LXC::check_ct_modify_config_perm`):

| Item | Erro com token |
|---|---|
| Feature flags, exceto `nesting` | `changing feature flags (except nesting) is only allowed for root@pam` |
| Device passthrough | `configuring device passthrough is only allowed for root@pam` |

Por isso `keyctl` fica `false` aqui e `/dev/net/tun` **não** está no recurso:
quem aplica os dois é o Ansible, pelo role `lxc_flags`, rodando `pct set` como
root no host via SSH.

`nesting` fica no Terraform porque é a única flag que um token consegue mexer
em container unprivileged.

As saídas seriam autenticar o provider com usuário/senha de `root@pam` (funciona,
ao custo de por a senha de admin no estado) ou manter o token e aplicar fora —
**escolhemos a segunda**.

## Estado

`terraform.tfstate` é local e ignorado pelo git. Ele não é só o estado do
Terraform: é a **fonte do inventário do Ansible** (recursos `ansible_host`).
Se ele sumir, o Ansible perde o mapa de hosts mesmo com os dois repos intactos.
Vale backup, ou migrar para state remoto.

`.terraform.lock.hcl` **é** versionado: é ele que fixa as versões dos providers.
