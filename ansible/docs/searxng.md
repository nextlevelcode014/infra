# SearXNG no Raspberry Pi

`playbooks/searxng.yml` sobe o SearXNG no Pi, saindo pela VPN: o
`searxng-core` vive na rede do gluetun (`docs/gluetun.md`), que publica a
WebUI na porta `8082` do IP Tailscale.

| O quê | Onde |
|---|---|
| Interface | `https://searxng.lab.nextlevelcode.pro` (Caddy → `ts_ip:8082`, rota em `caddy_lab_pi_routes`) |
| Config | `/mnt/secure/appdata/searxng/core-config` (`searxng_config_dir`): o `settings.yml` renderizado |
| Stack | `/opt/searxng`: `searxng-core` (na rede do gluetun) e `searxng-valkey` (cache, na `vpn_net`) |

O `settings.yml` sai de `roles/searxng/templates/settings.yml.j2`: engines
ligadas e desligadas, timeouts e o `secret_key`, que vem do vault. Mudar uma
engine é editar o template e reaplicar.

## Antes de aplicar

- **Vault:** `vault_searxng_secret_key` (`openssl rand -hex 32`). Ele assina
  os cookies das preferências: trocar desloga todos os navegadores.
- **gluetun** com a config WireGuard (`docs/gluetun.md`, "Antes de aplicar").
  O `searxng.yml` aplica o role do gluetun como dependência.
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:pi:8082`. Sem ele, o Caddy dá timeout sem erro nenhum no SearXNG.

## Instalação

1. **Testar no pi-lab:**

   ```bash
   ansible-playbook playbooks/searxng.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `ssh root@10.50.0.203 'wget -S -O /dev/null http://10.50.0.203:8082/ 2>&1 | grep HTTP/'`
   mostra `HTTP/1.1 200 OK`.

2. **Aplicar no Pi e no Caddy** (o do Proxmox e o reserva do Pi leem a mesma
   rota):

   ```bash
   ansible-playbook playbooks/searxng.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/searxng.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass
   ```

   Confira: `curl -s -o /dev/null -w '%{http_code}\n' https://searxng.lab.nextlevelcode.pro/`
   devolve `200`, e uma busca traz resultados.

3. **Monitor:** o *SearXNG* já está em `group_vars/vps/monitors.yml`.

   Confira: fica verde no Uptime Kuma.

## Backup

Nenhum: a config inteira vem do repo e do vault, e o Valkey é só cache. As
preferências de cada pessoa ficam no cookie do navegador.

## Operação

- **Engine falhando** (busca pela metade, "timeout" ou "unexpected crash"
  numa engine): veja as estatísticas que o próprio SearXNG mantém, desde o
  último restart:

  ```bash
  ssh ubuntu@nextlevelcode.<tailnet>.ts.net 'curl -s "http://$(tailscale ip -4):8082/stats/errors"'
  ```

  Ou `https://searxng.lab.nextlevelcode.pro/stats` no navegador, com tempo de
  resposta e confiabilidade por engine. O log do container quase não registra
  timeout. Engine que falha sempre sai no `settings.yml.j2` (`disabled:
  true`, com um comentário do porquê), como o Brave e o Pinterest, que pela
  VPN são bloqueados ou têm o parser quebrado.

- **Sem rede depois de recriar o gluetun:** o role do gluetun recria o
  `searxng-core` sozinho (`docs/gluetun.md`, "Operação").

- **Atualizar:** a imagem é `latest` e o `pi-atualizar.yml` a puxa. Engine
  que volta a funcionar depois de uma atualização pode ser religada.

## Limitações

- Tudo sai pelo IP da ProtonVPN, compartilhado e conhecido: buscadores
  grandes bloqueiam ou pedem captcha com frequência, e por isso o Google está
  desligado.
