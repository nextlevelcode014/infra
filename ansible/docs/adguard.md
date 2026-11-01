# AdGuard no Raspberry Pi

`playbooks/adguard.yml` sobe o AdGuard no Pi com o DNS publicado nos IPs do
próprio host e a interface web atrás do Caddy:

| O quê | Onde |
|---|---|
| DNS para a LAN (roteador) | `lan_ip:53` (hoje `192.168.18.99`), TCP/UDP |
| DNS para a tailnet | `ts_ip:53`, TCP/UDP |
| Interface web | `https://adguard.lab.nextlevelcode.pro` (Caddy → `ts_ip:8084`, rota em `caddy_lab_pi_routes`) |
| Dados | `/mnt/secure/appdata/adguard` (`adguard_data_dir`): `conf/` e `work/` |

O DNS escuta nos dois IPs e nunca em `0.0.0.0`: o `systemd-resolved` do host
ocupa `127.0.0.53`. O DHCP do AdGuard fica desligado: quem distribui IP é o
roteador. O DNS é declarado em `roles/adguard_dns/defaults/main.yml` e aplicado pelo
Ansible no deploy e no restore:

| Variável | Padrão |
|---|---|
| `adguard_dns_upstreams` | Quad9 e Mullvad por DoH |
| `adguard_dns_bootstrap` | Quad9 (`9.9.9.10`, `149.112.112.10`) e Cloudflare (`1.1.1.1`, `1.0.0.1`) |
| `adguard_dns_mode` | `parallel` |

Em `parallel`, as consultas que chegam aos upstreams vão aos dois provedores;
o primeiro a responder atende. Isso aumenta a exposição das consultas aos
dois provedores, uma escolha aceita para reduzir a espera quando um falha.
O bootstrap resolve os nomes dos servidores DoH por DNS comum: precisa de
provedores independentes também. Os endereços IPv4 bastam para estabelecer
DoH; consultas AAAA continuam funcionando.

O role mescla somente `dns.upstream_dns`, `dns.bootstrap_dns` e
`dns.upstream_mode` no `AdGuardHome.yaml`. Preserva usuários, filtros, regras
e as demais opções, mas a serialização pode mudar a formatação do YAML.
Se houver diferença, para o container, relê o arquivo após a parada, grava
sem exibir conteúdo no diff e religa se ele estava rodando. Sem diferença,
não reinicia. `--check --diff` só informa a necessidade de mudança.
`upstream_dns_file` precisa estar vazio: o role recusa uma fonte externa
que teria precedência sobre a lista declarada. Decisão: ADR 0022.

## Antes de aplicar

- **ACL** (`tailscale/policy.hujson`), já na política: membros e `tag:vps`
  → `tag:pi` em `udp:53` e `tcp:53`, e `tag:caddy` → `tag:pi:8084`. Sem isso,
  o DNS da tailnet não responde e a interface não abre pelo Caddy.
- **Reserva fixa do Pi no roteador.** O Pi pega IP por DHCP, e o DNS da LAN
  depende de o `lan_ip` não mudar (passo 6 da instalação).

## Instalação

1. **Testar no pi-lab** (sem config, o AdGuard sobe no assistente de
   instalação e não responde DNS; o teste é o container e as portas):

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit pi_staging
   ssh root@10.50.0.203 'docker logs adguardhome 2>&1 | tail -3; ss -lun | grep ":53 "'
   ```

   Confira: os logs mostram o assistente (`starting the initial setup`) e a
   53/udp escuta em `10.50.0.203`.

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
   Depois do assistente, reaplique os valores declarados:

   ```bash
   ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi
   ```

   O assistente inicial continua manual porque cria a credencial de admin.
   Upstreams, bootstrap e modo passam a ser gerenciados pelo Ansible.

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
   uci set dhcp.@host[-1].ip='192.168.18.99'
   uci add_list dhcp.lan.dhcp_option='6,192.168.18.99'
   uci commit dhcp
   /etc/init.d/dnsmasq restart
   ```

   Confira num dispositivo da LAN, depois de renovar o DHCP: o DNS dele é
   `192.168.18.99`, e `doubleclick.net` resolve para `0.0.0.0`.

7. **Nameservers da tailnet no console do Tailscale** (DNS → Nameservers):
   AdGuard (`ts_ip` do Pi) e Cloudflare como reserva global, conforme o
   paliativo registrado na issue #66. O DNS da tailnet não está na
   `policy.hujson`, por isso este passo ainda é manual.

   Os LXCs com `tag:caddy` e `tag:proxmox-lxc` não têm acesso à porta 53 do
   Pi pela ACL atual; dependem da reserva. A autonomia do DNS dos LXCs é
   tratada na #66. A reserva pública não oferece os filtros locais do AdGuard.

   Confira num dispositivo da tailnet:

   ```bash
   tailscale dns status
   dig +short @<ts_ip> doubleclick.net
   ```

   O status deve mostrar AdGuard e Cloudflare; a consulta direta ao Pi deve
   devolver `0.0.0.0` se a regra de bloqueio estiver ativa.

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

### Conferir DNS após aplicar ou restaurar

```bash
dig @192.168.18.99 nextlevelcode.pro +short
ssh ubuntu@nextlevelcode 'docker logs --since 5m adguardhome 2>&1 | tail -30'
```

Confira: a consulta responde e não há falhas contínuas de resolução. Um
upstream bloqueado ainda pode gerar `exchange failed` em `parallel`; isso
isoladamente não indica indisponibilidade se o outro atende. Não publique
logs brutos: podem conter nomes consultados.

Para conferir só as opções gerenciadas, sem expor usuários ou outras opções:

```bash
ssh ubuntu@nextlevelcode sudo cat /mnt/secure/appdata/adguard/conf/AdGuardHome.yaml | \
  awk '/^[[:space:]]+(upstream_dns|bootstrap_dns|upstream_mode):/ {mostrar=1; print; next} mostrar && /^[[:space:]]+- / {print; next} {mostrar=0}'
```

Confira: Quad9 e Mullvad, bootstrap Quad9 e Cloudflare e modo `parallel`.
Reaplique o playbook: as tasks DNS não devem mudar nem parar o container.

### Atualizar

Versão exata em `adguard_image` (projeto `0.x`, e ele migra o
`AdGuardHome.yaml` ao subir): o `pi-atualizar.yml` não muda essa imagem.
Para subir, leia as notas da versão, troque a variável e reaplique o
`adguard.yml`. O DNS da casa cai por alguns segundos enquanto o container
é recriado.

### Roteador novo ou faixa da LAN nova

O AdGuard escuta no `lan_ip`, lido dos fatos. Se esse IP muda, o DNS da LAN
para até reaplicar o playbook. A tailnet também perde o AdGuard: o container
publica a 53 nos dois IPs, e num restart ou reboot não sobe se um deles
sumir. Até reaplicar, a tailnet segue pela reserva pública da tailnet.

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
  (`uci add_list dhcp.@dnsmasq[0].server='192.168.18.99'` mais um público
  como segundo). O custo é o AdGuard passar a ver só o IP do roteador nas
  consultas.
- **Configuração parcialmente declarada.** Upstreams, bootstrap e modo vivem
  no código. Listas, regras e usuários ainda dependem do backup do
  `AdGuardHome.yaml`; esta mudança não automatiza o assistente inicial.
