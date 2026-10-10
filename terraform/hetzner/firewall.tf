# Firewall da Hetzner Cloud: fica fora da VM, então vale mesmo que o UFW
# caia, e barra também as portas que o Docker publica por cima do UFW. Com
# regras de entrada, tudo que não está aqui é descartado; saída fica livre.
# É stateful: as respostas voltam sozinhas.
resource "hcloud_firewall" "vps" {
  name = "vps-publica"

  labels = {
    gerido_por = "terraform"
  }

  # Caddy público (forge e status page).
  rule {
    description = "HTTP"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "HTTPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  # Conexão direta do Tailscale; sem ela os pares caem no relay (DERP).
  rule {
    description = "Tailscale direto"
    direction   = "in"
    protocol    = "udp"
    port        = "41641"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "ICMP (ping, path MTU)"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}
resource "hcloud_firewall_attachment" "vps" {
  firewall_id = hcloud_firewall.vps.id
  server_ids  = [hcloud_server.vps.id]
}
