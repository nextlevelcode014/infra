variable "node_name" {
  type        = string
  description = "Nome do nó Proxmox onde os containers serão criados"
}

variable "gateway" {
  type        = string
  description = "Gateway da rede dos containers"
}
