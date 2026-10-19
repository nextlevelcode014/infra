# 0012. Stack Arr no `latest`, com o backup como volta

- **Status:** Aceita
- **Data:** 2026-10-19

## Contexto

A stack Arr tem onze imagens, todas em `latest` antes da 0005. Ao aplicar a
regra:

- **Jellyfin**, **Seerr** e **Dozzle** publicam tag de major (ou de versão)
  e entram na 0005 sem exceção.
- **FlareSolverr** e **decluttarr** não publicam major e não guardam
  estado: cabem na 0010 como ela está.
- **Sonarr, Radarr, Prowlarr, Bazarr, qBittorrent e Profilarr** não publicam
  tag de major. O linuxserver.io (os cinco primeiros) publica `latest` e
  versões completas (`4.0.20.3014-ls329`), reconstruídas toda semana. Mas
  eles guardam estado num SQLite que algumas versões migram ao subir, e
  voltar a imagem depois dessa migração não é suportado. A condição 2 da
  0010 (volta barata, sem migração sem volta) não vale para eles.

A alternativa dentro da 0005 seria versão exata nos seis, com bump à mão
toda semana.

## Decisão

Os seis ficam em `latest`, com o **backup como volta**: se uma atualização
migrar o banco e quebrar, volta-se a imagem pelo digest do log do
`pi-atualizar.yml` e o banco pelo archive `arr-*` mais recente
(`ansible/docs/arr-stack-restore.md`).

Vale porque:

- o archive `arr-*` é diário e feito com a stack **parada**, então os bancos
  saem consistentes;
- o que se perde ao voltar um dia é de pouco valor e se refaz: fila,
  histórico de downloads, uma busca. A biblioteca (os arquivos de mídia)
  não está nesses bancos;
- a imagem só muda quando alguém roda o `pi-atualizar.yml`, de olho.

O **Jellyfin** fica fora desta exceção, com versão exata: usuários,
histórico do que foi assistido e metadados são o que mais custaria perder,
e a migração dele entre versões não volta.

## Alternativas descartadas

- **Versão exata nos seis:** seis bumps à mão por semana; na prática a
  stack ficaria velha, sem as correções que o linuxserver.io traz.
- **qBittorrent com versão exata:** cogitado, porque troca de versão já
  mudou a WebUI e o formato da config. O estado dele (a lista de torrents,
  `BT_backup`) está no mesmo backup diário, e a troca fica a uma linha de
  distância se ele quebrar mais de uma vez.

## Consequências

- Um `pi-atualizar.yml` pode trazer um *arr que migra o banco. O resumo do
  fim mostra o que mudou; antes de atualizar, conferir que o monitor
  *Backup Stack Arr* está verde.
- A tabela de imagens em `latest` da 0010 ganha estas seis, por esta.
