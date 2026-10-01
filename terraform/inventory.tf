resource "ansible_host" "caddy" {
  name   = "caddy"
  groups = ["lxc"]

  depends_on = [module.caddy]
  variables = {
    ansible_host                 = module.caddy.ip_address
    ansible_user                 = "root"
    ansible_ssh_private_key_file = "~/.ssh/id_ed25519"
    lxc_vmid                     = module.caddy.vm_id
  }
}

resource "ansible_host" "forgejo" {
  name   = "forgejo"
  groups = ["lxc"]

  depends_on = [module.forgejo]
  variables = {
    ansible_host                 = module.forgejo.ip_address
    ansible_user                 = "root"
    ansible_ssh_private_key_file = "~/.ssh/id_ed25519"
    lxc_vmid                     = module.forgejo.vm_id
  }
}

resource "ansible_host" "vaultwarden" {
  name   = "vaultwarden"
  groups = ["lxc"]

  depends_on = [module.vaultwarden]
  variables = {
    ansible_host                 = module.vaultwarden.ip_address
    ansible_user                 = "root"
    ansible_ssh_private_key_file = "~/.ssh/id_ed25519"
    lxc_vmid                     = module.vaultwarden.vm_id
  }
}

resource "ansible_host" "pi_lab" {
  name   = "pi-lab"
  groups = ["lxc", "staging", "pi_staging"]

  depends_on = [module.pi_lab]
  variables = {
    ansible_host                 = module.pi_lab.ip_address
    ansible_user                 = "root"
    ansible_ssh_private_key_file = "~/.ssh/id_ed25519"
    lxc_vmid                     = module.pi_lab.vm_id
  }
}
