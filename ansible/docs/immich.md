# Immich no Raspberry Pi

`playbooks/immich.yml` sobe o Immich no Pi em `/opt/immich`, com o acesso só
pelo Caddy.

| O quê | Onde |
|---|---|
| Interface e apps | `https://immich.lab.nextlevelcode.pro` (Caddy → `ts_ip:2283`, rota em `caddy_lab_pi_routes`) |
| Fotos e vídeos | `/mnt/secure/appdata/immich/upload` (`immich_upload_location`), no LUKS |
| Banco | `/mnt/secure/appdata/immich/postgres` (`immich_db_data_location`), no LUKS |
| Stack | `/opt/immich`: `immich_server`, `immich_machine_learning`, `immich_redis`, `immich_postgres` |

A versão fica fixa em `immich_version` (versão exata, `v3.3.3`; ADR 0005):
o Immich migra o banco ao subir, e o dump do backup só restaura na mesma
versão, então atualizar é trocar essa variável de propósito. O compose parte do oficial do Immich
(`roles/immich/templates/compose.yml.j2`, link no cabeçalho), com a porta só
no IP Tailscale.

## Antes de aplicar

- **Vault:** `vault_immich_db_password`, **só letras e números**. O `.env` é
  `env_file`, e o Compose interpola `$` nele: o Postgres receberia outra
  senha, sem erro.
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:pi:2283`.
- **Repositório do backup**, só com o backup ligado: o `immich` no
  BorgBase, como em "Backup → Configurar". Sem `vault_borg_immich_repo` e
  `vault_borg_immich_known_host_key` no vault, todo playbook do Pi falha:
  o `borg_client` põe o host desse repositório no `known_hosts`.

## Instalação

1. **Testar no pi-lab** (senha de banco de mentira em
   `group_vars/pi_staging/vars.yml`):

   ```bash
   ansible-playbook playbooks/immich.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `ssh root@10.50.0.203 wget -qO- http://10.50.0.203:2283/api/server/ping` devolve
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
só dele (`borg_immich_repo`, ADR 0016), com a mesma chave SSH e a mesma
senha do compartilhado: as fotos não disputam a cota nem a trava com os
outros serviços. Roda depois dos outros serviços do Pi: `pg_dump` para dentro
do `upload/` e `borg create` dele inteiro, com os thumbs e os vídeos
re-encodados (ADR 0015): o restore volta pronto, sem regerar nada no Pi.
**Não para os containers**: o banco sai consistente pelo dump, e as fotos
não mudam depois de gravadas. Monitor *Backup Immich*.

### Configurar

Manual: o repositório nasce no console do BorgBase, e o Borg o inicializa
de dentro do Pi, onde a senha já está. Até o passo 4, o backup das 02:30
falha só no Immich (monitor vermelho); os outros serviços seguem.

1. **Repositório no BorgBase.** No console, *New Repo*: nome `immich`, a
   mesma região do compartilhado, e a chave SSH do compartilhado com
   **acesso total** (o prune do borgmatic apaga archives). Uma cota no
   repositório segura um Immich que cresça demais sem tocar o resto da
   conta.

   Confira: o repositório aparece na lista, com a URL
   `ssh://<id>@<id>.repo.borgbase.com/./repo`.

2. **Vault.** A URL em `vault_borg_immich_repo` e a chave pública do
   servidor em `vault_borg_immich_known_host_key` (sem o hostname no
   início):

   ```bash
   ssh-keyscan -t ed25519 <id>.repo.borgbase.com
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira a impressão digital do `ssh-keyscan` com a que o BorgBase
   mostra no console antes de gravar.

3. **Aplicar** o `immich.yml` no Pi (Instalação, passo 2).

   Confira: o diff mostra o `/etc/borgmatic/immich.yaml` com o repositório
   novo, e a linha nova no `/root/.ssh/known_hosts`.

4. **Criar o repositório Borg**, com a senha que o Pi já tem
   (`/root/.borg-pass`):

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/immich.yaml repo-create --encryption repokey-blake2
   ```

   Confira: `sudo borgmatic -c /etc/borgmatic/immich.yaml repo-info` mostra
   o repositório, sem archive.

5. **Primeiro backup**, à mão: ele leva horas, e assim dá para acompanhar.

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/immich.yaml --verbosity 1 --stats
   ```

   Confira: um archive `immich-*` no fim do `--stats`, o espaço usado no
   `immich` no BorgBase, e o monitor *Backup Immich* verde.

## Restore

Ainda não automatizado (#10). À mão, com o `borg` do Pi, o prefixo
`immich-*` e o repositório `borg_immich_repo` (o `borg_restore` aceita ele
em `borg_restore_repo`).

### Depois do restore

Restore da mesma versão do Immich, de archive com os thumbs e os vídeos
re-encodados, não pede nada daqui. Os passos abaixo são para quando a
timeline mostra *error loading image* ou um vídeo não toca: restore que
cruza versão, ou de archive anterior ao ADR 0015.

O banco diz quais thumbnails, vídeos re-encodados e metadados existem, e o
disco pode não bater. Os jobs com *Missing* escolhem pelo banco, não pelo
disco, então não veem essa falta: o que conserta é o *All*, ou a ação na
seleção. Os jobs ficam na interface (*Administração → Jobs*); por API,
pediriam uma chave de admin a mais no vault para um passo que só roda no
restore.

1. **Thumbnails:** *Generate Thumbnails → All*. Leva tempo de CPU
   proporcional à biblioteca.

   Confira, com a timeline aberta: o log não mostra thumb faltando.

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net 'sudo docker logs --since 10m immich_server 2>&1 | grep -c "ENOENT.*thumbs"'
   ```

   `0` é o certo.

2. **Vídeos com `Missing video metadata` no log:** falta a linha deles em
   `asset_video`, que o Immich lê do banco para gerar thumbnail e
   transcode. Na busca, filtre por *Vídeos*, selecione todos e, no menu
   **⋮** da seleção, rode em ordem, esperando a fila de cada um zerar:
   *Refresh metadata*, *Regenerate thumbnails*, *Refresh encoded videos*.
   Sem essas ações no menu: *Extract Metadata → All*, *Generate Thumbnails
   → All* e *Transcode Videos → All*, que releem a biblioteca inteira.

   Confira: o log não mostra mais o erro, e um vídeo gravado no celular
   toca na interface.

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net 'sudo docker logs --since 10m immich_server 2>&1 | grep -c "Missing video metadata"'
   ```

   Vídeo que continua com o erro tem o original corrompido (`ffprobe` nele
   dentro de `library/`).

## Operação

- **Atualizar:** ler as notas da versão (o Immich muda o compose e migra o
  banco entre versões; as de quebra vêm marcadas), conferir que o último
  backup `immich-*` terminou, trocar `immich_version` e reaplicar o
  `immich.yml`. Se o compose oficial da versão nova mudar (Valkey, Postgres
  e os digests deles), acompanhe em `compose.yml.j2` e nas variáveis
  `immich_*_image`. O `pi-atualizar.yml` não muda a versão: a tag é exata.
- **Backup grande** (muitas fotos novas de uma vez): pode esperar o timer,
  porque a trava é só do repositório do Immich. À mão, como no passo 5 de
  "Backup → Configurar", para acompanhar.

## Limitações

- Uma cópia só fora de casa, no BorgBase, dentro da cota do plano.
- A chave SSH e a senha são as do compartilhado: quem tem uma abre os dois
  repositórios. Separar foi pela cota e pela trava, não por isolamento.
