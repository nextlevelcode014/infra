# Hetzner Cloud

A VPS (`ubuntu-4gb-fsn1-1`, CX23 em Falkenstein) e o firewall da Hetzner
Cloud na frente dela. Stack separada da do Proxmox, com **state próprio**
(`hetzner/terraform.tfstate`): um erro aqui não toca os containers, e vice-
versa. O que roda dentro da VPS é o repo `ansible` (`docs/vps.md`).

## Firewall

`vps-publica` deixa entrar só `80` e `443` TCP, `41641` UDP (conexão direta do
Tailscale) e ICMP. O resto é descartado **antes de chegar na VM**: vale mesmo
com o UFW desligado, e barra as portas que o Docker publica por cima do UFW. A
administração continua pelo Tailscale SSH, que não depende de porta aberta.

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
3. ```bash
   terraform init
   terraform plan      # nunca aplicar com "destroy" ou "must be replaced"
   terraform apply
   ```

Confira o firewall, de fora da tailnet (outra rede, ou o celular no 4G):

```bash
nc -zv -w 5 <ip-publico-da-vps> 22      # timeout
nc -zv -w 5 <ip-publico-da-vps> 443     # succeeded
```
