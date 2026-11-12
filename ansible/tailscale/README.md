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
2. Colar o conteúdo inteiro de `policy.hujson`, trocar
   `<ip-tailscale-do-desktop-1>` e `<ip-tailscale-do-desktop-2>` pelos IPs
   reais (os que já estão no console, ou `tailscale ip -4` em cada desktop).
   Preencha também os endereços do [piloto AndBible](#piloto-andbible) e salve.
   Os IPs ficam fora do repo público. O console recusa os placeholders
   por serem endereços inválidos.
3. Conferir: o save só completa se a seção `tests` passar. Erro de teste = a
   mudança reabriu algo que devia estar fechado; corrija no repo, não no console.

Por que não dá para scriptar: o console exige login no navegador, e a
alternativa (API) é o token descartado acima.

## Piloto AndBible

A [issue #86](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/86)
usa o LXC descartável `lab-andbible` do repo `lab`. No console
**Machines**, copie o IPv4 Tailscale dos dois
aparelhos de teste e do LXC para os três placeholders em `hosts`.
No LXC, confirme o endereço com `tailscale ip -4` e a tag `tag:lab`
antes de salvar. O grant abre TCP 443 só desses aparelhos para o IP
do LXC. A autenticação WebDAV continua por conta individual.

Se o LXC for recriado ou um aparelho trocar de IP, confira os novos
endereços antes de reaplicar a política no console. No fim do piloto,
remova os três aliases, o grant e os dois testes em um PR. Depois do
merge, salve a política atualizada no console e confira que os aparelhos
do piloto ficaram sem o grant.

## Mudou no console?

Qualquer edição feita direto no console precisa voltar para cá num PR — senão
os dois divergem e a próxima colagem desfaz a edição.

## Tags

Aplicadas à mão no console → **Machines** → nó → **Edit ACL tags**. Confira o
nome do nó antes: o nome MagicDNS pode diferir do hostname.

| Nó | Tags |
|---|---|
| Raspberry Pi (o host) | `tag:pi` |
| Proxmox (hypervisor) | `tag:proxmox` |
| LXC do Caddy | `tag:caddy` |
| LXCs do Forgejo e do Vaultwarden | `tag:proxmox-lxc`; o do Forgejo também `tag:forgejo` |
| VPS | `tag:vps`, `tag:caddy-vps` |
| Nós Tailscale em container (sidecar do FMD, exit node) | `tag:containers`; o FMD também `tag:public` (Funnel) |
| Máquinas do repo `lab` | `tag:lab`, pela auth key efêmera (não se aplica à mão) |
| Runner do GitHub Actions dos testes do `lab` | `tag:lab-ci`, pelo OAuth client (não se aplica à mão) |
| Desktops de administração | sem tag — ficam em `hosts.infra-admin-1` e `hosts.infra-admin-2` |

Desktop não leva tag: com tag o nó deixa de ser dispositivo pessoal e sai de
`autogroup:self` e `autogroup:member`. O IP dele é o de `tailscale ip -4` no
próprio desktop. Para um desktop a mais, crie `infra-admin-N` em `hosts` e
inclua o alias em todos os grants de administração (os que têm
`infra-admin-1` como origem).

SSH passa por duas camadas: o grant de rede (só os IPs de `hosts` chegam na
porta 22) e a regra `ssh` (identidade humana com `action: check`, que pede
reautenticação). As duas precisam permitir.

## Contingência: Forgejo e Vaultwarden no Pi

Os grants comentados no fim de `grants` ficam **fora** da política no uso
normal. Durante um DR ([`docs/pi-recuperacao.md`](../docs/pi-recuperacao.md)),
descomente os dois no repo, tire `tag:pi:3000` do `deny` do teste de
`tag:caddy-vps` (senão o save falha) e cole o arquivo inteiro no console: o
Caddy da VPS passa a alcançar o Forgejo do Pi (`3000`, o `forge` público), e
a tailnet o SSH do Git (`2222`). O `*.lab` não passa pela VPS: quem assume é
o Caddy reserva do Pi, pelo grant de `tcp:443` em `tag:pi`, que fica sempre
ativo. Depois do failback, cole de novo o `policy.hujson` do repo: ele volta
com os grants comentados e os denies no lugar.

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
