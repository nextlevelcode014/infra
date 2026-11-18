# Hetzner Cloud

A VPS (`ubuntu-4gb-fsn1-1`, CX23 em Falkenstein) e o firewall da Hetzner
Cloud na frente dela. Stack separada da do Proxmox, com **state próprio**
(workspace `infra-hetzner` no HCP Terraform, ADR 0019): um erro aqui não
toca os containers, e vice-versa. O que roda dentro da VPS é do
`ansible/` (`ansible/docs/vps.md`).

## Firewall

`vps-publica` deixa entrar só `80` e `443` TCP, `41641` UDP (conexão direta do
Tailscale) e ICMP. O resto é descartado **antes de chegar na VM**: vale mesmo
com o UFW desligado, e barra as portas que o Docker publica por cima do UFW. A
administração continua pelo Tailscale SSH, que não depende de porta aberta.

Com `mailserver_piloto_habilitado = true`, o Terraform também abre a TCP/25
de entrada em IPv4 e configura o PTR do IPv4 primário para o nome do MX.
A liberação de **saída** é por conta na Hetzner. Veja a ordem de ativação no
[guia do Mailserver](../../ansible/docs/mailserver.md).

## Proteções

- `delete_protection` e `rebuild_protection` ligadas na Hetzner: nem o console
  apaga ou reinstala a VPS sem desligá-las antes.
- `prevent_destroy` no Terraform: o `apply` recusa qualquer plano que a apague.
- `ignore_changes` em `image`, `ssh_keys` e `user_data`: a VPS foi criada à
  mão, e mudar qualquer um deles a recriaria.

## Uso

O token da API vai no `terraform.tfvars` (fora do git; ver o `.example`).
Não dá para gerar pela CLI: o console da Hetzner exige login.

1. Console → projeto → **Security → API tokens** → *Generate API token*,
   leitura e escrita. Guarde no Vaultwarden.
2. `cp terraform.tfvars.example terraform.tfvars` e cole o token.
3. `terraform login`, se esta máquina ainda não tem
   (`../CLAUDE.md`, "Configurar o HCP Terraform").
4. ```bash
   terraform init
   terraform plan      # nunca aplicar com "destroy" ou "must be replaced"
   terraform apply
   ```

Confira o firewall, de fora da tailnet (outra rede, ou o celular no 4G):

```bash
IP=$(terraform state show -no-color hcloud_server.vps | awk -F'"' '/ ipv4_address /{print $2}')
nc -zv -w 5 "$IP" 22      # timeout
nc -zv -w 5 "$IP" 443     # succeeded
```
