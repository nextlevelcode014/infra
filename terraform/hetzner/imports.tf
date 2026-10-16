# A VPS foi criada à mão no console. O import a traz para o state sem
# recriar; a configuração em server.tf foi gerada a partir dela
# (terraform plan -generate-config-out). Depois do primeiro apply este bloco
# não faz mais nada e pode ficar.
import {
  to = hcloud_server.vps
  id = "167186432"
}
