# 0026. Bread of Life usa HTTPS no Caddy do Proxmox

- **Status:** Proposta
- **Data:** 2026-11-12

## Contexto

A [issue #86](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/86)
encerrou o piloto com a escolha do Bread of Life. O servidor aceita cadastro
de quem alcança a API. O padrão de DNS dos serviços internos é
`*.lab.nextlevelcode.pro`, com o HTTPS no Caddy do Proxmox. O grant HTTPS
desse Caddy cobre os membros da tailnet.

## Decisão

Usar o LXC 204 não privilegiado na `vmbr1`, com a base Docker dos LXCs do
`infra`. O servidor roda como usuário sem privilégios no Docker e publica
a porta no IP Tailscale do LXC. O LXC usa a tag compartilhada
`tag:proxmox-lxc`. O grant existente do Caddy do Proxmox para essa tag
inclui a porta 4000. No Caddy, a rota exige o IP exato de um dos aparelhos
autorizados, pelo endereço da conexão TCP.

## Alternativas descartadas

- **Tailscale Serve:** usaria um nome próprio da tailnet para o HTTPS,
  fora do padrão de nomes dos serviços internos.
- **VM dedicada:** isolaria o kernel. O serviço tem um único processo Node
  fixado, executa sem privilégios e segue o perfil das stacks de serviço
  já geridas nos LXCs. Jobs Docker do runner têm outro perfil de risco.
- **Node direto no LXC:** exigiria manter runtime e unidade systemd
  específicos para esse serviço, que usa Docker na distribuição oficial.

## Consequências

A lista de IPs no vault controla a rota. Se um aparelho mudar de endereço
Tailscale, atualize o vault e reaplique o Caddy. O acesso passa pelo Caddy
do Proxmox e usa o certificado wildcard existente. O grant permite que o
Caddy acesse a porta 4000 em qualquer LXC com `tag:proxmox-lxc` que tenha
um serviço escutando nessa porta. O Docker compartilha o kernel do Proxmox
por meio do LXC.
