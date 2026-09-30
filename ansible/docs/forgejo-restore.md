# Restore do Forgejo

Este procedimento substitui os dados do Forgejo pelo archive Borg mais recente
com o prefixo exato `forgejo-*`. O playbook normal (`playbooks/forgejo.yml`)
nunca executa restore.

## Antes de executar

1. Confirmar que o Proxmox está indisponível ou que esta é a migração inicial,
   e que este host será temporariamente a única instância autoritativa.
2. Confirmar que o volume onde `forgejo_dir` está montado e desbloqueado.
3. Confirmar que a execução normal de `playbooks/forgejo.yml` já instalou o
   pacote `borgbackup` e distribuiu a chave SSH e a senha do Borg a partir do
   vault Ansible.
4. Preencher as variáveis `vault_forgejo_borg_*` no vault Ansible, incluindo
   `vault_forgejo_borg_password` e `vault_forgejo_borg_ssh_private_key`.
5. Aplicar primeiro `playbooks/forgejo.yml` para preparar o Compose, as imagens
   e os diretórios, se esta for uma máquina nova.

Para restaurar o archive legado criado no Pi, informe também os caminhos
antigos do archive:

```bash
-e forgejo_restore_data_archive_path=mnt/secure/appdata/forgejo/forgejo
```

## Executar

```bash
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
  -e forgejo_restore_confirmation=RESTORE_FORGEJO
```

A confirmação é obrigatória porque o role remove os diretórios atuais do
Forgejo e do PostgreSQL antes de carregar o dump.

## Conferir

```bash
docker compose -f /opt/forgejo/docker-compose.yml ps
docker compose -f /opt/forgejo/docker-compose.yml logs --tail=100 server db
```

Validar login, leitura de repositórios, clone, push SSH e webhooks antes de
anunciar o serviço como recuperado. O domínio e a rota de contingência do Caddy
continuam sendo ativados manualmente conforme o runbook da infraestrutura.
