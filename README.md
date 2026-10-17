# infra

A infraestrutura da NextLevelCode: um Proxmox e um Raspberry Pi em casa, e
uma VPS na Hetzner, todos ligados pelo Tailscale. Tudo que se aplica a essas
máquinas está aqui, em duas partes:

| Diretório | O quê |
|---|---|
| [`terraform/`](terraform/) | **cria** as máquinas: os LXCs do Proxmox e a VPS com o firewall da Hetzner |
| [`ansible/`](ansible/) | **configura** o que roda dentro de cada uma, do sistema aos serviços |

O Terraform registra cada LXC no state, e o Ansible lê esse state como
inventário. Por isso os dois moram no mesmo repo.

## As máquinas

```
                        internet
                           │
              Cloudflare (forge, status)
                           │
          ┌────────────────┴────────────────┐
          │  VPS Hetzner (`hetzner`)         │  domínios públicos,
          │  Caddy · Anubis · Uptime Kuma    │  monitoramento fora de casa
          └────────────────┬────────────────┘
                           │ tailnet (Tailscale)
        ┌──────────────────┴──────────────────┐
        │                                     │
┌───────┴────────────────────┐   ┌────────────┴───────────────────────┐
│ Proxmox (`pve`, notebook)  │   │ Raspberry Pi 5 (`nextlevelcode`)   │
│ LXCs: Caddy (*.lab),       │   │ LUKS em /mnt/secure; Jellyfin e    │
│ Forgejo, Vaultwarden,      │   │ *arr, AdGuard, FMD, SearXNG,       │
│ pi-lab (staging do Pi)     │   │ Immich, Nextcloud, exit node;      │
│                            │   │ reserva do Forgejo e Vaultwarden   │
└────────────────────────────┘   └────────────────────────────────────┘
```

Os serviços privados ficam em `https://<serviço>.lab.nextlevelcode.pro`, só
na tailnet. Tudo é acessado pelo Tailscale; a ACL da tailnet está em
[`ansible/tailscale/`](ansible/tailscale/README.md).
## Segredos e valores locais

Nada sensível entra no git. Os segredos do Ansible ficam no `vault.yml`
cifrado, os do Terraform no `terraform.tfvars`, e os dois têm um
`.example` versionado com o que vai em cada chave. O nome da tailnet e os
IPs Tailscale também ficam fora: nos docs eles aparecem como
`<tailnet>.ts.net` e `<ts_ip>`.

Por estarem fora do git, esses arquivos só existem no notebook: as cópias
fora da infra, e como fazê-las, estão em
[`docs/fora-da-infra.md`](docs/fora-da-infra.md).

## Fluxo de mudança

Nada vai direto para o `main`: branch, PR no Forgejo, squash merge. Passo
que não dá para automatizar (console, login, token) entra no doc do serviço,
na ordem em que acontece, com o comando e como conferir.

## Decisões

O porquê das escolhas que não são óbvias pelo código fica em
[`docs/decisoes/`](docs/decisoes/README.md), um ADR por decisão. Antes de
desfazer algo que parece estranho, procure lá.
