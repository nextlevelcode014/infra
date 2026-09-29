output "ip_address" {
  description = "The assigned IPv4 address"
  value       = proxmox_virtual_environment_container.this.network_interface[0].ipv4_address
}
