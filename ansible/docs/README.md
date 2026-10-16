# Docs

Um doc por host, um por serviço e um de restore para cada serviço que tem
playbook de restore. Os modelos estão no fim; doc novo ou reescrito segue o
modelo.

## Índice

### Hosts e operações que cruzam serviços

| Doc | O que cobre |
|---|---|
| `pi.md` | base do Raspberry Pi: instalação, LUKS, boot, atualização, `pi-lab`, serviço novo |
| `pi-reconstrucao.md` | Pi do zero, com os dados do Borg |
| `pi-recuperacao.md` | Pi no lugar do Proxmox (contingência) e a volta |
| `proxmox.md` | host do Proxmox (notebook) |
| `vps.md` | base da VPS e VPS nova |
| `caddy.md` | os três Caddys (Proxmox, VPS, Pi) e a troca do token da Cloudflare |
| `backup.md` | borgmatic, monitor push e serviço novo com backup |

### Serviços

| Serviço | Host | Doc | Restore |
|---|---|---|---|
| AdGuard | Pi | `adguard.md` | `adguard-restore.md` |
| Anubis | VPS | `anubis.md` | — |
| Stack Arr | Pi | `arr-stack.md` | `arr-stack-restore.md` |
| Exit node | Pi | `exit-node.md` | — |
| FMD | Pi | `fmd.md` | `fmd-restore.md` |
| Forgejo | LXC | `forgejo.md` | `forgejo-restore.md` |
| gluetun | Pi | `gluetun.md` | — |
| Immich | Pi | `immich.md` | — |
| Nextcloud AIO | Pi | `nextcloud.md` | seção no próprio doc (pelo AIO) |
| SearXNG | Pi | `searxng.md` | — |
| Uptime Kuma | VPS | `uptime-kuma.md` | seção no próprio doc (sem role) |
| Vaultwarden | LXC | `vaultwarden.md` | `vaultwarden-restore.md` |

*falta* = o playbook existe, o doc não.

## Regras

- **O doc descreve o presente.** Como se chegou aqui fica no git e nos PRs.
  Exceção: uma seção `## Histórico` curta, quando sobrou algo no mundo real
  que confunde quem encontra (um cron antigo, um nó velho na tailnet).
- **Passo a passo em ordem de execução.** Cada passo tem o comando literal e
  uma linha "Confira:" com o que deve aparecer. Passo manual (console, login,
  token, browser) leva uma linha dizendo por que não dá para automatizar.
- **IP e porta pelo nome, nunca pelo valor:** `ts_ip`, `<proxmox_host>`. O
  repo é público, então tailnet e IPs Tailscale ficam no `vault.yml`
  (`vault.yml.example` diz quais); nos comandos, o nome da tailnet aparece
  como `<tailnet>.ts.net`. IP da LAN (`192.168.50.x`) pode ir pelo valor.
- **Nada de referência ao que não está no repo** ("o runbook da
  infraestrutura"). Se o passo depende de outro doc, cite o arquivo e a seção.
- **Restore em arquivo próprio** quando há `playbooks/<serviço>-restore.yml`,
  com o mesmo nome: no dia do desastre se abre um arquivo, sem procurar
  seção. Sem playbook de restore, o restore manual é uma seção `## Restore`
  no doc do serviço.

## Modelo: `<serviço>.md`

As seções marcadas como opcionais só entram quando há o que dizer.

````markdown
# <Serviço> no <host>

`playbooks/<serviço>.yml` <o que faz, em uma ou duas frases>.

| O quê | Onde |
|---|---|
| Interface | `https://<serviço>.lab.nextlevelcode.pro` (Caddy → `<host>:<porta>`) |
| Dados | `<diretório>` |

## Antes de aplicar

O que precisa existir fora do Ansible: variáveis no vault (`vault.yml.example`),
grant na ACL (`tailscale/policy.hujson`), registro na Cloudflare, rota no
Caddy.

## Instalação

1. **<Passo>:**

   ```bash
   <comando>
   ```

   Confira: <comando ou o que deve aparecer>.

Serviço do Pi: o passo 1 é o `pi-lab` (`--limit pi_staging`).

## Backup

Prefixo `<serviço>-*` no borgmatic de `<host>` (`docs/backup.md`). O que entra,
o que fica de fora e por quê, se para o serviço, monitor
*Backup <Rótulo>*. Restore: `docs/<serviço>-restore.md`.

## Operação (opcional)

O que se faz depois de instalado: trocar config, diagnóstico, atualizar.

## Limitações (opcional)
````

## Modelo: `<serviço>-restore.md`

````markdown
# Restore do <Serviço>

O que o restore substitui e de qual archive (prefixo, máquina de origem).
O playbook normal nunca restaura.

## Antes de executar

O que precisa estar pronto, em lista numerada, com "Confira:".

## Executar

Um bloco por lugar onde o serviço pode ser restaurado (ex.: no LXC e no Pi
de recuperação, `-e restore_on_pi=true`).

## Conferir

## Ensaio no pi-lab
````
