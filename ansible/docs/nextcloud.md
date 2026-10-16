# Nextcloud AIO no Raspberry Pi

`playbooks/nextcloud.yml` cuida das três peças do Nextcloud no Pi que ficam
fora do próprio AIO:

- o **mastercontainer** do AIO (`/opt/nextcloud-aio`). Os outros containers
  (`nextcloud-aio-nextcloud`, `-database`, `-apache`, `-talk`,
  `-collabora`…) são criados e geridos pelo AIO, não pelo Ansible;
- o **coturn** do Talk (`/opt/coturn-turn`, `network_mode: host`), com o
  segredo vindo do vault;
- o **`tailscale serve` do host**, que publica só a interface do AIO, na
  tailnet.

| O quê | Onde |
|---|---|
| Nextcloud | `https://nextcloud.lab.nextlevelcode.pro` (Caddy → Apache do AIO em `ts_ip:11000`, `APACHE_IP_BINDING`) |
| Interface do AIO | `https://nextlevelcode.<tailnet>.ts.net:8080` (`tailscale serve` do host, só tailnet) |
| Talk (TURN/STUN) | coturn em `ts_ip:3479`, relay UDP `49160-49200` |
| Dados | `/mnt/secure/appdata/nextcloud/ncdata` (`NEXTCLOUD_DATADIR`), no LUKS: não mude depois de instalar |

O playbook mira só o `rpi`: o AIO cria uma dúzia de containers e valida o
domínio, e no pi-lab o ensaio não diria muito.

## Antes de aplicar

- **Vault:** `vault_nextcloud_turn_secret` (`openssl rand -hex 32`), o
  segredo compartilhado entre o coturn e o Talk.
- **ACL** (`tailscale/policy.hujson`), já na política:

  | De | Para | Portas | Para quê |
  |---|---|---|---|
  | `tag:caddy` | `tag:pi` | `tcp:11000` | o Caddy chegar no Apache do AIO |
  | `tag:pi` | `tag:caddy` | `tcp:443` | o Nextcloud testar o próprio HPB pelo domínio |
  | `autogroup:member` | `tag:pi` | `udp:3479`, `tcp:3479`, `udp:49160-49200` | o Talk chegar no coturn |
  | dispositivos de admin | `tag:pi` | `tcp:8080` | a interface do AIO |

  O intervalo de relay tem que ser o mesmo de `nextcloud_turn_min_port` /
  `nextcloud_turn_max_port`. Mudando um, mude o outro: a ACL primeiro,
  depois o coturn, para nenhuma chamada cair no meio.

## Instalação

1. **Aplicar no Pi e no Caddy** (o do Proxmox e o reserva do Pi leem a mesma
   rota):

   ```bash
   ansible-playbook playbooks/nextcloud.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/nextcloud.yml --ask-vault-pass
   ansible-playbook playbooks/caddy.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-pi.yml --ask-vault-pass
   ```

   Confira: `ssh ubuntu@nextlevelcode.<tailnet>.ts.net sudo tailscale serve status`
   lista a 8080, e `https://nextlevelcode.<tailnet>.ts.net:8080` abre a
   interface do AIO.

2. **AIO, na interface** (manual: o AIO só se configura por ela). Na
   primeira tela ele mostra a **passphrase** da interface: guarde no
   Vaultwarden. Depois, um de dois caminhos:

   - **Com backup:** *Restore former AIO instance*, com o repositório e a
     **senha de criptografia do backup** (anotada fora do Pi,
     `docs/pi-reconstrucao.md`). O domínio, as contas e os apps voltam com
     o backup.
   - **Instância nova:** domínio `nextcloud.lab.nextlevelcode.pro` (o AIO
     valida o domínio pelo Caddy até a 11000; sem o grant da ACL, a
     validação falha), os containers opcionais (Talk, Collabora) e *Start
     containers*. O AIO mostra a senha do usuário `admin` uma vez.

   Confira:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net docker port nextcloud-aio-apache
   curl -s https://nextcloud.lab.nextlevelcode.pro/status.php
   ```

   O primeiro mostra `<ts_ip>:11000`; o segundo, um JSON com
   `"installed":true`. Em *Administração → Visão geral*, nenhum aviso de
   proxy reverso ou de domínio.

3. **Talk.** O AIO cadastra TURN e STUN em
   `nextcloud.lab.nextlevelcode.pro:3478`, que aponta para o Caddy e não
   funciona (o Caddy só encaminha HTTPS). Em *Administração → Talk*, deixe só
   o coturn: STUN `<ts_ip>:3479` e TURN `<ts_ip>:3479` (UDP e TCP),
   com o segredo do `vault_nextcloud_turn_secret`.

   Confira: o ❗ ao lado do TURN e o aviso do HPB somem, e uma chamada de
   teste conecta.

4. **Backup do AIO** (instância nova): na interface, o local do backup e
   *Create backup*. Guarde a senha de criptografia que ele mostra **fora do
   Pi**: sem ela, o backup não restaura.

5. **Clientes** (desktop, celular): conta com
   `https://nextcloud.lab.nextlevelcode.pro`, com o aparelho na tailnet.

## Backup

Não passa pelo borgmatic: é o Borg embutido do AIO, configurado na interface
dele, com retenção em `BORG_RETENTION_POLICY` no compose. O destino hoje é o
celular (Termux); levar para o repositório compartilhado é a #44.

## Restore

Não há playbook: é a primeira tela do AIO, *Restore former AIO instance*
(Instalação, passo 2, caminho "Com backup"). Num Pi novo, aplique o passo 1
antes, para a interface existir.

## Operação

- **Atualizar:** o mastercontainer e os containers do AIO se atualizam pela
  interface do AIO, não pelo `pi-atualizar.yml`.
- **`tailscale serve` do host:** o role deixa só a 8080. Ele também apaga
  as portas antigas `8000` (um Funnel público) e `9080`, e a `443` quando o
  domínio do AIO já é o `nextcloud.lab`: num host limpo, nada disso
  existe e as tasks não fazem nada.

## Limitações

- O backup do Nextcloud não está no repositório compartilhado nem tem
  monitor no Uptime Kuma (#44).
