# Nextcloud AIO no Raspberry Pi

`playbooks/nextcloud.yml` aplica o que antes subia por `make up SVC=nextcloud`
no `self-hosted`:

- o **mastercontainer** do AIO (`/opt/nextcloud-aio`). Os outros containers
  (`nextcloud-aio-nextcloud`, `-database`, `-talk`, `-collabora`…) são criados
  e geridos pelo próprio AIO, não pelo Ansible;
- o **coturn** do Talk (`/opt/coturn-turn`), com o segredo vindo do vault;
- o **`tailscale serve` do host**: fica só a interface do AIO em
  `https://nextlevelcode.<tailnet>.ts.net:8080` (só tailnet).

O Nextcloud passa a ser `https://nextcloud.lab.nextlevelcode.pro`, pelo Caddy do
Proxmox. Para isso o Apache do AIO escuta na 11000 do IP Tailscale do Pi
(`APACHE_IP_BINDING`), e não mais em `127.0.0.1` atrás do serve do host.

Fica como estava: o backup do AIO (Borg embutido, configurado na interface do
AIO) e os dados (110 GB em `/mnt/secure/appdata/nextcloud/ncdata`).

## Migração para nextcloud.lab

A troca de domínio é o procedimento oficial do AIO: parar os containers pela
interface, editar o domínio na `configuration.json` e subir de novo. O
Nextcloud fica fora do ar entre o passo 4 e o passo 6.

1. **Vault.** O segredo do coturn está hoje no Pi:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net sudo grep '^TURN_SECRET=' /mnt/secure/env/nextcloud.env
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   O valor vai em `vault_nextcloud_turn_secret`.

2. **ACL do Tailscale** (console):

   | De | Para | Portas | Para quê |
   |---|---|---|---|
   | `tag:caddy` | Pi | `tcp:11000` | o Caddy chegar no Apache do AIO |
   | Pi | `tag:caddy` | `tcp:443` | o Nextcloud testar o próprio HPB pelo domínio |
   | `autogroup:member` | Pi | `udp:3479`, `tcp:3479`, `udp:49160-49200` | o Talk chegar no coturn (TURN/STUN e relay) |
   | dispositivos de admin | Pi | `tcp:8080` | a interface do AIO |

   O intervalo de relay tem que ser o mesmo de `nextcloud_turn_min_port` /
   `nextcloud_turn_max_port`. Mudando um, mude o outro: a ACL primeiro, depois
   o coturn, para nenhuma chamada cair no meio.

3. **Aplicar o role e o Caddy.** O mastercontainer é recriado (o Nextcloud
   continua no ar), o serve perde as sobras 8000 e 9080 e mantém a 443:

   ```bash
   ansible-playbook playbooks/nextcloud.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/nextcloud.yml --ask-vault-pass
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

4. **Parar os containers** na interface do AIO
   (`https://nextlevelcode.<tailnet>.ts.net:8080` → *Stop containers*).

5. **Trocar o domínio.** Abre a `configuration.json` no editor:

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net 'sudo docker run -it --rm --volume nextcloud_aio_mastercontainer:/mnt/docker-aio-config:rw alpine sh -c "apk add --no-cache nano && nano /mnt/docker-aio-config/data/configuration.json"'
   ```

   Troque `"domain":"nextlevelcode.<tailnet>.ts.net"` por
   `"domain":"nextcloud.lab.nextlevelcode.pro"` e salve.

6. **Subir os containers** na interface do AIO (*Start containers*). Agora o
   Apache sobe em `<ts_ip>:11000` com o domínio novo.

   Confira:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker port nextcloud-aio-apache
   curl -s https://nextcloud.lab.nextlevelcode.pro/status.php
   ```

   O primeiro mostra `<ts_ip>:11000`; o segundo, um JSON com
   `"installed":true`. No navegador: login, um arquivo, uma chamada de teste no
   Talk e um documento no Collabora. Em *Administração → Visão geral*, nenhum
   aviso de proxy reverso ou de domínio.

7. **Tirar a 443 do serve do host.** O role só faz isso depois que o AIO já
   está no domínio novo:

   ```bash
   ansible-playbook playbooks/nextcloud.yml --ask-vault-pass
   ```

   Confira: `ssh ubuntu@nextlevelcode.<tailnet>.ts.net sudo tailscale serve status`
   lista só a 8080.

8. **Talk.** Com o domínio novo, o AIO cadastra TURN e STUN em
   `nextcloud.lab.nextlevelcode.pro:3478`, que aponta para o Caddy e não
   funciona (o Caddy só encaminha HTTPS). Em *Administração → Talk*, deixe só
   o coturn: STUN `<ts_ip>:3479` e TURN `<ts_ip>:3479` (UDP e TCP),
   com o segredo do `vault_nextcloud_turn_secret`. O ❗ ao lado do TURN e o
   aviso do HPB somem quando a ACL do passo 2 está certa.

9. **Reconectar os clientes** (desktop, celular): adicionar a conta de novo com
   `https://nextcloud.lab.nextlevelcode.pro`. Os apps do Nextcloud não migram a
   URL sozinhos.

### Se algo der errado

- **Antes do passo 6** (containers parados, domínio já editado): volte o
  `domain` para `nextlevelcode.<tailnet>.ts.net` e suba os containers. Tudo
  volta como era.
- **Depois do passo 6**, o Apache escuta só em `<ts_ip>:11000`, e a 443 do
  serve (que aponta para `127.0.0.1:11000`) não chega mais nele. Para voltar:
  pare os containers, volte o `domain`, aplique o role com
  `-e nextcloud_apache_ip_binding=127.0.0.1` e suba os containers pela
  interface.

A partir daqui, não use mais `make up SVC=nextcloud` no `self-hosted`.
