locals {
  ubuntu_template = "local:vztmpl/ubuntu-26.04-standard_26.04-1_amd64.tar.zst"
  template_type   = "ubuntu"
  dns_servers     = ["192.168.50.1"]
  ssh_public_key  = trimspace(file(pathexpand("~/.ssh/id_ed25519.pub")))
}
