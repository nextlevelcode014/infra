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
| Rede do runner (`ansible/vars/rede-runner.yml`) | Checks do root Proxmox e do Ansible | Terraform e Ansible leem os mesmos parâmetros |
| Terraform Hetzner | Os mesmos comandos no root `terraform/hetzner` | Mesmo isolamento, com o lock do root Hetzner |
| Ansible, incluindo roles, inventário e dependências | `ansible-playbook -i localhost, --syntax-check` no `site.yml` e nos playbooks. Regressões de DNS, Forgejo e AdGuard | Inventário fictício; só no syntax-check, padrões de hosts sem correspondência são ignorados. API HTTP simulada em loopback e arquivos descartáveis. O teste DNS usa `systemctl --root` numa árvore temporária |
| `verificar.py` | Todos os checks locais | Mesmo efeito dos checks individuais |
| `.forgejo/workflows/` | Todos os checks locais | Mudança na orquestração da CI deve validar os componentes que ela pode selecionar |
| Markdown, política Tailscale ou `.gitignore` | Conferência de valores privados no diff | Revisão da política Tailscale é manual |

A conferência de privacidade roda nos dois perfis. Ela busca nomes de
tailnet e IPv4 Tailscale nas linhas acrescentadas, com exceções para os
endereços genéricos e para o domínio fictício do teste DNS. Mostra apenas os
caminhos suspeitos. Revise também os demais dados sensíveis antes de publicar.

## Execução em pull requests

O workflow `.forgejo/workflows/pull-request.yml` inicia nas aberturas,
reaberturas e atualizações de commits (`synchronize`). Ele busca os SHAs da
base e do head informados pelo evento, confere que o head é o `HEAD` do
checkout e executa `python3 verificar.py pr <base> <head>`. O workflow não
filtra caminhos: mudança documental também recebe o check, e mudança em
`.forgejo/workflows/` seleciona todos os checks locais. Um novo evento do
mesmo PR cancela uma execução anterior ainda em andamento. A síntese do job
registra os SHAs, a seleção e os limites, e o título da execução mostra o
número do PR e o SHA do head. Checks obrigatórios para merge são configurados
separadamente na Etapa 7.

## Repetir uma verificação de um PR

Use os SHAs completos da base e do head registrados no PR ou no resumo do
job. Em um clone separado, confirme o remote e busque o head do PR se
ele ainda faltar, inclusive após o squash e a exclusão da branch:

```bash
git remote -v
git fetch origin "$base" "refs/pull/${numero_pr}/head"
git switch --detach "$head"
git rev-parse HEAD "$base"
git status --short
python3 verificar.py pr "$base" "$head"
```

Preencha `numero_pr`, `base` e `head` com os valores do PR. Confira os
dois SHAs na ordem head e base e a saída vazia do status. Se o comando
original usava `origin/main HEAD`, passe os SHAs registrados no lugar
dessas referências. Preserve o perfil e as opções, como `--colecoes` e
`--espelho-providers`, ajustando os caminhos para as dependências
equivalentes no novo ambiente. Registre o tempo de execução, a seleção,
o resultado e as diferenças de ambiente. Em caso de nova tentativa,
registre o motivo e o tempo até o primeiro resultado útil.

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
conseguir abrir um socket em `127.0.0.1`. Se o ambiente negar a abertura
desse socket, registre a limitação e repita onde o loopback local seja
permitido.

Integração DNS por namespaces, consultas a provedores reais e operações em
máquinas têm procedimentos no [guia DNS](../ansible/docs/lxc-dns.md#testes-locais).
Registre a execução pelo [contrato de evidências](fluxo-de-mudanca.md).
