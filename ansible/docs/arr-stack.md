# Stack Arr no Raspberry Pi

`playbooks/arr-stack.yml` aplica no Pi a stack que antes subia por
`make up SVC=arr` no repo `self-hosted`. O compose é o mesmo
(`self-hosted/arr/compose.media-stack.yml`); muda só quem o aplica e onde ele
mora: `/opt/arr`. O nome do projeto Compose continua `arr`, então os
containers que já estão rodando são adotados, não duplicados.

## Dependências que continuam no `self-hosted`

- **gluetun** (`self-hosted/gluetun`): o qBittorrent usa a netns dele
  (`network_mode: container:gluetun`) e o decluttarr fala com
  `gluetun:8090`. Precisa estar de pé antes.
- **LUKS destrancado** (`make unlock`): o role recusa rodar sem
  `/mnt/secure` montado.

## Primeira aplicação

Feita uma vez, à mão, porque envolve o vault e o crontab que hoje está no Pi.

1. Adicionar as chaves `vault_arr_*` (modelo em `vault.yml.example`). As
   duas API keys se copiam de *Settings → General → API Key* do Radarr e do
   Sonarr; usuário e senha são os da WebUI do qBittorrent. Os mesmos valores
   estão hoje em `/mnt/secure/env/arr.env` no Pi.

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

2. Conferir que o gluetun está de pé:

   ```bash
   ssh ubuntu@nextlevelcode docker ps --filter name=gluetun --format '{{.Status}}'
   ```

   Deve mostrar `Up ... (healthy)`.

3. Ver o que vai mudar, sem aplicar:

   ```bash
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass --check --diff
   ```

4. Aplicar:

   ```bash
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass
   ```

5. Tirar a linha do arr do crontab antigo. O role instala o script no mesmo
   caminho (`/usr/local/bin/backup-arr.sh`) e agenda o próprio cron; com as
   duas linhas, o backup roda duas vezes às 02h.

   ```bash
   ssh ubuntu@nextlevelcode sudo crontab -l | grep backup-arr
   ssh -t ubuntu@nextlevelcode sudo crontab -e
   ```

   Apague a linha **sem** o comentário `#Ansible: Backup Borg da stack Arr`
   acima dela. Confira que sobrou uma:

   ```bash
   ssh ubuntu@nextlevelcode sudo crontab -l | grep -c backup-arr
   ```

6. Conferir que a stack é a de `/opt/arr`:

   ```bash
   ssh ubuntu@nextlevelcode docker compose ls --filter name=arr
   ```

   A coluna `CONFIG FILES` deve mostrar `/opt/arr/compose.yml`.

A partir daqui, `make up SVC=arr` no `self-hosted` não deve mais ser usado:
ele sobe a mesma stack a partir de outro arquivo.

## Backup

Diário às 02h, `/usr/local/bin/backup-arr.sh`, log em
`/var/log/arr_backup.log`. Para a stack, faz `borg create` da config inteira
(`/mnt/secure/appdata/mnt/media-stack/config`, sem logs e caches), sobe a
stack, aplica a retenção 7d/4w/3m e compacta. A mídia (`data/`) não entra no
backup. Restore em [`arr-stack-restore.md`](arr-stack-restore.md).
