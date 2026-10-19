# FMD (FindMyDevice) no Raspberry Pi

`playbooks/fmd.yml` sobe o servidor do FMD no Pi, com um sidecar Tailscale
que publica o acesso de emergência pelo Funnel e um Anubis na frente dele.

| O quê | Onde |
|---|---|
| Uso normal (só tailnet) | `https://fmd.lab.nextlevelcode.pro` (Caddy → `ts_ip:8085`, rota em `caddy_lab_pi_routes`) |
| Emergência (**público**) | `https://fmd.<tailnet>.ts.net` (Funnel do sidecar → Anubis → FMD) |
| Dados | `/mnt/secure/appdata/fmd` (`fmd_data_dir`): `fmddata/` (SQLite em WAL) e `tailscale-state/` (identidade do nó e certificado do Funnel) |
| Stack | `/opt/fmd`: `fmd-tailscale`, `fmd-anubis` e `fmd`, os dois últimos na rede do sidecar |

O Funnel é público de propósito: se o celular sumiu, você abre o FMD de
qualquer aparelho emprestado, sem tailnet. Nada em `*.nextlevelcode.pro`
público. O FMD exige HTTPS (Web Crypto), por isso o `fmd.lab` passa pelo
Caddy e não há acesso por IP.

## Segurança do acesso público

O FMD não tem 2FA, e um 2FA atrapalharia o caso de uso: se o celular sumiu, o
app de 2FA quase sempre sumiu junto. O que protege:

- **senha longa e memorável** (frase de 6+ palavras aleatórias), que você
  consiga digitar de cabeça num aparelho emprestado;
- a trava do FMD: 5 senhas erradas bloqueiam a conta por 10 minutos (por
  usuário, não por IP), uns 720 palpites por dia no máximo;
- os dados são cifrados no aparelho: invadir o servidor dá metadado (quem tem
  conta, quando cada aparelho falou), não o mapa;
- `FMD_REGISTRATIONTOKEN` obrigatório: vazio = qualquer um cria conta;
- o **Anubis** no endereço do Funnel (`fmd_anubis`): todo acesso pela
  internet, inclusive o login, passa antes por uma prova de trabalho no
  navegador. Bot nenhum chega a tentar senha nem a travar a conta. Pela
  tailnet (o app do celular) e pelo `fmd.lab` passa direto (`docs/anubis.md`).

## Antes de aplicar

- **Vault** (`inventory/group_vars/all/vault.yml`, modelo em
  `vault.yml.example`):
  - `vault_fmd_registration_token` (`openssl rand -base64 32`): o app pede
    para criar conta;
  - `vault_fmd_ts_authkey`: auth key do Tailscale para o sidecar. Só é usada
    quando o nó não tem estado (instância nova, ou `tailscale-state/`
    perdido); com o estado restaurado, o nó volta com a identidade de antes.
- **ACL** (`tailscale/policy.hujson`), já na política: `tag:caddy` →
  `tag:pi:8085`, membros → `tag:public:443`, e o `nodeAttrs` que dá `funnel`
  a `tag:public`. Sem o último, o sidecar sobe e o Funnel não abre.

## Instalação

1. **Testar no pi-lab** (sem sidecar nem Anubis: entraria na tailnet como
   outro `fmd`, com Funnel):

   ```bash
   ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `ssh root@10.50.0.203 'wget -S -O /dev/null http://10.50.0.203:8085 2>&1 | grep HTTP/'`
   mostra `HTTP/1.1 200 OK` (a página em si reclama da falta de HTTPS, e é esperado).

2. **Dados.** Com backup a trazer, restaure antes de aplicar
   (`docs/fmd-restore.md`): o banco e o estado do sidecar voltam, e o Funnel
   continua em `fmd.<tailnet>.ts.net` sem nó novo. Os passos 3 e 5 não se
   aplicam.

3. **Nó antigo, só sem estado restaurado.** O sidecar vai entrar na tailnet
   com a auth key como `fmd`. Se um nó `fmd` antigo ainda existir no console, o
   novo vira `fmd-1` e o Funnel muda de nome: remova o antigo antes de
   aplicar (console → Machines). É manual porque mexer em nós é do console.

   Confira: o console não lista nenhum nó `fmd`.

4. **Aplicar no Pi e no Caddy** (o do Proxmox e o reserva do Pi leem a mesma
   rota):

   ```bash
   ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass
   ```

   Confira:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker exec fmd-tailscale tailscale funnel status
   curl -s -o /dev/null -w '%{http_code}\n' https://fmd.lab.nextlevelcode.pro/
   ```

   O primeiro mostra `Funnel on` com proxy para `127.0.0.1:8923` (o Anubis),
   e o segundo devolve `200`. No console, o nó `fmd` tem `tag:containers` e
   `tag:public`.

