# Restore da stack Arr

Substitui a config de todos os apps da stack (bancos, `config.xml` com as API
keys, config do qBittorrent) pelo archive `arr-*` mais recente feito pelo Pi
(`arr_restore_source_host: ubuntu`). Grava direto no caminho real, no LUKS
(`/mnt/secure/appdata/mnt/media-stack/config`). **A mídia não está no
archive.** O `arr-stack.yml` nunca restaura.

## Antes de executar

1. **LUKS aberto** (`docs/pi.md`, "A cada boot"). O restore confere e para se
   `/mnt/secure` não estiver montado. A extração temporária também fica no
   LUKS (`/mnt/secure/restore/arr`): a config tem API keys, e a raiz não tem
   espaço.

2. **A stack instalada ou não, tanto faz.** Com ela em `/opt/arr`, o restore
   para, troca a config e sobe. Sem ela (Pi novo), só põe a config no lugar,
   e o `arr-stack.yml` sobe depois: é o que o `pi-completo.yml` faz
   (`docs/pi-reconstrucao.md`).

## Executar

**No Pi:**

```bash
ansible-playbook playbooks/arr-stack-restore.yml --ask-vault-pass --limit rpi \
  -e arr_restore_confirmation=RESTORE_ARR
```

Sempre com `--limit`: o playbook mira `pi_hosts`, que inclui o pi-lab. A
confirmação é obrigatória porque o role apaga a config atual antes de copiar
a do archive.

**No Pi novo, junto com todo o resto:** `docs/pi-reconstrucao.md`, com
`-e pi_restaurar_tudo=RESTAURAR_PI`, que vale como a confirmação deste.

Confira na task "Extrair o archive" que a data é a do backup esperado. O
restore para se o archive não tiver o `config.xml` do Sonarr e do Radarr.

## Conferir

```bash
ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker compose -f /opt/arr/compose.yml ps
ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker compose -f /opt/arr/compose.yml logs --tail=50 sonarr radarr
```

Todos `Up`. Em `https://sonarr.lab.nextlevelcode.pro` e
`https://radarr.lab.nextlevelcode.pro`, a biblioteca e *System → Status* sem
erro de banco. Se as API keys do archive são outras que as do vault (o vault
mudou depois do backup), acerte o vault e reaplique `arr-stack.yml`, para o
decluttarr.

## Ensaio no pi-lab

O pi-lab restaura o archive real de produção, só para leitura: ele tem o
acesso ao Borg, mas `borg_backup_enabled: false` impede que escreva lá. A
config restaurada traz as API keys e as credenciais dos indexadores, então
**limpe no fim**.

O restore deixa a stack **parada** no pi-lab (`arr_restore_start_stack:
false`): subir tudo faria o qBittorrent baixar de novo os torrents e os
*arr dispararem buscas.

1. Restaurar:

   ```bash
   ansible-playbook playbooks/arr-stack-restore.yml --ask-vault-pass --limit pi_staging \
     -e arr_restore_confirmation=RESTORE_ARR
   ```

   Anote o archive escolhido e a duração.

2. Subir só os apps a conferir, sem qBittorrent, Prowlarr e decluttarr:

   ```bash
   ssh root@10.50.0.203 docker compose -f /opt/arr/compose.yml up -d sonarr radarr bazarr jellyfin jellyseerr
   ```

3. Conferir em `http://localhost:<porta>` (pelo túnel, `docs/pi.md`, "pi-lab"): Sonarr (`8989`) e Radarr
   (`7878`) com séries, filmes e perfis; Jellyfin (`8096`) com usuários e
   bibliotecas (sem mídia, os itens aparecem indisponíveis); Jellyseerr
   (`5055`) com os pedidos. Em *System → Status* dos *arr, nenhum erro de
   banco corrompido.

4. Limpar:

   ```bash
   ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
   ```

   **Não rode `arr-stack.yml` no pi-lab antes de limpar**: ele sobe a stack
   inteira, com qBittorrent.
