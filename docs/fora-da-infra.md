# O que fica fora da infra

Arquivos e senhas sem os quais nada se reconstrói, e que por isso não podem
morar só dentro do que eles reconstroem. O `vault.yml` guarda a chave e a
senha do Borg: se ele existir só no notebook, perder o notebook é perder
todos os backups de uma vez.

A regra: **cada item tem duas cópias fora da infra, em lugares que não se
perdem juntos.** Fora da infra quer dizer fora do Proxmox, do Pi, da VPS e de
tudo que roda neles (Vaultwarden, Forgejo, Borg): uma cópia lá cai junto com
o que ela devia recuperar (ADR 0004 tem o mesmo motivo).

## Onde: o KeePass, em mais de um aparelho

Tudo fica numa entrada `infra` do KeePass (`.kdbx`): as senhas em campos, os
arquivos como anexo. O `.kdbx` é offline e cifrado, então os
`terraform.tfvars`, que são texto puro, entram como anexo sem cifrar antes.

A redundância é o próprio `.kdbx` copiado entre os seus aparelhos. Para
contar como cópia fora da infra:

- **Em pelo menos dois aparelhos que não se perdem juntos** (não os dois na
  mesma mochila).
- **Fora da infra:** um `.kdbx` sincronizado pelo Nextcloud do Pi não conta,
  só a cópia que chega nos aparelhos.

A senha mestra protege tudo junto e é o único item sem cópia: ela é longa,
única e fica só na sua cabeça.

## Os itens

| O quê | Onde fica no notebook | Na entrada `infra` |
|---|---|---|
| `vault.yml` | `ansible/inventory/group_vars/all/` | anexo |
| Senha do Ansible Vault | na sua cabeça | campo de senha |
| `terraform.tfvars` | `terraform/` | anexo `terraform.tfvars` |
| `terraform.tfvars` da Hetzner | `terraform/hetzner/` | anexo `hetzner.tfvars` |
| Passphrase do LUKS do Pi | na sua cabeça | campo extra |
| `terraform.tfstate` | `terraform/` | anexo `terraform.tfstate` |
| `terraform.tfstate` da Hetzner | `terraform/hetzner/` | anexo `hetzner.tfstate` |
| Chave SSH dos LXCs | `~/.ssh/id_ed25519` e `.pub` | anexos com os mesmos nomes |
| Chave do repositório Borg do Immich | no repositório, no Borg offsite | anexo `borg-immich.key` (`ansible/docs/immich.md`, "Ligar o backup") |

O state muda a cada `apply`: a cópia no KeePass é provisória, até ele ir
para um state remoto (#8). A `id_ed25519` precisa de cópia porque o
`terraform/local.tf` lê a `.pub` e grava nos containers: com uma chave nova,
o plan quer mudar os quatro LXCs.

Não precisam de cópia: o clone do repo (está no Forgejo, e qualquer clone
serve) e os `*.example` (estão no git). Formatar o desktop tem passo a passo
próprio: [`maquina-nova.md`](maquina-nova.md).
Os itens só do Pi (archives do Borg, backup do Nextcloud) estão em
`ansible/docs/pi-reconstrucao.md`.

## Fazer as cópias

Passo manual: o KeePass pede a senha mestra de forma interativa.

1. Crie a entrada `infra`, preencha a senha do Ansible Vault e a passphrase
   do LUKS, e anexe os arquivos da tabela (aba *Avançado* → *Anexos* no
   KeePassXC). Salve o `.kdbx`.
2. Copie o `.kdbx` para os outros aparelhos, como você já faz.

Confira que o anexo abre: salve o `vault.yml` do KeePass num arquivo
temporário e rode

```bash
ansible-vault view /tmp/vault.yml >/dev/null && echo ok && rm /tmp/vault.yml
```

## Quando refazer

Toda vez que um dos arquivos mudar (`ansible-vault edit`, token novo no
`tfvars`, qualquer `terraform apply`): troque o anexo e copie o `.kdbx` de
novo para os aparelhos.
Para saber se a cópia ficou para trás, salve o anexo e compare:

```bash
cmp ansible/inventory/group_vars/all/vault.yml /tmp/vault.yml && echo igual
```

## Restaurar

Num computador novo, salve os anexos da entrada `infra` nos lugares da
tabela. A ordem completa (Tailscale, chaves, clone, conferências) está em
[`maquina-nova.md`](maquina-nova.md), seção *Na máquina nova*.
