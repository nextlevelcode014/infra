# 0015. O backup do Immich leva também os vídeos re-encodados

- **Status:** Aceita
- **Data:** 2026-10-19

## Contexto

O ADR 0014 pôs `thumbs/` no backup e deixou `encoded-video/` de fora, para
poupar a cota do BorgBase: o vídeo re-encodado pesa perto do original, e o
Immich gera de novo.

Regerar no restore se mostrou mais caro do que parecia. No mesmo restore,
196 de 223 vídeos não tinham a linha de `asset_video` (codec, resolução,
frames), que o Immich v3 lê do banco para gerar thumbnail e transcode. O
*Transcode Videos → All* sozinho não resolveu: foi preciso descobrir a
causa, refazer os metadados dos vídeos, regerar os thumbnails e só depois
transcodificar. Cada etapa é um job longo no Pi, e um vídeo sem o arquivo
re-encodado não toca no navegador até o fim de tudo.

Medido em outubro de 2026: originais 8,3 GB, thumbs 527 MB, vídeos
re-encodados 921 MB (40 arquivos).

## Decisão

O backup do Immich leva todo o `upload/`, sem exclusão: originais, dump do
banco, thumbs e vídeos re-encodados. Gastar cota para o restore voltar
pronto vale mais que o espaço poupado.

## Alternativas descartadas

- **Manter o 0014 (só os thumbs):** o restore depende de uma sequência de
  jobs no Pi para os vídeos voltarem a tocar, com a armadilha do *Missing*
  que escolhe pelo banco e não pelo disco.

## Consequências

- O archive `immich-*` fica perto de 17% maior que os originais (6% de
  thumbs e 11% de vídeos re-encodados, na medição acima), e cresce com os
  vídeos. A cota do BorgBase (0008) é o limite a acompanhar.
- O primeiro backup depois da mudança envia todos os re-encodados de uma
  vez; os seguintes, só os novos, pela deduplicação do Borg.
- Restore da mesma versão do Immich volta sem regerar nada. Restore que
  cruza versão, ou de archive anterior a este ADR, ainda pode pedir os jobs
  de `ansible/docs/immich.md`, "Depois do restore".
- Substitui o 0014.
