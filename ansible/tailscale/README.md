# Política da tailnet

[`policy.hujson`](policy.hujson) é a política de acesso (ACL) da tailnet. Está
aqui para que toda mudança passe por diff e PR — no console, uma edição é salva
direto, sem revisão.

O arquivo é **cópia de referência, não fonte aplicada**: nada sincroniza o repo
com o console. Automatizar exigiria um token da API do Tailscale capaz de
reescrever a ACL inteira, e esse token viraria o segredo mais sensível do
homelab — não compensa para uma tailnet de uma pessoa.

## Aplicar uma mudança

Depois do merge do PR:

1. Abrir <https://login.tailscale.com/admin/acls/file>.
2. Colar o conteúdo inteiro de `policy.hujson` e salvar.
3. Conferir: o save só completa se a seção `tests` passar. Erro de teste = a
   mudança reabriu algo que devia estar fechado; corrija no repo, não no console.

Por que não dá para scriptar: o console exige login no navegador, e a
alternativa (API) é o token descartado acima.

## Mudou no console?

Qualquer edição feita direto no console precisa voltar para cá num PR — senão
os dois divergem e a próxima colagem desfaz a edição.

## Tags

Aplicadas à mão no console → **Machines** → nó → **Edit ACL tags**. Confira o
nome do nó antes: o nome MagicDNS pode diferir do hostname.

| Nó | Tags |
|---|---|
| Raspberry Pi (o host) | `tag:pi` |
| Proxmox (hypervisor e subnet router de `10.10.10.0/24`) | `tag:proxmox` |
| LXC do Caddy | `tag:caddy` |
| LXCs do Forgejo e do Vaultwarden | `tag:proxmox-lxc`; o do Forgejo também `tag:forgejo` |
| VPS | `tag:vps`, `tag:caddy-vps` |
| Nós Tailscale em container (sidecar do FMD, exit node) | `tag:containers`; o FMD também `tag:public` (Funnel) |
| Desktop de administração | sem tag — fica em `hosts.infra-admin-1` |

Desktop não leva tag: com tag o nó deixa de ser dispositivo pessoal e sai de
`autogroup:self` e `autogroup:member`. O IP dele é o de `tailscale ip -4` no
próprio desktop. Para um segundo desktop, crie `infra-admin-2` em `hosts` e
inclua o alias nos três grants de administração.

SSH passa por duas camadas: o grant de rede (só os IPs de `hosts` chegam na
porta 22) e a regra `ssh` (identidade humana com `action: check`, que pede
reautenticação). As duas precisam permitir.

## Contingência: Forgejo e Vaultwarden no Pi

Os grants comentados no fim de `grants` ficam **fora** da política no uso
normal. Durante um DR ([`docs/pi-recuperacao.md`](../docs/pi-recuperacao.md)),
descomente os dois no console, tire `tag:pi:3000` e `tag:pi:8083` do `deny`
do teste de `tag:caddy-vps` (senão o save falha) e salve: o Caddy da VPS passa a alcançar o
Forgejo (`3000`) e o Vaultwarden (`8083`) do Pi, e a tailnet o SSH do Git
(`2222`). Depois do failback, cole de novo o `policy.hujson` do repo: ele volta com os
grants comentados e os denies no lugar.

## Checklist ao mexer em serviços

- **Porta nova atrás do Caddy:** acrescentar no grant `tag:caddy` → `tag:pi`
  (ou → `tag:proxmox-lxc`). Sem ela o serviço sobe e o Caddy devolve 502, sem
  erro nenhum do lado do Tailscale.
- **Porta fora da 443 para os clientes** (DNS, TURN, SSH do Git): grant de
  `autogroup:member` para a tag do destino, só com a porta.
- **Monitor novo no Uptime Kuma** que não passe pelo Caddy: grant de `tag:vps`
  para o destino, e um `accept` no teste de `tag:vps`.
- **Serviço público (Funnel):** `tag:public` no nó + `AllowFunnel` no serve. A
  política já cobre.
