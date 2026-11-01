# DNS declarado do AdGuard

Role compartilhado por `adguard` e `adguard_restore`. Não instala software,
não cria stack e não importa dados. Recebe o caminho do YAML e da stack dos
chamadores; usa `adguardhome` como nome do container, conforme o compose.

Os defaults declaram upstreams, bootstrap e modo. O arquivo deve existir
(assistente ou restore); configuração ausente só gera instrução. Quando
necessário, para o container existente, relê o YAML, mescla as três chaves e
religa somente se ele estava rodando. Sem stack, edita somente o arquivo,
que será lido no primeiro deploy. Não use com um container iniciado fora do
compose gerenciado por este repo.

O `--check` não para nem grava. Conteúdo privado usa `no_log` e não aparece
em `--diff`. A transformação preserva as demais opções semanticamente,
mas não comentários ou formatação. A operação é descrita em
`docs/adguard.md` e a decisão no ADR 0022.

## Teste local

De dentro de `ansible/`, com as collections já disponíveis:

```bash
ansible-playbook -i localhost, roles/adguard_dns/tests/test.yml
```

Usa somente arquivos fictícios num diretório temporário, removido ao final.
Confere configuração ausente, simulação sem gravação, atualização de backup
antigo, preservação de usuários/regras/outras opções DNS e idempotência.
Não usa vault, inventário real, Docker nem serviço de produção. O ciclo de
parada/partida real e resolução DNS precisam de ensaio em staging antes da
aplicação em produção (`docs/adguard-restore.md`).
