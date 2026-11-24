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
2. Colar o conteúdo inteiro de `policy.hujson` e preencher todos os
   placeholders em `hosts` com os IPv4 Tailscale correspondentes. Confira
   o nó na página **Machines** ou rode `tailscale ip -4` no desktop.
   Preencha os IPs no console para manter os endereços fora do repositório
   público e salve a política.
3. Conferir: o save só completa se a seção `tests` passar. Erro de teste = a
   mudança reabriu algo que devia estar fechado; corrija no repo, não no console.

Por que não dá para scriptar: o console exige login no navegador, e a
alternativa (API) é o token descartado acima.

### Desktop e celular de correio

Associe `correio-desktop` e `correio-celular` aos dois dispositivos de correio
já cadastrados na tailnet. O grant desses aliases abre SMTP autenticado
(587) e IMAPS (993) na VPS. Os testes do console conferem essas portas e o
bloqueio do SSH na VPS (22) para os dois aliases.

Depois de salvar, com o Tailscale conectado em cada dispositivo, confirme
que o app sincroniza a caixa via IMAPS e consegue enviar uma mensagem via
SMTP autenticado. Use as configurações do [guia do Mailserver](../docs/mailserver.md).

### Funnel do webhook temporário

O alias `webhook-temporario` autoriza o Funnel para um único nó, preservando
sua identidade na tailnet. A publicação é configurada no próprio nó e deve
apontar para o proxy local dedicado ao webhook. Depois de publicar, rode
`sudo tailscale funnel status` no nó para conferir a origem configurada e
valide de fora da tailnet que o proxy aceita a rota do webhook e rejeita
as demais. Ao encerrar o uso temporário, desative a publicação e remova
o alias e seu atributo em um PR.

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
| LXC do Forgejo | `tag:proxmox-lxc`, `tag:forgejo` |
| LXC do Vaultwarden | `tag:proxmox-lxc`, `tag:vaultwarden` |
| LXC do Bread of Life | `tag:proxmox-lxc` |
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
