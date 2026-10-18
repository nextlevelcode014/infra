# Anubis na VPS

`playbooks/anubis.yml` sobe o [Anubis](https://anubis.techaro.lol) na VPS, na
frente dos domínios públicos que o Caddy da VPS serve: um proxy reverso que,
na primeira visita, faz o navegador resolver uma prova de trabalho (achar um
SHA-256 com N zeros no começo) em ~1 s, grava um cookie assinado e depois
deixa passar direto. Para uma pessoa custa uma espera, uma vez; para quem
baixa milhões de páginas custa caro, e a maioria dos scrapers nem roda
JavaScript. É a camada anti-bot própria, no lugar do proxy da Cloudflare (que
este homelab não usa, por privacidade).

| O quê | Onde |
|---|---|
| `forge.nextlevelcode.pro` | Caddy da VPS → `anubis-forgejo` (`127.0.0.1:8923`) → Forgejo (`forgejo_tailscale_ip:3000`) |
| `fmd.<tailnet>.ts.net` (Funnel) | sidecar `fmd-tailscale` → `fmd-anubis` (`:8923`) → FMD (`:8080`), no Pi, na stack do FMD (`playbooks/fmd.yml`) |
| Instâncias da VPS | `anubis_instances` em `inventory/group_vars/vps/vars.yml`, uma por serviço |
| Política | `roles/anubis/templates/policy.yaml.j2`, renderizada em `/opt/anubis/policy-<instância>.yaml` |
| Imagem | `anubis_image` (versão exata: fica exposto à internet, ADR 0005) |

O endereço do Funnel atende a internet **e** a tailnet (o MagicDNS resolve o
mesmo nome para o IP da tailnet). Os dois passam pelo `fmd-anubis`, e a
política separa: da tailnet passa direto (o app do celular não roda
JavaScript), da internet é desafiado. O `fmd.lab` (Caddy do Proxmox → porta
`8085`) nem passa pelo Anubis.

## Antes de aplicar

Nada no vault: a chave que assina o cookie é gerada na partida do container,
de propósito (um segredo a menos). O que precisa existir é a instância em
`anubis_instances` e o site no `Caddyfile.vps.j2` apontando para a porta dela
(ver "Serviço novo").

## Instalação

1. **Anubis da VPS**, sempre antes do Caddy: o Caddy passa a apontar para
   ele.

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ```

   Confira: `ssh hetzner@hetzner sudo docker ps --filter name=anubis` lista
   um `anubis-<instância>` por item de `anubis_instances`.

2. **Anubis do FMD**, que mora na stack do FMD no Pi. Recria a stack uma vez
   (o `ts-serve.json` muda): o FMD e o Funnel piscam alguns segundos, e o nó
   Tailscale é o mesmo (estado no volume).

   ```bash
   ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit rpi
   ```

3. **Monitores**, que apontam para os caminhos liberados:

   ```bash
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Confira de **fora da tailnet** (4G, ou outro aparelho sem Tailscale):

   ```bash
   curl -s -A 'Mozilla/5.0' https://forge.nextlevelcode.pro/ | grep -io 'not a bot' | head -1
   curl -s -o /dev/null -w '%{http_code}\n' https://forge.nextlevelcode.pro/api/healthz
   git clone https://forge.nextlevelcode.pro/nextlevelcode/infra.git /tmp/anubis-teste && rm -rf /tmp/anubis-teste
   curl -s -A 'Mozilla/5.0' https://fmd.<tailnet>.ts.net/ | grep -io 'not a bot' | head -1
   curl -s https://fmd.<tailnet>.ts.net/api/v1/version
   ```

   Desafio nas linhas 1 e 4, `200` na 2, clone sem erro, versão na 5. Abra os
   dois num navegador: passam depois de ~1 s, e o login do FMD funciona. O
   `tea pr ls` continua funcionando, e o app do celular continua
   sincronizando pela tailnet.

## Backup

Não tem: o Anubis não guarda estado. A política vem do repo e a chave do
cookie é gerada na partida.

## Operação

### O que passa sem desafio

A política é a mesma base para todos: nega bots patológicos e de IA, deixa
passar `robots.txt`, favicon e `.well-known`, e desafia o resto. É
**própria**, não a padrão do Anubis: a padrão dá peso extra a tráfego do
Brasil. Cada serviço acrescenta o que precisa passar sem JavaScript:

| Serviço | Liberado | Por quê |
|---|---|---|
| Forgejo | buscadores verificados por IP | sem isso o forge some das buscas |
| Forgejo | clientes git (`(data)/clients/git.yaml`) | `git clone` por HTTPS |
| Forgejo | `*.rss`, `*.atom` | leitores de feed |
| Forgejo | `/api/*` **com** header `Authorization` | o `tea` e scripts com token; API anônima segue desafiada |
| Forgejo | `/api/healthz` | monitor do Uptime Kuma |
| FMD | tudo o que vem da **tailnet** (sem o header `Tailscale-Funnel-Request`) | o app do celular; o `tailscale serve` apaga esse header do cliente e só o põe em requisição do Funnel, então não dá para forjar |
| FMD | `/api/v1/version` | monitor do Uptime Kuma |

No FMD, da internet, **todo o resto é desafiado, inclusive o login**
(`/api/v1/salt`, `/requestAccess`). A trava do FMD é por usuário (5 erros =
10 min): sem o Anubis, qualquer bot travava a sua conta na hora da
emergência. No navegador o login funciona normal, porque o cookie do desafio
vale para as chamadas da página.

Os monitores do Uptime Kuma apontam para os caminhos liberados porque a
página de desafio responde **200**: apontando para a raiz, ficariam verdes
com o serviço fora do ar.

### Serviço novo

1. Uma instância em `anubis_instances` (`inventory/group_vars/vps/vars.yml`):
   `name`, `port` livre em `127.0.0.1`, `target`, `redirect_domains` (o
   domínio público; sem ele o Anubis redireciona para qualquer domínio
   depois do desafio) e `policy.rules` com o que o serviço precisa liberar
   (app móvel, API, webhooks, health check). Campos das regras:
   <https://anubis.techaro.lol/docs/admin/policies>.
2. No `Caddyfile.vps.j2`, o site aponta para a porta do Anubis com
   `header_up X-Real-Ip {remote_host}`: o Anubis responde **500** sem o IP do
   cliente.
3. Aplicar o Anubis antes do Caddy, como no passo 1 da instalação.

Mudar a política de uma instância reinicia só ela: o Anubis lê a política na
partida, e o role reinicia quem teve o arquivo alterado.

### Atualizar

Versão exata em `anubis_image` (`roles/anubis/defaults/main.yml`), a mesma
para a VPS e o FMD: o `vps-atualizar.yml` não muda essa imagem. Para subir,
ler as notas da versão, trocar a variável e reaplicar o `anubis.yml` e o
`fmd.yml`.

### Logs e rollback

```bash
ssh hetzner@hetzner 'sudo docker logs --since 10m anubis-forgejo'
ssh ubuntu@nextlevelcode 'docker logs --since 10m fmd-anubis'
```

Tirar o Anubis do caminho:

- Forgejo: `caddy_vps_forgejo_upstream: "{{ forgejo_tailscale_ip }}:3000"`
  em `inventory/group_vars/vps/vars.yml` e reaplicar o `caddy-vps.yml`.
- FMD: `ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit rpi -e fmd_anubis=false`.

## Limitações

- **Exige JavaScript.** Navegador sem JS não passa.
- **O Anubis do FMD vê todo mundo como `127.0.0.1`** (`USE_REMOTE_ADDRESS`).
  Ele exige o IP do cliente e descarta IPs da tailnet (`100.64.0.0/10`) do
  `X-Forwarded-For`; sem isso, quem vem da tailnet levava 500 antes de
  qualquer regra. Nenhuma regra do FMD depende de IP, e os logs do FMD
  continuam com o IP real.
- **Restart = desafio de novo.** A chave que assina o cookie é gerada na
  partida.
