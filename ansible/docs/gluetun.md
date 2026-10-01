# gluetun no Raspberry Pi

`playbooks/gluetun.yml` aplica o gateway VPN que antes subia por
`make up SVC=gluetun` no `self-hosted`. O compose é o mesmo
(`self-hosted/gluetun/compose.yml`) e passa a morar em `/opt/gluetun`. O nome do
projeto Compose continua `gluetun`, então o container atual é adotado.

Além das portas do compose original, publica `8082` (WebUI do SearXNG) só no
IP Tailscale, para o Caddy. O `arr-stack.yml` e o `searxng.yml` já o aplicam
como dependência. Quando o gluetun é recriado, o
role reinicia quem usa a netns dele (`qbittorrent`, `searxng-core`): sem isso
eles ficam sem rede.

## Primeira aplicação no Pi

1. Pôr no vault os valores que hoje estão em `/mnt/secure/env/gluetun.env` no
   Pi:

   ```bash
   ssh ubuntu@nextlevelcode cat /mnt/secure/env/gluetun.env
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   `WIREGUARD_PRIVATE_KEY` vai em `vault_gluetun_wireguard_private_key` e
   `WIREGUARD_ADDRESSES` em `vault_gluetun_wireguard_addresses`.

2. Ver o que muda e aplicar:

   ```bash
   ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit rpi
   ```

3. Conferir a saída pela VPN e a stack adotada:

   ```bash
   ssh ubuntu@nextlevelcode docker exec gluetun wget -qO- https://ipinfo.io/ip
   ssh ubuntu@nextlevelcode docker compose ls --filter name=gluetun
   ```

   O IP deve ser da ProtonVPN, e `CONFIG FILES` deve mostrar
   `/opt/gluetun/compose.yml`.

A partir daqui, não use mais `make up SVC=gluetun` no `self-hosted`. O SearXNG
continua lá e segue funcionando: ele só precisa do container `gluetun`.
