locals {
  ubuntu_template = "local:vztmpl/ubuntu-26.04-standard_26.04-1_amd64.tar.zst"
  template_type   = "ubuntu"
  ssh_public_key  = trimspace(file(pathexpand("~/.ssh/id_ed25519.pub")))

  # Rede dos LXCs (ADR 0009): bridge só do Proxmox, com NAT para fora. Quem
  # cria a bridge é o Ansible (role proxmox_host), com a mesma faixa: mudar
  # aqui é mudar lá. Não depende da LAN onde o Proxmox estiver.
  lxc_bridge  = "vmbr1"
  lxc_gateway = "10.50.0.1"
  # O DNS do roteador mudaria com a LAN. Quad9: público, sem log de IP.
  # Os LXCs na tailnet passam a usar o MagicDNS ao entrar nela.
  dns_servers = ["9.9.9.9", "149.112.112.112"]
}
