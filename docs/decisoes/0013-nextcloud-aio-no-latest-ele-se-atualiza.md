# 0013. Nextcloud AIO no `latest`: ele se atualiza sozinho

- **Status:** Aceita
- **Data:** 2026-10-19

## Contexto

O Nextcloud All-in-One tem um container que o Ansible sobe, o
mastercontainer, e ele cria e gere todos os outros (`nextcloud-aio-*`:
Nextcloud, banco, Redis, Talk, o Borg dele). A atualização é dele também:
pela interface do AIO, o mastercontainer puxa a imagem nova **do canal**
(`latest` ou `beta`), se recria e depois atualiza os containers que gere,
na ordem que o projeto define.

A 0005 pede tag de major ou versão exata, e as exceções da 0010 a 0012 não
servem: o AIO não publica major, mas tem estado (o banco do Nextcloud) que
migra sem volta.

## Decisão

`nextcloud_aio_image` fica em `ghcr.io/nextcloud-releases/all-in-one:latest`,
o canal estável, e a atualização continua pela interface do AIO, fora do
`pi-atualizar.yml`.

O que a 0005 protege (não trocar de versão sem querer) já vale aqui por
outro caminho: o Ansible sobe o mastercontainer com `pull: missing`, então
reaplicar o `nextcloud.yml` não puxa versão nova, e só o AIO, quando você
manda pela interface, troca a imagem.

## Alternativas descartadas

- **Versão exata no mastercontainer:** o AIO puxa o canal dele ao se
  atualizar; uma tag fixa no compose ou seria ignorada até o próximo
  `nextcloud.yml` (que voltaria a imagem antiga), ou travaria o mecanismo
  de atualização. Os containers que ele cria nem passam pelo compose.
- **Pôr o AIO no `pi-atualizar.yml`:** puxar a imagem do mastercontainer
  não atualiza os containers que ele gere, e recriá-lo fora da interface
  pula os passos do próprio AIO (backup antes, ordem dos containers).

## Consequências

- O registro de versões do `pi-atualizar.yml` não cobre o AIO. A versão de
  cada container aparece na interface do AIO, e a volta é o backup diário
  dele (Borg próprio, `docs/nextcloud.md`): antes de atualizar, confira na
  interface que o último terminou.
- O coturn, que mora no mesmo role mas o AIO não gere, segue a 0005 normal.
