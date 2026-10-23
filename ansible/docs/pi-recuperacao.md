# Pi de recuperação: Forgejo e Vaultwarden

A produção do Forgejo e do Vaultwarden roda nos LXCs do Proxmox. O Pi fica
pronto para assumir se o Proxmox cair (ou for desligado de propósito, por
dias), com o Caddy reserva do Pi no lugar do Caddy do Proxmox, sem nunca rodar
os dois ao mesmo tempo que a produção: duas instâncias aceitando escrita
separam os dados.

`playbooks/pi-recuperacao.yml` deixa o Pi em **standby**:

- compose renderizado e imagens baixadas (o restore não depende de registry na
  hora do desastre);
- dados no LUKS (`/mnt/secure/appdata/forgejo` e `.../vaultwarden`);
- containers **parados** e **sem backup** (um archive do Pi com o mesmo
  prefixo viraria o mais recente para o restore);
- Vaultwarden na porta `8083` do IP Tailscale (a `8080` está ocupada no Pi).

Subir é sempre pelo restore, com o archive mais recente da produção. O restore
escolhe só archives feitos pela máquina de produção (`*_restore_source_host`):
o próprio Pi grava archives `vaultwarden-*` e `forgejo-*` no mesmo repositório
durante uma contingência, e sem o filtro o mais recente podia ser um deles.

## Preparar (uma vez)

1. **Aplicar o standby:** compose renderizado, imagens baixadas e os
   containers parados, sem backup:

   ```bash
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi
   ```

   Confira: `ssh ubuntu@nextlevelcode docker ps -a --filter name=forgejo --filter name=vaultwarden`
   não lista nada, e `ls /etc/borgmatic` não tem `forgejo.yaml` nem
   `vaultwarden.yaml`.

2. **Caddy reserva do Pi.** Fica sempre no ar, só no IP Tailscale do Pi, com
   o certificado do `*.lab` em dia; só recebe tráfego quando o DNS mandar.
   Precisa do `vault_caddy_pi_cloudflare_token` no vault (token próprio,
   Zone:DNS:Edit em `nextlevelcode.pro`):

   ```bash
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass --limit rpi
   ```

   Confira, sem mexer no DNS (força o nome para o IP do Pi):

   ```bash
   curl -sI --resolve jellyfin.lab.nextlevelcode.pro:443:$(tailscale ip -4 nextlevelcode) \
     https://jellyfin.lab.nextlevelcode.pro | head -1
   ```

   Tem que responder com certificado válido (sem `-k`).

## Assumir: o Pi no lugar do Proxmox

Com o Proxmox fora, não caem só o Forgejo e o Vaultwarden: o curinga `*.lab`
aponta para o Caddy do Proxmox, então todos os sites do Pi (jellyfin.lab,
immich.lab, nextcloud.lab...) ficam inacessíveis junto. Na contingência o
**Caddy reserva do Pi** assume o `*.lab` inteiro: basta o registro `*.lab` da
Cloudflare apontar para ele. O tráfego fica em casa, e a VPS segue só com o
que é público.

A variável `proxmox_fora` (`inventory/group_vars/all/vars.yml`) cuida do
resto:

| | `false` (normal) | `true` (contingência) |
|---|---|---|
| Forgejo e Vaultwarden no Pi | standby, sem backup | no ar, com backup às 02:30 |
| Anubis do `forge` e monitor do SSH do Git | `forgejo-lxc` | Pi |

Quem atende o `*.lab` não é variável, é o DNS: Caddy do Proxmox no normal,
Caddy reserva do Pi na contingência (passo 8).

Os backups do Pi avisam os mesmos monitores push (o token sai do nome do
serviço). O monitor **Proxmox (ping)** fica vermelho até o Proxmox voltar, e
ele está certo.

### Parada planejada: antes de desligar

Com o Proxmox ainda no ar. O objetivo é que o último backup dos LXCs tenha
tudo e que nada escreva neles depois.

1. **Merge de tudo que estiver aberto.** O remote dos repositórios é o
   Forgejo do LXC: o que não estiver nele antes do backup não chega ao Pi.

