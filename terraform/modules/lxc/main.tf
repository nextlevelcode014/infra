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

  # Volumes extras do datastore, montados dentro do container. O pi-lab usa
  # um para simular o /mnt/secure (LUKS) do Raspberry Pi: precisa ser um
  # mountpoint de verdade, porque os roles do Pi checam isso antes de gravar.
  dynamic "mount_point" {
    for_each = var.mount_points
    content {
      volume = var.datastore_id
      size   = mount_point.value.size
      path   = mount_point.value.path
    }
  }

  operating_system {
    template_file_id = var.template_file_id
    type             = var.template_type
  }

  network_interface {
    name   = "eth0"
    bridge = var.bridge
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

  # keyctl e device_passthrough são do Ansible (roles/lxc_flags). Sem isto,
  # todo plan tenta desfazer o que o role aplicou — e o apply ou leva 403 do
  # token, ou, se passasse, desligaria o Docker dentro do container.
  lifecycle {
    ignore_changes = [features[0].keyctl, device_passthrough]
  }
}

# /dev/net/tun NÃO fica aqui: device passthrough tem a mesma restrição do
# Proxmox ("configuring device passthrough is only allowed for root@pam"),
# então um token nunca consegue aplicá-lo. Vai no mesmo role do keyctl.
