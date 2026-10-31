# 0021. O lab mora numa bridge própria, que só sai para a internet

- **Status:** Aceita
- **Data:** 2026-10-31

## Contexto

As VMs do repo `lab` ligavam na `vmbr0`, com DHCP da LAN onde o notebook do
Proxmox estivesse. Desde o ADR 0009 o notebook muda de rede e os LXCs moram
na `vmbr1`, mas o lab continuou na `vmbr0`, e isso trouxe três problemas:

- a VM do lab ficava na LAN de onde o notebook estivesse, que nem sempre é a
  de casa: alcançava o que houvesse nela, e uma porta aberta antes do
  primeiro login (o cadastro de admin de um app novo) ficava exposta a ela;
- com o `ip_forward` do ADR 0009 ligado e nenhuma regra de `FORWARD`, uma VM
  do lab que pusesse uma rota para `10.50.0.0/24` pelo IP do Proxmox na LAN
  chegava aos LXCs da produção. O isolamento do lab dependia só de ninguém
  escrever essa rota;
- longe do notebook, a máquina de administração não chegava à VM antes de
  ela entrar na tailnet, e o playbook do experimento parava no SSH.

## Decisão

As VMs do lab ligam na `vmbr2` (`10.60.0.0/24`), uma bridge só do Proxmox,
como a dos LXCs, com NAT pela `vmbr0`. O script `lab-isolamento`, que sobe
com a bridge, faz o firewall: o lab só abre conexão para a internet (fora
das faixas privadas e da CGNAT da tailnet), não abre conexão com o próprio
host, e ninguém abre conexão com o lab. O acesso de administração salta pelo
Proxmox, como o dos LXCs. O IP de cada VM é fixo e sai do VMID (no repo
`lab`), porque na `vmbr2` não há DHCP.

## Alternativas descartadas

- **Manter a `vmbr0` e só saltar pelo Proxmox:** resolve o acesso, mas
  deixa a VM na LAN alheia e o caminho até a `vmbr1` aberto.
- **Lab na `vmbr1`, junto com os LXCs:** separar lab e produção na mesma
  bridge pediria regra por IP, e um IP errado no lab o poria ao lado da
  produção.
- **Firewall do Proxmox (`pve-firewall`):** ele filtra por VM e por grupo,
  mas é ligado por datacenter e mexeria na produção inteira para proteger o
  lab. As chains próprias do script tocam só o que passa pela `vmbr2`.
- **DHCP na `vmbr2` (dnsmasq no host):** um serviço a mais no host para
  um IP que dá para calcular do VMID.

## Consequências

- O lab não alcança a produção, nem a LAN, nem o host, por regra no host e
  não por convenção. A permissão de rede do `lab@pve` passa a ser só a
  `vmbr2`: uma VM do lab na `vmbr0` falha no `apply`.
- Faixa e gateway moram em dois repos que andam juntos: o `defaults` do
  `proxmox_host` aqui e o `modules/proxmox-vm` do lab.
- Porta de app do lab no navegador, antes de a VM entrar na tailnet, é por
  túnel SSH pelo mesmo salto.
- Fica de fora a mesma pergunta para a `vmbr1`: hoje nada impede um
  dispositivo da LAN de rotear até os LXCs pelo Proxmox. Fechar isso mexe
  no caminho da produção e é decisão à parte.