5. **Conta, só em instância nova.** No app FMD do celular: servidor
   `https://fmd.lab.nextlevelcode.pro` (o celular na tailnet), token de
   cadastro do vault e a senha longa da seção acima. É manual porque a conta
   nasce no app.

   Confira: o login em `https://fmd.lab.nextlevelcode.pro` mostra o aparelho
   com a última localização.

6. **Funnel de fora** (dados móveis, sem tailnet): abrir
   `https://fmd.<tailnet>.ts.net`.

   Confira: aparece o desafio do Anubis, depois o login do FMD.

7. **Primeiro backup:**

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo borgmatic -c /etc/borgmatic/fmd.yaml --verbosity 1 --stats
   ```

   Confira: os monitores *FMD*, *FMD (Funnel)* e *Backup FMD* ficam verdes no
   Uptime Kuma.

## Backup

Prefixo `fmd-*`, no borgmatic do Pi (`/etc/borgmatic/fmd.yaml`,
`docs/backup.md`). Leva `fmddata/` e o `tailscale-state/`: num Pi
reconstruído, o Funnel volta com a mesma URL. Para só o `fmd` por alguns
segundos, porque o SQLite está em WAL; o sidecar e o Funnel continuam.
Monitor *Backup FMD*. Restore: `docs/fmd-restore.md`.

## Operação

- **Reiniciar a stack: `up -d --force-recreate`, nunca `restart`.** O `fmd`
  e o `fmd-anubis` vivem na rede do sidecar. O `restart` reinicia os três ao
  mesmo tempo, e os dois tentam entrar numa rede que ainda não existe e
  ficam parados. O `up` respeita a ordem do compose:

  ```bash
  ssh ubuntu@nextlevelcode.<tailnet>.ts.net sudo docker compose -f /opt/fmd/compose.yml up -d --force-recreate
  ```

  Confira: `docker ps --filter name=fmd` mostra os três `Up`.

- **Funnel fora com o `fmd.lab` no ar** (monitor *FMD (Funnel)* vermelho,
  "socket disconnected before secure TLS connection"): a conexão da internet
  não chega ao sidecar. Teste as entradas do Funnel uma a uma, de fora da
  tailnet:

  ```bash
  for ip in $(dig +short @9.9.9.9 fmd.<tailnet>.ts.net A); do
    curl -sS -m 20 --resolve fmd.<tailnet>.ts.net:443:$ip -o /dev/null \
      -w "$ip %{http_code}\n" https://fmd.<tailnet>.ts.net/api/v1/version
  done
  ```

  Todas falhando: recrie a stack (acima), para o sidecar se registrar de
  novo. Só uma falhando com a config igual: é do lado do Tailscale; espere e,
  se persistir, chamado no suporte com os IPs e o horário.
- **Atualizar:** o FMD tem versão exata (`fmd_image`, projeto `0.x`): sobe
  trocando a variável, depois de ler as notas da versão. O Anubis usa a do
  role `anubis` (`docs/anubis.md`, "Atualizar"). O sidecar usa
  `tailscale_image` (em `group_vars/all`, a mesma do exit node), em `latest`
  (ADR 0010), e anda com o `pi-atualizar.yml`.

## Limitações

- O monitor *FMD (Funnel)* passa pelo `/api/v1/version`, o único caminho que o
  Anubis libera da internet. Ele prova que o Funnel chega ao FMD, não que o
  login funciona.
