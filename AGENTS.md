# AGENTS.md

Infra da NextLevelCode em duas partes, cada uma com o seu `AGENTS.md`:

- `terraform/`: **cria** máquinas (LXCs do Proxmox, VPS da Hetzner).
- `ansible/`: **configura** o que roda dentro delas.

Leia o `AGENTS.md` da parte em que vai mexer. Os comandos rodam **de dentro
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

**Decisões ficam em `docs/decisoes/`** (ADR). Antes de desfazer algo que
parece estranho, procure lá. Decisão nova que não é óbvia pelo código (o que
se descartou, uma regra para o que vier depois) leva um ADR no mesmo PR; ADR
aceito não se reescreve, é substituído (`docs/decisoes/README.md`).

## Preferência de configuração

Priorize arquivos versionados e aplicação pelo Ansible para gerenciar a infra.
Interfaces gráficas ficam para exceções documentadas. Uma API pode ser o
mecanismo de aplicação, mas os valores desejados devem estar no código;
segredos continuam fora do Git.

## Documentação e revisão

- Mantenha nos guias as regras e os procedimentos reutilizáveis. Registre
  contexto da mudança, escolhas e resultados de testes no PR. Use ADRs
  para decisões duradouras.
- Antes de editar, explique a proposta e como vai verificá-la. Durante o
  trabalho, sinalize escolhas e mudanças de rumo relevantes. Na entrega,
  indique o que foi verificado e o que ainda depende de ação.
