# Caddy

Três Caddys, todos do role `caddy`: binário custom com o plugin DNS-01 da
Cloudflare, Caddyfile do host e um drop-in do systemd.

| Caddy | Playbook | Atende | Token no vault |
|---|---|---|---|
| Proxmox (`caddy-lxc`) | `playbooks/caddy.yml` | `*.lab` | `vault_caddy_cloudflare_token` |
| VPS (`hetzner`) | `playbooks/caddy-vps.yml` | domínios públicos e `*.lab` que moram na VPS | `vault_caddy_vps_cloudflare_token` |
| Pi (reserva) | `playbooks/caddy-pi.yml` | `*.lab` quando o Proxmox cai (`docs/pi-recuperacao.md`) | `vault_caddy_pi_cloudflare_token` |

O token fica em `/etc/caddy/cf-token.env` (`root:caddy`, `0640`) e só é usado
para emitir e renovar certificado (DNS-01). Um token por Caddy: dá para
revogar um sem derrubar os outros, e a auditoria da Cloudflare mostra qual
deles agiu.

O drop-in troca o `ExecStart` do pacote, que usa `--environ` e imprimiria o
token no journal a cada start, e põe `Restart=on-failure`: no boot o Caddy do
Pi pode subir antes de o IP Tailscale existir.

## Antes de aplicar

Token na Cloudflare com escopo **Zone:DNS:Edit** na zona `nextlevelcode.pro`,
no vault com o nome da tabela (`vault.yml.example`).

## Operação

### Trocar o token da Cloudflare

Faça isto em um Caddy de cada vez. Se o token vazou (em log, terminal ou
transcript), faça nos três: apagar o log não adianta, só a revogação inutiliza
o token. Os passos na Cloudflare são manuais porque criar token pede login no
painel, e a API exigiria um token com poder de criar tokens, mais perigoso que
o que se está trocando.

1. **Criar o token novo** em https://dash.cloudflare.com/profile/api-tokens →
   *Create Token* → *Edit zone DNS*, zona `nextlevelcode.pro`. Dê um nome que
   diga o host (`caddy-pi`, `caddy-vps`, `caddy-proxmox`).

   Confira: o token aparece na lista com o nome e o escopo certos.

2. **Pôr no vault**, na variável do host (tabela acima):

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

3. **Aplicar** o playbook do host (o do Pi com `--limit rpi`):

   ```bash
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass --limit rpi
   ```

   Confira, com o token lido do próprio host (assim ele não passa pelo seu
   terminal nem pelo histórico do shell):

   ```bash
   ssh ubuntu@nextlevelcode 'sudo sh -c ". /etc/caddy/cf-token.env; curl -s -H \"Authorization: Bearer \$CLOUDFLARE_API_TOKEN\" \"https://api.cloudflare.com/client/v4/zones?name=nextlevelcode.pro\"" | grep -o "\"success\":[a-z]*"'
   ```

   Deve aparecer `"success":true`. É a mesma consulta que o Caddy faz para
   achar a zona. Não use o `/user/tokens/verify`: token de conta (prefixo
   `cfat_`) responde `Invalid API Token` ali mesmo estando bom. Na VPS é
   `ssh hetzner@hetzner`; no Proxmox, `ssh root@<ip do caddy-lxc>`.

4. **Revogar o token antigo** no mesmo painel (*Roll* ou *Delete*).

   Confira: só o token novo aparece com aquele nome.

Caddy fora do ar (o do Proxmox enquanto o notebook está desligado): revogue o
antigo já, deixe o vault com o novo e aplique quando o host voltar. Até lá
ele não renova certificado, e nada mais depende do token.

Confira que o token não aparece mais no log depois de um restart:

```bash
ssh ubuntu@nextlevelcode 'sudo journalctl -u caddy --since "-10 min" | grep -c CLOUDFLARE_API_TOKEN'
```

Deve dar `0`. Entradas mais antigas continuam lá com o token revogado, que
já não abre nada.
