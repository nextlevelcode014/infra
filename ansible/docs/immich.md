# Immich no Raspberry Pi

`playbooks/immich.yml` aplica o Immich que antes subia por `make up SVC=immich`
no `self-hosted`. O compose é o mesmo, com duas mudanças:

- **sem o sidecar Tailscale.** O acesso passa a ser só
  `https://immich.lab.nextlevelcode.pro`, pelo Caddy do Proxmox;
- a porta `2283` é publicada no IP Tailscale do Pi, para o Caddy chegar.

A versão fica fixa em `immich_version` (hoje `v3`): o dump do banco só restaura
na mesma versão.

## Backup

Pronto, mas **desligado** (`immich_backup_enabled: false`): o repositório Borg
compartilhado tem cota de 10 GB e as fotos têm ~30 GB. Quando o plano for
ampliado, mude para `true` em `roles/immich/defaults/main.yml` e reaplique.

Ligado, ele roda diário às 03:30 (`/usr/local/bin/backup-immich.sh`, log em
`/var/log/immich_backup.log`): `pg_dump` para dentro do `UPLOAD_LOCATION` e
`borg create` dele no repositório compartilhado, prefixo `immich-*`, sem thumbs
e vídeos re-encodados (o Immich regenera). Não para os containers.

**Enquanto estiver desligado, o único backup é o de 28/09 no omarchy**
(`/home/sia/immich-backup-temp`, senha em `/root/.borg-immich-pass` no Pi).
Não apague nenhum dos dois antes do primeiro backup no repositório
compartilhado.

## Primeira aplicação

A troca de acesso é de uma vez: ao aplicar, o sidecar sai e
`immich.<tailnet>.ts.net` para de responder. Tenha o celular em mãos para trocar
a URL logo depois.

1. **Vault.** A senha do banco está hoje no Pi:

   ```bash
   ssh ubuntu@nextlevelcode sudo grep '^DB_PASSWORD=' /mnt/secure/env/immich.env
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   O valor vai em `vault_immich_db_password`.

2. **ACL do Tailscale** (console): o `tag:caddy` precisa alcançar o Pi em
   `tcp:2283`.

3. **Aplicar** (recria o `immich_server` e remove o `immich_tailscale`; o banco
   não é tocado):

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

   Confira: `https://immich.lab.nextlevelcode.pro` abre o login, e
   `ssh ubuntu@nextlevelcode docker compose ls --filter name=immich` mostra
   `/opt/immich/compose.yml`.

4. **Trocar a URL nos apps** (celular, desktop) para
   `https://immich.lab.nextlevelcode.pro` e testar o upload de uma foto e de um
   vídeo.

5. **Remover o nó `immich` no console do Tailscale** (Machines → `immich` →
   Remove). O container o Compose já removeu; o nó fica listado até ser apagado
   à mão.

A partir daqui, não use mais `make up SVC=immich` no `self-hosted`.
