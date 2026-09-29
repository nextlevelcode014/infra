variable "node_name" {
  type = string
}

variable "vm_id" {
  type        = number
  description = "ID do container no Proxmox. Faixa reservada para containers: 200-299."

  validation {
    condition     = var.vm_id >= 200 && var.vm_id <= 299
    error_message = "VMID ${var.vm_id} fora da faixa reservada para containers (200-299)."
  }
}

variable "hostname" {
  type = string
}

variable "ip_address" {
  type    = string
  default = "dhcp"
}

variable "gateway" {
  type    = string
  default = null
}

variable "cores" {
  type    = number
  default = 1
}

variable "memory" {
  type    = number
  default = 512
}

variable "disk_size" {
  type    = number
  default = 8
}

variable "datastore_id" {
  type = string
}

variable "template_file_id" {
  type = string
}

variable "template_type" {
  type = string
}

variable "dns_servers" {
  type    = list(string)
  default = ["8.8.8.8"]
}

variable "ssh_public_key" {
  type = string
}

variable "nesting" {
  type    = bool
  default = false
}

variable "keyctl" {
  type    = bool
  default = false
}

