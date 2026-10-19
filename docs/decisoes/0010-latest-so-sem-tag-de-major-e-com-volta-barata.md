# 0010. `latest` só sem tag de major e com volta barata

- **Status:** Aceita, com a exceção da 0011 (gluetun)
- **Data:** 2026-10-19

## Contexto

O ADR 0005 proíbe `latest` e manda usar a tag de major, ou a versão exata
onde a atualização não volta atrás ou a superfície é pública. Ao aplicar a
regra nas stacks do Pi, apareceram imagens que não se encaixam:

- **SearXNG** não publica versão nem major: só tags por data, várias por dia
  (`2026.10.17-1c10abe2d`). Quase toda versão nova conserta um motor de busca
  que parou. Com versão exata, ele ficaria semanas parado com motores
  quebrados, ou pediria um bump por dia.
- **Tailscale** publica `v1.104` e `v1.104.1`, sem `v1`. O sidecar do FMD
  serve o Funnel, exposto à internet, o que pela 0005 pediria versão exata.
  Mas ele é o agente de rede: as correções de segurança chegam em versão
  nova, e travar a versão deixaria justamente o nó exposto sem elas.

Além disso, o motivo principal contra o `latest` na 0005 ("a versão em
produção vira a do dia do último pull, que ninguém sabe dizer qual é")
deixou de valer: os playbooks de atualização registram o digest e a versão
de cada container antes e depois (role `registro_versoes`), e a imagem só
muda quando alguém roda o `pi-atualizar.yml` ou o `vps-atualizar.yml`.

## Decisão

`latest` passa a ser permitido para uma imagem que cumpre as duas condições,
e que esteja listada aqui:

1. o projeto **não publica tag de major** (com major publicada, vale a 0005);
2. **voltar é barato**: a imagem não guarda estado, ou o estado dela
   sobrevive a voltar de versão, sem migração de banco que não volta atrás.

| Imagem | Onde | Por que cumpre |
|---|---|---|
| `searxng/searxng` | `searxng_image` | sem estado; a config vem do repo |
| `tailscale/tailscale` | `tailscale_image` (sidecar do FMD, exit node) | o estado do nó sobrevive a subir e voltar de versão; estar em dia é a proteção do nó exposto |

O resto da 0005 continua: variável por imagem, versão exata onde a
atualização migra banco sem volta (Forgejo, Vaultwarden, Immich, AdGuard),
major onde o projeto publica. Imagem nova em `latest` entra nesta tabela,
num PR que diga como ela cumpre as duas condições.

## Alternativas descartadas

- **Versão exata no SearXNG e no Tailscale:** bump à mão toda semana (ou
  todo dia, no SearXNG); na prática a versão ficaria velha, o que é pior do
  que a mudança que o `latest` traz.
- **Tag de minor no Tailscale (`v1.104`):** só traz correção da mesma
  minor, e a Tailscale corrige segurança em minor nova também; vira bump à
  mão a cada poucas semanas, com a mesma consequência.
- **`stable` em vez de `latest` no Tailscale:** hoje apontam para a mesma
  imagem; ficou o `latest`, o nome que o projeto documenta.

## Consequências

- Um `pi-atualizar.yml` pode trazer um SearXNG ou um Tailscale com mudança
  que quebra. O resumo do fim mostra o que mudou, e o log tem o digest de
  antes para voltar (`ansible/docs/pi.md`, "Atualizar").
- A 0005 continua aceita; esta é a exceção a ela, com regra própria.
- A stack Arr é candidata (sem major publicada nos *arr do linuxserver.io),
  e entra aqui no PR dela se cumprir as duas condições; o Jellyfin não
  cumpre (migra o banco sem volta).
