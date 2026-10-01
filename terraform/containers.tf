# Faixa reservada para containers gerenciados aqui: 200-299.
# Convenção: hostname, VMID e último octeto do IP usam o mesmo número.
#   caddy        -> vmid 200 -> 192.168.50.200
#   forgejo      -> vmid 201 -> 192.168.50.201
#   vaultwarden  -> vmid 202 -> 192.168.50.202
#   pi-lab       -> vmid 203 -> 192.168.50.203  (staging do Raspberry Pi)
# O Ansible consome isso pelo grupo "lxc" (ver inventory.tf).

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

module "pi_lab" {
  source           = "./modules/lxc"
  node_name        = var.node_name
  vm_id            = 203
  hostname         = "pi-lab"
  ip_address       = "192.168.50.203/24"
  gateway          = var.gateway
  cores            = 4
  memory           = 4096
  disk_size        = 32
  datastore_id     = "local-lvm"
  template_file_id = local.ubuntu_template
  template_type    = local.template_type
  dns_servers      = local.dns_servers
  ssh_public_key   = local.ssh_public_key
  nesting          = true

  # Faz o papel do volume LUKS do Pi (/mnt/secure), onde ficam os dados dos
  # serviços e o data-root do Docker.
  mount_points = [{ path = "/mnt/secure", size = "20G" }]
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

output "pi_lab" {
  description = "Container pi-lab IP"
  value       = module.pi_lab.ip_address
}
