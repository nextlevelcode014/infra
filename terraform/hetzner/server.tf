# A VPS da Hetzner (criada à mão, trazida pelo import em imports.tf). A
# configuração foi gerada a partir da API e limpa: o que está aqui é o que ela
# é, não um pedido para mudar.
resource "hcloud_server" "vps" {
  name        = "ubuntu-4gb-fsn1-1"
  server_type = "cx23"
  location    = "fsn1"
  image       = "ubuntu-26.04"
  backups     = false

  # Proteção da Hetzner contra apagar ou reinstalar por engano (pela API ou
  # pelo console). Precisam ir juntas. Para destruir de propósito, desligue
  # as duas antes.
  delete_protection  = true
  rebuild_protection = true

  # O firewall entra pelo hcloud_firewall_attachment (firewall.tf). Sem isto
  # o servidor brigaria com o attachment a cada plan.
  ignore_remote_firewall_ids = true

  lifecycle {
    # Uma VPS criada à mão: imagem, chaves e user_data de quando ela nasceu
    # não vêm da API do mesmo jeito, e mudar qualquer um deles a recriaria.
    ignore_changes = [image, ssh_keys, user_data]
    # O apply nunca pode apagar a VPS: ela tem o forge e o Uptime Kuma.
    prevent_destroy = true
  }
}
