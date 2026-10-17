# 0001. Registrar decisões em ADR

- **Status:** Aceita
- **Data:** 2026-10-17

## Contexto

O motivo de várias escolhas do infra vivia só na descrição de um PR ou na
memória. Ao perguntar por que a VPS não tem playbook de atualização como o Pi,
não havia como saber se era decisão ou esquecimento. Os docs não resolvem: a
regra deles é descrever o presente (`ansible/docs/README.md`), não o caminho
até ele.

## Decisão

Toda decisão que mudou como o infra funciona ganha um ADR em
`docs/decisoes/`, no mesmo PR da mudança. ADR aceito não se reescreve: é
substituído por outro.

## Alternativas descartadas

- **Só a descrição do PR:** some da vista; ninguém procura no Forgejo o PR que
  criou um arquivo antes de mexer nele.
- **Seção "Por quê" em cada doc:** mistura presente e histórico, que é
  justamente o que a regra dos docs evita, e uma decisão que cruza vários
  serviços não tem doc dono.

## Consequências

- PR com decisão nova leva o ADR junto; o `CLAUDE.md` da raiz lembra disso.
- Decisões antigas entram aos poucos, quando alguém esbarrar nelas, com a data
  e a fonte de onde o motivo foi tirado.
