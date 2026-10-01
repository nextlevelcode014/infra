# Raspberry Pi — base do host

`playbooks/pi.yml` aplica o role `pi_host`, que substitui as etapas 0 a 0.2
do `BOOTSTRAP.md` do `self-hosted` (`make host`, `bin/unlock`, `disk-guard`).
Todo playbook de serviço do Pi já puxa esse role como dependência, então
rodar só `playbooks/arr-stack.yml` também prepara o host.

O que ele faz:

- instala `git`, `rsync`, `cryptsetup` e o Docker (`geerlingguy.docker`);
- registra o LUKS em `/etc/crypttab` e `/etc/fstab` com `noauto`;
- instala `/usr/local/bin/secure-unlock` (o antigo `make unlock`);
- põe o data-root do Docker no LUKS e impede o Docker de subir sem ele;
- deixa o Docker **desabilitado no boot**: quem o sobe é o `secure-unlock`;
- cria as redes `medianet` e `vpn_net`;
- instala o `disk-guard` (script, service e timer).

## Passos manuais

Ficam fora do Ansible porque precisam da passphrase do LUKS ou de login
interativo, e nenhum dos dois pode viver no repo.

### Uma vez, num Pi zerado

1. **Tailscale no host.** O Ansible chega ao Pi pela tailnet
   (`ansible_host: nextlevelcode`), então este passo vem antes de tudo.

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh --hostname=nextlevelcode
   ```

   Confira do seu computador: `ssh ubuntu@nextlevelcode true`.

2. **Partição LUKS** na partição reservada (`p3`). Guarde a passphrase
   **fora do Pi**: no Bitwarden acessado de outro dispositivo e em papel.
   Sem ela, os dados somem — e não pode ficar só no Vaultwarden que roda aqui.

   ```bash
   sudo cryptsetup luksFormat /dev/<p3>
   sudo cryptsetup open /dev/<p3> secure
   sudo mkfs.ext4 -L secure /dev/mapper/secure
   sudo mkdir -p /mnt/secure && sudo mount /dev/mapper/secure /mnt/secure
   sudo blkid -s UUID -o value /dev/<p3>
   ```

   Ponha o UUID impresso em `pi_luks_uuid` no `inventory/pi.yml`.

3. **Aplicar a base:**

   ```bash
   ansible-playbook playbooks/pi.yml --ask-vault-pass
   ```

   Confira: `ssh ubuntu@nextlevelcode 'docker info -f {{.DockerRootDir}}'`
   deve responder `/mnt/secure/docker`.

### A cada boot

A raiz sobe sozinha; o LUKS não, e o Docker fica parado até ele abrir.

```bash
ssh -t ubuntu@nextlevelcode secure-unlock
```

Pede a passphrase, monta `/mnt/secure` e sobe o Docker. Os containers
voltam sozinhos (`restart: unless-stopped`). Confira com
`ssh ubuntu@nextlevelcode mountpoint /mnt/secure`.

Enquanto o volume estiver fechado, qualquer playbook do Pi para no começo com
`/mnt/secure não está montado` — é a guarda, não um erro do playbook.

## Adicionar um serviço no Pi

O `arr_stack` é o modelo. Um role novo precisa de:

1. `meta/main.yml` com as dependências:

   ```yaml
   dependencies:
     - role: pi_host
     - role: borg_client          # se tiver backup ou restore
     - role: secure_links         # se usar caminho fora de appdata_dir
       secure_links_paths:
         - /caminho/que/o/compose/usa
   ```

   Serviço novo não precisa de link: pode gravar direto em
   `{{ appdata_dir }}/<serviço>`. O `secure_links` existe para manter os
   caminhos antigos do `self-hosted` (`storage.map`) sem mexer no compose.
2. Compose em `/opt/<serviço>` e `docker_compose_v2`, portas publicadas só em
   `{{ ts_ip }}`.
3. Backup com o prefixo `<serviço>-*` usando `borg_repo`, `borg_passcommand`,
   `borg_rsh`, `borg_backup_compression` e `borg_backup_retention` (todos em
   `group_vars/all/vars.yml`).
4. Um role `<serviço>_restore` com `-e <serviço>_restore_confirmation=...`.
5. Playbook em `playbooks/` e entrada no `site.yml`.
6. Rota no `roles/caddy/templates/Caddyfile.j2`.
