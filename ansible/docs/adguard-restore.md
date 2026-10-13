# Restore do AdGuard

Substitui o `conf/` (config, usuários, listas, regras) e o `work/`
(estatísticas e filtros baixados) do AdGuard pelo archive `adguard-*` mais
recente feito pelo Pi (`adguard_restore_source_host: ubuntu`). O querylog
nunca está no archive: volta vazio. O `adguard.yml` nunca restaura.

**O DNS da casa fica fora** do momento em que o restore para o AdGuard até ele
subir de novo, alguns segundos. A tailnet segue pelo fallback do Quad9; a LAN
fica sem DNS (`docs/adguard.md`, "Limitações").

## Antes de executar

1. **LUKS aberto** (`docs/pi.md`, "A cada boot"). O restore confere e para se
   `/mnt/secure` não estiver montado: sem ele, os dados iriam para a raiz em
   claro.

2. **O AdGuard instalado ou não, tanto faz.** Com a stack em `/opt/adguard`, o
   restore para, troca os dados e sobe. Sem ela (Pi novo), só põe os dados no
   lugar, e o `adguard.yml` sobe depois já com a config restaurada: é o que
   o `pi-completo.yml` faz (`docs/pi-reconstrucao.md`).

## Executar

**No Pi:**

```bash
ansible-playbook playbooks/adguard-restore.yml --ask-vault-pass --limit rpi \
  -e adguard_restore_confirmation=RESTORE_ADGUARD
```

Sempre com `--limit`: o playbook mira `pi_hosts`, que inclui o pi-lab.

**No Pi novo, junto com todo o resto:** `docs/pi-reconstrucao.md`, com
`-e pi_restaurar_tudo=RESTAURAR_PI`, que vale como a confirmação deste.

Confira na task "Extrair o archive" que a data é a do backup esperado.

## Conferir

```bash
ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker ps --filter name=adguardhome
dig +short @<ts_ip> doubleclick.net
```

O container está `Up`, e o `dig` devolve `0.0.0.0`. Depois, o login em
`https://adguard.lab.nextlevelcode.pro` com o usuário de antes, e as listas e
regras em Filters iguais às de antes.

## Ensaio no pi-lab

Restaura o archive real do Pi no pi-lab:

```bash
ansible-playbook playbooks/adguard.yml --ask-vault-pass --limit pi_staging
ansible-playbook playbooks/adguard-restore.yml --ask-vault-pass --limit pi_staging \
  -e adguard_restore_confirmation=RESTORE_ADGUARD
```

Confira: `dig +short @192.168.50.203 doubleclick.net` devolve `0.0.0.0`, o
que prova que a config voltou (sem ela, o AdGuard fica no assistente e não
responde DNS). Limpe no fim: a config tem o hash da senha do admin.

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```
