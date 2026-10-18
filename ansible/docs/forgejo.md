# Forgejo no LXC do Proxmox

`playbooks/forgejo.yml` sobe o Forgejo e o Postgres dele no LXC `forgejo`
(vmid 201, `10.50.0.201`), com o backup no borgmatic do próprio LXC.

| O quê | Onde |
|---|---|
| Web e clone HTTPS (público) | `https://forge.nextlevelcode.pro`: Cloudflare → Caddy da VPS → Anubis (`127.0.0.1:8923`) → `forgejo_tailscale_ip:3000` |
| SSH do Git (só tailnet) | `forgejo-lxc:2222` (`forgejo_ssh_domain`), sem passar por Caddy |
| Dados | `/opt/forgejo` (`forgejo_dir`): `forgejo/` (repositórios e config) e `postgres/` |
| Na contingência | no Pi, em `/mnt/secure/appdata/forgejo` (`docs/pi-recuperacao.md`) |

O compose fixa a instalação: `INSTALL_LOCK=true` (sem assistente web),
cadastro fechado (`DISABLE_REGISTRATION=true`) e repositórios públicos
visíveis sem login. O web só existe pelo domínio público: não há rota no
`*.lab`.

## Antes de aplicar

- **Vault** (`inventory/group_vars/all/vault.yml`, modelo em
  `vault.yml.example`): `vault_forgejo_db_password`, as duas
  `vault_forgejo_signing_ssh_*` (seção "Assinatura dos merges") e as quatro
  `vault_forgejo_borg_*`, que são do Borg de todos os serviços.
- **ACL** (`tailscale/policy.hujson`), já na política: membros da tailnet →
  `tag:forgejo:2222` (Git), `tag:caddy-vps` → `tag:forgejo:3000` (web
  público) e `tag:vps` → `tag:forgejo:2222` (monitor do SSH).
- **Cloudflare:** registro `forge` apontando para o IP público da VPS. Só muda
  com VPS nova (`docs/vps.md`).

## Instalação

1. **LXC pelo Terraform**, em `../terraform/`:

   ```bash
   cd ../terraform && terraform plan && terraform apply
   ```

   Confira: `ansible-inventory --graph lxc` lista `forgejo`.

2. **Base do LXC** (flags, Tailscale, Docker):

   ```bash
   ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,forgejo
   ```

   Confira: o nó `forgejo-lxc` aparece no console do Tailscale.

3. **Tags e IP Tailscale.** No console → Machines → `forgejo-lxc` → Edit ACL
   tags: `tag:proxmox-lxc` e `tag:forgejo`. É manual porque as tags de nó
   ficam no console (`tailscale/README.md`, "Tags"). Depois ponha o IP do nó
   (`ssh root@10.50.0.201 tailscale ip -4`) em `forgejo_tailscale_ip`
   (`inventory/group_vars/all/vars.yml`): a VPS não resolve nomes da
   tailnet, então o Anubis e o Uptime Kuma usam o IP.

   Confira: `ssh root@10.50.0.201 tailscale status --self` mostra as duas
   tags.

4. **Forgejo:**

   ```bash
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass
   ```

   Confira: `ssh root@10.50.0.201 docker compose -f /opt/forgejo/compose.yml ps`
   mostra `forgejo` e `forgejo-db` rodando, e
   `ssh root@10.50.0.201 curl -s localhost:3000/api/healthz` traz
   `"status": "pass"`.

5. **Dados.** Com backup a trazer, este é o momento do restore
   (`docs/forgejo-restore.md`); o admin e os repositórios vêm junto, e o
   passo 6 não se aplica. Instância nova segue para o 6.

6. **Admin, só em instância nova.** Com `INSTALL_LOCK` e o cadastro fechado,
   a interface não cria o primeiro usuário: ele sai pela CLI. É manual porque
   a senha não deve passar pelo repo; a CLI gera uma e mostra uma vez.

   ```bash
   ssh -t root@10.50.0.201 docker exec -it forgejo \
     forgejo admin user create --admin --username <usuário> --email <email> --random-password
   ```

   Confira: o login em `https://forge.nextlevelcode.pro` (passo 7) funciona
   com a senha impressa. Troque-a na interface e guarde no Vaultwarden.

7. **VPS: Anubis, Caddy e monitores.** Só é preciso se o
   `forgejo_tailscale_ip` mudou no passo 3: o Anubis e o monitor do SSH
   apontam para ele.

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Confira: `https://forge.nextlevelcode.pro` abre (depois do desafio do
   Anubis), e os monitores *Forgejo* e *Forgejo (SSH)* ficam verdes.

8. **Cliente SSH**, em cada computador que faz push (`~/.ssh/config`):

   ```
   Host forgejo forgejo-lxc
       HostName forgejo-lxc
       Port 2222
       User git
       IdentityFile <sua chave>
       IdentitiesOnly yes
   ```

   Confira: `ssh -T forgejo` responde com o seu usuário, e
   `git ls-remote origin` funciona num clone (`ssh://git@forgejo-lxc:2222/<org>/<repo>.git`).

## Assinatura dos merges

