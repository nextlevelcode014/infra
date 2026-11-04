# DNS dos LXCs

`playbooks/lxc-dns.yml` configura DNS público independente do Raspberry Pi e
MagicDNS local. Não instala pacotes nem modifica o painel do Tailscale. O role
`lxc_dns` também entra pelo `common`, inclusive no pi-lab. Decisão: ADR 0023.

| Consulta | Caminho |
|---|---|
| Pública | stub local → DNS4EU Unfiltered ou Cloudflare em eth0, TLS obrigatório |
| FQDN da tailnet e nome curto | stub → MagicDNS local global, só nos LXCs com Tailscale |
| Docker sem DNS explícito | listener da ponte Docker → resolved → mesma seleção |

`roles/lxc_dns/defaults/main.yml` declara IP + SNI oficial, nesta preferência:
`86.54.11.100#unfiltered.joindns4.eu` e `1.1.1.1#one.one.one.one`.
O resolved mantém o servidor atual até detectar erro; não garante prioridade
estrita, paralelismo entre provedores ou retorno automático ao primeiro.

O drop-in de `eth0.network` declara `~.` e TLS obrigatório. O drop-in global
do resolved declara `100.100.100.100`, sem TLS, e o domínio privado como busca
e roteamento. O domínio mais específico vence `~.`. O nome real vem do vault.
Não há configuração nossa em tailscale0, timer ou script de reconciliação.
Na migração, depois de preparar o MagicDNS global, o role limpa com
`resolvectl revert tailscale0` o DNS/domínio transitório que a integração
anterior deixou nessa interface. O resolved persiste esse estado em `/run`;
reiniciar o daemon não basta para removê-lo. Reaplicações sem resíduo não
executam essa limpeza.

O Proxmox continua gerando IP e gateway em `/etc/systemd/network/eth0.network`.
O Ansible acrescenta `eth0.network.d/60-lxc-dns.conf`; não substitui o arquivo
base. `/etc/.pve-ignore.resolv.conf` protege o link para o stub do resolved.
O `resolv.conf` gerado em `/run` nunca é editado diretamente.

O bootstrap do Terraform usa os mesmos IPs, por DNS comum/53, antes do Ansible.
Ambos responderam a consultas UDP/53 e DoT autenticado a partir do Caddy, do
Proxmox e do Pi na inspeção de 02/11/2026. Não usar IP de serviço exclusivamente
DoT/DoH como nameserver comum do Terraform.

## Produção em 04/11/2026

Rollout autorizado pela branch do PR #69, antes do merge, na ordem Caddy →
Forgejo → Vaultwarden. Código final aplicado: `1c76eea`. A regressão encontrada
na primeira aplicação e sua validação estão registradas abaixo.

| Host | Aplicação inicial (`4e66690`) | Limpeza (`1c76eea`) | Reaplicação final |
|---|---|---|---|
| Caddy (`10.50.0.200`) | `changed=7` | `changed=1` | `changed=0` |
| Forgejo (`10.50.0.201`) | `changed=7` | `changed=1` | `changed=0` |
| Vaultwarden (`10.50.0.202`) | `changed=7` | `changed=1` | `changed=0` |

Todas as execuções terminaram com `failed=0` e `unreachable=0`. O check/diff
inicial mostrou `changed=5` por host. O da correção mostrou `changed=0`:
`resolvectl revert` é pulado em check mode, que não simula a limpeza transitória.

Depois da correção, cada host passou duas vezes pela matriz, com pelo menos
15 segundos entre execuções: público por eth0 com `~.` e DoT obrigatório,
MagicDNS FQDN/curto no host e em containers reais sem DNS explícito, MagicDNS
global e nenhum DNS/domínio residual em tailscale0. Units, script e vínculos
antigos ausentes; stub, marker, rede, gateway, daemon.json, identidade e
`accept-dns=false` preservados. O InvocationID do Docker e os IDs dos containers
de aplicações permaneceram iguais ao baseline.

Caddy respondeu HTTPS `200` para `/alive` e página inicial do Vaultwarden.
Forgejo respondeu `/api/healthz` com `status: pass` e sua página inicial;
Vaultwarden respondeu `/alive` e página inicial. Docker não reiniciou, e não
houve reboot ou rollback de produção. Nenhum Terraform apply integrou o rollout.

