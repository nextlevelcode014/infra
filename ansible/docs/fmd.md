# FMD (FindMyDevice) no Raspberry Pi

`playbooks/fmd.yml` aplica o FMD que antes subia por `make up SVC=fmd` no
`self-hosted`. Ele tem dois acessos:

| Acesso | Para quê |
|---|---|
| `https://fmd.<tailnet>.ts.net` (Funnel, **público**) | emergência: abrir de qualquer aparelho, sem entrar na tailnet |
| `https://fmd.lab.nextlevelcode.pro` (Caddy, só tailnet) | uso normal |

Nada em `*.nextlevelcode.pro` público. O compose é o do `self-hosted`, com os
dados no LUKS (`/mnt/secure/appdata/fmd`) e a porta `8085` publicada pelo
sidecar, no IP Tailscale, para o Caddy.

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
- o **Anubis** no caminho do Funnel (`fmd_anubis`): todo acesso pela internet,
  inclusive o login, passa antes por uma prova de trabalho no navegador. Bot
  nenhum chega a tentar senha nem a travar a conta. O `fmd.lab` segue direto.
  Da tailnet, o endereço do Funnel dá 500: use o `fmd.lab` (`docs/anubis.md`).

## Backup

Diário às 02:50, `/usr/local/bin/backup-fmd.sh`, log em
`/var/log/fmd_backup.log`, prefixo `fmd-*`. Para só o `fmd` (o sidecar e o
Funnel continuam) por alguns segundos, porque o SQLite está em modo WAL.

## Primeira aplicação

No `self-hosted`, o `link-data` nunca foi aplicado ao FMD: o banco, o estado do
sidecar (identidade do nó e certificado do Funnel) e o `.env` com o token estão
em `/home/ubuntu/self-hosted/fmd`, na raiz **sem criptografia**. A migração
leva tudo para o LUKS. O role para sozinho se encontrar banco no caminho antigo
e nenhum no novo.

1. **Vault.** Os valores estão hoje no Pi:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net grep -E '^(TS_AUTHKEY|FMD_REGISTRATIONTOKEN)=' /home/ubuntu/self-hosted/fmd/.env
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   `TS_AUTHKEY` → `vault_fmd_ts_authkey`, `FMD_REGISTRATIONTOKEN` →
   `vault_fmd_registration_token`.

2. **ACL do Tailscale** (console): o `tag:caddy` precisa alcançar o Pi em
   `tcp:8085`.

3. **Testar no pi-lab** (sem sidecar):

   ```bash
   ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit pi_staging
   ```

   Confira: `http://192.168.50.203:8085` responde (a página reclama da falta de
   HTTPS, e é esperado: o Web Crypto só funciona com HTTPS).

4. **Migrar os dados no Pi** (o FMD fica fora por um ou dois minutos):

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net '
     docker compose -f ~/self-hosted/fmd/compose.yml down &&
     sudo mkdir -p /mnt/secure/appdata/fmd &&
     sudo rsync -a ~/self-hosted/fmd/fmddata/ /mnt/secure/appdata/fmd/fmddata/ &&
     sudo rsync -a ~/self-hosted/fmd/tailscale-state/ /mnt/secure/appdata/fmd/tailscale-state/'
   ```

   Confira: `sudo ls /mnt/secure/appdata/fmd/fmddata/db` mostra o `fmd.sqlite`, e
   `sudo ls /mnt/secure/appdata/fmd/tailscale-state` o `tailscaled.state`.

5. **Aplicar no Pi:**

   ```bash
   ansible-playbook playbooks/fmd.yml --ask-vault-pass --limit rpi
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ```

   Confira:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker exec fmd-tailscale tailscale funnel status
   curl -s -o /dev/null -w '%{http_code}\n' https://fmd.<tailnet>.ts.net/
   curl -s -o /dev/null -w '%{http_code}\n' https://fmd.lab.nextlevelcode.pro/
   ```

   O Funnel continua em `fmd.<tailnet>.ts.net` (mesmo nó, sem nova aprovação),
   os dois respondem `200`, e o login com a sua conta mostra os aparelhos.

6. **Apagar a cópia em claro na raiz.** Só depois do passo 5 conferido:

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net 'sudo rm -rf ~/self-hosted/fmd/fmddata ~/self-hosted/fmd/tailscale-state ~/self-hosted/fmd/.env'
   ```

7. **Primeiro backup:**

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net sudo /usr/local/bin/backup-fmd.sh
   ```

A partir daqui, não use mais `make up SVC=fmd` no `self-hosted`.
