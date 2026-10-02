# AdGuard no Raspberry Pi

`playbooks/adguard.yml` aplica o AdGuard que antes subia por `make up
SVC=adguard` no `self-hosted`, **sem o sidecar Tailscale**:

| O quê | Onde |
|---|---|
| DNS para a LAN (roteador) | `192.168.50.187:53` (TCP/UDP), o `lan_ip` do Pi |
| DNS para a tailnet | `<ts_ip>:53` (TCP/UDP), o `ts_ip` do Pi |
| Interface web | `https://adguard.lab.nextlevelcode.pro` (Caddy → `nextlevelcode:8084`) |

A config e os dados continuam em `/mnt/secure/appdata/adguard`. O DHCP do
AdGuard segue desligado: quem distribui IP é o roteador.

## Backup

Diário às 02:45, `/usr/local/bin/backup-adguard.sh`, log em
`/var/log/adguard_backup.log`, prefixo `adguard-*` no repositório compartilhado.
Leva `conf/` e `work/`, **sem** o `querylog.json` (o log de todas as consultas DNS
da casa: centenas de MB e o dado mais sensível). Não para o AdGuard.

## Aplicação

Ao aplicar no Pi, o sidecar sai e o IP do DNS da tailnet muda de
`<ip-tailscale-do-adguard-antigo>` (nó `adguard`) para `<ts_ip>` (o Pi). Entre a aplicação e a
troca no console, a tailnet usa o fallback (Cloudflare). Faça os passos em
sequência.

1. **ACL do Tailscale** (console, antes de aplicar): os dispositivos da tailnet
   precisam alcançar o Pi em `udp:53` e `tcp:53`, e o `tag:caddy` em `tcp:8084`.
   Sem isso, o DNS da tailnet não volta depois da troca.

2. **Testar no pi-lab** (sem config, o AdGuard sobe no assistente de
   instalação e não responde DNS; o teste é o container e as portas):

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit pi_staging
   ssh root@192.168.50.203 'docker logs adguardhome 2>&1 | tail -3; ss -lun | grep ":53 "'
   ```

   Os logs devem mostrar o assistente (`starting the initial setup`) e a 53/udp
   escutando em `192.168.50.203`.

3. **Aplicar no Pi:**

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi
   ```

   Confira, de um computador da tailnet:

   ```bash
   dig +short @<ts_ip> nextlevelcode.pro
   dig +short @<ts_ip> doubleclick.net
   ```

   O primeiro devolve o IP; o segundo, `0.0.0.0` (bloqueado).

4. **Trocar o nameserver no console do Tailscale** (DNS → Nameservers):
   `<ip-tailscale-do-adguard-antigo>` sai, `<ts_ip>` entra. Mantenha o fallback da Cloudflare.
   Confira num dispositivo da tailnet que a navegação segue e que o AdGuard
   registra as consultas (interface web → Query Log).

5. **Caddy:**

   ```bash
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

   Confira: `https://adguard.lab.nextlevelcode.pro` abre o login do AdGuard.

6. **Remover o nó `adguard`** no console do Tailscale (Machines → `adguard` →
   Remove).

7. **Primeiro backup:**

   ```bash
   ssh -t ubuntu@nextlevelcode sudo /usr/local/bin/backup-adguard.sh
   ```

## Roteador OpenWrt

Feito no roteador, porque o Ansible não gerencia o OpenWrt.

1. **Reserva fixa para o Pi.** O Pi pega IP por DHCP (`netplan`, `dhcp4: true`).
   Sem reserva, o IP pode mudar e a LAN fica sem DNS. Pegue o MAC do Pi:

   ```bash
   ssh ubuntu@nextlevelcode cat /sys/class/net/eth0/address
   ```

   No OpenWrt (SSH no roteador):

   ```bash
   uci add dhcp host
   uci set dhcp.@host[-1].name='nextlevelcode'
   uci set dhcp.@host[-1].mac='<MAC do Pi>'
   uci set dhcp.@host[-1].ip='192.168.50.187'
   uci commit dhcp
   ```

2. **Entregar o AdGuard como DNS para a LAN** (opção 6 do DHCP). Assim cada
   dispositivo consulta o AdGuard direto, e o AdGuard vê o IP de cada um:

   ```bash
   uci add_list dhcp.lan.dhcp_option='6,192.168.50.187'
   uci commit dhcp
   /etc/init.d/dnsmasq restart
   ```

   Confira num dispositivo da LAN, depois de renovar o DHCP: o DNS dele é
   `192.168.50.187`, e `doubleclick.net` resolve para `0.0.0.0`.

Se o Pi cair, a LAN fica sem DNS. Para ter fallback, em vez da opção 6 deixe o
dnsmasq do OpenWrt como DNS dos clientes e o AdGuard como servidor dele
(`uci add_list dhcp.@dnsmasq[0].server='192.168.50.187'` mais um público como
segundo). O custo é o AdGuard passar a ver só o IP do roteador nas consultas.

A partir daqui, não use mais `make up SVC=adguard` no `self-hosted`.