O Caddy recebeu a imagem `postgres:16-alpine` com download autorizado. Forgejo
usou a mesma tag já local; Vaultwarden usou `vaultwarden/server:1.37.4` já local,
somente com shell/getent, sem iniciar outra instância da aplicação. Todos os
containers de consulta foram temporários, com `--rm` e `--pull=never`.

Os três hosts mantêm a referência original de rollback em
`/root/antes-lxc-dns-pr69-producao`, com diretório `700 root` e `estado.json`
`600 root`. Ela não foi sobrescrita pela correção. O utilitário correspondente
está em `/root/lxc-dns-estado.py`. Para conferir ou restaurar um host, escolha
seu IP na tabela antes de executar:

```bash
dns_ip=10.50.0.200
ssh "root@$dns_ip" 'stat -c "%a %U %n" /root/antes-lxc-dns-pr69-producao /root/antes-lxc-dns-pr69-producao/estado.json'
# Somente em contingência, na janela autorizada:
ssh "root@$dns_ip" 'python3 /root/lxc-dns-estado.py restaurar /root/antes-lxc-dns-pr69-producao'
```

Confira: permissões acima; depois de restaurar, DNS e saúde dos serviços,
incluindo a integração antiga correspondente ao host, conforme a seção
Rollback. A restauração é manual porque escolhe um host e interrompe serviços;
não executar apenas para testar a existência da referência.

## Antes de aplicar

- Ubuntu LXC com resolved instalado, networkd **já ativo** e arquivo
  `/etc/systemd/network/<interface>.network` existente; o role recusa outro
  gerenciador de rede. `lxc_dns_interface` é `eth0` por padrão.
- TCP/853 liberado para pelo menos um dos dois provedores, certificados CA e
  relógio corretos. O relógio do LXC é o do host Proxmox.
- SSH pela bridge ou console do Proxmox disponível: não depender de MagicDNS
  para reparar DNS. Use a configuração SSH com salto já descrita em `proxmox.md`.
- Janela autorizada para recarregar a rede, reiniciar resolved e eventualmente
  Docker. A alteração dos arquivos neste PR não autoriza aplicar em produção.
- Sem mudança de topologia: a separação pressupõe que eth0 mantenha o escopo
  `~.`. Se a interface/configuração desaparecer, o escopo global pode voltar a
  receber consultas sem correspondência. Falha de provedores não remove `~.`.

O listener usa `docker0.ipv4.address`, ou `172.17.0.1` antes do Docker existir.
Declare `lxc_dns_docker_address` se usar outra ponte. Ele não ocupa a porta LAN
usada pelo AdGuard no pi-lab. Outras opções do daemon, como `data-root`, são
preservadas; DNS explícito nos composes mantém sua política.

## Testes locais

De dentro de `ansible/`, sem inventário real nem vault:

```bash
python3 -m unittest discover -s roles/lxc_dns/tests -p 'test_*.py' -v
python3 roles/lxc_dns/tests/integracao.py
python3 roles/lxc_dns/tests/integracao.py --rede-real --magicdns-real
python3 roles/lxc_dns/tests/provedores.py
```

Confira: os testes terminam com código zero e listam os cenários aprovados.
O primeiro testa restauração de arquivos, links quebrados, modos e ausências,
além da rejeição de manifestos inválidos. Com `systemctl` disponível, também
testa o rollback de habilitação permanente para `enabled-runtime` usando
`systemctl --root` numa árvore temporária. Não executa serviços no host.

`integracao.py` usa namespaces de usuário, montagem, PID e rede: `/etc`,
`/run`, `/proc`, `/sys` e D-Bus são próprios do teste. Requer ferramentas já
instaladas: `unshare` com subuids/subgids, `newuidmap`, `newgidmap`, iproute2,
D-Bus, systemd, OpenSSL, dig, Python, Jinja2 e PyYAML. Não instala nada.

Sem flags, usa provedores e MagicDNS fictícios e uma CA de teste confiada só no
namespace. Renderiza os templates reais, executa networkd e resolved reais,
verifica libc/getent, o listener da ponte, FQDN e nome curto, falha imediata e
handshake sem resposta em cada provedor, recuperação, falha simultânea,
reinícios dos dois daemons, limpeza de tailscale0 e DNS público sem MagicDNS.

`--rede-real` encaminha bytes TLS por sockets Unix para DNS4EU e Cloudflare
reais; o resolved de teste valida o certificado/SNI real. A falha é injetada
somente no transporte do teste. `--magicdns-real` usa o tailscaled **já ativo**
na máquina e o peer `caddy-lxc`, sem alterar preferências ou reiniciar o daemon.
O domínio e IP reais ficam só no diretório privado `/tmp/lxc-dns-integracao-*`,
fora do Git. Não publique esses logs. A indisponibilidade do MagicDNS nesse
ensaio é simulada no encaminhamento, nunca parando o Tailscale real.

