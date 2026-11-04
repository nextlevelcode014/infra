# 0023. DNS público dos LXCs independente do Pi

- **Status:** Aceita
- **Data:** 2026-11-02
- **Aceite:** 2026-11-04, PR #69 aprovado e rollout autorizado pelo responsável.

## Contexto

Os LXCs precisam resolver DNS público mesmo sem o AdGuard do Raspberry Pi.
Dispositivos pessoais continuam usando os resolvedores globais do Tailscale;
esta decisão não altera o painel nem a política da tailnet. O Quad9 apresentou
falhas recorrentes. A Mullvad anunciou o encerramento do seu DNS público
criptografado em 02/11/2026, portanto também não é uma alternativa sustentável.

O Ubuntu 26.04 dos LXCs já tem systemd-resolved e systemd-networkd. O Proxmox
gera `/etc/systemd/network/eth0.network`, mas normalmente também reescreve
`resolv.conf`. Configurações manuais via resolvectl em tailscale0 são transitórias
e disputam o mesmo escopo usado pelo Tailscale, mesmo com accept-dns desativado.

## Decisão

DNS público fica num drop-in de `eth0.network`, com `Domains=~.` e
`DNSOverTLS=yes`. Os provedores são DNS4EU Unfiltered
(`86.54.11.100#unfiltered.joindns4.eu`) e Cloudflare
(`1.1.1.1#one.one.one.one`), nesta ordem de preferência declarada. O resolved
mantém estado e troca de servidor ao detectar falhas: não há prioridade estrita,
consultas paralelas por provedor ou retorno automático ao primeiro.
Ambos precisam oferecer o mesmo escopo público. Unfiltered não significa
isenção de bloqueios legais: o DNS4EU informa que ordens judiciais se aplicam.

MagicDNS fica no escopo global do resolved: `DNS=100.100.100.100`, com o domínio
real da tailnet como busca e roteamento, vindo do vault, e `DNSOverTLS=no`.
A correspondência mais específica do domínio privado vence `~.` de eth0.
Tailscale usa `--accept-dns=false`; seu resolvedor local continua disponível.
Não declaramos DNS, endereços nem rotas de tailscale0. Não há timer, script de
reconciliação ou dependência de uma unit `.device`. A migração remove as units
antigas e, depois de preparar o MagicDNS global, limpa o DNS/domínio residual
com `resolvectl revert tailscale0`. O resolved persiste configurações de
resolvectl em `/run`: reiniciar o daemon não descarta esse estado. Sem resíduo,
a reaplicação não executa a limpeza.

O Proxmox continua responsável por endereço e gateway de eth0; o Ansible
acrescenta somente o drop-in DNS. `.pve-ignore.resolv.conf` preserva o symlink
para `/run/systemd/resolve/stub-resolv.conf`. DHCP/RA não importam DNS no
drop-in. O role exige networkd já ativo; não migra gerenciadores de rede.

O stub atende também no endereço da ponte padrão Docker, e o daemon Docker
usa esse listener, preservando outras opções. DNS explícito de composes,
como gluetun, continua com sua própria política. O pi-lab recebe somente DNS
público, pois não participa da tailnet. Não são instalados pacotes.

O Terraform declara `86.54.11.100` e `1.1.1.1` como bootstrap por DNS comum/53
antes do Ansible. Esses endpoints aceitam DNS comum; o runtime do LXC depois
usa TLS estrito. IP + SNI no runtime evita bootstrap para autenticar o DoT.

## Alternativas descartadas

- **Aceitar DNS global nos LXCs:** importa a política do AdGuard junto com
  MagicDNS; não há opção documentada para importar só MagicDNS.
- **accept-dns=true e outra rota ~.:** rotas igualmente específicas podem
  enviar consultas pelos dois caminhos, sem garantir a separação desejada.
- **Configurar tailscale0 e reparar a cada cinco segundos:** disputa uma
  configuração transitória e admite janela de falha; os escopos persistentes
  eliminam a necessidade do reparo.
- **Networkd configurando tailscale0:** desnecessário, pois ele já controla a
  interface pública. Evitamos acrescentar um segundo gerente à interface VPN.
- **Encaminhador adicional:** pode separar domínios e oferecer DoH, mas inclui
  pacote e serviço sem necessidade enquanto TCP/853 estiver disponível.
- **TLS oportunista:** permite downgrade, contrariando a política explícita.
- **Quad9 ou Mullvad:** conectividade recorrente e encerramento anunciado,
  respectivamente. O PR não modifica os upstreams existentes do AdGuard.

## Consequências

O DNS público independe do Pi e do tailscaled enquanto eth0 estiver configurada
e ao menos um provedor responder por TCP/853. Falhas podem impor timeout antes
da troca. Bloqueio dos dois provedores resulta em falha, sem DNS comum de
reserva. `FallbackDNS=` é vazio e não constitui mecanismo de failover.

O MagicDNS depende do tailscaled local e de seu estado da tailnet. Os arquivos
sobrevivem aos reinícios dos daemons; networkd comunica seu estado ao resolved.
Uma mudança no nome da interface ou no gerenciador de rede exige revisar o role.
Público sem eth0 configurada não tem garantia de isolamento: o escopo global
pode ser considerado se a rota DNS ~. desaparecer. O ensaio cobre provedores
indisponíveis mantendo eth0 ativa, não uma troca de topologia de rede.

Os hosts físicos não são alterados aqui. A auditoria e as limitações estão no
runbook: ambos ainda aceitam DNS global, com AdGuard e Cloudflare. Isso oferece
um caminho independente via Cloudflare, mas não prova resiliência por desligamento.
A lista global também não garante filtragem dos dispositivos pessoais: o
Tailscale pode consultar upstreams em paralelo. Preservamos essa configuração
por decisão explícita do usuário.

Aplicação pode reconfigurar eth0 e reiniciar resolved e Docker: produção exige
janela autorizada. Snapshot e rollback preservam arquivos, links, ausências,
preferência accept-dns e estados das units, em vez de supor o estado anterior.

## Referências

- [DNS4EU: endpoints e variantes](https://joindns4.eu/for-public)
- [Cloudflare: DoT em TCP/853](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-tls/)
- [Tailscale: MagicDNS com accept-dns=false](https://tailscale.com/docs/reference/faq/dns-resolv-conf)
- [Tailscale: seleção de múltiplos resolvedores](https://tailscale.com/docs/reference/dns-in-tailscale)
- [systemd 259: roteamento e seleção de servidores](https://www.freedesktop.org/software/systemd/man/259/systemd-resolved.service.html)
- [systemd 259: drop-ins de rede](https://www.freedesktop.org/software/systemd/man/259/systemd.network.html)
- [Mullvad: encerramento do DNS público](https://mullvad.net/en/blog/shutting-down-our-public-encrypted-dns-servers-and-sponsoring-quad9-instead)
