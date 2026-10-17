# 0004. Standby com as imagens já baixadas

- **Status:** Aceita
- **Data:** 2026-10-02
- **Fonte:** #33 do antigo repo `ansible`; comentário em
  `ansible/roles/forgejo/tasks/main.yml`

## Contexto

O Pi é o plano B do Forgejo e do Vaultwarden quando o Proxmox cai
(`ansible/docs/pi-recuperacao.md`). No dia do desastre, baixar a imagem na
hora depende de internet, DNS (o AdGuard roda no próprio Pi), do registry no
ar e sem limite de pull, e de a tag ainda apontar para uma versão que lê o
backup.

## Decisão

Em standby (`<svc>_standby: true`), o role baixa as imagens e não sobe
container nenhum. O restore usa só o que já está no disco: a imagem e o
archive do Borg.

## Alternativas descartadas

- **Container rodando em standby:** gastaria RAM do Pi à toa e arriscaria um
  segundo Forgejo escrevendo dados que o restore depois sobrescreve.
- **Pull na hora do restore:** exatamente a dependência que se quer evitar.

## Consequências

- Standby nunca faz backup: o archive dele viraria o mais recente e o restore
  pegaria dados velhos.
- A imagem em standby é a do último pull. Para restaurar sem surpresa, ela
  precisa ser a mesma versão do principal, o que só a tag fixa garante
  (ver 0005).