2. **Último backup** dos dois LXCs (pelo Ansible, porque o `~/.ssh/config`
   manda `forgejo-lxc` para a porta 2222 do Git):

   ```bash
   ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'systemctl start borgmatic.service'
   ```

   O comando só volta quando o backup termina. Confira: os monitores
   **Forgejo** e **Vaultwarden** do grupo Backups no Uptime Kuma receberam o
   aviso agora.

3. **Parar os LXCs de vez:** a stack e o timer do backup. Ao religar o
   Proxmox, os LXCs sobem sem serviço e sem gravar archive novo com os dados
   velhos:

   ```bash
   ansible forgejo --ask-vault-pass -m command -a 'docker compose -f /opt/forgejo/compose.yml down'
   ansible vaultwarden --ask-vault-pass -m command -a 'docker compose -f /opt/vaultwarden/compose.yml down'
   ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'systemctl disable --now borgmatic.timer'
   ```

   Confira: `ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'docker ps -q'`
   não lista nada.

Depois siga a lista abaixo a partir do passo 3 (o LUKS já está aberto). O
Proxmox pode ser desligado no fim.

### No desastre, ou depois dos passos acima

1. Confirmar que o Forgejo e o Vaultwarden do Proxmox estão fora (ou parados,
   na parada planejada). Nunca com a produção no ar.
2. Destravar o LUKS, se o Pi reiniciou: `ssh -t ubuntu@nextlevelcode secure-unlock`.
3. **Restaurar e subir** cada serviço com o archive mais recente dos LXCs:

   ```bash
   ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
     --limit rpi -e restore_on_pi=true -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
   ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
     --limit rpi -e restore_on_pi=true -e forgejo_restore_confirmation=RESTORE_FORGEJO
   ```

   O nome da task "Extrair o archive ..." mostra o archive escolhido. A data
   tem que ser a do último backup (o do passo 2 acima, na parada planejada).

4. **Ligar a contingência no repo:** `proxmox_fora: true` em
   `inventory/group_vars/all/vars.yml`, numa branch. O PR vai para o Forgejo
   do Pi depois do passo 9, e serve de teste do push.

5. **Backup do Pi** para os dois serviços:

   ```bash
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi
   ```

   Confira: `ssh ubuntu@nextlevelcode.<tailnet>.ts.net ls /etc/borgmatic` lista
   `forgejo.yaml` e `vaultwarden.yaml`, e
   `ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker ps --filter name=forgejo --filter name=vaultwarden`
   mostra `forgejo`, `forgejo-db` e `vaultwarden` rodando.

6. **ACL do Tailscale:** no `tailscale/policy.hujson`, descomente os dois
   blocos `CONTINGÊNCIA` e tire `tag:pi:3000` do `deny` do teste de
   `tag:caddy-vps`. Cole **o arquivo inteiro do repo** por cima do console
   (`tailscale/README.md`), em vez de descomentar lá. E commite na mesma
   branch do passo 4. Sem isso o Anubis da VPS não alcança o Forgejo do Pi, e
   o `forge` dá 502. Um `want: Drop, got: Accept` no save é o `deny` do teste
   que ficou. O `*.lab` não depende disto: o grant de `tcp:443` no Pi é fixo.

7. **VPS**: o Anubis do `forge` passa a apontar para o Forgejo do Pi, e o
   monitor do SSH do Git também:

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Confira: `curl -s https://forge.nextlevelcode.pro/api/healthz` devolve
   `"status": "pass"`.

8. **Cloudflare** (zona `nextlevelcode.pro`, DNS only): **anote o valor
   atual** do registro `*.lab` (o IP Tailscale do Caddy do Proxmox, que volta
   no fim) e troque pelo IP Tailscale do Pi:

   ```bash
   tailscale ip -4 nextlevelcode
   ```

   Confira, depois de uns minutos (TTL):
   `dig +short vault.lab.nextlevelcode.pro` devolve o IP do Pi,
   `curl -s https://vault.lab.nextlevelcode.pro/alive` responde, e
   `https://jellyfin.lab.nextlevelcode.pro` abre. É à mão porque este repo
   não gerencia registros da Cloudflare (a VPS nova também é assim,
   `docs/vps.md`).

