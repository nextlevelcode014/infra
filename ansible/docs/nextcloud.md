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

4. **Backup do AIO** (instância nova): o repositório no BorgBase, como
   em "Backup" abaixo. Guarde a senha de criptografia que ele mostra
   **fora do Pi**: sem ela, o backup não restaura.

5. **Clientes** (desktop, celular): conta com
   `https://nextcloud.lab.nextlevelcode.pro`, com o aparelho na tailnet.

## Backup

Não passa pelo borgmatic: é o Borg embutido do AIO, configurado na interface
dele, com retenção em `BORG_RETENTION_POLICY` no compose. O destino é um
repositório remoto no BorgBase, na mesma conta do compartilhado mas
**separado dele**: o AIO cria o repositório com uma senha que ele mesmo
gera, e um repositório Borg só tem uma (ADR 0008). O AIO para os
containers durante o backup e avisa uma falha no próprio Nextcloud; não há
monitor no Uptime Kuma, e quem avisa de fora é o alerta do BorgBase.

### Configurar

Manual: o repositório nasce no console do BorgBase, e o destino do backup
só se configura na interface do AIO.

1. **Repositório no BorgBase.** No console, *New Repo*: nome
   `nextcloud-aio`, a mesma região do compartilhado, e o alerta de
   inatividade em 2 dias (o aviso que o Uptime Kuma não dá).

   Confira: o repositório aparece na lista, com a URL
   `ssh://<id>@<id>.repo.borgbase.com/./repo`.

2. **Repositório remoto no AIO.** Na interface do AIO
   (`https://nextlevelcode.<tailnet>.ts.net:8080`), com os containers
   parados, seção de backup: deixe o caminho local vazio e cole a URL do
   passo 1 no repositório remoto. Com um destino já configurado,
   *Reset backup location* antes.

   Confira: o campo mostra o repositório remoto.

3. **Chave do AIO.** *Create backup*: a primeira tentativa falha e a
   interface mostra uma chave pública. No BorgBase, *Account → SSH Keys →
   Add Key* com ela, e no repositório `nextcloud-aio`, *Edit*: a chave com
   **acesso total** (não append-only: o prune do AIO precisa apagar).

   Confira: a chave aparece no acesso do `nextcloud-aio`, e em nenhum
   outro repositório.

4. **Primeiro backup.** *Create backup* de novo. Confira que a senha de
   criptografia que a interface mostra é a que está no KeePass
   (`docs/pi-reconstrucao.md`); se mudou, troque lá.

   Confira: o backup aparece na lista da interface, e o `nextcloud-aio`
   no BorgBase mostra o espaço usado.

5. **Backup diário**, na mesma seção, às 04:00: depois do borgmatic do Pi,
   para os dois não disputarem o upload. Confira o fuso que a interface
   indica.

   Confira: a interface mostra o backup diário ligado, e no dia seguinte há
   um backup novo na lista.

## Restore

Não há playbook: é a primeira tela do AIO, *Restore former AIO instance*
(Instalação, passo 2, caminho "Com backup"). Num Pi novo, aplique o passo 1
antes, para a interface existir.

## Operação

- **Atualizar:** o mastercontainer e os containers do AIO se atualizam pela
  interface do AIO, não pelo `pi-atualizar.yml`; por isso a imagem fica em
  `latest` (ADR 0013). O coturn fica na major (`nextcloud_coturn_image`,
  `4`) e anda com o `pi-atualizar.yml`; depois de uma versão nova, uma
  chamada no Talk de fora de casa confirma o relay. Se ele não subir
  (`docker logs coturn-turn-coturn-1` com `unrecognized option`), uma opção
  do `command` mudou de nome: veja as notas da versão, ou volte a variável
  para a versão anterior.
- **`tailscale serve` do host:** o role deixa só a 8080. Ele também apaga
  as portas antigas `8000` (um Funnel público) e `9080`, e a `443` quando o
  domínio do AIO já é o `nextcloud.lab`: num host limpo, nada disso
  existe e as tasks não fazem nada.

## Limitações

- Uma cópia só fora de casa, no BorgBase, e sem monitor no Uptime Kuma:
  falha só aparece no Nextcloud e no alerta de inatividade do BorgBase.
