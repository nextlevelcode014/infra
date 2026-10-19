# 0014. O backup do Immich leva os thumbs, não os vídeos re-encodados

- **Status:** Aceita
- **Data:** 2026-10-19

## Contexto

O backup do Immich deixava de fora `thumbs/` e `encoded-video/`, como o guia
de backup do Immich sugere: os dois são gerados a partir dos originais.

Na migração para o `compose_stack`, os dados voltaram sem eles. O banco
voltou do dump dizendo que cada foto tinha thumbnail e preview, com o
caminho do arquivo, mas o diretório estava vazio: 1554 de 1804 thumbnails
faltando, e a timeline mostrando só as poucas que restaram.

O job *Generate Thumbnails → Missing* não conserta isso. Ele escolhe as
fotos pelo banco (quem não tem registro de thumbnail), não pelo disco. Como
o banco dizia que todas tinham, o job processou só as que não tinham
registro. Quem conserta é o *All*, que regera tudo, e esse passo não estava
escrito em lugar nenhum.

## Decisão

O backup passa a levar `thumbs/`. O `encoded-video/` continua de fora.

## Alternativas descartadas

- **Seguir sem os thumbs e só documentar o *All*:** a timeline volta vazia
  depois de todo restore até alguém lembrar do passo. No Pi, regerar a
  biblioteca inteira leva tempo de CPU que cresce com as fotos.
- **Levar o `encoded-video/` também:** o vídeo re-encodado pesa perto do
  original, e a cota do BorgBase é paga e cresce com as fotos (0008). Sem
  ele, só a reprodução dos vídeos que precisaram de transcode falha, e não a
  timeline; o *Transcode Videos → All* resolve depois do restore.

## Consequências

- O archive `immich-*` cresce cerca de 10% sobre os originais (medido em
  outubro de 2026: ~100 MB de thumbs para 250 fotos, perto de 0,4 MB por
  foto). O primeiro backup depois da mudança envia todos os thumbs de uma
  vez; os seguintes, só os novos, pela deduplicação do Borg.
- O dump do banco sai antes do `borg create`, no mesmo archive: thumbnail
  gerado no meio do backup vira arquivo sem registro no banco, que não
  quebra nada.
- Restore que cruza versão do Immich, ou de archive anterior a esta
  mudança, ainda pode pedir o *Generate Thumbnails → All*
  (`ansible/docs/immich.md`, "Depois do restore"). O *Transcode Videos →
  All* entra em todo restore.
