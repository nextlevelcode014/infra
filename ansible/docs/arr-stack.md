# Stack Arr no Raspberry Pi

`playbooks/arr-stack.yml` sobe a stack de mídia do Pi em `/opt/arr`. Cada app
publica a sua porta só no IP Tailscale, e o acesso é pelo Caddy, em
`https://<app>.lab.nextlevelcode.pro` (rotas em `caddy_lab_pi_routes`).

| App | Porta | Papel |
|---|---|---|
| Jellyfin | `8096` | player e bibliotecas |
| Jellyseerr | `5055` | pedidos de filmes e séries |
| Sonarr / Radarr | `8989` / `7878` | séries / filmes: busca, download, organização |
| Prowlarr | `9696` | indexadores, repassados aos *arr (com o FlareSolverr, sem porta) |
| Bazarr | `6767` | legendas |
| Profilarr | `6868` | perfis de qualidade dos *arr |
| qBittorrent | `8090` | download, **pela VPN**: vive na rede do gluetun, que publica a porta (`docs/gluetun.md`) |
| decluttarr | — | limpa downloads travados; fala com o qBittorrent em `gluetun:8090` |
| Dozzle | `8081` | logs dos containers |

| O quê | Onde |
|---|---|
| Config dos apps | `/mnt/media-stack/config`, symlink para `/mnt/secure/appdata/mnt/media-stack/config` (LUKS) |
| Mídia | `/mnt/media-stack/data`, symlink para o LUKS (`secure_links`) |
| Stack | `/opt/arr`: `compose.yml`, `.env` e a config do decluttarr |

Os symlinks vêm do role `secure_links` (`meta/main.yml`): o compose usa
`/mnt/media-stack/...`, e os dados moram no LUKS.

## Antes de aplicar

- **Vault** (modelo em `vault.yml.example`), usado só pelo decluttarr:
  `vault_arr_radarr_api_key` e `vault_arr_sonarr_api_key` (Settings →
  General → API Key de cada app), e `vault_arr_qbit_username` /
  `vault_arr_qbit_password` (os da WebUI do qBittorrent).
- **gluetun** com a config WireGuard (`docs/gluetun.md`). O role do gluetun
  entra como dependência.
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:pi` nas portas da tabela acima (um grant por rota).

## Instalação

1. **Testar no pi-lab** (as API keys do pi-lab são de mentira, em
   `group_vars/pi_staging/vars.yml`):

   ```bash
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `ssh root@10.50.0.203 docker compose -f /opt/arr/compose.yml ps`
   lista todos `Up`, e
   `ssh root@10.50.0.203 docker exec qbittorrent curl -s https://ipinfo.io/ip`
   mostra um IP da ProtonVPN.

2. **Dados.** Com backup a trazer, restaure antes de aplicar
   (`docs/arr-stack-restore.md`): a config de todos os apps volta, com as
   ligações entre eles, e o passo 4 não se aplica.

3. **Aplicar no Pi e no Caddy** (o do Proxmox e o reserva do Pi leem as
   mesmas rotas):

   ```bash
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass
   ```

   Confira: `https://sonarr.lab.nextlevelcode.pro` e os outros abrem, e os
   monitores do grupo *Raspberry Pi* ficam verdes no Uptime Kuma.

4. **Apps, só em instância nova.** A config de cada app é feita na interface
   dele, e as ligações entre eles também: Prowlarr → Sonarr/Radarr (API
   keys), Sonarr/Radarr → qBittorrent (`gluetun:8090`), Jellyseerr →
   Jellyfin e *arr. É manual porque cada app guarda a sua config no próprio
   banco. Depois, as API keys do Radarr e do Sonarr e a senha do qBittorrent
   vão para o vault, e reaplique o passo 3 para o decluttarr.

   Confira: `docker logs decluttarr --tail 20` sem erro de autenticação.

5. **Primeiro backup:**

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/arr.yaml --verbosity 1 --stats
   ```

   Confira: o monitor *Backup Stack Arr* fica verde.

## Backup

Prefixo `arr-*`, no borgmatic do Pi (`/etc/borgmatic/arr.yaml`,
`docs/backup.md`). **Para a stack inteira** durante o `borg create`, para os
bancos SQLite saírem consistentes, e sobe no fim (também quando falha). Leva
a config inteira, pelo caminho real no LUKS (o Borg não segue o symlink),
sem logs, caches, o Sentry e os zips de backup interno de cada app
(`arr_backup_excluded_app_backups`): com a stack parada, eles só repetem o
que o Borg já guarda. **A mídia não entra.** Monitor *Backup Stack Arr*.
Restore: `docs/arr-stack-restore.md`.

## Operação

- **Credencial trocada num app** (API key, senha do qBittorrent): os apps
  guardam cópia da credencial uns dos outros, e nada ressincroniza. Troque
  em todo app que a usa, no vault e reaplique (#23 quer tirar isso da mão).
- **qBittorrent sem rede depois de recriar o gluetun:** o role do gluetun o
  recria sozinho (`docs/gluetun.md`, "Operação").
- **Atualizar:** `pi-atualizar.yml` (`docs/pi.md`, "Atualizar"), com o
  monitor *Backup Stack Arr* verde antes. As imagens ficam no `defaults` do
  role: o Jellyfin tem versão exata (`arr_jellyfin_image`; sobe trocando a
  variável, depois de ler as notas, porque migra o banco sem volta); Seerr e
  Dozzle, a major; o resto, `latest` (ADRs 0010 e 0012). Se um *arr quebrar
  depois de atualizar: a imagem volta pelo digest do log, e o banco pelo
  archive `arr-*` (`docs/arr-stack-restore.md`).

## Limitações

- Mídia sem backup: perder o LUKS é baixar tudo de novo.
- A porta `8090` do qBittorrent sai em todas as interfaces, LAN incluída,
  porque é publicada pelo gluetun (#43).
