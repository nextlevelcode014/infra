locals {
  mailserver = yamldecode(file("${path.module}/../../ansible/vars/mailserver.yml"))
}

variable "mailserver_piloto_habilitado" {
  description = "Libera o SMTP IPv4 de entrada e configura o PTR do piloto."
  type        = bool
  default     = false
}

resource "hcloud_rdns" "mailserver" {
  count      = var.mailserver_piloto_habilitado ? 1 : 0
  server_id  = hcloud_server.vps.id
  ip_address = hcloud_server.vps.ipv4_address
  dns_ptr    = local.mailserver.mailserver_mx
}

output "mailserver_ipv4" {
  description = "IPv4 público da VPS para conferir o A e o PTR do Mailserver."
  value       = hcloud_server.vps.ipv4_address
}