Os artefatos e logs ficam no diretório temporário informado. O teste não altera
o host nem reutiliza a auth key. É manual porque precisa de namespaces locais
e, com as flags, de conectividade externa e Tailscale já autenticado.

`provedores.py` mede três consultas A de `example.com` por UDP e três por DoT
para cada provedor. A medição DoT inclui uma conexão nova e autenticação TLS;
não representa a latência de uma conexão persistente ou cache aquecido.
Para repetir a sondagem somente de leitura numa máquina, sem copiar arquivos:

```bash
ssh root@<ip-do-lxc> python3 - < roles/lxc_dns/tests/provedores.py
ssh root@<proxmox_host> python3 - < roles/lxc_dns/tests/provedores.py
ssh ubuntu@<host-do-pi> python3 - < roles/lxc_dns/tests/provedores.py
```

Confira: `sucessos: 3`, sem erros, nos quatro resultados. Isso mede conexões
diretas, não altera nem prova o failover do resolvedor configurado nesses hosts.

## Resultado da validação de 02/11/2026

Sem aplicar a refatoração em produção:

| Validação | Resultado |
|---|---|
| Integração sem rede externa, systemd 262.1 local | Aprovada; provedores e MagicDNS fictícios |
| Integração com provedores e MagicDNS reais, systemd 262.1 | 30 cenários aprovados |
| Mesma matriz com cache limpo e binários systemd 259.5 do Caddy | 30 cenários aprovados |
| Rollback de arquivos | 3 testes aprovados; restauração exata e rejeição de entrada inválida |
| Ansible | YAML e syntax-check com inventário isolado aprovados |
| Terraform | `fmt -check local.tf` e `validate` aprovados; sem plan/apply |

Na matriz final 259.5, o failover com interrupção imediata levou 0,107 s de
DNS4EU para Cloudflare e 0,740 s no sentido inverso. Com handshake sem resposta,
levou 10,295 s e 10,757 s, respectivamente. O cache foi limpo antes de cada
consulta. A recuperação funcionou sem exigir retorno ao provedor preferido.
Ambos indisponíveis fizeram a consulta pública falhar, sem usar MagicDNS;
o MagicDNS continuou respondendo. Os tempos são observações, não SLA.

DoT real valida CA e SNI; a matriz offline valida também que nomes públicos
não chegam ao MagicDNS e nomes privados não chegam aos provedores públicos.
O Caddy respondeu a uma consulta MagicDNS direta com `CorpDNS: false`, sem
qualquer mudança de configuração.

Sondagens diretas, três amostras por protocolo/provedor; todos tiveram 3/3
sucessos. Medianas em milissegundos (DoT inclui conexão nova):

| Origem | DNS4EU UDP | Cloudflare UDP | DNS4EU DoT | Cloudflare DoT |
|---|---:|---:|---:|---:|
| Notebook local | 172,7 | 55,7 | 780,0 | 151,5 |
| Caddy LXC | 184,6 | 60,0 | 788,2 | 92,1 |
| Proxmox físico | 180,9 | 60,3 | 771,5 | 91,4 |
| Raspberry Pi físico | 180,8 | 60,1 | 783,4 | 96,8 |

