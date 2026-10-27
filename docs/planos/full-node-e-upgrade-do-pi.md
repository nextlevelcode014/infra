# Plano: full node Bitcoin e upgrade do Pi

**Status:** planejado, nada comprado. Preços de 2026-10-27.

Dois upgrades que andam juntos:

- **Pi 5:** UPS para segurar quedas curtas de energia, NVMe pela PCIe e
  refrigeração melhor.
- **Notebook do Proxmox:** um full node Bitcoin próprio (bitcoind + Fulcrum +
  Mempool). Ele valida tudo sozinho, as carteiras falam com o próprio servidor
  e a consulta de transação ou endereço não vaza o IP para um explorer
  público.

Este doc é o plano. Os passos de cada serviço, quando existirem, vão para o
doc dele em `ansible/docs/`, e as decisões para `docs/decisoes/`.

## Por que o node fica no notebook, e não no Pi

Lido nas máquinas em 2026-10-27 (`free -h`, `lsblk`, `lsusb -t`,
`dmidecode -t 17`):

| | Pi 5 | Notebook (IdeaPad 3 15ALC6) |
|---|---|---|
| CPU | 4 núcleos ARM | Ryzen 7 5700U, 16 threads |
| RAM | 8 GB, **já com 1,7 GB em swap** | 12 GB (4 soldados + 8 no slot), 7,4 GB livres |
| Disco | XS1000 1 TB por USB; `/mnt/secure` com 453 GB livres | NVMe 512 GB; `local-lvm` com ~330 GB livres |
| USB | 5 Gbps | dois controladores de 10 Gbps (um já leva o adaptador Ethernet) |
| Energia | UPS (este plano) | bateria própria, em `Long_Life` |

- **O Pi não tem RAM para o node.** Os serviços de hoje já usam swap.
  bitcoind, Fulcrum e Mempool pedem 3 a 4 GB a mais, e a RAM do Pi 5 não se
  troca. Disco daria para arrumar, memória não.
- **O notebook sobra em CPU e RAM.** O sync inicial leva por volta de um dia,
  contra vários dias no Pi. Ele já tem bateria e o fluxo de LXC (o Terraform
  cria, o Ansible configura).
- **Descartados:** a chain inteira numa VPS (um volume de 1 TB na Hetzner
  custa ~€44 por mês), e juntar discos com LVM ou RAID 0 (a falha de um disco
  derrubaria o volume inteiro, e com ele o resto dos dados).

## Compras

### Notebook (full node)

| Item | Onde | Preço |
|---|---|---|
| SSD externo Kingston XS1000 2 TB (SXS1000/2000G) | [Mercado Livre](https://www.mercadolivre.com.br/p/MLB26032011), vendedor ONLYONE E-SPORTS (MercadoLíder, +1000 vendas) | R$ 1.798,37 |
| SO-DIMM DDR4 3200 de 16 GB | a pesquisar | — |

- **XS1000:** é o mesmo modelo que já roda no Pi por USB. Prefira esse
  vendedor ao anúncio de R$ 1.650 (pouco histórico) e **fuja do anúncio "da
  China" a R$ 1.279**: é o preço do de 1 TB, sinal de disco falso que mente a
  capacidade.
- **RAM:** o pente de 16 GB entra no lugar do de 8 GB, e os 4 soldados ficam:
  20 GB no total. Isso passa dos 16 GB que o firmware declara. Costuma
  funcionar nesse modelo, mas não é garantido, então compre onde a devolução
  for fácil. O pente de 8 GB que sai fica de reserva.

### Pi (UPS + NVMe)

AliExpress, loja oficial da Geekworm: **R$ 558,67** com ICMS.

- UPS X1200: <https://pt.aliexpress.com/item/1005006420068840.html>
- Case X1200-C1: <https://pt.aliexpress.com/item/1005007053365826.html>
- Placa NVMe X1001 (só a placa): <https://pt.aliexpress.com/item/1005006312075034.html>
- Cooler H505: <https://pt.aliexpress.com/item/1005007299906886.html>

Baterias 18650 (2 unidades):

- **Escolhida:** 2× Murata (Sony) VTC6 no Mercado Livre, vendedor 4mmagazine
  (MercadoLíder, +5 mil vendidos, 604 avaliações), R$ 113,80 com frete grátis:
  <https://www.mercadolivre.com.br/pilha-18650-murata-vtc6-cilindrica-1-unidad/p/MLB21693131>
  - 3000 mAh, flat top, sem proteção (a VTC6 original não tem).
  - O anúncio fala em "chip de proteção" e "3.7 V": é texto genérico copiado
    (proteção não combina com 30 A). Pergunte ao vendedor antes ou confira ao
    chegar.
- **Alternativa:** 2× BAP-18650H na Amazon, R$ 99,80, frete grátis:
  <https://www.amazon.com.br/dp/B0HN84QP4J>. As specs são coerentes (3,6 V,
  12C), mas são só 2500 mAh (~20% menos autonomia) e a marca não tem
  avaliações.
