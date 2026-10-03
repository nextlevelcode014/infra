# Anubis: desafio anti-bot nos serviços públicos

O [Anubis](https://anubis.techaro.lol) é um proxy reverso que fica entre o
proxy público e o serviço. Na primeira visita ele entrega uma página que faz o
navegador resolver uma prova de trabalho (achar um SHA-256 com N zeros no
começo), em ~1 s; depois grava um cookie assinado e deixa passar direto. Para
uma pessoa custa uma espera, uma vez. Para quem baixa milhões de páginas custa
caro, e a maioria dos scrapers nem roda JavaScript.

É a camada anti-bot própria, no lugar do proxy da Cloudflare (que este
homelab não usa, por privacidade).

| Serviço | Caminho | Onde roda o Anubis |
|---|---|---|
| `forge.nextlevelcode.pro` | Caddy da VPS → `anubis-forgejo` (`127.0.0.1:8923`) → Forgejo (`<ip-tailscale-do-forgejo>:3000`) | VPS, `playbooks/anubis.yml` |
| `fmd.<tailnet>.ts.net` (Funnel) | sidecar `fmd-tailscale` → `fmd-anubis` (`:8923`) → FMD (`:8080`) | Pi, na stack do FMD, `playbooks/fmd.yml` |

O endereço do Funnel atende a internet **e** a tailnet (o MagicDNS resolve o
mesmo nome para o IP da tailnet). Os dois passam pelo `fmd-anubis`, e a
política separa: da tailnet passa direto (o app do celular não roda
JavaScript), da internet é desafiado. O `fmd.lab` (Caddy do Proxmox → porta
`8085`) nem passa pelo Anubis.

## O que passa sem desafio

A política (`roles/anubis/templates/policy.yaml.j2`) é a mesma base para
todos: nega bots patológicos e de IA, deixa passar `robots.txt`, favicon e
`.well-known`, e desafia o resto. É **própria**, não a padrão do Anubis: a
padrão dá peso extra a tráfego do Brasil.

Cada serviço acrescenta o que precisa passar sem JavaScript:

| Serviço | Liberado | Por quê |
|---|---|---|
| Forgejo | buscadores verificados por IP | sem isso o forge some das buscas |
| Forgejo | clientes git (`(data)/clients/git.yaml`) | `git clone` por HTTPS |
| Forgejo | `*.rss`, `*.atom` | leitores de feed |
| Forgejo | `/api/*` **com** header `Authorization` | o `tea` e scripts com token; API anônima segue desafiada |
| Forgejo | `/api/healthz` | monitor do Uptime Kuma |
| FMD | tudo o que vem da **tailnet** (sem o header `Tailscale-Funnel-Request`) | o app do celular; o `tailscale serve` apaga esse header do cliente e só o põe em requisição do Funnel, então não dá para forjar |
| FMD | `/api/v1/version` | monitor do Uptime Kuma |

No FMD, da internet, **todo o resto é desafiado, inclusive o login** (`/api/v1/salt`,
`/requestAccess`). A trava do FMD é por usuário (5 erros = 10 min): sem o
Anubis, qualquer bot travava a sua conta na hora da emergência. No navegador o
login funciona normal, porque o cookie do desafio vale para as chamadas da
página.

Os monitores do Uptime Kuma apontam para os caminhos liberados porque a página
de desafio responde **200**: apontando para a raiz, ficariam verdes com o
serviço fora do ar.

## Serviço novo

1. Uma instância em `anubis_instances` (`inventory/group_vars/vps/vars.yml`):
   `name`, `port` livre em `127.0.0.1`, `target`, `redirect_domains` (o domínio
   público; sem ele o Anubis redireciona para qualquer domínio depois do
   desafio) e `policy.rules` com o que o serviço precisa liberar (app móvel,
   API, webhooks, health check). Campos das regras:
   <https://anubis.techaro.lol/docs/admin/policies>.
2. No `Caddyfile.vps.j2`, o site aponta para a porta do Anubis com
   `header_up X-Real-Ip {remote_host}`: o Anubis responde **500** sem o IP do
   cliente.
3. Aplicar o Anubis antes do Caddy:

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ```

## Aplicação (primeira vez)

```bash
ansible-playbook playbooks/anubis.yml --ask-vault-pass --check --diff
ansible-playbook playbooks/anubis.yml --ask-vault-pass
ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
ansible-playbook playbooks/fmd.yml --ask-vault-pass --check --diff
ansible-playbook playbooks/fmd.yml --ask-vault-pass
ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
```

O `fmd.yml` recria a stack do FMD uma vez (o `ts-serve.json` muda): o FMD e o
Funnel piscam alguns segundos. O nó Tailscale é o mesmo (estado no volume).

Confira de **fora da tailnet** (4G, ou outro aparelho sem Tailscale):

```bash
curl -s -A 'Mozilla/5.0' https://forge.nextlevelcode.pro/ | grep -io 'not a bot' | head -1
curl -s -o /dev/null -w '%{http_code}\n' https://forge.nextlevelcode.pro/api/healthz
git clone https://forge.nextlevelcode.pro/nextlevelcode/ansible.git /tmp/anubis-teste && rm -rf /tmp/anubis-teste
curl -s -A 'Mozilla/5.0' https://fmd.<tailnet>.ts.net/ | grep -io 'not a bot' | head -1
curl -s https://fmd.<tailnet>.ts.net/api/v1/version
```

Desafio nas linhas 1 e 4, `200` na 2, clone sem erro, versão na 5. Abra os
dois num navegador: passam depois de ~1 s, e o login do FMD funciona. O
`tea pr ls` continua funcionando, e o app do celular continua sincronizando
pela tailnet.

## Limitações

- **Exige JavaScript.** Navegador sem JS não passa.
- **O Anubis do FMD vê todo mundo como `127.0.0.1`** (`USE_REMOTE_ADDRESS`).
  Ele exige o IP do cliente e descarta IPs da tailnet (`100.64.0.0/10`) do
  `X-Forwarded-For`; sem isso, quem vem da tailnet levava 500 antes de qualquer
  regra. Nenhuma regra do FMD depende de IP, e os logs do FMD continuam com o
  IP real.
- **Restart = desafio de novo.** A chave que assina o cookie é gerada na
  partida (sem chave no vault de propósito: um segredo a menos).

## Logs e rollback

```bash
ssh hetzner@hetzner 'sudo docker logs --since 10m anubis-forgejo'
ssh ubuntu@nextlevelcode.<tailnet>.ts.net 'docker logs --since 10m fmd-anubis'
```

- Forgejo: `caddy_vps_forgejo_upstream: <ip-tailscale-do-forgejo>:3000` em
  `inventory/group_vars/vps/vars.yml` e reaplicar o `caddy-vps.yml`.
- FMD: `ansible-playbook playbooks/fmd.yml --ask-vault-pass -e fmd_anubis=false`.
