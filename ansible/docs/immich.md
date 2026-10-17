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

Prefixo `immich-*` no borgmatic do Pi (`docs/backup.md`), num repositório
próprio no Borg offsite (`docs/borg-offsite.md`), e não no
compartilhado: as fotos (~30 GB) não cabem na cota de 10 GB do BorgBase
(ADR 0007). Mesma chave e mesma senha do compartilhado.

Roda depois dos outros serviços do Pi: `pg_dump` para dentro do `upload/` e
`borg create` dele, sem thumbs e vídeos re-encodados (o Immich gera de
novo). **Não para os containers**: o banco sai consistente pelo dump, e as
fotos não mudam depois de gravadas. Monitor *Backup Immich*.

Com a máquina offsite desligada o backup falha em 10 s (`ConnectTimeout`) e o
monitor cai; os outros serviços do Pi, antes dele, não são afetados.

Restore: ainda não automatizado (#10). À mão, com o `borg` do Pi apontando
para `borg_offsite_repo_immich`.

### Ligar o backup

Uma vez, depois do Borg offsite pronto (`docs/borg-offsite.md`, passos 1 a 5):

1. **Aplicar o config e o monitor:**

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Confira: `ssh ubuntu@nextlevelcode.<tailnet>.ts.net sudo ls /etc/borgmatic`
   lista o `immich.yaml`.

2. **Criar o repositório.** Manual porque só acontece uma vez, e o Ansible
   não depende da máquina offsite ligada para aplicar o Immich.

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/immich.yaml repo-create --encryption repokey-blake2
   ```

   Confira: `sudo borgmatic -c /etc/borgmatic/immich.yaml repo-info` no Pi
   mostra o repositório, cifrado (`repokey BLAKE2b`).

3. **Exportar a chave do repositório** para o KeePass
   (`../docs/fora-da-infra.md`). A chave mora dentro do repositório
   (`repokey`): com o cabeçalho dele corrompido, só a cópia exportada e a
   senha abrem os archives. Manual porque o KeePass pede a senha mestra.

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/immich.yaml key export
   ```

   Confira: a saída começa com `BORG_KEY` e está na entrada `infra`, como o
   anexo `borg-immich.key`.

4. **Primeiro backup à mão** (~30 GB pela internet; os seguintes só
   levam o que mudou):

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/immich.yaml --verbosity 1 --stats
   ```

   Confira: termina sem `ERROR`, e o monitor *Backup Immich* fica verde.

5. **Apagar o backup provisório**, só depois do passo 4: o de 28/09 no
   omarchy (`/home/sia/immich-backup-temp`) e a senha dele no Pi
   (`/root/.borg-immich-pass`). Até o primeiro backup no Borg offsite, eles são
   a única cópia das fotos.

   Confira: `sudo borgmatic -c /etc/borgmatic/immich.yaml repo-list` no Pi
   lista um archive `immich-*` de hoje antes de apagar.

## Operação

- **Atualizar:** trocar `immich_version` e reaplicar, lendo antes as notas da
  versão (o Immich muda o compose e migra o banco entre versões). O
  `pi-atualizar.yml` só puxa a imagem da tag fixa.

## Limitações

- Uma cópia só, no Borg offsite (`docs/borg-offsite.md`, "Limitações").
