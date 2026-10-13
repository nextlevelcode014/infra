# Immich no Raspberry Pi

`playbooks/immich.yml` sobe o Immich no Pi em `/opt/immich`, com o acesso só
pelo Caddy.

| O quê | Onde |
|---|---|
| Interface e apps | `https://immich.lab.nextlevelcode.pro` (Caddy → `ts_ip:2283`, rota em `caddy_lab_pi_routes`) |
| Fotos e vídeos | `/mnt/secure/appdata/immich/upload` (`immich_upload_location`), no LUKS |
| Banco | `/mnt/secure/appdata/immich/postgres` (`immich_db_data_location`), no LUKS |
| Stack | `/opt/immich`: `immich_server`, `immich_machine_learning`, `immich_redis`, `immich_postgres` |

A versão fica fixa em `immich_version` (hoje `v3`): o dump do banco só
restaura na mesma versão, então atualizar é trocar essa variável de
propósito. O compose parte do oficial do Immich
(`roles/immich/templates/compose.yml.j2`, link no cabeçalho), com a porta só
no IP Tailscale.

## Antes de aplicar

- **Vault:** `vault_immich_db_password`, **só letras e números**. O `.env` é
  `env_file`, e o Compose interpola `$` nele: o Postgres receberia outra
  senha, sem erro.
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:pi:2283`.

## Instalação

1. **Testar no pi-lab** (senha de banco de mentira em
   `group_vars/pi_staging/vars.yml`):

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `curl -s http://192.168.50.203:2283/api/server/ping` devolve
   `{"res":"pong"}`.

2. **Aplicar no Pi e no Caddy** (o do Proxmox e o reserva do Pi leem a mesma
   rota):

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass
   ```

   Confira: `https://immich.lab.nextlevelcode.pro` abre, e o monitor *Immich*
   fica verde.

3. **Admin, só em instância nova.** O primeiro acesso à interface cria a conta
   de admin. É manual porque a senha não deve passar pelo repo.

   Confira: o login funciona e a página de administração abre.

4. **Apps** (celular, desktop): servidor `https://immich.lab.nextlevelcode.pro`,
   com o aparelho na tailnet.

   Confira: o upload de uma foto e de um vídeo aparece na interface.

## Backup

**Desligado** (`immich_backup_enabled: false`): o repositório Borg
compartilhado tem cota de 10 GB e as fotos têm ~30 GB (#31).

**Enquanto estiver desligado, o único backup é o de 28/09 no omarchy**
(`/home/sia/immich-backup-temp`, senha em `/root/.borg-immich-pass` no Pi).
Não apague nenhum dos dois antes do primeiro backup no repositório
compartilhado.

O config já está pronto. Para ligar, quando o plano for ampliado:

1. `immich_backup_enabled: true` em `roles/immich/defaults/main.yml`, e
   `immich: Immich` em `uptime_kuma_backups` (`group_vars/vps/monitors.yml`).
2. Reaplicar:

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

3. Primeiro backup à mão, e conferir o tempo: com o Immich, o borgmatic do Pi
   precisa terminar antes das 03:10, quando a VPS começa (`docs/backup.md`).

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/immich.yaml --verbosity 1 --stats
   ```

   Confira: o monitor *Backup Immich* fica verde.

Ligado, ele roda depois dos outros serviços do Pi, com prefixo `immich-*`:
`pg_dump` para dentro do `upload/` e `borg create` dele, sem thumbs e vídeos
re-encodados (o Immich gera de novo). **Não para os containers**: o banco sai
consistente pelo dump, e as fotos não mudam depois de gravadas.

Não há restore automatizado ainda (#29).

## Operação

- **Atualizar:** trocar `immich_version` e reaplicar, lendo antes as notas da
  versão (o Immich muda o compose e migra o banco entre versões). O
  `pi-atualizar.yml` só puxa a imagem da tag fixa.

## Limitações

- Sem backup no repositório compartilhado até ampliar a cota (#31).
