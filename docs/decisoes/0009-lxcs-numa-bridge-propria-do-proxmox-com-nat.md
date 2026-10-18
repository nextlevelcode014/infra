# 0009. LXCs numa bridge própria do Proxmox, com NAT

- **Status:** Aceita
- **Data:** 2026-10-18

## Contexto

Os LXCs (caddy, forgejo, vaultwarden, pi-lab) estavam na `vmbr0`, a bridge
ligada à LAN do roteador, com IP fixo da faixa dele (`192.168.50.200-203`),
gateway e DNS no roteador. O Ansible chegava a eles por esse IP.

A `vmbr0` do Proxmox é DHCP, numa placa USB. Quando o notebook foi para outra
rede, o Proxmox pegou IP da faixa nova e continuou na tailnet, mas os LXCs
ficaram sem rota: sem internet, fora da tailnet por dias e sem acesso pelo
Ansible. Qualquer troca de rede, ou de roteador, repete isso, e consertar
pedia mudar IP no Terraform e no inventário a cada vez.

## Decisão

Os LXCs moram na `vmbr1`, uma bridge só do Proxmox, sem porta física, em
`10.50.0.0/24` (faixa escolhida por fugir das redes domésticas comuns). O
Proxmox é o gateway (`10.50.0.1`) e faz NAT para fora pela `vmbr0`. O DNS dos
LXCs é público (Quad9), não o do roteador. Quem cria a bridge é o Ansible
(`proxmox_host`); o Terraform só liga os containers nela.

Da máquina de administração não há rota até a `vmbr1`: o SSH, do Ansible e
manual, salta pelo Proxmox pela tailnet (`-J`/`ProxyJump`). Trocar de rede
passa a mudar só o DHCP da `vmbr0`.

## Alternativas descartadas

- **Subnet router do Tailscale no Proxmox** anunciando `10.50.0.0/24`: daria
  acesso direto, inclusive pelo navegador às portas do pi-lab. Mas a
  `tailscale/policy.hujson` é toda por tag, com testes, e uma rota de subnet
  traz regra por IP. Fica para quando o acesso pelo navegador ao pi-lab de
  fora da LAN virar necessidade, com grant restrito à faixa e ADR próprio.
  Até lá, túnel SSH pelo mesmo salto (`ansible/docs/pi.md`, "pi-lab").
- **Cada LXC na tailnet, com DHCP na LAN:** o Ansible precisa chegar ao
  container antes de ele entrar na tailnet, e o IP do DHCP muda. E o pi-lab
  fica fora da tailnet de propósito (`ansible/docs/pi.md`).
- **Manter a `vmbr0` e só trocar o IP quando a rede mudar:** é o que quebrou;
  depende de alguém lembrar, com o Proxmox longe.

## Consequências

- O IP dos LXCs, o Terraform e o inventário não mudam com a rede. A faixa
  mora em dois lugares que andam juntos: `ansible/roles/proxmox_host`
  (`defaults`) e `terraform/local.tf`.
- Num Proxmox novo, a bridge vem antes dos containers: `proxmox.yml`, depois
  `terraform apply`, depois `lxc.yml`.
- Todo acesso aos LXCs passa pelo Proxmox. O root dele usa `check` no
  Tailscale SSH, então o salto pede reautenticação no navegador de tempos em
  tempos (`ansible/docs/proxmox.md`, "Rede dos LXCs").
- A LAN não chega aos LXCs (eles chegam a ela, pelo NAT): serviço que
  precise ser alcançado pela LAN não pode morar num LXC sem uma regra nova
  no Proxmox. Quem chega a eles de fora é a tailnet, nos que estão nela.
