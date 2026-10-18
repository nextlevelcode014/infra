# Restore do FMD

Substitui o banco do FMD (`fmddata/`) e, quando há sidecar, o estado do nó
Tailscale (`tailscale-state/`) pelo archive `fmd-*` mais recente feito pelo Pi
(`fmd_restore_source_host: ubuntu`). Com o estado de volta, o sidecar é o
mesmo nó de antes, e o Funnel continua em `fmd.<tailnet>.ts.net` sem
aprovação nova. O `fmd.yml` nunca restaura.

O FMD fica fora do momento em que o restore para a stack até ela subir de
novo, alguns segundos.

## Antes de executar

1. **LUKS aberto** (`docs/pi.md`, "A cada boot"). O restore confere e para se
   `/mnt/secure` não estiver montado: sem ele, o banco e a identidade do nó
   iriam para a raiz em claro.

2. **O FMD instalado ou não, tanto faz.** Com a stack em `/opt/fmd`, o
   restore para, troca os dados e sobe. Sem ela (Pi novo), só põe os dados no
   lugar, e o `fmd.yml` sobe depois já com eles: é o que o `pi-completo.yml`
   faz (`docs/pi-reconstrucao.md`).

3. **Nenhum outro nó usando a identidade.** O estado restaurado é o do nó
   `fmd` da tailnet. Se outro sidecar estiver no ar com ele (um Pi antigo
   ainda ligado), os dois disputam o mesmo nó.

## Executar

**No Pi:**

```bash
ansible-playbook playbooks/fmd-restore.yml --ask-vault-pass --limit rpi \
  -e fmd_restore_confirmation=RESTORE_FMD
```

Sempre com `--limit`: o playbook mira `pi_hosts`, que inclui o pi-lab.

**No Pi novo, junto com todo o resto:** `docs/pi-reconstrucao.md`, com
`-e pi_restaurar_tudo=RESTAURAR_PI`, que vale como a confirmação deste.

Confira na task "Extrair o archive" que a data é a do backup esperado.

## Conferir

```bash
ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker ps --filter name=fmd
ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker exec fmd-tailscale tailscale funnel status
```

Os três containers estão `Up`, e o Funnel aparece `on` em
`fmd.<tailnet>.ts.net` (se aparecer `fmd-1`, o estado não voltou e o nó é
novo: `docs/fmd.md`, "Instalação", passo 3). Depois, o login em
`https://fmd.lab.nextlevelcode.pro` mostra os aparelhos com a última
localização de antes do backup.

## Ensaio no pi-lab

O pi-lab não tem sidecar, e o restore pula o estado do nó lá
(`fmd_tailscale_sidecar: false`): o ensaio prova o banco, não o Funnel.

```bash
ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit pi_staging
ansible-playbook playbooks/fmd-restore.yml --ask-vault-pass --limit pi_staging \
  -e fmd_restore_confirmation=RESTORE_FMD
```

Confira: `ssh root@10.50.0.203 ls -l /mnt/secure/appdata/fmd/fmddata/db`
mostra o `fmd.sqlite` com o tamanho do de produção, e
`ssh root@10.50.0.203 'wget -S -O /dev/null http://10.50.0.203:8085 2>&1 | grep HTTP/'` mostra
`HTTP/1.1 200 OK`. Limpe no fim: o banco tem as contas e os metadados dos aparelhos.

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```