9. **Remote do Git:** no `~/.ssh/config`, o bloco do Forgejo fica assim (só a
   linha `HostName` muda, e entra a `HostKeyAlias`; a linha `Host` fica igual):

   ```
   Host forgejo forgejo-lxc
       HostName nextlevelcode.<tailnet>.ts.net
       HostKeyAlias [forgejo-lxc]:2222
       Port 2222
       ...
   ```

   O `HostKeyAlias` confere a chave contra a entrada que o `known_hosts` já
   tem do LXC: a chave é a mesma, porque veio no restore. Trocar a linha
   `Host` em vez da `HostName` manda **todo** ssh para o Pi (inclusive o do
   Ansible) para o `git@forgejo-lxc:2222`. Os remotes continuam iguais.

   Confira: `git ls-remote origin` neste repo lista as branches.

10. Desligar o Proxmox (parada planejada):
    `ssh root@<proxmox_host> poweroff`.

**Enquanto o Pi for a produção, `proxmox_fora` fica `true`.** Rodar o
`pi-recuperacao.yml` com ela em `false` derruba o Forgejo e o Vaultwarden do
Pi.

## Voltar ao Proxmox

O caminho inverso: o último backup do Pi vira os dados dos LXCs. Os restores
dos LXCs filtram por máquina de origem (`forgejo`, `vaultwarden`), então aqui
eles recebem a do Pi (`ubuntu`) e o caminho que os dados têm no archive dele.

Do passo 4 ao 9 o remote do Git não responde: o Forgejo do Pi está parado e
o `~/.ssh/config` ainda manda para ele. A branch do passo 6 pode ir para o
Forgejo do Pi antes do passo 4 (ela volta com o restore); feita depois, o
push espera o passo 9. O merge dela fica para o fim, no passo 10: com
`proxmox_fora: false` no `main`, o `pi-recuperacao.yml` derruba o Forgejo e o
Vaultwarden do Pi enquanto ele ainda é a produção.

1. **Proxmox ligado**, com os LXCs sem serviço (parados no passo 3 da parada
   planejada). Confira: `ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'docker ps -q'`
   não lista nada, e `tailscale status` mostra `caddy-lxc`, `forgejo-lxc` e
   `vaultwarden-lxc` online. Depois de um desastre eles sobem com os dados
   velhos: pare a stack deles como no passo 3 antes de seguir.

2. **Caddy do Proxmox em dia.** Enquanto o `*.lab` apontou para o Pi, o
   Caddy do Proxmox ficou sem receber o que mudou no repo (token da
   Cloudflare, rotas novas do Pi) e pode estar com o certificado vencido.
   Ele volta a atender no passo 8:

   ```bash
   ansible-playbook playbooks/caddy.yml --ask-vault-pass --limit caddy --check --diff
   ansible-playbook playbooks/caddy.yml --ask-vault-pass --limit caddy
   ```

   Confira, sem mexer no DNS (força o nome para o IP do Caddy do Proxmox):

   ```bash
   curl -sI --resolve jellyfin.lab.nextlevelcode.pro:443:$(tailscale ip -4 caddy-lxc) \
     https://jellyfin.lab.nextlevelcode.pro | head -1
   ```

   Tem que responder com certificado válido (sem `-k`).

3. **Standby nos LXCs:** compose atual e imagens baixadas, containers parados
   e sem backup. O restore sobe a stack pelo `compose.yml` que já está no LXC,
   e o dele é de antes da contingência: com uma imagem mais velha que a do
   Pi, o Forgejo ou o Vaultwarden abre um banco que já passou por migrations
   que ele não conhece. Com o Pi ainda no ar, o pull não conta como parada:

   ```bash
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass -e forgejo_standby=true --check --diff
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass -e forgejo_standby=true
   ansible-playbook playbooks/vaultwarden.yml --ask-vault-pass -e vaultwarden_standby=true --check --diff
   ansible-playbook playbooks/vaultwarden.yml --ask-vault-pass -e vaultwarden_standby=true
   ```

   Confira: `ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'docker ps -q'`
   continua sem nada, e
   `ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'ls /etc/borgmatic'`
   não lista `forgejo.yaml` nem `vaultwarden.yaml`.

