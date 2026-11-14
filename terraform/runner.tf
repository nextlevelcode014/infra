locals {
  runner_rede = yamldecode(file("${path.module}/../ansible/vars/rede-runner.yml"))
}

resource "proxmox_virtual_environment_vm" "forgejo_runner" {
  name      = "forgejo-runner"
  vm_id     = local.runner_rede.runner_vmid
  node_name = var.node_name

  # A primeira partida só acontece depois de conferir o firewall no host.
  started = false
  on_boot = false

  cpu {
    cores = 2
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = 4096
  }

  operating_system {
    type = "l26"
  }

  serial_device {}

  disk {
    datastore_id = "local-lvm"
    import_from  = "local:import/ubuntu-26.04-server-cloudimg-amd64.qcow2"
    interface    = "virtio0"
    size         = 30
    discard      = "on"
    iothread     = true
  }

  network_device {
    bridge = local.runner_rede.runner_rede_bridge
  }

  initialization {
    datastore_id = "local-lvm"

    ip_config {
      ipv4 {
        address = "${local.runner_rede.runner_rede_ip}/${split("/", local.runner_rede.runner_rede_cidr)[1]}"
        gateway = local.runner_rede.runner_rede_gateway
      }
    }

    dns {
      servers = local.runner_rede.runner_rede_dns
    }

    user_account {
      username = "ubuntu"
      keys     = [local.ssh_public_key]
    }
  }

  lifecycle {
    prevent_destroy = true
    # Após a criação, as partidas e paradas ficam com o operador.
    ignore_changes = [started]
  }
}

resource "ansible_host" "forgejo_runner" {
  name   = proxmox_virtual_environment_vm.forgejo_runner.name
  groups = ["forgejo_runners"]

  variables = {
    ansible_host                 = local.runner_rede.runner_rede_ip
    ansible_user                 = "ubuntu"
    ansible_ssh_private_key_file = "~/.ssh/id_ed25519.pub"
  }
}
