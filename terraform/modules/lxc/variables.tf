variable "node_name" {
  type = string
}

variable "vm_id" {
  type = number
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
