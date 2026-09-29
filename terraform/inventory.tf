resource "ansible_host" "caddy" {
  name = "caddy"
  groups = ["lxc"]

  variable = {
    ansible_host        = split("/", module.caddy.ip_address)[0]
    ansible_user        = "root"
    ansible_ssh_private_key_file = "~/.ssh/id_ed25519"
  }
}