- **Descartadas:**
  - Samsung 30Q no ML: um anúncio só, vendedores com "entrega a combinar" e
    relato de falsificação.
  - AliExpress: célula solta é carga perigosa no envio internacional. Lá só há
    vendedores locais caros (EVE 30P ~R$ 65 a célula, Molicel P30B R$ 116) ou
    falsas ("6800/8800 mAh").
  - Qualquer anúncio com "entrega a combinar": o frete sai do ML e a proteção
    de compra fica mais fraca.

Outro SSD Kingston para a infra do Pi: capacidade e modelo a definir (o atual
é um XS1000 de 1 TB por USB).

Já tenho: o Raspberry Pi 5, a fonte de 5 V / 5 A e o SSD NVMe Samsung de
512 GB (2280, compatível com o X1001).

Fica de fora: a bateria do RTC (o relógio acerta pelo NTP quando a rede sobe).

### Total

| Bloco | Valor |
|---|---|
| Upgrade do Pi (AliExpress + baterias) | R$ 672,47 |
| XS1000 2 TB | R$ 1.798,37 |
| RAM de 16 GB | a pesquisar |
| SSD Kingston do Pi | a definir |
| **Já conhecido** | **R$ 2.470,84** |

## Upgrade do Pi

### Montagem (de baixo para cima)

1. Placa UPS X1200 + 2 baterias 18650
2. Raspberry Pi 5
3. Cooler H505
4. Placa NVMe X1001 + SSD Samsung

Tudo dentro do case metálico X1200-C1. O Pi fica no cabo de rede, então o
metal não atrapalha.

### Ao receber as baterias

Se qualquer item falhar, devolva pelo ML.

1. **Formato:** polo positivo reto (flat top, sem "botão") e ~65 mm. Acima de
   ~68 mm não cabe no suporte.
2. **Peso:** ~46 g cada. Muito abaixo disso é falsa.
3. **Tensão** (multímetro): as duas têm que estar a no máximo ~0,1 V uma da
   outra. A X1200 liga as células em paralelo, e uma diferença grande força
   corrente de uma para a outra.

### Cuidados na montagem

- Baterias sem proteção, da mesma marca e do mesmo lote, com a polaridade
  certa (+ com +).
- As baterias entram **antes** de ligar a fonte.
- A fonte vai na USB-C da X1200, **nunca** na do Pi.
- A primeira carga é com o Pi desligado, acompanhando se as baterias esquentam
  de forma estranha.
- Troque as baterias a cada ~2 anos.

### Configuração depois de montar

Com a X1200, o Pi recebe energia pelos pinos, não pela USB-C. Por isso ele
não negocia 5 A com a fonte e limita as portas USB a 600 mA, o que derruba o
XS1000 que leva o sistema. Confirme na wiki da Geekworm (X1200) e então:

```bash
sudo rpi-eeprom-config --edit
```

Acrescente `PSU_MAX_CURRENT=5000`, salve e reinicie.

Confira: `vcgencmd get_config usb_max_current_enable` devolve `1`.

### Próximos passos do Pi

- Script de monitoramento do UPS (timer do systemd, no repo): numa queda de
  energia o Pi continua ligado, e só desliga com a bateria baixa (~15–20%).
- Migrar o boot para o NVMe (opcional).
- Estudar como destravar o LUKS sem ir até o Pi (SSH no initramfs, ou
  Clevis + Tang).

## Upgrade do notebook

1. **RAM:** com o notebook desligado e fora da tomada, troque o pente de
   8 GB pelo de 16 GB.

   Confira: `free -h` mostra ~19 GB, e `dmidecode -t 17` mostra 4 GB
   soldados + 16 GB SODIMM. Se não passar do POST, ou mostrar menos, volte o
   pente de 8 GB e devolva o novo.

2. **XS1000:** ligue o disco numa porta do controlador de 10 Gbps que **não**
   tem o adaptador Ethernet.

   Confira: em `lsusb -t`, o disco aparece com `Driver=uas, 10000M`. Se
   aparecer `5000M`, troque de porta.

## Full node

### Layout de disco

| Dado | Tamanho | Onde |
|---|---|---|
| `blocks/` (`-blocksdir`) | ~750 GB, cresce ~60–80 GB por ano | XS1000, ext4 no host, bind mount no LXC |
| chainstate, txindex, Fulcrum, MariaDB do Mempool | ~200–250 GB | disco do LXC no `local-lvm` |

Os blocos, frios e grandes, ficam no disco novo. O que muda o tempo todo fica
no NVMe interno. Se o XS1000 morrer, só se perde o `blocks/`, e o remédio é
baixar de novo ou reindexar.

O XS1000 fica sem LUKS: só guarda blocos públicos. O fstab leva `nofail`, para
que o host suba mesmo sem o disco.

Os tamanhos da chain são estimativa, não medição. Confira o tamanho atual
antes de dimensionar o disco do LXC.

### Serviços

