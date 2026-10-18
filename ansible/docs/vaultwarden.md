# Vaultwarden no LXC do Proxmox

`playbooks/vaultwarden.yml` sobe o Vaultwarden no LXC `vaultwarden` (vmid 202,
`10.50.0.202`), com o backup no borgmatic do próprio LXC. Só existe na
tailnet: não há domínio público.

| O quê | Onde |
|---|---|
| Interface e clientes Bitwarden | `https://vault.lab.nextlevelcode.pro` (`vaultwarden_domain`): Caddy do Proxmox → `vaultwarden-lxc:8080` |
| Painel admin | `https://vault.lab.nextlevelcode.pro/admin` |
| Dados | `/opt/vaultwarden/vw-data` (`vaultwarden_dir`): SQLite, anexos, chaves |
| Na contingência | no Pi, em `/mnt/secure/appdata/vaultwarden`, porta `8083` no `ts_ip` (`docs/pi-recuperacao.md`) |

**Toda a config vem do compose**, por variável de ambiente
(`roles/vaultwarden/defaults/main.yml`): cadastro fechado, verificação de
e-mail, SMTP do Proton, 2FA por e-mail. O playbook apaga o
`vw-data/config.json` a cada execução, então **o que se muda no painel admin
some na próxima aplicação**. Mudança de config é no defaults e reaplicar.

## Antes de aplicar

- **Vault** (`inventory/group_vars/all/vault.yml`, modelo em
  `vault.yml.example`):
  - `vault_vaultwarden_admin_token`: o **hash** argon2 do token do painel,
    gerado com `docker run --rm -it vaultwarden/server /vaultwarden hash`. O
    token em texto, o que se digita no `/admin`, fica fora do Vaultwarden
    (Bitwarden de outro aparelho e papel): sem ele não se entra no painel
    com o cofre fora do ar;
  - `vault_vaultwarden_smtp_username` e `vault_vaultwarden_smtp_password`:
    o token SMTP do Proton para `vaultwarden@nextlevelcode.pro`;
  - as quatro `vault_forgejo_borg_*`, que são do Borg de todos os serviços.
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:proxmox-lxc:8080`.
- **DNS:** nada a fazer. O curinga `*.lab` da Cloudflare já aponta para o
  Caddy do Proxmox.

## Instalação

1. **LXC pelo Terraform**, em `../terraform/`:

   ```bash
   cd ../terraform && terraform plan && terraform apply
   ```

   Confira: `ansible-inventory --graph lxc` lista `vaultwarden`.

2. **Base do LXC** (flags, Tailscale, Docker):

   ```bash
   ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,vaultwarden
   ```

   Confira: o nó `vaultwarden-lxc` aparece no console do Tailscale.

3. **Tag** no console → Machines → `vaultwarden-lxc` → Edit ACL tags:
   `tag:proxmox-lxc`. É manual porque as tags de nó ficam no console
   (`tailscale/README.md`, "Tags"). Sem ela, o Caddy não alcança a 8080.

   Confira: `ssh root@10.50.0.202 tailscale status --self` mostra a tag.

4. **Vaultwarden:**

   ```bash
   ansible-playbook playbooks/vaultwarden.yml --ask-vault-pass
   ```

   Confira: `ssh root@10.50.0.202 curl -s localhost:8080/alive` devolve
   uma data, e `https://vault.lab.nextlevelcode.pro` abre o login (o Caddy do
   Proxmox já tem a rota, `roles/caddy/templates/Caddyfile.j2`).

5. **Dados.** Com backup a trazer, este é o momento do restore
   (`docs/vaultwarden-restore.md`); as contas e os cofres vêm junto, e o
   passo 6 não se aplica. Instância nova segue para o 6.

6. **Primeira conta, só em instância nova.** Com o cadastro fechado, a conta
   nasce por convite: `/admin` → token em texto → Users → Invite User com o
   seu e-mail. O convite chega pelo SMTP; o link abre o cadastro. É manual
   porque passa pelo navegador e pela caixa de e-mail.

   Confira: o e-mail do convite chega (prova que o SMTP funciona), e o login
   com a conta nova abre o cofre vazio.

7. **Monitores.** O *Vaultwarden* (`/alive` pelo `vault.lab`) e o *Backup
   Vaultwarden* já estão em `group_vars/vps/monitors.yml`. Só reaplique o
   `uptime-kuma.yml` se mudou algo lá.

   Confira: os dois ficam verdes no Uptime Kuma (o de backup, depois da
   primeira noite ou de um backup manual, `docs/backup.md`).

8. **Clientes** (extensão, celular, desktop): servidor auto-hospedado
   `https://vault.lab.nextlevelcode.pro`. Só funcionam com o aparelho na
   tailnet.

## Backup

Prefixo `vaultwarden-*`, no borgmatic do LXC às 02:15 (`docs/backup.md`). A
stack **para** durante o `borg create`, para o SQLite ser copiado parado, e
sobe no fim, também quando o backup falha: o cofre fica fora do ar por menos
de um minuto. Leva o `vw-data/` inteiro, menos `*.tmp`, `*.log` e `cache/`.

O token admin e o SMTP não estão no archive: vêm do vault do Ansible. Por
isso o vault e a senha dele também precisam existir fora do homelab
(`docs/pi-reconstrucao.md`, "O que precisa existir fora do Pi").

Monitor *Backup Vaultwarden*. Em standby (o Pi fora da contingência) não há
backup: um archive `vaultwarden-*` do Pi viraria o mais recente para o
restore. Restore: `docs/vaultwarden-restore.md`.

## Operação

- **Atualizar:** a imagem tem versão exata (`vaultwarden_image`, no
  `defaults` do role), porque o Vaultwarden migra o banco ao subir e a
  migração não volta atrás. Para subir: ler as notas da versão, conferir que
  o monitor *Backup Vaultwarden* está verde, trocar a variável e reaplicar o
  `vaultwarden.yml` (no Pi, o `pi-recuperacao.yml`). Reaplicar sem trocar a
  variável não muda a versão.
- **Proxmox fora:** o Pi assume, `docs/pi-recuperacao.md`.
