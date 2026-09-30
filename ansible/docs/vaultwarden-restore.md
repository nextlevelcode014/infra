# Restore do Vaultwarden

Este procedimento substitui o diretório `vw-data/` do Vaultwarden pelo
archive Borg mais recente com o prefixo exato `vaultwarden-*`. O playbook
normal (`playbooks/vaultwarden.yml`) nunca executa restore.

O `.env` do Vaultwarden (com `ADMIN_TOKEN` e demais segredos) **não**
está no archive — é o seed que reconstrói tudo. Deve estar disponível
via Ansible Vault antes do restore.

## Antes de executar

1. Confirmar que o Proxmox está indisponível ou que esta é a migração
   inicial, e que este host será temporariamente a única instância
   autoritativa.
2. Confirmar que o volume onde `vaultwarden_dir` está montado e desbloqueado.
3. Confirmar que a execução normal de `playbooks/vaultwarden.yml` já
   instalou o pacote `borgbackup` e distribuiu a chave SSH e a senha do
   Borg a partir do vault Ansible (os mesmos arquivos do Forgejo: ambos
   usam o mesmo repositório).
4. Preencher `vault_vaultwarden_admin_token` no vault Ansible.
5. Aplicar primeiro `playbooks/vaultwarden.yml` para preparar o Compose,
   as imagens e os diretórios, se esta for uma máquina nova.

Para restaurar o archive legado criado no Pi, informe também o caminho
antigo do archive:

```bash
-e vaultwarden_restore_data_archive_path=home/ubuntu/self-hosted/vaultwarden/vw-data
```

## Executar

```bash
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
  -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
```

A confirmação é obrigatória porque o role remove o diretório `vw-data/`
atual antes de copiar os dados extraídos do archive.

## Conferir

```bash
docker compose -f /opt/vaultwarden/docker-compose.yml ps
docker compose -f /opt/vaultwarden/docker-compose.yml logs --tail=100 vaultwarden
```

Validar login, sincronização de clientes e recuperação antes de anunciar
o serviço como recuperado. O domínio e a rota de contingência do Caddy
continuam sendo ativados manualmente conforme o runbook da
infraestrutura.