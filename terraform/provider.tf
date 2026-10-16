# Fica no terraform.tfvars (fora do git): leva o nome da tailnet.
variable "proxmox_endpoint" {
  type = string
}

provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = true
}

variable "proxmox_api_token" {
  type      = string
  sensitive = true
}

provider "ansible" {}