4. **Último backup do Pi** e parar os dois, para nada escrever depois dele:

   ```bash
   ansible rpi --ask-vault-pass -m command -a 'borgmatic -c /etc/borgmatic/forgejo.yaml --verbosity 1 --stats'
   ansible rpi --ask-vault-pass -m command -a 'borgmatic -c /etc/borgmatic/vaultwarden.yaml --verbosity 1 --stats'
   ansible rpi --ask-vault-pass -m command -a 'docker compose -f /mnt/secure/appdata/forgejo/compose.yml down'
   ansible rpi --ask-vault-pass -m command -a 'docker compose -f /mnt/secure/appdata/vaultwarden/compose.yml down'
   ```

5. **Restaurar nos LXCs** a partir do archive do Pi:

   ```bash
   ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
     -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN \
     -e vaultwarden_restore_source_host=ubuntu \
     -e vaultwarden_restore_data_archive_path=mnt/secure/appdata/vaultwarden/vw-data
   ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
     -e forgejo_restore_confirmation=RESTORE_FORGEJO \
     -e forgejo_restore_source_host=ubuntu \
     -e forgejo_restore_data_archive_path=mnt/secure/appdata/forgejo/forgejo
   ```

   Confira na task "Extrair o archive ..." que a data é a do passo 4.

6. **Desligar a contingência no repo**, numa branch: `proxmox_fora: false` e
   os blocos `CONTINGÊNCIA` do `policy.hujson` comentados de novo, com
   `tag:pi:3000` de volta no `deny` do teste de `tag:caddy-vps`. Cole **o
   arquivo inteiro do repo** por cima do console (`tailscale/README.md`).
   Confira: o save passa nos testes (um `want: Drop, got: Accept` é o `deny`
   que faltou voltar).

7. **Reaplicar**, nesta ordem:

   ```bash
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass
   ansible-playbook playbooks/vaultwarden.yml --ask-vault-pass
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Os dois primeiros tiram os LXCs do standby e religam o backup deles; o
   `pi-recuperacao.yml` devolve o Pi ao standby e tira o backup dele.
   Confira: `ansible forgejo,vaultwarden --ask-vault-pass -m command -a 'systemctl is-active borgmatic.timer'`
   responde `active`, `ls /etc/borgmatic` no Pi não tem mais `forgejo.yaml`
   nem `vaultwarden.yaml`, e `curl -s https://forge.nextlevelcode.pro/api/healthz`
   devolve `"status": "pass"`.

8. **Cloudflare:** `*.lab` de volta para o IP anotado no passo 8 da ida (o
   de `tailscale ip -4 caddy-lxc`).
   Confira, depois de uns minutos (TTL): `dig +short vault.lab.nextlevelcode.pro`
   devolve esse IP e `curl -s https://vault.lab.nextlevelcode.pro/alive`
   responde.

9. **Remote do Git:** `HostName forgejo-lxc` de volta no `~/.ssh/config`, e
   a linha `HostKeyAlias` sai.
   Confira: `git ls-remote origin` lista as branches, com a do passo 6 se
   ela foi antes do passo 4. Se não foi, o push e o PR dela vão agora, e são
   o teste do Forgejo do LXC.

10. Confira o conjunto: `vault.lab` mostra o que foi salvo durante a
    contingência, o `forge` tem os commits feitos no Pi (o PR do passo 4 da
    ida), e o Uptime Kuma fica todo verde. Depois disso, o merge do PR do
    passo 6.

## Ensaio no pi-lab

Restaura os archives reais da produção no pi-lab, que não tem LUKS de verdade:
os repositórios e o cofre ficam num volume sem criptografia. Limpe no fim.

```bash
ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,pi_staging
ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit pi_staging
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass --limit pi_staging \
  -e restore_on_pi=true -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass --limit pi_staging \
  -e restore_on_pi=true -e forgejo_restore_confirmation=RESTORE_FORGEJO
```

Confira:

- Vaultwarden: `ssh root@10.50.0.203 wget -qO- http://10.50.0.203:8083/alive`
  devolve uma data, e `.../api/config` no lugar do `/alive` mostra que o
  servidor está de pé;
- Forgejo: `http://localhost:3000` (pelo túnel, `docs/pi.md`, "pi-lab") lista os repositórios, com o `main` do
  `ansible` igual ao da produção.

Anote a duração de cada restore. Para limpar:

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```

Derruba todas as stacks, apaga os dados restaurados e tira a chave e a senha
do Borg do pi-lab. A base (Docker, redes, imagens) fica, para o próximo ensaio.
