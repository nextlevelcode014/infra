# Pi de recuperação: Forgejo e Vaultwarden

A produção do Forgejo e do Vaultwarden roda nos LXCs do Proxmox. O Pi fica
pronto para assumir se o Proxmox cair, sem nunca rodar os dois ao mesmo tempo
que a produção: duas instâncias aceitando escrita separam os dados.

`playbooks/pi-recuperacao.yml` deixa o Pi em **standby**:

- compose renderizado e imagens baixadas (o restore não depende de registry na
  hora do desastre);
- dados no LUKS (`/mnt/secure/appdata/forgejo` e `.../vaultwarden`);
- containers **parados** e **sem cron de backup** (um archive do Pi com o mesmo
  prefixo viraria o mais recente para o restore);
- Vaultwarden na porta `8083` do IP Tailscale (a `8080` está ocupada no Pi).

Subir é sempre pelo restore, com o archive mais recente da produção. O restore
escolhe só archives feitos pela máquina de produção (`*_restore_source_host`):
o Pi antigo deixou archives `vaultwarden-*` e `forgejo-*` no mesmo repositório,
e sem o filtro o mais recente podia ser um deles.

## Preparar (uma vez)

1. **Nenhum cliente pode usar as instâncias antigas do Pi.** Em cada cliente
   Bitwarden (extensão, celular, desktop), o servidor tem que ser
   `https://vault.lab.nextlevelcode.pro`, e não `vaultwarden.<tailnet>.ts.net`.
   Se algo foi salvo só no Pi, exporte desse cliente e importe na produção antes
   de trocar. Os remotes git têm que apontar para `forgejo-lxc:2222`.

2. **Aplicar o standby.** Isto **derruba** o Forgejo e o Vaultwarden antigos do
   Pi, os sidecars Tailscale e o Funnel público do Forgejo:

   ```bash
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi --check --diff
   ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi
   ```

   Confira: `ssh ubuntu@nextlevelcode docker ps -a --filter name=forgejo --filter name=vaultwarden`
   não lista nada, e `crontab -l` do root não tem backup de Forgejo nem de
   Vaultwarden.

3. **Remover os nós antigos** `forgejo` e `vaultwarden` no console do Tailscale
   (Machines → Remove). Os containers saíram; os nós ficam listados até serem
   apagados à mão.

## No desastre (Proxmox fora)

1. Confirmar que o Proxmox está mesmo fora e decidir que o Pi assume. Nunca
   com a produção no ar.
2. Destravar o LUKS: `ssh -t ubuntu@nextlevelcode secure-unlock`.
3. Restaurar e subir cada serviço:

   ```bash
   ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass \
     --limit rpi -e restore_on_pi=true -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
   ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass \
     --limit rpi -e restore_on_pi=true -e forgejo_restore_confirmation=RESTORE_FORGEJO
   ```

4. Apontar o acesso para o Pi: Vaultwarden em `nextlevelcode:8083`, Forgejo
   em `nextlevelcode:3000` (web) e `nextlevelcode:2222` (SSH). A troca de rota no
   Caddy da VPS e do DNS interno é a Fase 8 do plano de migração e ainda não tem
   runbook.
5. **Enquanto o Pi for a produção, não rode o `pi-recuperacao.yml`:** ele
   voltaria a derrubar os serviços.

O caminho de volta (sincronizar o que foi escrito no Pi de volta aos LXCs) ainda
não está documentado nem ensaiado.

## Ensaio no pi-lab

Restaura os archives reais da produção no pi-lab, que não tem LUKS de verdade:
os repositórios e o cofre ficam num volume sem criptografia. Limpe no fim.

```bash
ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,pi_staging
ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit pi_staging
ansible-playbook playbooks/vaultwarden-restore.yml --ask-vault-pass --limit pi_staging \
  -e restore_on_pi=true -e vaultwarden_restore_confirmation=RESTORE_VAULTWARDEN
ansible-playbook playbooks/forgejo-restore.yml --ask-vault-pass --limit pi_staging \
  -e restore_on_pi=true -e forgejo_restore_confirmation=RESTORE_FORGEJO
```

Confira:

- Vaultwarden: `http://192.168.50.203:8083/alive` responde, e o login com a sua
  conta mostra o cofre (o cliente precisa aceitar HTTP de teste; um
  `curl -s http://192.168.50.203:8083/api/config` já mostra que o servidor está de pé);
- Forgejo: `http://192.168.50.203:3000` lista os repositórios, com o `main` do
  `ansible` igual ao da produção.

Anote a duração de cada restore. Para limpar:

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```

Derruba todas as stacks, apaga os dados restaurados e tira a chave e a senha
do Borg do pi-lab. A base (Docker, redes, imagens) fica, para o próximo ensaio.
