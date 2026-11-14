# Verificações locais

Na raiz do repositório, com a revisão proposta em checkout:

```bash
python3 verificar.py pr origin/main HEAD
python3 verificar.py completo origin/main HEAD
```

Use como base a referência atual do destino do PR. O perfil `pr` seleciona
os checks pelo diff do ancestral comum com a base até o head. O perfil
`completo` roda todos os checks locais. O comando imprime os SHAs e testa
uma cópia temporária dos arquivos versionados no head. Faça um commit para
incluir alterações locais no ensaio. Um arquivo sem regra de seleção exige
classificação, e qualquer comando que falhar interrompe a verificação.

| Alteração | Check | Efeito e dependências |
|---|---|---|
| Terraform Proxmox ou módulo LXC | `terraform fmt -check -diff` no root e no módulo, `terraform init -backend=false -input=false -lockfile=readonly` e `terraform validate` no root | Providers fixados pelo lock. Inicialização pode baixar providers para a cópia temporária |
| Terraform Hetzner | Os mesmos comandos no root `terraform/hetzner` | Mesmo isolamento, com o lock do root Hetzner |
| Ansible, incluindo roles, inventário e dependências | `ansible-playbook -i localhost, --syntax-check` no `site.yml` e nos playbooks. Regressões de DNS, Forgejo e AdGuard | Inventário fictício, API HTTP simulada em loopback e arquivos descartáveis. O teste DNS usa `systemctl --root` numa árvore temporária |
| `verificar.py` | Todos os checks locais | Mesmo efeito dos checks individuais |
| Markdown, política Tailscale ou `.gitignore` | Conferência de valores privados no diff | Revisão da política Tailscale é manual |

A conferência de privacidade roda nos dois perfis. Ela busca nomes de
tailnet e IPv4 Tailscale nas linhas acrescentadas, com exceções para os
endereços genéricos e para o domínio fictício do teste DNS. Mostra apenas os
caminhos suspeitos. Revise também os demais dados sensíveis antes de publicar.

## Dependências

Referência para reprodução em Linux: Git, Python **3.14.8**, Terraform
**1.15.9**, Ansible **14.5.0** (core **2.21.5**, com PyYAML **6.0.3**),
`artis3n.tailscale` **1.2.1** e systemd (`systemctl`). O pacote Ansible
inclui as coleções citadas pelos playbooks. A coleção adicional é procurada
em `~/.ansible/collections`, com alternativa explícita em
`--colecoes /caminho/collections`. O diretório deve conter
`ansible_collections/artis3n/tailscale`. Confira as versões antes do ensaio
e registre diferenças no PR.

Para usar apenas providers disponíveis num espelho local:

```bash
python3 verificar.py completo origin/main HEAD --espelho-providers /caminho/espelho
```

O espelho deve ter a estrutura de um
[filesystem mirror do Terraform](https://developer.hashicorp.com/terraform/cli/config/config-file#filesystem_mirror).
Se faltar uma versão do lock, a inicialização falha. O root Proxmox
recebe uma chave pública fictícia no diretório temporário. O ambiente
descarta configurações e variáveis da sessão, incluindo credenciais,
inventário operacional e configurações de proxy. O teste Forgejo precisa
conseguir abrir um socket em `127.0.0.1`.

Integração DNS por namespaces, consultas a provedores reais e operações em
máquinas têm procedimentos no [guia DNS](../ansible/docs/lxc-dns.md#testes-locais).
Registre a execução pelo [contrato de evidências](fluxo-de-mudanca.md).
