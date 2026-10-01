# Restore da stack Arr

Este procedimento substitui a config da stack Arr
(`/mnt/secure/appdata/mnt/media-stack/config`, para onde aponta o symlink
`/mnt/media-stack/config`) pelo archive Borg mais recente com o prefixo
exato `arr-*`. O playbook normal (`playbooks/arr-stack.yml`) nunca executa
restore.

O archive tem só a config (bancos, `config.xml` com as API keys, config do
qBittorrent). A mídia em `/mnt/media-stack/data` **não** está nele.

## Antes de executar

1. Destrancar o LUKS no Pi e confirmar que está montado:

   ```bash
   ssh ubuntu@nextlevelcode mountpoint /mnt/secure
   ```

   Deve responder `/mnt/secure is a mountpoint`.
2. Se for uma máquina nova, aplicar primeiro `playbooks/arr-stack.yml`
   (ver [`arr-stack.md`](arr-stack.md)). Ele cria os symlinks, o compose em
   `/opt/arr` e instala o Borg com a chave e a senha do vault.
3. Conferir o caminho dentro do archive mais recente:

   ```bash
   ssh -t ubuntu@nextlevelcode sudo \
     BORG_PASSCOMMAND='cat /root/.borg-pass' \
     BORG_RSH='ssh -i /root/.ssh/id_ed25519' \
     borg list --short '<repo>::<arr-timestamp>' | head
   ```

   As linhas devem começar com `mnt/secure/appdata/mnt/media-stack/config/`.
   Os archives antigos, criados antes da troca do `backup-arr.sh`, usam outro
   caminho (`mnt/media-stack/config/...`) e só parte da config (as pastas
   `Backups/` dos *arr); **não** servem para este restore.

## Executar

```bash
ansible-playbook playbooks/arr-stack-restore.yml --ask-vault-pass \
  -e arr_restore_confirmation=RESTORE_ARR
```

A confirmação é obrigatória porque o role apaga a config atual antes de
copiar a do archive. A extração temporária fica em `/mnt/secure/restore/arr`,
dentro do LUKS, e é removida no fim.

## Conferir

```bash
ssh ubuntu@nextlevelcode docker compose -f /opt/arr/compose.yml ps
ssh ubuntu@nextlevelcode docker compose -f /opt/arr/compose.yml logs --tail=50 sonarr radarr
```

Abrir `https://sonarr.lab.nextlevelcode.pro` e `https://radarr.lab.nextlevelcode.pro`,
conferir a biblioteca e *System → Status*. Se as API keys mudaram, atualizar
`vault_arr_*` e reaplicar `playbooks/arr-stack.yml` para o decluttarr.
