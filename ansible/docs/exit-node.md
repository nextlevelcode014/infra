# Exit node (Tailscale + ProtonVPN) no Raspberry Pi

`playbooks/exit-node.yml` sobe o exit node `vpn-exit`: um nó Tailscale em
container que encaminha o tráfego de quem o escolhe para a ProtonVPN. Com ele
ligado no celular, a navegação sai pela Proton e os serviços da tailnet
continuam acessíveis.

| O quê | Onde |
|---|---|
| Nó na tailnet | `vpn-exit` (`tag:containers`) |
| Stack | `/opt/exit-node`: `gluetun-exit` (túnel WireGuard) e `tailscale-exit` (na rede dele) |
| Identidade do nó | volume Docker `exit-node_tailscale-exit-state`, no data-root do Docker (LUKS) |
| Saída | servidor Proton fixo: `exit_node_server_countries` e `exit_node_server_hostnames` |

As regras de roteamento, a trava contra vazamento e o motivo do servidor fixo
estão nos comentários do compose (`roles/exit_node/files/compose.yml`). O
projeto Compose é fixo em `exit-node` (`name:` do compose), e é isso que
mantém o volume, e o nó, entre aplicações.

## Antes de aplicar

- **Config WireGuard própria**, no vault (`vault_exit_node_wireguard_private_key`),
  gerada na Proton como a do gluetun (`docs/gluetun.md`, "Antes de
  aplicar"), mas **outra**: a mesma chave em dois lugares derruba um dos
  túneis. Por isso o playbook mira só o `rpi`, nunca o pi-lab.
- **Auth key** do Tailscale (`vault_exit_node_ts_authkey`), com
  `tag:containers`. Só é usada quando o nó não tem estado (volume novo).
- **ACL** (`tailscale/policy.hujson`), já na política: membros →
  `autogroup:internet`, que é o que deixa usar um exit node.

## Instalação

1. **Aplicar** (só no Pi; não há teste no pi-lab, pela chave única):

   ```bash
   ansible-playbook playbooks/exit-node.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/exit-node.yml --ask-vault-pass
   ```

   Confira (no Pi):

   ```bash
   docker exec gluetun-exit wget -qO- https://ipinfo.io/ip
   docker exec tailscale-exit tailscale status
   ```

   O IP é da Proton, não o da sua casa, e o nó aparece conectado.

2. **Aprovar o exit node, só com nó novo.** O `autoApprovers` da política
   cobre nós de usuário, não nós com tag: no console → Machines → `vpn-exit`
   → Edit route settings → *Use as exit node*. É manual porque a aprovação
   é do console.

   Confira: o `vpn-exit` aparece na lista de exit nodes do app.

3. **Testar no celular:** app do Tailscale → *Exit Node* → `vpn-exit`.

   Confira: `ipinfo.io` mostra o IP do passo 1, e um serviço da tailnet
   (Vaultwarden, Jellyfin) abre **com o exit node ligado**: é o ponto do
   exercício inteiro.

4. **Killswitch** (abaixo, "Operação"): teste uma vez depois de instalar.

## Backup

Nenhum: a config vem do repo e do vault. A identidade do nó mora num volume
Docker; perdido o volume, o nó volta novo com a auth key, e o passo 2 da
instalação se repete.

## Operação

### Trocar de país

Mude `exit_node_server_countries` e troque ou esvazie
`exit_node_server_hostnames` junto (senão os dois filtros não casam com nenhum
servidor e o gluetun não sobe), e reaplique. Depois rode
`docker exec gluetun-exit wget -qO- https://ipinfo.io/json` e veja se a cidade
bate: a base do gluetun erra o país de vários servidores.

### Killswitch (fail-closed)

Testar isso pelo IP de saída do container **não serve**: mede a chain `OUTPUT`,
não o caminho do celular. O teste certo pergunta ao kernel por onde sairia o
tráfego encaminhado, com o túnel caído:

```bash
docker exec gluetun-exit ip link set tun0 down
docker exec gluetun-exit ip route get 1.1.1.1 from <ip-tailnet-do-celular> iif tailscale0
```

- `RTNETLINK answers: Invalid argument` → correto, sem rota de fuga.
- `via 172.20.0.1 dev eth0` → **vazando** pelo IP de casa; as regras 97/98 não
  estão aplicadas (confira com `docker exec gluetun-exit ip rule`).

O gluetun restaura o túnel sozinho em alguns segundos. Se quiser forçar:

```bash
docker compose -f /opt/exit-node/compose.yml up -d --force-recreate gluetun-exit
```

### Diagnóstico: "conectei no exit node e não tem internet"

Nesse cenário o `tailscale status` mente: ele mostra o nó saudável e
anunciando exit node de qualquer jeito. O que localiza a falha é o
**contador**:

```bash
docker exec gluetun-exit iptables -L ts-forward -n -v
```

- **A chain `ts-forward` nem existe** → o tailscaled não conseguiu escrever as
  regras. Confirme com `docker logs tailscale-exit | grep -i "can't initialize"`.
  É o problema do backend legacy vs nft (comentário do `tailscale-exit` no compose).
- **Chain existe mas com tudo em zero** → os pacotes não chegam ao encaminhamento;
  o problema é de **rota**, não de firewall. Confirme para onde o kernel manda a
  resposta:

  ```bash
  docker exec gluetun-exit ip route get <ip-tailnet-do-celular>
  ```

  `dev tun0 table 51820` é o buraco negro (comentário da regra de prioridade 99 no compose);
  `dev tailscale0 table 52` é o correto.
- **Contadores subindo nas duas direções** → o encaminhamento está bom. Se ainda
  assim carrega texto e trava em página pesada, o suspeito é MTU: teste
  `WIREGUARD_MTU` entre 1380 e 1420.

## Limitações

### Velocidade

Duas coisas limitam, e nenhuma delas é config:

- **O download no celular é limitado pelo *upload* da casa.** O caminho é
  `internet → Proton → Pi → uplink de casa → celular`.
- **Relay DERP sempre, não "provavelmente".** Medido: `tailscale netcheck` reporta
  `MappingVariesByDestIP: true`, que é assinatura de **NAT simétrico**: a Proton
  não devolve porta previsível, então o furo de NAT não acontece e a conexão
  direta é impossível. A porta 41642 publicada só ajuda peers na mesma LAN.

Como o relay é inescapável, **a localização dele é a única alavanca**, e ela
depende de onde o túnel sai, porque o Tailscale mede latência de DERP através do
túnel. É por isso que o servidor fixo em São Paulo importa tanto: derrubou o
`sao` de 176,9 ms para 35,5 ms. Ver o comentário do `SERVER_HOSTNAMES` no compose.

A única saída restante contra o relay seria o `VPN_PORT_FORWARDING` da Proton
amarrado ao `--port` do tailscaled. A porta muda a cada reconexão, então o
acoplamento é frágil. Exige também gerar um config novo na Proton com P2P e port
forwarding ligados: **as *features* ficam presas ao config**, ao contrário do
país, que é livre (a chave é registrada na conta, não no servidor).

Se o download for lento com upload rápido, o suspeito é MTU: testar
`WIREGUARD_MTU` entre 1380 e 1420.
