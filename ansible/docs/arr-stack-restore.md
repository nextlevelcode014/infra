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

## Ensaio no pi-lab

O pi-lab restaura o archive real de produção, só para leitura: ele tem o acesso
ao Borg, mas `borg_backup_enabled: false` impede que escreva lá. A config
restaurada traz as API keys e as credenciais dos indexadores, então o pi-lab
passa a guardar segredos reais — destrua o volume ou reaplique a stack limpa
depois do ensaio.

O restore deixa a stack **parada** (`arr_restore_start_stack: false` no
`pi_staging`): subir tudo faria o qBittorrent baixar de novo os torrents e os
*arr dispararem buscas.

1. Rodar o restore:

   ```bash
   ansible-playbook playbooks/arr-stack-restore.yml --ask-vault-pass --limit pi_staging \
     -e arr_restore_confirmation=RESTORE_ARR
   ```

   Anote o archive escolhido (task "Guardar o nome do archive selecionado") e a
   duração.

2. Subir só os apps a conferir, sem qBittorrent, Prowlarr e decluttarr:

   ```bash
   ssh root@192.168.50.203 docker compose -f /opt/arr/compose.yml up -d sonarr radarr bazarr jellyfin jellyseerr
   ```

3. Conferir em `http://192.168.50.203:<porta>`: Sonarr (`8989`) e Radarr (`7878`)
   com séries, filmes e perfis; Jellyfin (`8096`) com usuários e bibliotecas
   (sem mídia, os itens aparecem indisponíveis); Jellyseerr (`5055`) com os
   pedidos. Em *System → Status* dos *arr, nenhum erro de banco corrompido.

4. Limpar: parar a stack e apagar a config de produção do pi-lab.

   ```bash
   ssh root@192.168.50.203 'docker compose -f /opt/arr/compose.yml down && rm -rf /mnt/secure/appdata/mnt/media-stack/config/*'
   ```

   **Não rode `arr-stack.yml` no pi-lab antes de limpar**: ele sobe a stack
   inteira, com qBittorrent.
