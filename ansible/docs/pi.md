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
- cria o usuário admin (`ubuntu`, uid 1000) se não existir;
- cria as redes `medianet` e `vpn_net`;
- instala o `disk-guard` (script, service e timer);
- instala o `reboot-watch` (ver "Atualizar");
- grava `PSU_MAX_CURRENT` na EEPROM (só no Pi físico; ver "Fonte e boot
  sozinho").

## Passos manuais

Ficam fora do Ansible porque precisam da passphrase do LUKS, de login
interativo ou da mão no disco, e nenhum dos três cabe no repo.

### Instalar o Ubuntu

O SSD é gravado no seu computador, pelo Raspberry Pi Imager, e a `p3` do
LUKS é criada **antes do primeiro boot**. Não dá para deixar para depois: a
imagem do Ubuntu sai só com `p1` (boot) e `p2` (raiz), e no primeiro boot o
cloud-init roda o `growpart`, que estica a `p2` até o fim do disco. Raiz em
ext4 montada não encolhe, então quem esquece este passo regrava o SSD.

1. **Gravar no Imager:** Raspberry Pi 5 → Other general-purpose OS → Ubuntu →
   Ubuntu Server 26.04 (64-bit) → o SSD. Em "Edit settings": hostname
   `nextlevelcode`, usuário **`ubuntu`** (vira o uid 1000, que o `pi_host`
   espera), SSH ligado só com chave pública (a sua `.pub`). Wi-Fi não: o Pi
   fica no cabo.

2. **Reservar a `p3`**, com o SSD ainda no seu computador. Ache o disco pelo
   tamanho (o SSD do Pi tem ~931G) e confira que as partições estão
   desmontadas (o desktop costuma montar a `p1` sozinho):

   ```bash
   lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
   sudo umount /dev/sdX1 /dev/sdX2 2>/dev/null
   sudo parted /dev/sdX resizepart 2 20GiB
   sudo parted /dev/sdX mkpart primary 20GiB 100%
   ```

   A `p3` fica sem filesystem: ela vira LUKS no passo 2 da próxima seção.
   O ext4 da raiz não precisa de `resize2fs`, porque o cloud-init o estica até
   os 20GiB no primeiro boot. O `growpart` não acha espaço livre colado na `p2`
   e não faz nada.

   Confira: `lsblk /dev/sdX` mostra `sdX2` com ~19G e `sdX3` com o resto,
   sem `FSTYPE`.

3. **Primeiro boot:** SSD no Pi, cabo de rede, fonte. Espere uns minutos (o
   cloud-init cria o usuário) e entre pela LAN, pelo IP que o roteador deu:

   ```bash
   ssh ubuntu@<ip-da-lan> lsblk
   ```

   Deve mostrar `sda2` em `/` com ~19G e `sda3` ainda sem filesystem.

### Uma vez, num Pi zerado

1. **Tailscale no host.** O Ansible chega ao Pi pela tailnet
   (`ansible_host: nextlevelcode`), então este passo vem antes de tudo.

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh --hostname=nextlevelcode
   ```

   Confira do seu computador: `ssh ubuntu@nextlevelcode true`.

2. **Partição LUKS** na `p3` reservada na instalação (no Pi, `/dev/sda3`).
   Guarde a passphrase **fora do Pi**: no Bitwarden acessado de outro
   dispositivo e em papel.
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

### Atualizar

Atualização de **segurança** do Ubuntu já entra sozinha: o
unattended-upgrades vem ligado na imagem e roda todo dia pelo
`apt-daily-upgrade.timer`, sem reiniciar. O resto (pacotes que não são de
segurança e as imagens das stacks) é sob demanda, quando você quiser:

```bash
ansible-playbook playbooks/pi-atualizar.yml --limit rpi --ask-vault-pass
```

Faz, nesta ordem: `apt dist-upgrade`, `pull` das imagens de cada stack,
`up -d` de cada stack (recria só o container cuja imagem mudou), recria os
dependentes do gluetun e apaga as imagens antigas do LUKS. Só troca imagem:
config nova continua sendo o playbook do serviço (ou o `pi-completo.yml`).
Não reinicia: se o SO pedir reboot, o playbook avisa no fim, e o reboot fica
com você porque derruba tudo até o `secure-unlock`.

Ficam de fora:

- **Nextcloud AIO**: o mastercontainer e os containers dele se atualizam pela
  interface do próprio AIO.
- **Forgejo e Vaultwarden em standby**: o role deles já faz `pull: always`.

Quase tudo está em `:latest` (e o Immich em `release`), então um pull pode
trazer versão nova com mudança que quebra. Confira depois:

```bash
ssh ubuntu@nextlevelcode 'docker ps --format "{{.Names}} {{.Status}}" | grep -v "Up"'
```

Sem saída, nenhum container está parado ou reiniciando. Se o SO pediu reboot,
reinicie e destrave como em "A cada boot".

Se o reboot ficar para depois, o `reboot-watch` lembra: passados **3 dias**
do pedido, o monitor *Atualizações Raspberry Pi* cai no Uptime Kuma e manda
e-mail com os pacotes que pediram o reboot (`docs/uptime-kuma.md`).

### Fonte e boot sozinho

A fonte oficial de 27W chega ao Pi sem negociação USB-PD, então o firmware
assume uma fonte fraca: limita a USB e, como o sistema boota pela USB, para
no boot pedindo o botão de power. Isso impede o reboot remoto e a volta
depois de uma queda de luz. O role grava `PSU_MAX_CURRENT=5000` na EEPROM
(`pi_psu_max_current` no `inventory/pi.yml`), mas a EEPROM só é gravada no
boot seguinte e o role não reinicia sozinho: **reiniciar é o passo manual**,
porque derruba todas as stacks até o `secure-unlock`.

1. Aplicar e reiniciar:

   ```bash
   ansible-playbook playbooks/pi.yml --ask-vault-pass
   ssh ubuntu@nextlevelcode sudo reboot
   ```

   O reboot pode demorar um pouco mais que o normal, porque o Pi grava a
   EEPROM antes de subir.

2. Destravar o LUKS (seção acima) e conferir:

   ```bash
   ssh ubuntu@nextlevelcode 'sudo rpi-eeprom-config | grep PSU_MAX_CURRENT'
   ssh ubuntu@nextlevelcode 'od -An -tx1 /proc/device-tree/chosen/power/max_current'
   ```

   O primeiro deve mostrar `PSU_MAX_CURRENT=5000`, e o segundo
   `00 00 13 88` (5000 em hexadecimal). Antes, mostrava `00 00 03 84` (900).

3. A prova de verdade: um `sudo reboot` com você fora de casa. Se o Pi
   volta à tailnet sem ninguém apertar nada, está resolvido.

## pi-lab — staging do Pi

O `pi-lab` (LXC x86, vmid 203, `192.168.50.203`) recebe os mesmos playbooks do
Pi para testar antes. O Terraform o põe no grupo `pi_staging`, que o
`inventory/pi.yml` coloca sob `pi_hosts`. O que muda está em
`group_vars/pi_staging/vars.yml`:

- **sem LUKS:** `/mnt/secure` é um volume do Proxmox. Sem `pi_luks_uuid`, o
  `pi_host` pula crypttab, fstab e `secure-unlock`, e o Docker sobe no boot;
- **sem Tailscale:** `ts_ip` é o IP da LAN, e o `lxc.yml` aplica no pi-lab só
  as flags do LXC (`keyctl`, `/dev/net/tun`), não a base dos outros LXCs;
- **sem backup:** `borg_backup_enabled: false` (timer do borgmatic parado e
  nenhum config). Um backup do pi-lab cairia no repositório de produção e
  viraria o archive mais recente para o restore. O acesso ao Borg continua
  instalado, para ensaiar restore aqui;
- **WireGuard próprio** e API keys de mentira para o decluttarr.

Cobre "o playbook roda e o compose sobe". Não cobre ARM64, LUKS de verdade nem
o disco do Pi.

### Preparar o pi-lab

1. No repo `terraform`, aplicar o volume `/mnt/secure` e o grupo `pi_staging`
   (recria o pi-lab):

   ```bash
   cd ../terraform && terraform plan && terraform apply
   ```

   Confira: `ansible-inventory --graph pi_staging` deve listar `pi-lab`.

2. Gerar uma config WireGuard **nova** na ProtonVPN (account.protonvpn.com →
   Downloads → WireGuard configuration) e pôr `PrivateKey` e `Address` em
   `vault_gluetun_staging_*`. Não dá para reaproveitar a do Pi: a mesma chave
   em duas máquinas derruba o túnel do Pi. É manual porque a ProtonVPN não tem
   API para isso.

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

3. Aplicar as flags do LXC (para e sobe o container) e depois a stack:

   ```bash
   ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,pi_staging
   ansible-playbook playbooks/arr-stack.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `ssh root@192.168.50.203 docker compose ls` lista `gluetun` e
   `arr`, e `ssh root@192.168.50.203 docker exec gluetun wget -qO- https://ipinfo.io/ip`
   mostra um IP da ProtonVPN, não o da sua casa.

**Sempre com `--limit pi_staging`.** Sem ele, os playbooks do Pi rodam também
no Raspberry de verdade.

## Adicionar um serviço no Pi

O `arr_stack` é o modelo. Um role novo precisa de:

1. `meta/main.yml` com as dependências:

   ```yaml
   dependencies:
     - role: pi_host
     - role: gluetun              # se sair pela VPN
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
3. Backup com `include_role: borg_client, tasks_from: backup` e o monitor em
   `uptime_kuma_backups`. A receita está em `docs/backup.md`, "Serviço novo".
4. Um role `<serviço>_restore` com `-e <serviço>_restore_confirmation=...`.
5. Playbook em `playbooks/` com `hosts: pi_hosts` e entrada no `site.yml`.
   Teste primeiro com `--limit pi_staging`.
6. Rota em `caddy_lab_pi_routes` (`group_vars/all/vars.yml`), que vale para o
   Caddy do Proxmox e para o reserva do Pi, e a porta no grant de `tag:caddy`
   → `tag:pi` no `tailscale/policy.hujson`. O Caddy reserva fala com o
   próprio IP Tailscale, sem passar pela ACL. Reaplique os dois:
   `playbooks/caddy.yml` e `playbooks/caddy-pi.yml`.
