variable "proxmox_endpoint" {
  type    = string
  default = "https://proxmox.<tailnet>.ts.net:8006"
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
