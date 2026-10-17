# Borg offsite

`playbooks/borg-offsite.yml` faz de uma máquina fora de casa um servidor
Borg: monta o disco dos repositórios, cria o usuário `borg` com cada chave
presa ao seu repositório e fecha o sshd para a tailnet. Hoje a máquina é um
desktop Omarchy (Arch) de uso normal, com um NVMe só para o Borg; o role não
mexe no resto do desktop.

| O quê | Onde |
|---|---|
| Máquina | host `borg-offsite` no inventário, pelo IP Tailscale (`vault_borg_offsite_tailscale_ip`) |
| Repositórios | `/srv/borg` (`borg_offsite_dir`), disco com label `borg` |
| Immich | `/srv/borg/immich`, do borgmatic do Pi (`docs/immich.md`, "Backup") |
| Nextcloud AIO | `/srv/borg/nextcloud`, do Borg do próprio AIO (`docs/nextcloud.md`, "Backup") |
| Acesso | OpenSSH na 22, só pela tailnet: `infra` (Ansible, sudo) e `borg` (`borg serve`) |

Por que um servidor próprio, e não o BorgBase: ADR 0007.

## Antes de aplicar

- **ACL** (`tailscale/policy.hujson`): `borg-offsite` em `hosts`, com o IP
  da máquina no lugar do placeholder, e o grant `tag:pi` →
  `borg-offsite:22` (passo 4).
- **Vault:** `vault_borg_offsite_*` (`vault.yml.example`), no passo 4. Sem
  eles, **todo playbook com backup falha**: o `borg_client` grava o
  known_host da máquina em todo cliente.

## Instalação

Nos comandos, `<borg_offsite_ts_ip>` é o IP Tailscale da máquina
(`tailscale ip -4` nela) e `<maquina>` o nome dela na tailnet.

1. **Bootstrap na máquina**, logado nela com o usuário do desktop. Manual
   porque o Ansible precisa de um usuário e de um sshd para entrar, e é isto
   que os cria. Troque a chave pelo conteúdo de `~/.ssh/id_ed25519.pub` do
   desktop de administração:

   ```bash
   sudo pacman -S --needed openssh python
   sudo useradd -m infra
   echo 'infra ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/infra
   sudo chmod 0440 /etc/sudoers.d/infra
   sudo install -d -m 0700 -o infra -g infra /home/infra/.ssh
   echo 'ssh-ed25519 AAAA... sia@omarchy' | sudo tee /home/infra/.ssh/authorized_keys
   sudo chown infra:infra /home/infra/.ssh/authorized_keys
   sudo chmod 0600 /home/infra/.ssh/authorized_keys
   sudo ufw allow in on tailscale0 to any port 22 proto tcp
   sudo systemctl enable --now sshd
   ```

   O `infra` fica sem senha: só entra por chave, e o sudo dele não pede.

   Confira, do desktop:

   ```bash
   ssh infra@<borg_offsite_ts_ip> sudo -n true && echo ok
   ```

2. **Tailscale sem expirar.** Dispositivo de usuário expira a chave a cada
   180 dias e sai da tailnet, e o backup para sem ninguém por perto para
   logar de novo. No console (<https://login.tailscale.com/admin/machines>),
   na `<maquina>`: *⋯* → *Disable key expiry*. Manual: é uma opção do
   console, sem a API.

   Confira: a linha da máquina mostra *Expiry disabled*.

3. **Formatar o disco do Borg**, na máquina. **Apaga o disco:** confira o
   modelo e o tamanho no `lsblk` antes, e troque `nvmeXn1` pelo disco do
   Borg, nunca o do sistema. Manual porque é destrutivo e acontece uma vez.

   ```bash
   lsblk -o NAME,SIZE,MODEL,FSTYPE,MOUNTPOINTS
   sudo mkfs.ext4 -L borg /dev/nvmeXn1
   ```

   Confira: `lsblk -f` mostra `ext4` com o label `borg` no disco certo, e o
   disco do sistema intacto.

4. **Vault e ACL.** No desktop:

   ```bash
   tailscale ip -4 <maquina>
   ssh-keyscan -t ed25519 <borg_offsite_ts_ip> | cut -d' ' -f2-
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo ssh-keygen -y -f /root/.ssh/id_ed25519
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Os três vão em `vault_borg_offsite_tailscale_ip`,
   `vault_borg_offsite_known_host_key` e `vault_borg_offsite_pi_public_key`;
   `vault_borg_offsite_aio_public_key: ""` por enquanto. Depois, cole a
   política (`tailscale/README.md`, "Aplicar uma mudança"), com o mesmo IP em
   `borg-offsite`.

   Confira: o save do console passa nos `tests`.

5. **Aplicar:**

   ```bash
   ansible-playbook playbooks/borg-offsite.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/borg-offsite.yml --ask-vault-pass
   ```

   Confira:

   ```bash
   ssh infra@<borg_offsite_ts_ip> 'findmnt /srv/borg; sudo sshd -T | grep -i allowusers'
   ```

   O `findmnt` mostra o disco em `/srv/borg`, e o `allowusers` só tem
   `infra` e `borg` com as faixas da tailnet.

6. **Clientes:** o Immich (`docs/immich.md`, "Backup") e o Nextcloud
   (`docs/nextcloud.md`, "Backup"). Cada um cria o próprio repositório na
   primeira vez; o diretório já existe vazio.

   O primeiro backup de cada um sobe tudo pela internet (o Immich tem
   ~30 GB). Antes, confira se o Pi fala direto com a máquina, e não por um
   relay da Tailscale (DERP), que é bem mais lento:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net tailscale ping <borg_offsite_ts_ip>
   ```

   Confira: a resposta diz `via <ip>:<porta>`; `via DERP` é relay.

## Backup

Os repositórios são o backup. A máquina em si não tem backup: reinstalada,
ela volta com os passos acima, e o disco só se formata no passo 3.

## Operação

- **Janela do backup:** a máquina precisa estar ligada, com internet e
  **sem suspender** das 02:30, quando começa o borgmatic do Pi, até o fim do
  backup diário do AIO. Noite com ela desligada é backup que não houve: o
  monitor *Backup Immich* cai em 26 h, e o AIO avisa a falha dele no
  Nextcloud.
- **Espaço:**

  ```bash
  ssh infra@<borg_offsite_ts_ip> df -h /srv/borg
  ```

- **Chave nova de cliente** (AIO reinstalado, chave do Pi trocada): o valor
  no vault e reaplicar o passo 5. O `authorized_keys` é o arquivo inteiro:
  chave que sai do vault sai do servidor.
- **Trocar de máquina:** os passos 1 a 5 na nova, o IP e o known_host novos
  no vault, e os repositórios copiados da antiga (`rsync -a` de
  `/srv/borg`) antes do próximo backup. Os clientes não mudam.

## Limitações

- **Uma cópia só fora de casa.** O Immich e o Nextcloud têm o original no
  Pi e o backup aqui; os outros serviços seguem no BorgBase.
- **A máquina fica com outra pessoa.** O Borg cifra no cliente, então o
  disco só tem texto cifrado; mas quem tem acesso físico pode apagá-lo.
- **Sem append-only.** Quem tem a chave do Pi pode apagar os archives do
  repositório dele (o prune precisa disso). O `--restrict-to-repository`
  protege um repositório do outro, não do próprio cliente.
- **Borg 1.x dos dois lados.** O Arch atualiza sozinho; se ele trocar o
  pacote `borg` pelo 2.x antes do Ubuntu do Pi, o `borg serve` deixa de
  falar com o cliente. `borg --version` nos dois antes de um `pacman -Syu`
  grande.
