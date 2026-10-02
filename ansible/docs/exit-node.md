# Exit node (Tailscale + ProtonVPN) no Raspberry Pi

`playbooks/exit-node.yml` aplica o exit node `vpn-exit`, que antes subia por
`make up SVC=exit-node` no `self-hosted`. O compose é o mesmo, sem mudança:
as regras de roteamento, a trava contra vazamento e o servidor ProtonVPN fixo
estão explicados nos comentários dele (`roles/exit_node/files/compose.yml`).

Ele usa uma config WireGuard **própria**, separada da do gluetun: a mesma chave
em dois lugares derruba um dos túneis. Por isso o playbook mira só o `rpi`,
nunca o pi-lab.

O projeto Compose se chama `exit-node` (fixo no `name:` do compose), então o
volume com a identidade do nó é adotado e o `vpn-exit` continua o mesmo nó.

## Primeira aplicação

No `self-hosted`, o `.env` deste serviço ficava na raiz, sem criptografia e
legível por qualquer usuário (`664`), com a auth key e a chave WireGuard.

1. **Vault.** Os valores estão hoje no Pi:

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net grep -E '^(TS_AUTHKEY|WIREGUARD_PRIVATE_KEY)=' /home/ubuntu/self-hosted/exit-node/.env
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   `TS_AUTHKEY` → `vault_exit_node_ts_authkey`, `WIREGUARD_PRIVATE_KEY` →
   `vault_exit_node_wireguard_private_key`.

2. **Aplicar.** O `tailscale-exit` é recriado (imagem `latest` mais nova), e o
   exit node cai por alguns segundos:

   ```bash
   ansible-playbook playbooks/exit-node.yml --ask-vault-pass --check --diff
   ansible-playbook playbooks/exit-node.yml --ask-vault-pass
   ```

3. **Conferir** (seção "Verificar" abaixo) e testar no celular.

4. **Apagar o `.env` em claro:**

   ```bash
   ssh ubuntu@nextlevelcode.<tailnet>.ts.net rm /home/ubuntu/self-hosted/exit-node/.env
   ```

A partir daqui, não use mais `make up SVC=exit-node` no `self-hosted`.

## Trocar de país

Mude `exit_node_server_countries` e troque ou esvazie
`exit_node_server_hostnames` junto (senão os dois filtros não casam com nenhum
servidor e o gluetun não sobe), e reaplique. Depois rode
`docker exec gluetun-exit wget -qO- https://ipinfo.io/json` e veja se a cidade
bate: a base do gluetun erra o país de vários servidores.

## Verificar

```bash
# IP público visto de dentro do túnel (deve ser o da Proton, não o seu):
docker exec gluetun-exit wget -qO- https://ipinfo.io/ip

# O nó autenticou e anunciou exit node?
docker exec tailscale-exit tailscale status

```

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

## Diagnóstico: "conectei no exit node e não tem internet"

Nesse cenário o `tailscale status` mente — ele mostra o nó saudável e anunciando
exit node de qualquer jeito. O que localiza a falha é o **contador**:

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

No celular: app do Tailscale → *Exit Node* → `vpn-exit`. Conferir em `ipinfo.io` que
o IP bate com o do comando acima, e abrir algum serviço da tailnet (Vaultwarden,
Jellyfin) **com o exit node ligado** — é o ponto do exercício inteiro.

## O que esperar de velocidade

Duas coisas limitam, e nenhuma delas é config:

- **O download no celular é limitado pelo *upload* da casa.** O caminho é
  `internet → Proton → Pi → uplink de casa → celular`.
- **Relay DERP sempre, não "provavelmente".** Medido: `tailscale netcheck` reporta
  `MappingVariesByDestIP: true`, que é assinatura de **NAT simétrico** — a Proton
  não devolve porta previsível, então o furo de NAT não acontece e a conexão
  direta é impossível. A porta 41642 publicada só ajuda peers na mesma LAN.

Como o relay é inescapável, **a localização dele é a única alavanca** — e ela
depende de onde o túnel sai, porque o Tailscale mede latência de DERP através do
túnel. É por isso que o servidor fixo em São Paulo importa tanto: derrubou o
`sao` de 176,9 ms para 35,5 ms. Ver o comentário do `SERVER_HOSTNAMES` no compose.

A única saída restante contra o relay seria o `VPN_PORT_FORWARDING` da Proton
amarrado ao `--port` do tailscaled — a porta muda a cada reconexão, então o
acoplamento é frágil. Exige também gerar um config novo na Proton com P2P e port
forwarding ligados: **as *features* ficam presas ao config**, ao contrário do
país, que é livre (a chave é registrada na conta, não no servidor).

Se o download for lento com upload rápido, o suspeito é MTU: testar
`WIREGUARD_MTU` entre 1380 e 1420.

