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
e-mail, SMTP do Mailserver, 2FA por e-mail. O playbook apaga o
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
  - `vault_vaultwarden_mailserver_smtp_password`: a senha SMTP da conta
    `vaultwarden@nextlevelcode.pro` no Mailserver;
  - as quatro `vault_forgejo_borg_*`, que são do Borg de todos os serviços.
- **ACL** (`tailscale/policy.hujson`): `tag:caddy` → `tag:proxmox-lxc:8080`
  para a interface web e `tag:vaultwarden` / `tag:pi` → `tag:vps:587`
  para o SMTP autenticado.
- **DNS:** o curinga `*.lab` aponta para o Caddy do Proxmox.
  `cliente-piloto.nextlevelcode.pro` aponta para a VPS na tailnet e consta
  no certificado do [Mailserver](mailserver.md).

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

3. **Tags** no console → Machines → `vaultwarden-lxc` → Edit ACL tags:
   `tag:proxmox-lxc` para o Caddy e `tag:vaultwarden` para o Mailserver.
   É manual porque as tags de nó ficam no console
   (`tailscale/README.md`, "Tags").

   Confira: `ssh root@10.50.0.202 tailscale status --json | jq -r '.Self.Tags[]'`
   mostra as duas tags.

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

## Migrar o SMTP para o Mailserver

Faça a aplicação em janela autorizada, depois do merge. O Mailserver deve
estar atendendo o domínio principal e entregando mensagens internas e externas.
Execute os comandos de `ansible/`.

1. Gere uma senha exclusiva para `vaultwarden@nextlevelcode.pro`. Guarde-a
   num gerenciador acessível mesmo com o Vaultwarden fora do ar. Estes
   comandos pedem a senha interativamente e abrem o vault cifrado.

   ```bash
   openssl passwd -6
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira no editor que `vault_mailserver_principal.contas.vaultwarden`
   contém o hash com prefixo `$6$` e que
   `vault_vaultwarden_mailserver_smtp_password` contém a senha que gerou esse
   hash. Mantenha o usuário e o token do Proton no vault durante a janela.
2. Cadastre a conta na VPS pelo playbook do Mailserver e confirme que o
   Dovecot reconhece o endereço.

   ```bash
   ansible-playbook playbooks/mailserver.yml --limit hetzner --ask-vault-pass -e mailserver_ativar=true
   ssh hetzner@hetzner 'sudo docker compose -f /opt/mailserver/compose.yml exec -T mailserver doveadm user vaultwarden@nextlevelcode.pro'
   ```

3. Compare a política do console com a versão do repositório e incorpore
   pelo fluxo de PR qualquer edição feita no console antes de publicar a
   [política da tailnet](../tailscale/README.md#aplicar-uma-mudança).
   Acrescente `tag:vaultwarden` ao LXC conforme o passo 3 da
   instalação. Confirme `tag:pi` no Pi e `tag:vps` na VPS em **Machines**.
   Do LXC e do Pi, valide a 587 e o nome no certificado. A saída de cada
   host deve mostrar a verificação TLS bem-sucedida.

   ```bash
   ansible 'vaultwarden,rpi' --ask-vault-pass -m shell -a 'timeout 15 openssl s_client -starttls smtp -connect cliente-piloto.nextlevelcode.pro:587 -verify_hostname cliente-piloto.nextlevelcode.pro -verify_return_error -brief </dev/null'
   ```

4. Atualize o LXC. O Compose recria o container para carregar as variáveis
   SMTP, com uma breve interrupção do serviço. Confirme o `/alive` e repita
   a verificação TLS de dentro do container para conferir o caminho do Docker.

   ```bash
   ansible-playbook playbooks/vaultwarden.yml --limit vaultwarden --ask-vault-pass
   curl -fsS https://vault.lab.nextlevelcode.pro/alive
   ssh root@10.50.0.202 'timeout 15 docker exec vaultwarden openssl s_client -starttls smtp -connect cliente-piloto.nextlevelcode.pro:587 -verify_hostname cliente-piloto.nextlevelcode.pro -verify_return_error -brief'
   ```

5. Com uma sessão atual aberta, entre pela janela privativa do navegador
   com uma conta que usa 2FA por e-mail. Receba o código enviado de
   `vaultwarden@nextlevelcode.pro`, use-o e confirme que o cofre abre.
   Esse teste é manual porque passa pelo navegador e pela caixa de e-mail.
6. Atualize a configuração de contingência com `proxmox_fora: false` e
   o LUKS do Pi montado. Confira que o container do Vaultwarden segue parado.
   Repita o teste de 2FA no Pi quando ele assumir em um ensaio ou na
   [contingência](pi-recuperacao.md).

   ```bash
   ansible-playbook playbooks/pi-recuperacao.yml --limit rpi --ask-vault-pass
   ssh ubuntu@nextlevelcode 'sudo docker ps -q --filter name=vaultwarden'
   ```

Se a entrega falhar e o Proton ainda estiver apto a enviar para a caixa de
2FA, reaplique o playbook do LXC com o token anterior e repita o teste em
janela privativa.

```bash
ansible-playbook playbooks/vaultwarden.yml --limit vaultwarden --ask-vault-pass -e vaultwarden_smtp_mailserver_ativo=false
```

Se o Pi já tiver recebido a configuração nova, reverta também em standby
e confira o resultado com o comando do passo 6.

```bash
ansible-playbook playbooks/pi-recuperacao.yml --limit rpi --ask-vault-pass -e vaultwarden_smtp_mailserver_ativo=false
```

O parâmetro vale para uma execução. Se a reversão precisar durar, registre
o valor em branch antes da próxima aplicação.

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
