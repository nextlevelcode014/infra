# Backup (borgmatic)

Todo serviço com dado faz backup no mesmo repositório Borg (BorgBase), cada um
com o seu prefixo: `forgejo-*`, `vaultwarden-*`, `arr-*`, `adguard-*`, `fmd-*`
e `uptime-kuma-*`. A exceção é o Immich (`immich-*`), grande demais para a
cota: vai para um repositório próprio no Borg offsite
(`docs/borg-offsite.md`, ADR 0007), passando `borg_backup_repo`. O
Nextcloud AIO usa o Borg dele, para a mesma máquina (`docs/nextcloud.md`). Quem roda é o
[borgmatic](https://torsion.org/borgmatic/); os restores continuam chamando o
`borg` direto (`roles/borg_restore`, `docs/*-restore.md`).

## Como funciona

- O role `borg_client` instala a chave, a senha, o `known_hosts`, o borgmatic
  (pacote do Ubuntu) e **um timer por host**: o `borgmatic.timer`, que roda
  `borgmatic -c /etc/borgmatic`. Ele lê todos os `.yaml` do diretório e faz
  um serviço depois do outro.
- Cada role de serviço põe o seu `/etc/borgmatic/<serviço>.yaml` com
  `include_role: borg_client, tasks_from: backup`. Esse config diz o que
  guardar, o que excluir, como parar e subir a stack em volta do
  `borg create`, a retenção (7 diários, 4 semanais, 3 mensais, só dentro do
  prefixo dele) e para onde avisar.
- Ao fim de cada serviço, o borgmatic avisa um **monitor push** no Uptime
  Kuma (grupo *Backups*). O monitor cai com o aviso de falha, na hora, ou
  quando passa 26 h sem aviso nenhum. As duas coisas viram e-mail.
- Não há `check` do repositório: com um repositório só, cada serviço leria
  tudo de novo. Os scripts antigos também não faziam.

| Host | Horário | Serviços, em ordem |
|---|---|---|
| `forgejo` (LXC) | 02:00 | forgejo |
| `vaultwarden` (LXC) | 02:15 | vaultwarden |
| `pi` | 02:30 | adguard, arr, fmd, immich |
| `hetzner` (VPS) | 03:00 | uptime-kuma |

Os horários ficam em `borg_backup_times` (`group_vars/all/vars.yml`). Entre
hosts a trava do Borg ainda é disputada (`borg_lock_wait`: 10 min). O Immich
não entra nessa conta: o repositório dele é outro, e ele roda por último no
Pi.

O timer é `Persistent`: um host desligado na hora roda o backup assim que
ligar. No Pi, isso acontece antes do `secure-unlock`. O config exige que os
caminhos existam (`source_directories_must_exist`), então o backup falha e
avisa em vez de gravar um archive vazio. Rode o backup à mão depois do
unlock (abaixo).

O `borgmatic.service` vem do role da borgbase com `ConditionACPower=true`:
com o notebook do Proxmox na bateria (queda de luz), os LXCs pulam o backup
da noite sem erro. Quem avisa é o monitor, depois de 26 h sem aviso.

## Rodar, ver e conferir

```bash
# Rodar agora (todos os serviços do host, ou só um):
sudo systemctl start borgmatic.service
sudo borgmatic -c /etc/borgmatic/fmd.yaml --verbosity 1 --stats

# Log da última execução do timer:
sudo journalctl -u borgmatic --since today

# Próxima execução:
systemctl list-timers borgmatic.timer

# Archives de um serviço:
sudo borgmatic -c /etc/borgmatic/fmd.yaml repo-list
```

`journalctl` deve terminar sem `ERROR` e o monitor *Backup <serviço>* deve
ficar verde no Uptime Kuma.

## Serviço novo

1. No role do serviço, depois do compose:

   ```yaml
   - name: Configurar o backup do <serviço>
     ansible.builtin.include_role:
       name: borg_client
       tasks_from: backup
     vars:
       borg_backup_name: <serviço>          # prefixo dos archives e do monitor
       borg_backup_sources: [/caminho/absoluto]
       borg_backup_commands:                 # opcional: parar e subir
         - before: action
           when: [create]
           run: [docker compose -f /opt/<serviço>/compose.yml stop <container>]
         - after: action
           when: [create]
           run: &up [docker compose -f /opt/<serviço>/compose.yml start <container>]
         - after: error
           run: *up
   ```

   O `after: error` é o que sobe a stack de volta se o backup falhar no meio.
   O cabeçalho de `roles/borg_client/tasks/backup.yml` lista as outras
   variáveis, inclusive `borg_backup_repo`, para outro repositório que não o
   compartilhado (como o Immich).
2. `<serviço>: <Rótulo>` em `uptime_kuma_backups`
   (`group_vars/vps/monitors.yml`) e reaplicar `playbooks/uptime-kuma.yml`.
3. Host novo com backup: uma entrada em `borg_backup_times` e o grant de
   `tcp:443` para `tag:caddy-vps` na ACL (`tailscale/policy.hujson`). Sem o
   grant o backup roda, mas o aviso não chega, e o monitor cai em 26 h.
   Para conferir a rede de dentro do host (pelo IP Tailscale: no desktop,
   `forgejo-lxc` é o SSH do Git):

   ```bash
   ssh root@forgejo-lxc curl -s -o /dev/null -w '%{http_code}\n' https://uptime.lab.nextlevelcode.pro/api/push/x
   ```

   Qualquer código HTTP (404 inclusive) prova que a rede passa; `000` é a
   ACL bloqueando.

## Histórico

Até outubro de 2026 cada serviço tinha um `backup-*.sh` e um cron próprios
(#58). A troca apagou os dois em todos os hosts. Se algum dia aparecer um
cron `Backup Borg do ...` no `crontab -l` do root, ele é dessa época e roda
em dobro com o borgmatic: apague.
