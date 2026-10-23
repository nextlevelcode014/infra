# 0016. O Immich faz backup num repositório Borg próprio

- **Status:** Aceita
- **Data:** 2026-10-23

## Contexto

O ADR 0008 pôs o Immich de volta no repositório compartilhado do BorgBase,
com prefixo `immich-*`, e aceitou duas consequências: o backup grande do
Immich segura a trava do repositório por horas (o da VPS, às 03:00, desiste
depois de `borg_lock_wait`), e por isso roda à mão, de dia.

Antes do plano Small, a cota mostrou o outro lado (#39): o config do
Immich, gravado por engano, mandaria as fotos para o repositório
compartilhado, estouraria a cota e faria falhar o backup de **todos** os
serviços. Com a cota maior o risco diminui, mas não some: as fotos crescem
todo mês, e os outros serviços somam ~2 GB.

O Nextcloud AIO já ficou num repositório só dele, porque o Borg do AIO
exige (ADR 0008).

## Decisão

O Immich vai para um repositório próprio no BorgBase, `immich`, na mesma
conta, com a mesma chave SSH e a mesma senha do compartilhado. O
`borg_client` ganha `borg_backup_repo` (o repositório de um serviço) e
`borg_known_hosts` (um host por repositório); o `borg_restore`, o
`borg_restore_repo`.

## Alternativas descartadas

- **Seguir no compartilhado:** a cota e a trava continuam compartilhadas, e
  um Immich que cresça demais derruba o backup do Vaultwarden e do Forgejo.
  A deduplicação que se perde é nenhuma: fotos não têm bloco em comum com
  config e banco.
- **Chave SSH e senha próprias:** isolaria um repositório do outro, mas são
  mais três segredos no vault e no KeePass. Os dois saem do mesmo Pi, então
  quem tem a chave de um já está na máquina que tem a do outro.
- **Um repositório por serviço:** os outros são pequenos e não disputam a
  trava por mais de minutos; seria configuração a mais sem ganho.

## Consequências

- A cota do `immich` no BorgBase limita as fotos sem tocar os outros
  serviços, e o backup do Immich não segura a trava de ninguém: backup
  grande pode esperar o timer.
- O repositório novo precisa ser criado no BorgBase e inicializado no Pi
  (`borgmatic repo-create`), à mão (`ansible/docs/immich.md`, "Backup").
- Os archives `immich-*` anteriores a esta decisão, se houver, ficam no
  compartilhado até o prune deles; o restore procura no `immich`.
- Serviço novo com dado grande segue o mesmo caminho: `borg_backup_repo`,
  host em `borg_known_hosts` e o par `vault_borg_<serviço>_*`.
