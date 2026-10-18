# Restore do Forgejo

Substitui os repositórios (`forgejo/`) e o banco do Forgejo pelo archive
`forgejo-*` mais recente feito pela máquina de origem
(`forgejo_restore_source_host`, por padrão o LXC `forgejo`). Archives de
outras máquinas com o mesmo prefixo são ignorados. O `forgejo.yml` nunca
restaura.

O restore para a stack, **apaga** `forgejo/` e `postgres/`, copia os dados do
archive, carrega o dump num Postgres vazio e sobe tudo. Duas instâncias no ar
ao mesmo tempo separam os dados: restaure só onde vai ficar a única.

## Antes de executar

1. **A outra instância está parada.** Restaurando no LXC, o Forgejo do Pi
   está em standby; restaurando no Pi, o do LXC está fora ou parado
   (`docs/pi-recuperacao.md`).

   Confira: `docker ps --filter name=forgejo` no outro host não lista nada.

2. **O Forgejo está instalado no destino** (o restore recusa sem o
   `docker-compose.yml`): no LXC, `playbooks/forgejo.yml`
   (`docs/forgejo.md`, passos 1 a 4); no Pi, `playbooks/pi-recuperacao.yml`.
   O Borg (chave, senha, `known_hosts`) vem junto, pelo `borg_client`.

3. **No Pi, o LUKS aberto** (`docs/pi.md`, "A cada boot"). O playbook confere
   e para se `/mnt/secure` não estiver montado.

## Executar

**No LXC, com o backup do LXC** (perdeu os dados, LXC recriado):

```bash
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
  -e forgejo_restore_confirmation=RESTORE_FORGEJO
```

**No Pi, com o backup do LXC** (Proxmox fora; faz parte de
`docs/pi-recuperacao.md`, "Assumir", que diz o antes e o depois):

```bash
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
  --limit rpi -e restore_on_pi=true -e forgejo_restore_confirmation=RESTORE_FORGEJO
```

**No LXC, com o backup do Pi** (volta da contingência,
`docs/pi-recuperacao.md`, "Voltar ao Proxmox"). O archive é da máquina
`ubuntu`, e os dados estão nele com o caminho do Pi:

```bash
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
  -e forgejo_restore_confirmation=RESTORE_FORGEJO \
  -e forgejo_restore_source_host=ubuntu \
  -e forgejo_restore_data_archive_path=mnt/secure/appdata/forgejo/forgejo
```

A confirmação é obrigatória porque o role apaga os dados atuais antes de
carregar os do archive. Em todos os casos, confira na task "Extrair o
archive" que a data é a do backup esperado.

## Conferir

No host restaurado:

```bash
docker compose -f <forgejo_dir>/docker-compose.yml ps
docker compose -f <forgejo_dir>/docker-compose.yml logs --tail=100 server db
```

(`forgejo_dir`: `/opt/forgejo` no LXC, `/mnt/secure/appdata/forgejo` no Pi.)

Depois, de um computador da tailnet: login em
`https://forge.nextlevelcode.pro`, um repositório com o último commit que
você esperava, e `git ls-remote origin` num clone (o SSH do Git).

## Ensaio no pi-lab

Restaura o archive real da produção no pi-lab, sem tocar no LXC:

```bash
ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,pi_staging
ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit pi_staging
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass --limit pi_staging \
  -e restore_on_pi=true -e forgejo_restore_confirmation=RESTORE_FORGEJO
```

Confira: `http://localhost:3000` (pelo túnel, `docs/pi.md`, "pi-lab") lista os repositórios, com o `main` do
`ansible` igual ao da produção. O pi-lab não tem LUKS: os repositórios ficam
num volume sem criptografia, então limpe no fim:

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```
