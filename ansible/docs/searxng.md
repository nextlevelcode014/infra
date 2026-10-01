# SearXNG no Raspberry Pi

`playbooks/searxng.yml` aplica o SearXNG que antes subia por
`make up SVC=searxng` no `self-hosted`. O `searxng-core` sai pela VPN: vive na
netns do gluetun, que publica a WebUI na porta `8082` do IP Tailscale do Pi. O
acesso passa a ser `https://searxng.lab.nextlevelcode.pro`, pelo Caddy do Proxmox.
O sidecar Tailscale (`searxng.<tailnet>.ts.net`) **sai**.

O `settings.yml` agora é renderizado pelo Ansible
(`roles/searxng/templates/settings.yml.j2`), com o `secret_key` vindo do vault.
Para mudar uma engine, edite o template e reaplique.

## Testar no pi-lab

```bash
ansible-playbook playbooks/searxng.yml --ask-vault-pass --limit pi_staging
```

Confira: `curl -s -o /dev/null -w '%{http_code}\n' http://192.168.50.203:8082/`
deve responder `200`.

## Primeira aplicação no Pi

1. Copiar o `secret_key` atual para o vault. Com o mesmo valor, ninguém perde
   as preferências salvas no navegador.

   ```bash
   ssh ubuntu@nextlevelcode sudo grep secret_key /mnt/secure/appdata/searxng/core-config/settings.yml
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   O valor vai em `vault_searxng_secret_key`.

2. Aplicar o gluetun (porta `8082` nova; o role reinicia o `qbittorrent` e o
   `searxng-core`), o SearXNG e o Caddy:

   ```bash
   ansible-playbook playbooks/gluetun.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/searxng.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/searxng.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

3. Conferir:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://searxng.lab.nextlevelcode.pro/
   ssh ubuntu@nextlevelcode docker compose ls --filter name=searxng
   ```

   O primeiro deve responder `200`; o segundo, mostrar `/opt/searxng/compose.yml`.

   Se o Caddy der timeout, é a ACL do Tailscale: o grant `tag:caddy` → Pi
   precisa liberar `tcp:8082`. O mesmo aconteceu com o Vaultwarden (ver o plano de
   migração no `self-hosted`).

4. Remover o nó antigo `searxng` do console do Tailscale (Machines → `searxng`
   → Remove). O container do sidecar o Compose já removeu; o nó fica no
   console até ser apagado à mão, porque a API exigiria outro token só para isso.
   Confira que ele não aparece mais em `tailscale status`.

A partir daqui, não use mais `make up SVC=searxng` no `self-hosted`.
