# Forgejo no LXC do Proxmox

`playbooks/forgejo.yml` sobe o Forgejo e o Postgres dele no LXC `forgejo`
(vmid 201, `192.168.50.201`), com o backup no borgmatic do próprio LXC.

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
  `vault.yml.example`): `vault_forgejo_db_password` e as quatro
  `vault_forgejo_borg_*`, que são do Borg de todos os serviços.
- **ACL** (`tailscale/policy.hujson`), já na política: membros da tailnet →
  `tag:forgejo:2222` (Git), `tag:caddy-vps` → `tag:forgejo:3000` (web
  público) e `tag:vps` → `tag:forgejo:2222` (monitor do SSH).
- **Cloudflare:** registro `forge` apontando para o IP público da VPS. Só muda
  com VPS nova (`docs/vps.md`).

## Instalação

1. **LXC pelo Terraform**, no repo `terraform`:

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
   (`ssh root@192.168.50.201 tailscale ip -4`) em `forgejo_tailscale_ip`
   (`inventory/group_vars/all/vars.yml`): a VPS não resolve nomes da
   tailnet, então o Anubis e o Uptime Kuma usam o IP.

   Confira: `ssh root@192.168.50.201 tailscale status --self` mostra as duas
   tags.

4. **Forgejo:**

   ```bash
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass
   ```

   Confira: `ssh root@192.168.50.201 docker compose -f /opt/forgejo/docker-compose.yml ps`
   mostra `forgejo` e `forgejo-db` rodando, e
   `ssh root@192.168.50.201 curl -s localhost:3000/api/healthz` traz
   `"status": "pass"`.

5. **Dados.** Com backup a trazer, este é o momento do restore
   (`docs/forgejo-restore.md`); o admin e os repositórios vêm junto, e o
   passo 6 não se aplica. Instância nova segue para o 6.

6. **Admin, só em instância nova.** Com `INSTALL_LOCK` e o cadastro fechado,
   a interface não cria o primeiro usuário: ele sai pela CLI. É manual porque
   a senha não deve passar pelo repo; a CLI gera uma e mostra uma vez.

   ```bash
   ssh -t root@192.168.50.201 docker exec -it forgejo \
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

- **Atualizar:** o `forgejo.yml` faz `pull` a cada execução, e as tags são
  flutuantes (`15-rootless`, `postgres:16-alpine`): reaplicar o playbook
  também atualiza o Forgejo dentro da 15.x. Isso vai mudar com a #70.
- **Monitores:** *Forgejo* (`/api/healthz` pelo domínio público, o único
  caminho que o Anubis libera sem desafio) e *Forgejo (SSH)* (porta 2222 em
  `forgejo_tailscale_ip`).
- **Proxmox fora:** o Pi assume, `docs/pi-recuperacao.md`.