A preferência por DNS4EU foi mantida conforme a decisão do usuário, apesar
da latência maior nesta rede. Os endpoints e suporte DoT são publicados por
[DNS4EU](https://joindns4.eu/for-public) e
[Cloudflare](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-tls/).

Para repetir com os binários 259 sem instalar pacotes, copie apenas arquivos
de leitura do LXC para um diretório descartável:

```bash
mkdir -p /tmp/lxc-dns-systemd259
ssh root@<ip-do-lxc> 'tar -h -C / -cf - usr/lib/systemd/systemd-resolved usr/lib/systemd/systemd-networkd usr/lib/x86_64-linux-gnu/systemd/libsystemd-shared-259.so usr/lib/x86_64-linux-gnu/libcrypt.so.1 usr/bin/resolvectl usr/bin/networkctl' | tar -xf - -C /tmp/lxc-dns-systemd259
LXC_DNS_SYSTEMD_ROOT=/tmp/lxc-dns-systemd259 LD_LIBRARY_PATH=/tmp/lxc-dns-systemd259/usr/lib/x86_64-linux-gnu:/tmp/lxc-dns-systemd259/usr/lib/x86_64-linux-gnu/systemd python3 roles/lxc_dns/tests/integracao.py --rede-real --magicdns-real
```

Confira: a matriz termina com código zero. São binários/tools 259.5 em
namespaces locais, com bibliotecas compatíveis do host; não uma inicialização
completa do Ubuntu LXC. O procedimento é manual porque seleciona uma máquina
fonte e requer seus acessos. Nada é instalado ou iniciado nessa máquina fonte.

O ensaio em namespaces cobre o listener destinado ao Docker por DNS UDP,
sem executar o engine. A validação no LXC real está registrada abaixo.
O paliativo antigo do Caddy permanece como estava; este trabalho não removeu
o timer em produção.

### Revisão de 03/11/2026

A integração local sem rede externa passou novamente nos 30 cenários.
YAML do role, syntax-check do playbook DNS com inventário isolado,
`terraform fmt -check local.tf` e `terraform validate` também passaram.
Os quatro testes de rollback passaram, incluindo a regressão que retira a
habilitação permanente criada pelo role quando o snapshot registrou
`enabled-runtime`. Esta revisão não aplicou mudanças em produção.

### Regressão do estado transitório em 04/11/2026

A aplicação inicial do commit `4e66690` removeu arquivos e units, mas deixou
DNS/domínio em tailscale0 nos três hosts. A conferência adicional durante o
rollout detectou esse resíduo: resolved restaura o estado de
`/run/systemd/resolve/netif/`, mesmo depois de reiniciar sem unit legada ativa.
As consultas e aplicações continuavam funcionando; isso não bastava para
comprovar a migração completa. O avanço foi interrompido para corrigir e
validar a limpeza explícita antes de reaplicar.

O commit `1c76eea` acrescenta `resolvectl revert tailscale0` após preparar o
MagicDNS global e somente quando há DNS/domínio residual. A matriz local
passou em **32 cenários**, incluindo persistência do legado após restart,
limpeza e resolução pública/privada depois dela. Os quatro testes de rollback
também passaram.

No LXC 902, uma cópia independente do role corrigido passou nos perfis
oneshot e timer: DNS público/MagicDNS FQDN/curto no host e Docker, sentinela
SQL, rede e identidade preservadas, ausência de DNS/domínio em tailscale0 e
reaplicações `changed=0`. A limpeza persistiu após restart do resolved no
perfil timer. Rollbacks restauraram ambos os perfis, inclusive execução do
timer e oneshot ativa. O laboratório voltou ao baseline original.

### Validação autorizada no pi-lab em 03/11/2026

Role do commit `5a4627f`, no pi-lab (VMID 203, `10.50.0.203`), com
systemd `259.5-0ubuntu3`. O alvo foi confirmado no inventário do Terraform e
no Proxmox antes do ensaio. O pi-lab não tem Tailscale; este teste não valida
MagicDNS nem o reinício de tailscaled.

| Verificação | Resultado |
|---|---|
| Snapshot de arquivos e estados das units | `/root/antes-lxc-dns-pr69-staging`, diretório `700 root`, manifesto `600 root`; preservado após reboot |
| Ansible check/diff | Somente pi-lab, `changed=4`, `failed=0`, `unreachable=0` |
| Aplicação | `changed=5`, `failed=0`, `unreachable=0`; inclui o handler `networkctl reload`, que o check pula |
| Reaplicação antes e depois do reboot | Ambas `changed=0`, `failed=0`, `unreachable=0`; sem handlers |
| DNS público do host | `resolvectl query -4 example.com` por eth0; `~.` e `+DNSOverTLS`; nenhum DNS global |
| Sondagem direta de provedores | DNS4EU e Cloudflare: 3/3 UDP e 3/3 DoT autenticado por CA/SNI em cada um |
| Transporte da consulta pelo stub, após limpar cache | 25 pacotes TCP/853 para DNS4EU; nenhum pacote porta 53 na captura de eth0 |
| Docker real | Imagem local `postgres:16-alpine`, bridge padrão, sem `--dns` e sem pull; consulta A/AAAA pelo listener `172.17.0.1` |
| Reinício de resolved | DNS do host e do container funcionais depois do restart |
| Reboot via Proxmox | `pct reboot 203`; `boot_id` mudou; networkd, resolved e Docker voltaram ativos; DNS do host e container funcionais |
| Preservação | Hashes SHA-256 do `eth0.network` e `daemon.json` iguais antes/depois, inclusive após reboot; gateway, marker e symlink do stub preservados |

Docker já tinha o DNS `172.17.0.1`: o role não alterou seu arquivo nem
reiniciou o daemon. Os containers de aplicações estavam parados e continuam
parados; somente os containers temporários de consulta foram criados e
removidos com `--rm`. Nenhum pacote ou imagem foi instalado.

O ensaio usou inventário temporário isolado para não carregar o vault inteiro:
o role DNS de staging não precisa de segredos. Para reproduzir essa seleção,
de dentro de `ansible/`:

```bash
mkdir -p /tmp/pr69-staging
cat > /tmp/pr69-staging/inventory.yml <<'EOF'
all:
  children:
    lxc:
      hosts:
        pi-lab:
          ansible_host: 10.50.0.203
          ansible_user: root
          ansible_ssh_private_key_file: ~/.ssh/id_ed25519.pub
          ansible_ssh_common_args: '-J root@<proxmox_host>'
          lxc_vmid: 203
    staging:
      hosts:
        pi-lab: {}
    pi_staging:
      hosts:
        pi-lab: {}
EOF
ansible-playbook -i /tmp/pr69-staging/inventory.yml playbooks/lxc-dns.yml --limit pi_staging --list-hosts
ansible-playbook -i /tmp/pr69-staging/inventory.yml playbooks/lxc-dns.yml --limit pi_staging --check --diff
```

Confira: substitua `<proxmox_host>` pelo host do salto; somente `pi-lab` deve
aparecer. Esse inventário valida o playbook DNS isolado, não os playbooks
completos do Pi. A criação é manual porque exige confirmar o alvo e seu acesso.
Após o snapshot e com janela autorizada, rode o mesmo comando sem `--check
--diff` e repita para conferir `changed=0`:

```bash
ansible-playbook -i /tmp/pr69-staging/inventory.yml playbooks/lxc-dns.yml --limit pi_staging
ansible-playbook -i /tmp/pr69-staging/inventory.yml playbooks/lxc-dns.yml --limit pi_staging
```

O teste Docker executado antes e depois de cada reinício foi:

```bash
ssh root@10.50.0.203 'docker run --rm --pull=never --network bridge --entrypoint /bin/sh postgres:16-alpine -ec "cat /etc/resolv.conf; busybox nslookup example.com"'
```

Confira: nameserver `172.17.0.1` e respostas A/AAAA. É manual porque cria um
container temporário no host; requer a imagem já presente.

O utilitário deste ensaio ficou em `/root/lxc-dns-estado-pr69.py`; o snapshot
é de configuração, não de discos do Proxmox. Não foi necessário rollback.
Para a contingência correspondente a esse snapshot:

```bash
ssh root@10.50.0.203 'python3 /root/lxc-dns-estado-pr69.py restaurar /root/antes-lxc-dns-pr69-staging'
```

Confira DNS e serviços conforme a seção Rollback. É manual porque reconfigura
a rede e reinicia serviços. Não executar apenas para conferir o snapshot.

O pi-lab fica com a nova configuração DNS e o snapshot guardado; produção não
foi alterada por esta etapa. A validação com Tailscale está registrada abaixo.

### Validação autorizada com Tailscale em 03/11/2026

Experimento versionado em
[lab/experimentos/lxc-dns (PR #5)](https://forge.nextlevelcode.pro/nextlevelcode/lab/pulls/5),
com cópia independente do role de `infra@5a4627f`, identificada por checksums.
Alvo: LXC unprivileged 902, `lab-dns-pr69`, pool lab, vmbr2; state próprio e
token existente `lab@pve`. Ubuntu 26.04, systemd `259.5-0ubuntu3`, Tailscale
`1.104.5`, Docker `29.1.3`. Nenhuma alteração em ACLs, chaves existentes ou
DNS global da tailnet. O peer MagicDNS foi o desktop de administração.

| Verificação | Resultado |
|---|---|
| Baseline e snapshot | DNS funcional e Postgres descartável com sentinela SQL; snapshot 700/root, manifesto 600/root |
| Check/diff / aplicação | `changed=6` / `changed=7`, sem falhas ou hosts inalcançáveis; Docker reiniciou ao mudar DNS |
| Reaplicação antes/depois do reboot | Ambas `changed=0`, sem handlers |
| Público e MagicDNS FQDN/curto | Aprovados no host e em novos containers na bridge padrão, sem `--dns` |
| Restart tailscaled | Janela de startup observada; matriz completa após 15 s aprovada, sem reaplicar configuração |
| Restart resolved | Verificações imediatas e matriz completa após 15 s aprovadas |
| Reboot pelo Proxmox | boot_id novo; matriz imediata e após 15 s aprovada, stub/marker/DoT preservados |
| DoT autenticado direto | DNS4EU e Cloudflare: 3/3 sucessos por provedor; UDP também 3/3 |
| Rollback completo com carga ativa | Arquivos, links, modos, ownership e ausências iguais ao snapshot; Docker original restaurado e efetivamente reiniciado |
| Preservação | Hashes de eth0.network e baseline, gateway, identidade Tailscale, accept-dns=false e estados das units preservados; mesmo container e sentinela SQL |

A primeira verificação completa imediatamente após reiniciar tailscaled falhou
com `CalledProcessError`. A recuperação passou; no diagnóstico de um segundo
restart, o nó ainda não estava Running aos 0,042 s, o público respondeu aos
0,410 s e o MagicDNS FQDN aos 5,420 s. A matriz completa iniciada após 15 s
passou. A falha imediata foi mantida no registro; não houve reparo no role,
timer ou reaplicação para recuperar DNS. Esses tempos não são garantias.

O baseline do ensaio tinha Cloudflare por DoT e MagicDNS global nos drop-ins
50, mais Docker com DNS explícito `1.1.1.1`, data-root e opções de logs. O
role acrescentou seus drop-ins 60 e mudou somente a opção DNS do Docker.
O rollback removeu os arquivos antes ausentes, restaurou os demais exatamente
e preservou os drop-ins 50. O InvocationID do Docker mudou e o mesmo workload
voltou com a sentinela SQL. Após rollback, público e MagicDNS funcionaram no
host; Docker voltou a resolver público com seu DNS explícito anterior.

As medianas DoT com conexão nova foram 772,5 ms (DNS4EU) e 90,7 ms
(Cloudflare), três amostras por provedor. Não medem cache/conexão persistente;
os provedores continuam os mesmos, com eventual revisão na issue #71.

O LXC 902 ficou ativo no baseline após rollback, com snapshot e workload para
inspeção; não foi destruído. O arquivo temporário da senha do vault foi removido.
O README do experimento contém os comandos de criação, matriz, diagnóstico,
rollback e limpeza, cada qual com seu escopo de autorização.

Essa primeira matriz partiu de um baseline novo. O complemento abaixo cobre
as instalações legadas encontradas em produção. Não houve aplicação em
produção nem mudança do paliativo do Caddy.

### Complemento: migração e rollback dos estados atuais de produção

Em 03/11/2026, Caddy, Forgejo e Vaultwarden foram inspecionados somente por
leitura. Foram coletados hashes, metadados, estados/vínculos de units e campos
DNS sanitizados; nenhum arquivo privado completo foi necessário para montar
as fixtures. O código histórico foi copiado do Git e conferido contra os
hashes dos hosts, normalizando o domínio privado.

| Alvos auditados | Perfil reproduzido no 902 | Origem |
|---|---|---|
| Caddy | Script e timer de 5 s ativos; oneshot sem RemainAfterExit; quatro vínculos | `infra@af3f64e` |
| Forgejo e Vaultwarden | Oneshot active/exited com RemainAfterExit; três vínculos; sem timer/script | `infra@63d1070` |

Nos três, o resolved.conf legado é idêntico por SHA-256: Quad9/Cloudflare
globais com TLS, MagicDNS na interface tailscale0 pela integração antiga,
accept-dns=false, stub protegido pelo marker e Docker em `172.17.0.1`.
O experimento preserva os endereços, identidade, credenciais e dados do lab;
reproduz as configurações DNS, units, modos, vínculos e estados auditados.
Fixtures, auditoria reduzida, comparação e sequência executável estão no
experimento `lab/experimentos/lxc-dns` do PR lab #5, em `LEGADO.md`, `legado/`
e `scripts/legado.py`.

Cada perfil passou por baseline funcional, snapshot próprio, check/diff,
aplicação, reaplicação, reinícios reais de tailscaled/resolved, reboot pelo
Proxmox, reaplicação e rollback com a carga Postgres ativa. Resultados:

- Check/diff `changed=4` e aplicação `changed=6`, sem falhas, em ambos.
- Reaplicações antes/depois de reboot com `changed=0`, sem handlers.
- Público por eth0 com os dois provedores e DoT, MagicDNS FQDN/curto no host
  e em novos containers sem DNS explícito, antes/depois dos reinícios e boot.
- Migração removeu todas as units, scripts e vínculos de cada perfil.
- Rollback restaurou exatamente arquivos, modos, ownership, links e ausências,
  além dos estados de habilitação/atividade. No perfil do Caddy, o timer voltou ativo e
  foi observada uma nova execução real do script com sucesso. No outro perfil,
  a unit voltou active/exited e os três vínculos foram restaurados, sem criar
  timer ou script inexistentes no estado anterior.
- Rede, identidade Tailscale, configuração Docker, mesmo container e sentinela
  SQL preservados. Docker não reiniciou na migração/rollback desses perfis:
  seu DNS já era o desejado; o InvocationID foi conferido. O ensaio inicial
  cobre separadamente a alteração de DNS que exige restart do daemon.

As matrizes após reinícios foram conferidas após 15 s de estabilização, sem
promessa de resolução privada ininterrupta durante startup. O 902 foi
restaurado ao baseline original e o validador anterior passou; snapshots por
perfil ficaram guardados para inspeção. O role e o utilitário de rollback
não precisaram de alteração para esses cenários.

Esta matriz cobre os dois estados distintos auditados nos três alvos. Antes
de implantar, repetir a auditoria e interromper se aparecer estado diferente
das fixtures; cada host ainda exige snapshot, check/diff e validação individual
na janela autorizada. Desligamentos físicos e as melhorias #72–#74 continuam
fora do escopo. Essa validação de 03/11/2026 foi concluída antes da aplicação
em produção.

## Aplicação autorizada e conferência

1. **Guardar o estado anterior uma única vez por mudança e por host.**

   ```bash
   scp roles/lxc_dns/files/estado.py root@<ip-do-lxc>:/root/lxc-dns-estado.py
   ssh root@<ip-do-lxc> 'python3 /root/lxc-dns-estado.py salvar /root/antes-lxc-dns-refatoracao'
   ssh root@<ip-do-lxc> 'test -s /root/antes-lxc-dns-refatoracao/estado.json && stat -c "%a %U" /root/antes-lxc-dns-refatoracao'
   ```

   Confira: snapshot existe e diretório é `700 root`. O utilitário recusa
   sobrescrever snapshots. Guarda arquivos, links, ausências, permissões,
   accept-dns, estados das units e se Docker estava ativo. Não publique o JSON:
   pode conter o domínio privado e outras opções do Docker.
   É manual porque escolher a referência de rollback e interromper serviços
   exige uma janela autorizada, não uma execução implícita do role.

2. **Começar pelo staging sem Tailscale.**

   ```bash
   ansible-playbook playbooks/lxc-dns.yml --ask-vault-pass --limit pi_staging --check --diff
   ansible-playbook playbooks/lxc-dns.yml --ask-vault-pass --limit pi_staging
   ssh root@10.50.0.203 'readlink -f /etc/resolv.conf; resolvectl status eth0; getent ahostsv4 example.com'
   ```

   Confira: link para o stub, DNS4EU e Cloudflare em eth0, `~.` e `+DNSOverTLS`;
   consulta pública retorna endereços. Reaplique: deve resultar em `changed=0`,
   sem recarga de rede ou reinício de serviços. O pi-lab não valida MagicDNS.

3. **Em LXC de teste com Tailscale autorizado, validar ambos os caminhos.**

   ```bash
   resolvectl query example.com
   getent ahostsv4 <peer>.<tailnet>.ts.net
   getent ahostsv4 <peer>
   resolvectl dns tailscale0
   resolvectl domain tailscale0
   systemctl list-timers lxc-magicdns.timer
   tailscale debug prefs
   ```

   Confira: público por eth0, FQDN e nome curto retornam o peer, timer ausente
   e `CorpDNS: false`. As linhas de tailscale0 devem estar vazias depois dos
   dois-pontos; DNS/domínio privado ficam no escopo global. Consultas bem-sucedidas
   e units removidas, sozinhas, não comprovam a limpeza do estado legado.
   Não publique a saída completa de prefs/status.
   Um lab que entre na tailnet usa auth key efêmera e `tag:lab`; nunca a chave
   de produção. Criá-lo ou mudar a ACL exige autorização própria.

4. **Conferir containers e persistência no teste.**

   ```bash
   dig @<ip-da-ponte-docker> example.com +short
   docker run --rm --pull=never <imagem-local-com-getent> getent ahostsv4 example.com
   systemctl restart systemd-resolved
   getent ahostsv4 example.com
   getent ahostsv4 <peer>
   systemctl restart tailscaled
   getent ahostsv4 example.com
   getent ahostsv4 <peer>
   ```

   Confira novamente após 15 segundos e após reboot autorizado do LXC.
   O teste de container usa imagem existente, sem `--network host` nem `--dns`.
   Reboot verifica que o Proxmox preservou symlink e drop-in. Esses passos são
   manuais porque reiniciam serviços ou a máquina; não rodar em produção sem
   janela. Um reinício do tailscaled pode interromper MagicDNS enquanto ele
   está parado, mas não deve afetar o DNS público de eth0.

5. **Somente depois do ensaio, e com autorização de produção, um LXC por vez.**

   ```bash
   ansible-playbook playbooks/lxc-dns.yml --ask-vault-pass --limit caddy --check --diff
   ansible-playbook playbooks/lxc-dns.yml --ask-vault-pass --limit caddy
   ```

   Confira todos os caminhos antes de repetir para Forgejo e Vaultwarden.
   O `--check` não comprova resolução nem disponibilidade pós-reinício.

## Rollback

Pela bridge ou console, com o snapshot correspondente ao mesmo host:

```bash
ssh root@<ip-do-lxc> 'python3 /root/lxc-dns-estado.py restaurar /root/antes-lxc-dns-refatoracao'
ssh root@<ip-do-lxc> 'getent ahostsv4 example.com; systemctl is-active docker; readlink -f /etc/resolv.conf'
```

Confira DNS e serviços. O utilitário restaura a presença **ou ausência** dos
arquivos gerenciados, inclusive symlink original e marker do Proxmox; recarrega
a rede, reinicia resolved, restaura accept-dns e estados das units. Se o
snapshot era da versão com timer, restaura também essa integração. Docker só
recebe try-restart se estava ativo e seu arquivo mudou. Não habilita
accept-dns indiscriminadamente nem remove opções alheias do Docker.

Rollback é manual porque interrompe serviços e reconfigura a rede; não execute
pela única conexão que depende do DNS sendo reparado. Ele restaura o ponto do
snapshot: configurações posteriores nesses mesmos arquivos serão perdidas.
Não tenta reverter dados das aplicações nem alterações de topologia externas.

## Hosts físicos e limitações

Auditoria somente de leitura em 02/11/2026:

| Host | Estado DNS observado | Dependências e conclusão |
|---|---|---|
| Proxmox | `/etc/resolv.conf` com Quad100 IPv4/IPv6; accept-dns=true; base anterior no roteador LAN | tailscaled local; recebe AdGuard do Pi e Cloudflare; Cloudflare oferece caminho que não passa pelo Pi |
| Raspberry Pi | resolved/networkd ativos; stub local; accept-dns=true; DNS do roteador em eth0, Quad100 em tailscale0 | recebe AdGuard e Cloudflare; não apareceu um resolvedor hospedado no Proxmox na lista global |

O Tailscale não garante ordem de upstreams; quando faz proxy pode consultá-los
em paralelo e usar a resposta mais rápida. A configuração atual não cria
exclusividade do Pi no Proxmox, mas também não garante filtragem de todas as
consultas dos dispositivos pessoais. Nada foi alterado no painel.

As sondagens diretas dos dois provedores funcionaram nos dois hosts físicos.
Não provam recuperação do sistema com Pi/Proxmox realmente desligado. A
configuração upstream do roteador LAN não foi auditada. Permanecem dependências
com roteador, WAN e tailscaled local; a independência física completa precisa
ser ensaiada em janela própria, mantendo acesso de contingência.

O PR não muda o Pi físico, Proxmox físico nem AdGuard. O PR #68 ainda declara
Quad9 e Mullvad como upstreams do AdGuard; o encerramento anunciado da Mullvad
em 02/11/2026 é tratado separadamente na [issue #70](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/70). Não reescrever o
ADR 0022 aceito nem trocar upstreams do AdGuard incidentalmente neste PR.

Reverse DNS da tailnet e nomes compartilhados de outras tailnets não recebem
rotas adicionais aqui. Aplicações que escolhem DNS próprio contornam esta
política. TCP/853 bloqueado para ambos os provedores resulta em falha fechada;
não há downgrade para UDP/53 nem DoH automático no resolved.
