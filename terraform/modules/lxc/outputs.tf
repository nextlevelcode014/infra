output "ip_address" {
  description = "Endereço IPv4 do container, sem a máscara de rede"
  value       = split("/", var.ip_address)[0]
}

output "vm_id" {
  description = "ID do container no Proxmox"
  value       = var.vm_id
}
