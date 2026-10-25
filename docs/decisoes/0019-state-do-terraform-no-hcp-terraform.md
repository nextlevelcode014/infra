# 0019. O state do Terraform mora no HCP Terraform, com execução local

- **Status:** Aceita
- **Data:** 2026-10-25

## Contexto

Os dois root modules (`terraform/` e `terraform/hetzner/`) tinham state
local, ignorado pelo git. O state não é só do Terraform: é a fonte do grupo
`lxc` do Ansible (recursos `ansible_host`). Perder o arquivo é perder o mapa
dos LXCs, e a VPS só volta ao Terraform por `import`.

Pela regra de `fora-da-infra.md`, o state precisava de duas cópias fora da
infra, e ia como anexo do KeePass. Só que ele muda a cada `apply`, e o
anexo ficava velho sem aviso: era o item mais fácil de esquecer na lista.
O Nextcloud do Pi já leva o `~/Work` (ADR 0018), mas é infra e não conta.

Hoje o state não guarda credencial: os tokens do Proxmox e da Hetzner são
configuração do provider e não entram nele, e o `user_account` dos LXCs não
tem senha (o acesso é por chave pública). O que ele guarda é o mapa da
infra: hostnames, VMIDs, IPs da LAN, os IPs Tailscale dos LXCs (o provider
lê as interfaces), o IP público da VPS e as regras do firewall.

## Decisão

As duas stacks usam o bloco `cloud` do HCP Terraform, org `NextLevelCode`,
workspaces `infra-proxmox` e `infra-hetzner`. A execução é **local**
(default da org): o `plan` e o `apply` rodam no notebook, pela Tailscale e
com os `terraform.tfvars` locais, e o HCP só guarda o state, com histórico
de versões e lock.

Regra para o que vier: **nenhum recurso que gera segredo entra no
Terraform** (`random_password`, `tls_private_key`, senha em
`user_account`). O segredo fica no vault do Ansible. Se essa regra
precisar quebrar, a decisão se revisa pelo OpenTofu (abaixo).

## Alternativas descartadas

- **OpenTofu com o state cifrado no cliente** (AES-GCM, chave de uma
  passphrase no KeePass): o terceiro veria só texto cifrado. Ficou de fora
  porque, sem credencial no state, a cifra protegeria o mapa da infra a um
  custo que não acaba: uma ferramenta nova e lock files refeitos; um bucket
  S3 (Backblaze B2, Cloudflare R2 ou Hetzner) com chaves próprias, porque o
  HCP lê cada state que recebe e o cifrado não é suportado lá; e a
  passphrase em todo comando do Ansible, já que o plugin do inventário
  roda `tofu show`. Perder a passphrase é perder o state. É o caminho se o
  state passar a guardar segredo, ou se o mapa da infra deixar de poder
  ficar com a HashiCorp.
- **Terraform com backend S3:** o mesmo texto puro do HCP, num terceiro
  que não é o da ferramenta, e mais um par de chaves para guardar.
- **Backend na própria infra** (Postgres ou HTTP no Pi, no Forgejo): cai
  junto com o que ele devia ajudar a reconstruir.
- **Continuar com o anexo no KeePass:** funciona, mas depende de lembrar
  de trocar o anexo a cada `apply`, e o esquecido só aparece na hora de
  restaurar.
- **Execução remota no HCP (o default da org):** o runner da HashiCorp não
  alcança o Proxmox, que só responde pela Tailscale, e precisaria dos
  tokens do `terraform.tfvars` guardados lá.

## Consequências

- O state sai do KeePass e da tabela de `fora-da-infra.md`. No lugar entra
  o login do HCP Terraform (senha e códigos de recuperação do 2FA): sem a
  conta, o state só volta por `terraform import`.
- O mapa da infra (IPs da LAN e da tailnet, IP público da VPS) fica com a
  HashiCorp, em texto puro para eles. O repo continua sem esses valores.
- Toda máquina que roda Terraform ou Ansible precisa de `terraform login`,
  um passo manual pelo navegador (`maquina-nova.md`). O plugin
  `cloud.terraform` não muda: ele roda `terraform show -json` em
  `../terraform`, que lê o state remoto se a pasta tiver `init` e login.
- O `apply` tem lock no HCP: dois terminais não gravam o state ao mesmo
  tempo.
- O plano Free do HCP tem limite de recursos gerenciados, longe dos 11 de
  hoje. Se a HashiCorp mudar o plano, `terraform state pull` tira o state
  para outro backend.
