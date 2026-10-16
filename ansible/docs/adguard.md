# AdGuard no Raspberry Pi

`playbooks/adguard.yml` sobe o AdGuard no Pi com o DNS publicado nos IPs do
próprio host e a interface web atrás do Caddy:

| O quê | Onde |
|---|---|
| DNS para a LAN (roteador) | `lan_ip:53` (hoje `192.168.50.187`), TCP/UDP |
| DNS para a tailnet | `ts_ip:53`, TCP/UDP |
| Interface web | `https://adguard.lab.nextlevelcode.pro` (Caddy → `ts_ip:8084`, rota em `caddy_lab_pi_routes`) |
| Dados | `/mnt/secure/appdata/adguard` (`adguard_data_dir`): `conf/` e `work/` |

O DNS escuta nos dois IPs e nunca em `0.0.0.0`: o `systemd-resolved` do host
ocupa `127.0.0.53`. O DHCP do AdGuard fica desligado: quem distribui IP é o
roteador. O upstream é o Quad9 por DoH (`https://dns.quad9.net/dns-query`),
configurado na interface do AdGuard, não no repo.

## Antes de aplicar

- **ACL** (`tailscale/policy.hujson`), já na política: dispositivos da tailnet
  → `tag:pi` em `udp:53` e `tcp:53`, e `tag:caddy` → `tag:pi:8084`. Sem isso,
  o DNS da tailnet não responde e a interface não abre pelo Caddy.
- **Reserva fixa do Pi no roteador.** O Pi pega IP por DHCP, e o DNS da LAN
  depende de o `lan_ip` não mudar (passo 6 da instalação).

## Instalação

1. **Testar no pi-lab** (sem config, o AdGuard sobe no assistente de
   instalação e não responde DNS; o teste é o container e as portas):

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit pi_staging
   ssh root@192.168.50.203 'docker logs adguardhome 2>&1 | tail -3; ss -lun | grep ":53 "'
   ```

   Confira: os logs mostram o assistente (`starting the initial setup`) e a
   53/udp escuta em `192.168.50.203`.

2. **Dados.** Com backup a trazer, restaure antes de aplicar
   (`docs/adguard-restore.md`): o AdGuard já sobe com a config, e o passo 4
   não se aplica.

3. **Aplicar no Pi:**

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi
   ```

   Confira, de um computador da tailnet (com a config já no lugar):

   ```bash
   dig +short @<ts_ip> nextlevelcode.pro
   dig +short @<ts_ip> doubleclick.net
   ```

   O primeiro devolve o IP; o segundo, `0.0.0.0` (bloqueado).

4. **Assistente, só em instância nova.** Sem config, o AdGuard serve o
   assistente na porta 3000 do container, que o compose não publica. Abra
   por um túnel SSH até o IP do container. É manual porque o assistente cria
   o usuário admin, e a senha não deve passar pelo repo.

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net \
     "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' adguardhome"
   ssh -L 3000:<ip-do-container>:3000 ubuntu@nextlevelcode.<tailnet>.ts.net
   ```

   Em `http://localhost:3000`: interface web na porta **80** e DNS na **53**,
   as duas em todas as interfaces (é a rede do container; quem limita aos
   IPs do host é o compose). Crie o admin e guarde a senha no Vaultwarden.
   Depois, em Settings → DNS settings, o upstream
   `https://dns.quad9.net/dns-query`.

   Confira: os dois `dig` do passo 3 respondem como lá.

5. **Caddy** (o do Proxmox e o reserva do Pi leem a mesma rota):

   ```bash
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass
   ```

   Confira: `https://adguard.lab.nextlevelcode.pro` abre o login do AdGuard, e
   o Query Log mostra as consultas de um dispositivo da tailnet.

6. **Roteador OpenWrt.** É à mão porque o Ansible não gerencia o roteador.

   Reserva fixa para o Pi, com o MAC dele
   (`ssh ubuntu@nextlevelcode cat /sys/class/net/eth0/address`), e o AdGuard
   como DNS da LAN (opção 6 do DHCP), para cada dispositivo consultar o
   AdGuard direto e aparecer com o próprio IP no Query Log. No roteador:

   ```bash
   uci add dhcp host
   uci set dhcp.@host[-1].name='nextlevelcode'
   uci set dhcp.@host[-1].mac='<MAC do Pi>'
   uci set dhcp.@host[-1].ip='192.168.50.187'
   uci add_list dhcp.lan.dhcp_option='6,192.168.50.187'
   uci commit dhcp
   /etc/init.d/dnsmasq restart
   ```

   Confira num dispositivo da LAN, depois de renovar o DHCP: o DNS dele é
   `192.168.50.187`, e `doubleclick.net` resolve para `0.0.0.0`.

