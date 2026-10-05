# AdGuard no Raspberry Pi

`playbooks/adguard.yml` sobe o AdGuard no Pi com o DNS publicado nos IPs do
próprio host e a interface web atrás do Caddy:

| O quê | Onde |
|---|---|
| DNS para a LAN (roteador) | `192.168.50.187:53` (TCP/UDP), o `lan_ip` do Pi |
| DNS para a tailnet | `<ts_ip>:53` (TCP/UDP), o `ts_ip` do Pi |
| Interface web | `https://adguard.lab.nextlevelcode.pro` (Caddy → `nextlevelcode:8084`) |

A config e os dados continuam em `/mnt/secure/appdata/adguard`. O DHCP do
AdGuard segue desligado: quem distribui IP é o roteador.

## Backup

Diário, no borgmatic do Pi (`/etc/borgmatic/adguard.yaml`, `docs/backup.md`),
prefixo `adguard-*` no repositório compartilhado.
Leva `conf/` e `work/`, **sem** o `querylog.json` (o log de todas as consultas DNS
da casa: centenas de MB e o dado mais sensível). Não para o AdGuard.

## Instalação

Faça os passos em sequência. Até o passo 4, a tailnet segue com o DNS que já
tinha.

1. **ACL do Tailscale** (console, antes de aplicar): os dispositivos da tailnet
   precisam alcançar o Pi em `udp:53` e `tcp:53`, e o `tag:caddy` em `tcp:8084`.
   Sem isso, o DNS da tailnet não responde e a interface web não abre pelo
   Caddy.

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

4. **Nameserver da tailnet no console do Tailscale** (DNS → Nameservers):
   `<ts_ip>` entra. Mantenha o fallback da Cloudflare. Confira num
   dispositivo da tailnet que a navegação segue.

5. **Caddy:**

   ```bash
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

   Confira: `https://adguard.lab.nextlevelcode.pro` abre o login do AdGuard, e
   o Query Log mostra as consultas de um dispositivo da tailnet. Antes deste
   passo a interface só existe em `<ts_ip>:8084`, que a ACL libera para o
   Caddy, não para os dispositivos.

6. **Primeiro backup:**

   ```bash
   ssh -t ubuntu@nextlevelcode sudo borgmatic -c /etc/borgmatic/adguard.yaml --verbosity 1 --stats
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

## Roteador novo ou faixa da LAN nova

O AdGuard escuta no IP da LAN do Pi (`lan_ip`, lido dos fatos), e não em
`0.0.0.0`. Se esse IP muda (roteador trocado, faixa nova), o DNS da LAN para
até reaplicar o playbook. A tailnet também perde o AdGuard: o container publica
a 53 nos dois IPs, e num restart ou reboot não sobe se um deles sumir. Até
reaplicar, a tailnet segue pelo fallback da Cloudflare.

1. **No roteador novo**, a reserva fixa do Pi (MAC de
   `cat /sys/class/net/eth0/address`) com um IP da faixa nova, e o nome
   `nextlevelcode` para ela. Reinicie a rede do Pi ou o Pi para ele pegar o IP.

   Confira: `ssh ubuntu@nextlevelcode.<tailnet>.ts.net ip -4 addr show eth0`
   mostra o IP reservado.

2. **Reaplicar o AdGuard**, que lê o IP novo dos fatos:

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi
   ```

   Confira: `dig +short @<IP novo> doubleclick.net` devolve `0.0.0.0`.

3. **DNS da LAN** no roteador novo: o IP novo do Pi como servidor DNS
   entregue pelo DHCP (opção 6; no OpenWrt, os comandos da seção acima com o
   IP novo). Confira num dispositivo da LAN, depois de renovar o DHCP, que o
   DNS dele é o IP novo.

4. Atualize o IP antigo neste doc (seção acima e a tabela do começo).

Os dois passos no roteador são à mão: cada roteador tem a sua interface, e
este repo não gerencia nenhum.
