# CLAUDE.md

Infra da NextLevelCode em duas partes, cada uma com o seu `CLAUDE.md`:

- `terraform/`: **cria** máquinas (LXCs do Proxmox, VPS da Hetzner).
- `ansible/`: **configura** o que roda dentro delas.

Leia o `CLAUDE.md` da parte em que vai mexer. Os comandos rodam **de dentro
do diretório**: o `ansible.cfg` e o inventário usam caminhos relativos
(`../terraform` é o state que vira o grupo `lxc`), e o Terraform tem dois
root modules (`terraform/` e `terraform/hetzner/`).

**O repo é público.** Segredo vai no `ansible/inventory/group_vars/all/vault.yml`
ou no `terraform.tfvars`, os dois fora do git. Nome da tailnet e IP Tailscale
também: no código entram por variável, e nos docs por placeholder
(`<tailnet>.ts.net`, `<ts_ip>`, `<proxmox_host>`). IP da LAN pode aparecer.
Antes de commitar, confira que não entrou valor real:
`git diff --cached | grep -E 'ts\.net|\b100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.'`
só pode mostrar placeholder e os endereços genéricos do Tailscale
(`100.64.0.0/10`, `100.127.255.255`, `100.100.100.100`).

Mudança que toca as duas partes (container novo e a config dele) vai num PR
só.
