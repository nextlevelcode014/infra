# Immich no Raspberry Pi

`playbooks/immich.yml` aplica o Immich que antes subia por `make up SVC=immich`
no `self-hosted`. O compose é o mesmo, com duas mudanças:

- a porta `2283` publicada no IP Tailscale do Pi, para o Caddy do Proxmox
  (`https://immich.lab.nextlevelcode.pro`);
- o sidecar Tailscale (`immich.<tailnet>.ts.net`) virou opcional
  (`immich_tailscale_sidecar`). Ele continua ligado até os apps do celular
  trocarem de URL.

A versão fica fixa em `immich_version` (hoje `v3`): o dump do banco só restaura
na mesma versão.

## Backup

Repositório Borg **próprio**, no computador de trabalho (`omarchy`), e não o
repositório compartilhado: são ~30 GB de fotos. Diário às 03:30,
`/usr/local/bin/backup-immich.sh`, log em `/var/log/immich_backup.log`. Faz
`pg_dump` para dentro do `UPLOAD_LOCATION` e o `borg create` dele (sem thumbs e
vídeos re-encodados, que o Immich regenera). Não para os containers.

Só funciona com o omarchy ligado e alcançável pela tailnet. Se ele estiver
desligado às 03:30, o backup daquele dia falha e o log mostra o erro de SSH.

## Primeira aplicação

1. **Vault.** Os valores estão hoje no Pi:

   ```bash
   ssh ubuntu@nextlevelcode sudo grep -E '^(DB_PASSWORD|TS_AUTHKEY)=' /mnt/secure/env/immich.env
   ssh ubuntu@nextlevelcode sudo cat /root/.borg-immich-pass
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   `DB_PASSWORD` → `vault_immich_db_password`, `TS_AUTHKEY` →
   `vault_immich_ts_authkey`, o conteúdo do `.borg-immich-pass` →
   `vault_immich_borg_password`.

2. **Autorizar o Pi no omarchy, só para o Borg.** É manual porque mexe na
   segurança do seu computador. Pegue a chave pública do Borg do Pi:

   ```bash
   ssh ubuntu@nextlevelcode sudo ssh-keygen -y -f /root/.ssh/id_ed25519
   ```

   No omarchy, acrescente ao `~/.ssh/authorized_keys` (crie com modo `600` se
   não existir) uma linha com a restrição na frente da chave:

   ```text
   command="borg serve --restrict-to-path /home/sia/immich-backup-temp",restrict ssh-ed25519 AAAA... borg@pi
   ```

   Com `restrict` e `command=`, a chave não abre shell, não faz túnel e só fala
   com aquela pasta.

3. **ACL do Tailscale** (console): o Pi precisa alcançar o omarchy em
   `tcp:22`, e o `tag:caddy` precisa alcançar o Pi em `tcp:2283`.

4. **Testar no pi-lab** (sem sidecar e sem backup):

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `http://192.168.50.203:2283` abre a tela de criar o primeiro usuário.

5. **Aplicar no Pi** (recria o `immich_server` e o sidecar; o banco não é
   tocado):

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

   Confira: `https://immich.lab.nextlevelcode.pro` abre o login, e
   `ssh ubuntu@nextlevelcode docker compose ls --filter name=immich` mostra
   `/opt/immich/compose.yml`.

6. **Primeiro backup** (com o omarchy ligado):

   ```bash
   ssh -t ubuntu@nextlevelcode sudo /usr/local/bin/backup-immich.sh
   ```

   Confira no omarchy: `borg list /home/sia/immich-backup-temp` mostra um
   `immich-<data>` novo.

## Trocar a URL nos apps e tirar o sidecar

1. Em cada app do Immich (celular, desktop), trocar o servidor para
   `https://immich.lab.nextlevelcode.pro` e testar um upload de foto e de vídeo.
2. Depois de um período de uso sem problema, desligar o sidecar:
   `immich_tailscale_sidecar: false` em `inventory/pi.yml` (host `pi`) e
   reaplicar `playbooks/immich.yml --limit rpi`. O Compose remove o
   `immich_tailscale`.
3. Remover o nó `immich` no console do Tailscale (Machines → `immich` →
   Remove).

A partir daqui, não use mais `make up SVC=immich` no `self-hosted`.