O squash merge de um PR não reaproveita o commit da branch: o Forgejo cria um
commit novo no servidor, e a chave de quem escreveu não está lá. Por isso ele
assina esses commits com uma chave **da instância** (`[repository.signing]`
no compose, `MERGES=always`). A assinatura diz "mergeado por este Forgejo";
a autoria continua no autor do commit e na assinatura dele na branch. Autor
e committer do merge não mudam: continuam sendo quem escreveu e quem
mergeou. O `forgejo_signing_name` e o `forgejo_signing_email`
(`roles/forgejo/defaults/main.yml`) são obrigatórios na config, mas não
aparecem nesses commits.

A chave fica em `forgejo/signing/` (`key` e `key.pub`), escrita pelo role a
partir do vault, e entra no backup com o resto de `forgejo/`. Na contingência
o Pi assina com a mesma chave.

### Chave nova (uma vez, ou para trocar)

É manual porque a chave privada não pode passar pelo repo, e o vault só se
edita com a senha dele.

1. **Gerar**, sem passphrase (o Forgejo assina sem ninguém digitar nada):

   ```bash
   ssh-keygen -t ed25519 -N '' -C forgejo-signing -f /tmp/forgejo-signing
   ```

2. **Pôr no vault** o conteúdo de `/tmp/forgejo-signing` em
   `vault_forgejo_signing_ssh_private_key` (bloco `|`, como no `.example`) e o
   de `/tmp/forgejo-signing.pub` em `vault_forgejo_signing_ssh_public_key`:

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira: `ansible-vault view inventory/group_vars/all/vault.yml | grep -c forgejo_signing`
   dá `2`. Guarde a chave também no Vaultwarden e apague as duas de `/tmp`.

3. **Aplicar** onde o Forgejo está no ar. Reinicia o Forgejo: o push e a web
   caem por alguns segundos. Qual dos dois vale é o `proxmox_fora` do
   `inventory/group_vars/all/vars.yml`.

   - `proxmox_fora: false`, Forgejo no LXC do Proxmox:

     ```bash
     ansible-playbook playbooks/forgejo.yml --ask-vault-pass
     ```

   - `proxmox_fora: true`, Forgejo no Pi (contingência). Não há playbook só
     do Forgejo no Pi: o `pi-recuperacao.yml` reaplica também o `pi_host` e o
     Vaultwarden, então olhe o diff antes. Fora a chave e o compose do
     Forgejo, ele não deve mudar nada:

     ```bash
     ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi --check --diff
     ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi
     ```

   Confira, com `<host>` sendo `forgejo` (Proxmox) ou `rpi` (Pi):

   ```bash
   ansible <host> --ask-vault-pass -m command -a 'curl -s localhost:3000/api/v1/signing-key.ssh'
   ```

   devolve a chave pública que está no vault.

4. **Testar com um merge:** depois do próximo squash merge,

   ```bash
   git fetch origin && git log -1 --format='%G? %GK' origin/main
   ```

   mostra `U` e a impressão digital da chave: assinado, mas por uma chave que
   o seu git ainda não conhece. Ela tem que ser a mesma de
   `ssh-keygen -lf /tmp/forgejo-signing.pub` (ou da chave pública do vault).
   `N` quer dizer que o Forgejo não assinou: olhe o log do container.

5. **Confiar na chave**, em cada computador que confere assinatura: uma linha
   no `gpg.ssh.allowedSignersFile` (`git config gpg.ssh.allowedSignersFile`
   mostra qual é). O e-mail na frente é só o nome da chave nesse arquivo: o
   git acha a linha pela chave, não pelo committer.

   ```bash
   pub=$(ansible-vault view inventory/group_vars/all/vault.yml \
     | sed -n 's/^vault_forgejo_signing_ssh_public_key: "\(.*\)"$/\1/p')
   echo "forgejo@nextlevelcode.pro namespaces=\"git\" $pub" \
     >> "$(git config gpg.ssh.allowedSignersFile)"
   ```

   Confira: o `git log` do passo 4 passa a mostrar `G`. Os merges anteriores
   a esta mudança continuam `N`: assinatura não se põe em commit que já
   existe sem reescrever o histórico.

## Backup

Prefixo `forgejo-*`, no borgmatic do LXC às 02:00 (`docs/backup.md`). Antes do
`borg create`, um `pg_dump` com o banco no ar (vai para `/tmp`, que o
borgmatic.service tem privado) e depois a stack **para**: o Forgejo fica fora
do ar enquanto o Borg copia `forgejo/`, alguns minutos. Sobe de novo no fim,
também quando o backup falha. Fica de fora `*.tmp`, `*.log` e `cache/`; o
`postgres/` não entra, porque o dump é o que restaura.

Monitor *Backup Forgejo*. Em standby (o Pi fora da contingência) não há
backup: um archive `forgejo-*` do Pi viraria o mais recente para o restore.
Restore: `docs/forgejo-restore.md`.

## Operação

- **Atualizar:** as duas imagens têm versão exata (`forgejo_image` e
  `forgejo_db_image`, no `defaults` do role), porque o Forgejo migra o banco
  ao subir e a migração não volta atrás. Para subir: ler as notas da versão,
  conferir que o monitor *Backup Forgejo* está verde, trocar a variável e
  reaplicar o `forgejo.yml` (no Pi, o `pi-recuperacao.yml`). Reaplicar sem
  trocar a variável não muda a versão.
- **Monitores:** *Forgejo* (`/api/healthz` pelo domínio público, o único
  caminho que o Anubis libera sem desafio) e *Forgejo (SSH)* (porta 2222 em
  `forgejo_tailscale_ip`).
- **Proxmox fora:** o Pi assume, `docs/pi-recuperacao.md`.
