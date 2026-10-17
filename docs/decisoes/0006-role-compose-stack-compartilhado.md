# 0006. Um role compartilhado para o ciclo do compose

- **Status:** Aceita
- **Data:** 2026-10-17

## Contexto

Todo role de serviço repete o mesmo bloco: criar o diretório, renderizar o
compose, subir com `docker_compose_v2`. Cada cópia divergiu um pouco: só o
Forgejo e o Vaultwarden fazem `pull: always`, só eles sabem ficar em standby,
e o nome do arquivo varia (`docker-compose.yml.j2`, `compose.yml.j2`,
`files/compose.yml`). Corrigir um comportamento significa caçar a cópia em
cada role.

## Decisão

Um role `compose_stack`, chamado com `include_role` por todo role de
serviço, cuida do ciclo do compose: diretório, render de
`templates/compose.yml.j2` do role que chama, `up` e standby. A política de
pull padrão é `missing`: aplicar o playbook baixa uma tag nova, mas não troca
uma imagem que já existe.

O que é próprio de cada serviço (config extra, backup, sidecars, restart
depois de mudar um arquivo) continua no role do serviço.

## Alternativas descartadas

- **Só convenção escrita:** as cópias já divergiram uma vez com convenção
  implícita; escrita, divergiriam de novo, só que mais devagar.
- **`pull: always` como padrão:** reaplicar config traria imagem nova junto,
  e uma quebra não diria qual das duas mudou (o motivo do 0003).

## Consequências

- O Forgejo e o Vaultwarden deixam de fazer `pull: always`; com tag fixa
  (0005), trocar a tag já basta para baixar a nova.
- Um role novo é a config do serviço mais um `include_role`, e o standby vem
  de graça para qualquer serviço que precisar.
- O role ainda não existe: entra junto com a migração do primeiro serviço
  (`ansible/docs/padrao-de-role.md`, "Fora do padrão").
