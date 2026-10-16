# ansible

Configuração das máquinas do homelab da NextLevelCode: o que roda dentro de
cada máquina, do sistema aos serviços. Criar máquina (os containers do
Proxmox) é do [`terraform/`](../terraform/); aqui só se configura. Os
comandos abaixo rodam de dentro de `ansible/`.

## Antes de rodar

1. **Ansible e as dependências** (collections e roles vendidos):

   ```bash
   ansible-galaxy install -r requirements.yml
   ```

2. **Vault.** Os segredos ficam em `inventory/group_vars/all/vault.yml`,
   cifrado e fora do git (`.gitignore`). O modelo, com o que vai em cada
   chave e como gerar, é o [`vault.yml.example`](inventory/group_vars/all/vault.yml.example).
   Todo comando pede a senha do vault, mesmo para hosts que não usam
   segredo: o Ansible carrega todo o `group_vars/all/`.

3. **Tailscale** na máquina de onde se roda: Pi, VPS e Proxmox são
   alcançados pela tailnet.

4. **`terraform apply` feito em `../terraform`:** os LXCs não estão em
   arquivo de inventário nenhum, vêm do state.

   ```bash
   ansible-inventory --graph
   ```

   Confira: aparecem os grupos `proxmox`, `lxc` (com `caddy`, `forgejo`,
   `vaultwarden`, `pi-lab`), `pi_hosts` e `vps`. O grupo `lxc` vazio é o
   state do Terraform faltando.

## Rodar

Um playbook por serviço ou host, em `playbooks/`:

```bash
ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi --check --diff
ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit rpi
```

- **Playbook do Pi sempre com `--limit`:** `rpi` para o Pi, `pi_staging` para
  o pi-lab. O grupo `pi_hosts` tem os dois, e sem o limit o playbook roda
  nos dois.
- **Restore nunca é efeito colateral:** os `*-restore.yml` são playbooks
  separados e pedem uma confirmação explícita (`-e <serviço>_restore_confirmation=...`).
- O `site.yml` importa os playbooks principais em ordem. Ele recusa o
  pi-lab: rode com `--limit 'all:!pi_staging'`. Mesmo assim, prefira o
  playbook do serviço que mudou.

## Estrutura

| Caminho | O quê |
|---|---|
| `inventory/` | quatro fontes: `static.ini` (Proxmox), `pi.yml` (Pi e pi-lab), `vps.yml`, `terraform.yml` (LXCs, do state) |
| `inventory/group_vars/` | variáveis por grupo; `all/vars.yml` tem o que é comum (Borg, Caddy, rotas do `*.lab`) |
| `playbooks/` | um por serviço ou host, mais restores, `pi-completo.yml` e `pi-atualizar.yml` |
| `roles/` | um role por serviço, as bases (`pi_host`, `vps_host`, `common`), `borg_client` e os roles vendidos |
| `docs/` | um runbook por serviço e por host |
| `tailscale/` | cópia revisada da ACL da tailnet, aplicada à mão no console |

## Documentação

- [`docs/README.md`](docs/README.md): índice dos docs, o modelo de cada
  um e as regras. Cada serviço tem o seu (instalação, backup, operação) e,
  quando há playbook de restore, um `<serviço>-restore.md`.
- [`docs/backup.md`](docs/backup.md): como o backup funciona (borgmatic, um
  repositório Borg, um monitor push por serviço).
- [`docs/pi-reconstrucao.md`](docs/pi-reconstrucao.md) e
  [`docs/pi-recuperacao.md`](docs/pi-recuperacao.md): o Pi do zero, e o Pi
  no lugar do Proxmox.
- [`CLAUDE.md`](CLAUDE.md): o papel de cada playbook e role, as convenções e
  as armadilhas já encontradas. Vale ler antes de mudar qualquer coisa.
