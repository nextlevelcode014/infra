# Stack Arr no Raspberry Pi

`playbooks/arr-stack.yml` aplica no Pi a stack que antes subia por
`make up SVC=arr` no repo `self-hosted`. O compose é o mesmo
(`self-hosted/arr/compose.media-stack.yml`); muda só quem o aplica e onde ele
mora: `/opt/arr`. O nome do projeto Compose continua `arr`, então os
containers que já estão rodando são adotados, não duplicados.

## Dependências

Entram sozinhas, pelo `meta/main.yml` do role:

- **Base do Pi** (`pi_host`, ver [`pi.md`](pi.md)): LUKS aberto, Docker,
  redes `medianet`/`vpn_net`.
- **gluetun** (ver [`gluetun.md`](gluetun.md)): o qBittorrent usa a netns
  dele (`network_mode: container:gluetun`) e o decluttarr fala com
  `gluetun:8090`.

## Primeira aplicação

Feita uma vez, à mão, porque envolve o vault e o crontab que hoje está no Pi.

1. Adicionar as chaves `vault_arr_*` (modelo em `vault.yml.example`). As
   duas API keys se copiam de *Settings → General → API Key* do Radarr e do
   Sonarr; usuário e senha são os da WebUI do qBittorrent. Os mesmos valores
   estão hoje em `/mnt/secure/env/arr.env` no Pi.

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

2. Seguir antes a primeira aplicação do gluetun ([`gluetun.md`](gluetun.md)).

3. Ver o que vai mudar, sem aplicar:

   ```bash
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass --check --diff
   ```

4. Aplicar:

   ```bash
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass
   ```

5. Limpar o crontab antigo. Ele chama `/usr/local/bin/backup-arr.sh` às 02:30,
   mas o script no Pi se chamava `arr-stack-backup.sh` — **o backup do Arr não
   estava rodando**. Agora o role instala `backup-arr.sh` e agenda o próprio
   cron no mesmo horário; com a linha antiga, ele rodaria duas vezes.

   ```bash
   ssh -t ubuntu@nextlevelcode sudo crontab -e
   ```

   Apague a linha `30 2 * * * /usr/local/bin/backup-arr.sh ...` que **não**
   tem o comentário `#Ansible: Backup Borg da stack Arr` acima dela. Depois:

   ```bash
   ssh ubuntu@nextlevelcode sudo rm /usr/local/bin/arr-stack-backup.sh
   ssh ubuntu@nextlevelcode sudo crontab -l | grep -c backup-arr
   ```

   O último comando deve responder `1`.

6. Conferir que a stack é a de `/opt/arr`:

   ```bash
   ssh ubuntu@nextlevelcode docker compose ls --filter name=arr
   ```

   A coluna `CONFIG FILES` deve mostrar `/opt/arr/compose.yml`.

A partir daqui, `make up SVC=arr` no `self-hosted` não deve mais ser usado:
ele sobe a mesma stack a partir de outro arquivo.

## Backup

Diário às 02:30, `/usr/local/bin/backup-arr.sh`, log em
`/var/log/arr_backup.log`. Para a stack, faz `borg create` da config inteira
(`/mnt/secure/appdata/mnt/media-stack/config`, sem logs e caches), sobe a
stack, aplica a retenção 7d/4w/3m e compacta. A mídia (`data/`) não entra no
backup. Restore em [`arr-stack-restore.md`](arr-stack-restore.md).
