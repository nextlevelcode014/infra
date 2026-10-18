# gluetun no Raspberry Pi

`playbooks/gluetun.yml` sobe o gateway VPN do Pi: um túnel WireGuard da
ProtonVPN, com killswitch, por onde saem o qBittorrent e o SearXNG. Os dois
rodam dentro da rede do gluetun (`network_mode: container:gluetun`), então as
portas deles são publicadas por ele.

| Porta | Para quê |
|---|---|
| `8090` | WebUI do qBittorrent |
| `6881` TCP/UDP | qBittorrent (peers e DHT) |
| `ts_ip:8082` | WebUI do SearXNG, só no IP Tailscale, para o Caddy |
| `8888` | proxy HTTP do gluetun |
| `8001` | control server do gluetun |

| O quê | Onde |
|---|---|
| Stack | `/opt/gluetun` (`gluetun_dir`): `compose.yml` e `.env` |
| Dependentes | `gluetun_dependents` (`group_vars/pi_hosts/vars.yml`): `qbittorrent`, `searxng-core` |

O compose filtra os servidores com `PORT_FORWARD_ONLY=on`: na Proton, só os
servidores P2P têm port forwarding, e os gratuitos pausam a conexão com
tráfego P2P, deixando os dependentes sem rede. O `arr-stack.yml` e o
`searxng.yml` já aplicam este role como dependência.

## Antes de aplicar

- **Config WireGuard da ProtonVPN**, no vault
  (`vault_gluetun_wireguard_private_key` e
  `vault_gluetun_wireguard_addresses`): em account.protonvpn.com → Downloads
  → WireGuard configuration, o `PrivateKey` e o `Address` do `[Interface]`.
  É manual porque a Proton não tem API para gerar a config.
- **Uma config por máquina.** A mesma chave em dois lugares derruba o túnel
  de um deles: o pi-lab usa a sua (`vault_gluetun_staging_*`), e o exit node
  também tem a dele (`docs/exit-node.md`).
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:pi:8082`, para o Caddy chegar ao SearXNG.

## Instalação

1. **Testar no pi-lab:**

   ```bash
   ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `ssh root@10.50.0.203 docker exec gluetun wget -qO- https://ipinfo.io/ip`
   mostra um IP da ProtonVPN, não o da sua casa.

2. **Aplicar no Pi:**

   ```bash
   ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit rpi
   ```

   Confira:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker exec gluetun wget -qO- https://ipinfo.io/ip
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker ps --filter name=gluetun --format '{{.Status}}'
   ```

   O IP é da ProtonVPN, e o status termina em `(healthy)`.

Os dependentes sobem com o playbook de cada um: `docs/arr-stack.md` e
`docs/searxng.md`.

## Backup

Nenhum: o gluetun não guarda dado. A config inteira vem do repo e do vault.

## Operação

- **Dependentes sem rede depois de recriar o gluetun.** O `network_mode:
  container:gluetun` vira o ID do container na criação. Recriado o gluetun
  (imagem nova, config nova), quem dependia dele aponta para um ID que não
  existe mais; reiniciar não resolve, só recriar. O role faz isso sozinho
  (`tasks/dependentes.yml`, que o `pi-atualizar.yml` também chama): compara
  os IDs e recria só quem ficou preso. Se acontecer fora do Ansible, reaplique:

  ```bash
  ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit rpi
  ```

  Confira: `docker exec qbittorrent curl -s https://ipinfo.io/ip` mostra o
  IP da Proton.

- **Trocar a config WireGuard** (chave revogada, outra conta): gere uma nova
  como em "Antes de aplicar", troque no vault e reaplique. O gluetun é
  recriado, e os dependentes junto.

- **Dependente novo** (outro serviço saindo pela VPN): o nome do container
  entra em `gluetun_dependents`, e a porta dele no `compose.yml` do gluetun
  (`roles/gluetun/files/compose.yml`).

## Limitações

- As portas `8090`, `6881`, `8888` e `8001` são publicadas em todas as
  interfaces, LAN incluída, não só no IP Tailscale (#43).
