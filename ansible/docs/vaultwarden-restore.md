# Restore do Vaultwarden

Substitui o `vw-data/` do Vaultwarden (banco SQLite, anexos, chaves) pelo
archive `vaultwarden-*` mais recente feito pela máquina de origem
(`vaultwarden_restore_source_host`, por padrão o LXC `vaultwarden`). Archives
de outras máquinas com o mesmo prefixo são ignorados. O `vaultwarden.yml`
nunca restaura.

O restore para a stack, **apaga** o `vw-data/`, copia o do archive e sobe.
Token admin e SMTP não vêm do archive: o compose já os traz do vault do
Ansible. Duas instâncias no ar ao mesmo tempo separam os cofres: restaure só
onde vai ficar a única.

## Antes de executar

1. **A outra instância está parada.** Restaurando no LXC, o Vaultwarden do
   Pi está em standby; restaurando no Pi, o do LXC está fora ou parado
   (`docs/pi-recuperacao.md`).

   Confira: `docker ps --filter name=vaultwarden` no outro host não lista
   nada.

2. **O Vaultwarden está instalado no destino** (o restore recusa sem o
   `docker-compose.yml`): no LXC, `playbooks/vaultwarden.yml`
   (`docs/vaultwarden.md`, passos 1 a 4); no Pi,
   `playbooks/pi-recuperacao.yml`. O Borg (chave, senha, `known_hosts`) vem
   junto, pelo `borg_client`.

3. **No Pi, o LUKS aberto** (`docs/pi.md`, "A cada boot"). O playbook confere
   e para se `/mnt/secure` não estiver montado.

## Executar

**No LXC, com o backup do LXC** (perdeu os dados, LXC recriado):

```bash
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
  -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
```

**No Pi, com o backup do LXC** (Proxmox fora; faz parte de
`docs/pi-recuperacao.md`, "Assumir", que diz o antes e o depois):

```bash
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
  --limit rpi -e restore_on_pi=true -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
```

**No LXC, com o backup do Pi** (volta da contingência,
`docs/pi-recuperacao.md`, "Voltar ao Proxmox"). O archive é da máquina
`ubuntu`, e os dados estão nele com o caminho do Pi:

```bash
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
  -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN \
  -e vaultwarden_restore_source_host=ubuntu \
  -e vaultwarden_restore_data_archive_path=mnt/secure/appdata/vaultwarden/vw-data
```

A confirmação é obrigatória porque o role apaga o `vw-data/` atual antes de
copiar o do archive. Em todos os casos, confira na task "Extrair o archive"
que a data é a do backup esperado.

## Conferir

No host restaurado:

```bash
docker compose -f <vaultwarden_dir>/docker-compose.yml ps
docker compose -f <vaultwarden_dir>/docker-compose.yml logs --tail=100 vaultwarden
```

(`vaultwarden_dir`: `/opt/vaultwarden` no LXC, `/mnt/secure/appdata/vaultwarden`
no Pi.)

Depois, de um aparelho da tailnet: login em `https://vault.lab.nextlevelcode.pro`
com a sua conta, o item salvo por último aparece, e um cliente (extensão ou
celular) sincroniza.

## Ensaio no pi-lab

Restaura o archive real da produção no pi-lab, sem tocar no LXC:

```bash
ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,pi_staging
ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit pi_staging
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass --limit pi_staging \
  -e restore_on_pi=true -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
```

Confira: `curl -s http://192.168.50.203:8083/alive` devolve uma data, e
`curl -s http://192.168.50.203:8083/api/config` mostra o servidor de pé. O
login pelo navegador não funciona ali (sem HTTPS, o cliente web recusa). O
pi-lab não tem LUKS: o cofre fica num volume sem criptografia, então limpe no
fim:

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```