7. **Nameservers da tailnet no console do Tailscale** (DNS → Nameservers),
   nesta ordem: o `ts_ip` do Pi (AdGuard), depois **Quad9** escolhido na lista
   de provedores do "Add nameserver" (entra como `9.9.9.9` e já traz os outros
   endereços do Quad9; o console recusa o `149.112.112.112` à parte). O Quad9
   é o mesmo upstream do AdGuard, então só um provedor vê as consultas, e com
   o Pi fora ele ainda bloqueia malware e phishing. É passo de console porque
   o DNS da tailnet não está na `policy.hujson`.

   O fallback não espera o AdGuard falhar: o Tailscale dispara para os
   nameservers com um pequeno atraso entre eles e fica com a primeira
   resposta. Se o AdGuard demora, a consulta sai pelo Quad9 sem bloqueio de
   anúncio. Domínio bloqueado que às vezes resolve é isso, não falha do
   AdGuard.

   Confira, num dispositivo da tailnet:

   ```bash
   tailscale dns status                          # AdGuard e Quad9 entre os resolvers
   dig +short @100.100.100.100 doubleclick.net   # 0.0.0.0: AdGuard respondendo
   curl -s https://on.quad9.net | grep -o "YES\|NO"   # YES: termina no Quad9
   ```

   O `on.quad9.net` diz YES tanto pelo AdGuard quanto pelo fallback, porque
   os dois caminhos terminam no Quad9. Ele prova que a Cloudflare saiu, não
   qual caminho a consulta fez.

8. **Primeiro backup:**

   ```bash
   ssh -t ubuntu@nextlevelcode sudo borgmatic -c /etc/borgmatic/adguard.yaml --verbosity 1 --stats
   ```

   Confira: o monitor *Backup AdGuard* fica verde no Uptime Kuma.

## Backup

Prefixo `adguard-*`, no borgmatic do Pi (`/etc/borgmatic/adguard.yaml`,
`docs/backup.md`). Leva `conf/` e `work/`, **sem** o `querylog.json` (o log
de todas as consultas DNS da casa: centenas de MB e o dado mais sensível).
**Não para o AdGuard**: parar o DNS derruba a rede da casa, a config é um
arquivo pequeno, e o `stats.db`, se sair inconsistente, só perde
estatística. Monitor *Backup AdGuard*. Restore: `docs/adguard-restore.md`.

## Operação

### Roteador novo ou faixa da LAN nova

O AdGuard escuta no `lan_ip`, lido dos fatos. Se esse IP muda, o DNS da LAN
para até reaplicar o playbook. A tailnet também perde o AdGuard: o container
publica a 53 nos dois IPs, e num restart ou reboot não sobe se um deles
sumir. Até reaplicar, a tailnet segue pelo fallback do Quad9.

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
   entregue pelo DHCP (opção 6; no OpenWrt, os comandos do passo 6 da
   instalação com o IP novo). Confira num dispositivo da LAN, depois de
   renovar o DHCP, que o DNS dele é o IP novo.

4. Atualize o valor de hoje do `lan_ip` neste doc (a tabela do começo e o
   passo 6 da instalação).

Os passos no roteador são à mão: cada roteador tem a sua interface, e este
repo não gerencia nenhum.

## Limitações

- **Pi fora, LAN sem DNS.** Com a opção 6, os dispositivos da LAN só conhecem
  o AdGuard. Para ter fallback, em vez da opção 6 deixe o dnsmasq do OpenWrt
  como DNS dos clientes e o AdGuard como servidor dele
  (`uci add_list dhcp.@dnsmasq[0].server='192.168.50.187'` mais um público
  como segundo). O custo é o AdGuard passar a ver só o IP do roteador nas
  consultas.
- **Config fora do repo.** Listas, regras, upstream e usuário vivem no
  `AdGuardHome.yaml`, editado pela interface. O backup é o que guarda isso.
