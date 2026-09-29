resource "proxmox_virtual_environment_container" "this" {
  node_name    = var.node_name
  vm_id        = var.vm_id
  description  = "Gerenciado pelo Terraform"
  unprivileged = true
  started      = true
  tags         = ["terraform"]

  cpu { cores = var.cores }
  memory { dedicated = var.memory }

  disk {
    datastore_id = var.datastore_id
    size         = var.disk_size
  }

  operating_system {
    template_file_id = var.template_file_id
    type             = var.template_type
  }

  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
  }

  initialization {
    hostname = var.hostname

    ip_config {
      ipv4 {
        address = var.ip_address
        gateway = var.gateway
      }
    }

    dns { servers = var.dns_servers }

    user_account { keys = [var.ssh_public_key] }
  }

  features {
    # keyctl fica em false: feature flags só podem ser alteradas autenticado
    # como root@pam, e aqui usamos um token de API (recebe 403).
    # Quem aplica keyctl é o Ansible (roles/lxc_flags), via pct no host.
    nesting = var.nesting
    keyctl  = var.keyctl
  }
}

# /dev/net/tun NÃO fica aqui: device passthrough tem a mesma restrição do
# Proxmox ("configuring device passthrough is only allowed for root@pam"),
# então um token nunca consegue aplicá-lo. Vai no mesmo role do keyctl.
