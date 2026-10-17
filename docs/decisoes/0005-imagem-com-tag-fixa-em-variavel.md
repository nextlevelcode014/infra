# 0005. Imagem com tag fixa, em variável

- **Status:** Aceita
- **Data:** 2026-10-17
- **Fonte:** política proposta na #17 (que continua a self-hosted#72)

## Contexto

Cada role declarava imagem de um jeito: `latest` (stack Arr, SearXNG,
AdGuard, Vaultwarden), versão exata (Anubis, FMD), só a major (Forgejo,
Uptime Kuma) e o gluetun sem tag nenhuma. Algumas em variável, outras
escritas direto no compose. Com `latest`, um `pull` pode trazer mudança que
quebra, e o standby (0004) pode guardar uma versão diferente da que gerou o
backup.

## Decisão

Toda imagem fica numa variável do role (`<svc>_image`, ou
`<svc>_<componente>_image` quando há mais de uma) com tag explícita.
`latest` e imagem sem tag não entram. Qual tag:

| Tipo | Tag | Exemplos |
|---|---|---|
| Padrão | major (`:2`), se o projeto publicar | Uptime Kuma, *arr, Jellyfin, SearXNG |
| Banco que migra no boot, ou projeto `0.x` | versão exata, trocada de propósito | Forgejo, Immich, Vaultwarden, FMD |
| Exposto à internet | versão exata | Anubis, Caddy |

A major traz correção sem editar o repo; a versão exata fica onde a
atualização não volta atrás (migração de banco) ou onde a superfície é
pública. Imagem repetida em várias stacks (o sidecar do Tailscale) vira uma
variável só.

## Alternativas descartadas

- **Versão exata em tudo:** cada correção de segurança viraria um PR; a
  major cobre isso onde voltar atrás é barato.
- **Manter `latest`:** sem trabalho de bump, mas a versão em produção vira
  "a do dia do último pull", que ninguém sabe dizer qual é.
- **Digest (`@sha256:`):** reproduzível, mas ilegível e sem dizer a versão;
  fica para imagem que o próprio projeto publica assim (Immich).

## Consequências

- Versão exata sobe trocando a variável, lendo as notas da versão e
  reaplicando o playbook do serviço. Tag de major só anda com pull: o
  `pi-atualizar.yml` faz no Pi; na VPS falta o `vps-atualizar.yml` (#17).
- Com tag de major, o compose não diz o que está rodando: os playbooks de
  atualização passam a registrar a versão antes e depois (#17).
- O principal e o standby usam a mesma variável, então ficam na mesma versão.
- A migração dos roles que ainda usam `latest` é a #17; o que falta está em
  `ansible/docs/padrao-de-role.md`, seção "Fora do padrão".
