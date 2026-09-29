module "caddy" {
  source           = "./modules/lxc"
  node_name        = var.node_name
  vm_id            = 200
  hostname         = "caddy"
  ip_address       = "192.168.50.200/24"
  gateway          = var.gateway
  cores            = 1
  memory           = 512
  disk_size        = 8
  datastore_id     = "local-lvm"
  template_file_id = local.ubuntu_template
  template_type    = local.template_type
  dns_servers      = local.dns_servers
  ssh_public_key   = local.ssh_public_key
  nesting          = true
}

module "forgejo" {
  source           = "./modules/lxc"
  node_name        = var.node_name
  vm_id            = 201
  hostname         = "forgejo"
  ip_address       = "192.168.50.201/24"
  gateway          = var.gateway
  cores            = 2
  memory           = 2048
  disk_size        = 30
  datastore_id     = "local-lvm"
  template_file_id = local.ubuntu_template
  template_type    = local.template_type
  dns_servers      = local.dns_servers
  ssh_public_key   = local.ssh_public_key
  nesting          = true
}

module "vaultwarden" {
  source           = "./modules/lxc"
  node_name        = var.node_name
  vm_id            = 202
  hostname         = "vaultwarden"
  ip_address       = "192.168.50.202/24"
  gateway          = var.gateway
  cores            = 1
  memory           = 512
  disk_size        = 8
  datastore_id     = "local-lvm"
  template_file_id = local.ubuntu_template
  template_type    = local.template_type
  dns_servers      = local.dns_servers
  ssh_public_key   = local.ssh_public_key
  nesting          = true
}

output "caddy" {
  description = "Container Caddy IP"
  value       = module.caddy.ip_address
}

output "forgejo" {
  description = "Container Forgejo IP"
  value       = module.forgejo.ip_address
}

output "vaultwarden" {
  description = "Container Vaultwarden IP"
  value       = module.vaultwarden.ip_address
}
