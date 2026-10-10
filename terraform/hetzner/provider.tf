# Token da API da Hetzner Cloud (Security → API tokens, leitura e escrita),
# no terraform.tfvars desta pasta.
provider "hcloud" {
  token = var.hcloud_token
}