| Serviço | Como | Acesso |
|---|---|---|
| bitcoind | nativo, a partir do binário de bitcoincore.org conferido com `SHA256SUMS` + GPG; `txindex=1`, P2P pelo Tor | RPC só local e na rede Docker |
| Tor | pacote do Ubuntu, com ControlPort para o bitcoind | — |
| Fulcrum | imagem oficial `cculianu/fulcrum`, tag fixa, `compose_stack` | TCP 50001 no IP Tailscale (Sparrow e carteiras) |
| Mempool | imagens oficiais `mempool/backend` + `mempool/frontend` + MariaDB, tag fixa | `mempool.lab.nextlevelcode.pro` pelo Caddy do Proxmox |

O bitcoind roda fora do Docker de propósito: num node, confiar numa imagem
de terceiro anula o motivo de rodar um. Isso foge de
`ansible/docs/padrao-de-role.md` e leva um ADR.

Sem backup Borg: tudo se baixa ou se reindexa de novo.

### O que muda no repo (quando o hardware chegar)

1. **Terraform** (`terraform/containers.tf`): LXC `bitcoin` na `vmbr1`, com
   6 cores, 10 GB de RAM (6 GB se o sync começar antes da troca do pente) e
   250 GB no `local-lvm`, unprivileged, com `nesting`.
2. **Host Proxmox:** monta o XS1000 por UUID em `/mnt/btc-blocks`, com dono no
   uid mapeado do LXC. O bind mount entra pelo `lxc_flags`, porque bind mount
   é exclusivo do `root@pam`, como o `keyctl` (`ansible/roles/lxc_flags/README.md`).
3. **Ansible no LXC:** `playbooks/bitcoin.yml` com os roles `bitcoind`,
   `fulcrum` e `mempool`.
4. **Acesso:** rota no Caddyfile do Proxmox; tag e grants em
   `tailscale/policy.hujson` (`tag:caddy` → Mempool, aparelhos pessoais →
   50001); monitores em `group_vars/vps/monitors.yml`.
5. **Docs:** `ansible/docs/bitcoin.md` com os passos manuais, e as tabelas de
   `ansible/CLAUDE.md` e `terraform/CLAUDE.md`.
6. **ADRs:** o node roda no notebook, com os blocos num SSD USB dedicado; o
   bitcoind é nativo, do binário verificado, e não uma imagem.

### Ordem de aplicação

1. `terraform apply` (o LXC) → `playbooks/lxc.yml`.
2. Ligar o XS1000 e conferir o dispositivo pelo modelo **antes** do `mkfs`,
   que é destrutivo.
3. `playbooks/proxmox.yml` (montagem) → `lxc_flags` (bind mount).
4. `playbooks/bitcoin.yml` → sync inicial (~1 dia) → o Fulcrum indexa → o
   Mempool sobe.
5. `playbooks/caddy.yml`, a ACL colada no console, os monitores.
6. Baixar o `dbcache` depois do sync.

### Como conferir

- `bitcoin-cli getblockchaininfo`: `blocks` igual a `headers`, e
  `verificationprogress` perto de 1.
- `bitcoin-cli getnetworkinfo`: a rede `onion` está ativa.
- `df -h` no host: o `blocks/` cresce no XS1000, não no `local-lvm`.
- A Sparrow, ligada ao Fulcrum pela tailnet, mostra o saldo.
- `https://mempool.lab.nextlevelcode.pro` mostra os blocos recentes.
- O Uptime Kuma fica verde.

## Checklist

### Compras

- [ ] Kit Geekworm no AliExpress (X1200, X1200-C1, X1001, H505)
- [ ] 2× VTC6 (perguntar ao vendedor sobre a "proteção")
- [ ] XS1000 2 TB (ONLYONE E-SPORTS)
- [ ] SO-DIMM DDR4 3200 de 16 GB
- [ ] SSD Kingston do Pi (definir o modelo)

### Pi

- [ ] Conferir as baterias (formato, peso, tensão)
- [ ] Montar e fazer a primeira carga com o Pi desligado
- [ ] `PSU_MAX_CURRENT=5000` e conferir `usb_max_current_enable`
- [ ] Monitor do UPS
- [ ] Boot no NVMe (opcional)
- [ ] Destravar o LUKS remotamente (estudo)

### Notebook e node

- [ ] Trocar a RAM e conferir os 20 GB
- [ ] XS1000 na porta de 10 Gbps
- [ ] LXC `bitcoin` no Terraform
- [ ] Montagem e bind mount no host
- [ ] Roles `bitcoind`, `fulcrum` e `mempool`
- [ ] Sync inicial, e depois baixar o `dbcache`
- [ ] Mempool no Caddy, ACL e monitores
- [ ] `ansible/docs/bitcoin.md` e os dois ADRs

## Depois

- **BTCPay Server** numa VPS nova, com bitcoind pruned próprio: aceitar
  pagamento em BTC na NextLevelCode sem intermediário. Fica público (Caddy da
  VPS) e não cai junto com a casa. O Postgres dele vai para o Borg.
