# 0002. Terraform cria a máquina, Ansible configura

- **Status:** Aceita
- **Data:** 2026-10-15
- **Fonte:** `CLAUDE.md` da raiz e de cada parte; os dois repos viraram um só
  no #1

## Contexto

O infra tem máquinas de três tipos (LXC do Proxmox, VPS da Hetzner e o Pi,
que é físico) e serviços que mudam muito mais que elas. Misturar "existir a
máquina" com "o que roda nela" deixa um `apply` capaz de recriar um container
só para trocar uma config.

## Decisão

`terraform/` só cria máquinas. `ansible/` só configura o que roda dentro
delas. O Ansible enxerga os LXCs pelo state do Terraform (grupo `lxc`), sem
inventário escrito à mão.

## Alternativas descartadas

- **Provisioners do Terraform** (`remote-exec`): rodam uma vez, na criação;
  config que muda depois fica sem dono.
- **Ansible criando os LXCs** (`community.proxmox`): sem plano nem state, um
  container apagado à mão passa despercebido.

## Consequências

- Mudança que toca as duas partes vai num PR só.
- Sem `terraform apply`, o grupo `lxc` fica vazio.
- Exceção única: o role `lxc_flags` provisiona (aplica flags que o Proxmox
  reserva ao `root@pam`, que o token do Terraform não tem). Motivo em
  `ansible/roles/lxc_flags/README.md`.
