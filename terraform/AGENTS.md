# AGENTS.md

Provisionamento dos containers LXC do homelab no Proxmox. **Aqui só se cria
infra; configurar o que roda dentro é o `../ansible/`.**

Proxmox só é alcançável pela Tailscale — sem ela nada aqui funciona.

## Comandos

```bash
terraform login     # uma vez por máquina; ver "Estado"
terraform init
terraform plan      # sempre olhar o diff antes de aplicar
terraform apply
```

Valores locais ficam em `terraform.tfvars` (fora do git; ver
`terraform.tfvars.example`). O state é remoto, no HCP Terraform.

## Convenção — VMID 200-299

Todo container gerenciado aqui usa a **faixa 200-299**, e hostname, VMID e
último octeto do IP são o **mesmo número**:

| Hostname | VMID | IP | Uso |
|---|---|---|---|
| caddy | 200 | 10.50.0.200 | reverse proxy |
| forgejo | 201 | 10.50.0.201 | git + CI |
| vaultwarden | 202 | 10.50.0.202 | senhas |
| pi-lab | 203 | 10.50.0.203 | staging do Raspberry Pi: grupos `staging` + `pi_staging`, volume `/mnt/secure` no papel do LUKS |

`pi_staging` fica sob `pi_hosts` no Ansible, o grupo que recebe os playbooks
do Raspberry Pi.

O módulo `lxc` **valida** a faixa e falha o plano se você sair dela. Próximo
container livre: `204`.

Rede padrão (`local.tf`): bridge `vmbr1`, só do Proxmox, gateway
`10.50.0.1` (o próprio Proxmox, com NAT para fora), bootstrap DNS4EU Unfiltered
e Cloudflare por DNS comum (o Ansible depois configura TLS), datastore
`local-lvm`, template Ubuntu 26.04. A bridge não é do Terraform: quem a cria é
o Ansible (`playbooks/proxmox.yml`), e ela tem que existir antes do `apply`.
Da sua máquina não há rota até `10.50.0.0/24`: o SSH salta pelo Proxmox
(ADR 0009, `../ansible/docs/proxmox.md`, "Rede dos LXCs").

`destroy` apaga o container **e os discos** (`purge_on_destroy`). Só há dados
 descartáveis aqui, mas confirme antes de destruir em produção.

## Como adicionar um container

1. Bloco novo em `containers.tf`, chamando `./modules/lxc` com o próximo número
   livre da faixa (hostname, `vm_id` e IP batendo).
2. Bloco novo em `inventory.tf`: recurso `ansible_host` com `groups = ["lxc"]`,
   `depends_on = [module.<nome>]` e as vars `ansible_host`, `ansible_user`,
   `ansible_ssh_private_key_file` e `lxc_vmid`. Máquina de teste entra também
   no grupo `staging` (`groups = ["lxc", "staging"]`), para o Ansible poder
   mirar só nela com `--limit staging` e ter `group_vars/staging.yml` próprio.
3. `terraform apply`.
4. Ir para `../ansible/` e escrever o role do serviço.

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

## Hetzner (`hetzner/`)

A VPS e o firewall da Hetzner Cloud vivem numa **stack separada**, com state
próprio (workspace `infra-hetzner`), em `hetzner/` (`hetzner/README.md`).
Os comandos rodam de dentro da pasta. A VPS foi importada (criada à mão
antes), tem `prevent_destroy` e as proteções da Hetzner ligadas: plano com
`destroy` ou `must be replaced` nela é erro, não se aplica.

## Estado

O state mora no **HCP Terraform** (ADR 0019): org `NextLevelCode`, um
workspace por stack (`infra-proxmox` aqui, `infra-hetzner` em `hetzner/`),
declarados no bloco `cloud` do `versions.tf`. Ele não é só o estado do
Terraform: é a **fonte do inventário do Ansible** (recursos `ansible_host`),
e o plugin `cloud.terraform` lê o state remoto com `terraform show -json`
nesta pasta. Sem `init` e `terraform login`, o grupo `lxc` fica vazio.

A execução é **local**: o HCP só guarda o state, o histórico de versões e o
lock. O runner da HashiCorp não alcança o Proxmox (só pela Tailscale) e não
tem os `terraform.tfvars`.

**Nenhum recurso que gera segredo entra aqui** (`random_password`,
`tls_private_key`, senha em `user_account`): o state fica com a HashiCorp
em texto puro para eles. Segredo vai no vault do Ansible. Se isso tiver que
mudar, revise o ADR 0019 (a alternativa é o OpenTofu com state cifrado).

### Configurar o HCP Terraform

Passo manual: a conta, o login e as configurações da org são pela
interface web. Feito uma vez; numa máquina nova, só o passo 2.

1. **Execução local na org.** `app.terraform.io` → org `NextLevelCode` →
   **Settings → General → Default Execution Mode** → *Local* → *Update
   organization*. Os workspaces herdam da org (não mude no workspace).
2. **Login nesta máquina:**

   ```bash
   terraform login
   ```

   Ele abre o navegador para gerar um token de usuário e grava em
   `~/.terraform.d/credentials.tfrc.json`, fora do `~/Work` (não
   sincroniza).
3. **Workspaces:** o primeiro `terraform init` de cada stack cria o seu.
   Com um `terraform.tfstate` local na pasta, o `init` pergunta se migra:
   `yes` sobe o state (o `-migrate-state` não vale para o HCP).

Confira, nas duas stacks: `terraform plan` começa direto no `Refreshing
state...` e termina em `No changes.` Se a primeira linha for `Running plan
in HCP Terraform`, a execução ficou remota: volte ao passo 1.

Se a conta do HCP se perder, o state volta por `terraform import` de cada
recurso. O login da conta tem cópia fora da infra (`../docs/fora-da-infra.md`).

`.terraform.lock.hcl` **é** versionado: é ele que fixa as versões dos providers.
