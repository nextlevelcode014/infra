# 0027. O runner do Forgejo usa VM e bridge próprias

- **Status:** Aceita
- **Data:** 2026-11-14

## Contexto

Os checks do `infra` precisam de Git, Python, Terraform, Ansible,
`systemctl --root` e loopback. Os jobs podem executar código de um PR e
devem ser tratados como código de terceiros. Isso vale também para quem
pode publicar branches no repositório. A proteção de `main` controla o
merge. O isolamento da execução fica a cargo do runner e do Proxmox.
[Segurança de Actions](https://forgejo.org/docs/v17.0/admin/actions/security/).

A [rede do lab](0021-lab-numa-bridge-propria-que-so-sai-para-a-internet.md)
permite comunicação entre suas VMs. A rede dos LXCs contém os serviços. O
Forgejo tem endereço HTTPS público atrás de Anubis, que pode responder a
clientes não interativos com a página de desafio.

## Decisão

Rodar um Forgejo Runner persistente como serviço systemd em VM KVM exclusiva.
Terraform cria a VM e Ansible configura a rede, o Docker e o serviço conforme
o [ADR 0002](0002-terraform-cria-ansible-configura.md). O runner começa com
registro exclusivo do repositório `nextlevelcode/infra` e executa um job
por vez em containers Docker descartáveis. Provisionamento e registro são
operações separadas.

### Rede e administração

- Uma NIC numa bridge do Proxmox exclusiva do CI, sem porta física, com
  IPv4 estático e NAT pela uplink. A bridge recebe apenas a VM do runner.
  A faixa e o VMID são definidos com o responsável depois de conferir as
  rotas, a ocupação e as ACLs. A VM fica fora da faixa 900–999 do lab.
- O Proxmox aplica o isolamento antes de ligar a VM. Regras próprias do
  segmento, com aplicação atômica, bloqueiam conexões novas ao host e ao
  segmento e permitem saída pela uplink para HTTPS e para os resolvedores
  públicos designados. Negam destinos internos e especiais, incluindo LAN
  diretamente conectada mesmo se usar endereço público, demais bridges,
  loopback, link-local e CGNAT da tailnet. Filtram a origem esperada e
  bloqueiam IPv6 do segmento no host. No retorno passam as respostas de
  conexões permitidas. O desligamento ou falha de aplicação das regras deve
  impedir a VM de usar a rede sem a proteção.
- A VM fica fora da tailnet. Administração por SSH com chave, via salto
  pelo Proxmox, ou pelo console Proxmox para recuperação. A regra de entrada
  da VM admite SSH só da origem administrativa pela bridge. O firewall da
  VM também bloqueia conexões dos jobs aos serviços e gateways da própria
  VM. O Docker usa redes separadas por job. O filtro no host protege os
  demais segmentos mesmo se um job comprometer a VM.
- Controlador e jobs chegam ao Forgejo pelo endereço público com TLS. O
  Anubis deve deixar passar apenas os métodos e caminhos do RPC do runner
  e do Git HTTPS necessários ao piloto, validados com os clientes reais.
  O Forgejo continua autorizando cada chamada. Restringir a exceção ao
  host público do Forgejo e manter o desafio para a interface e demais
  rotas. Se o endereço de saída for compartilhado, o IP de origem sozinho
  não identifica a VM. Provar o acesso à API de logs usados pelo runner e
  à descoberta e ao fetch Git antes de ampliar o piloto. Artefatos
  adicionais são avaliados quando houver uso.

### Execução e credenciais

- Uma conta de serviço usa o socket Unix do Docker na VM. O acesso da
  conta ao daemon equivale a poder administrativo na VM. Configurar
  `container.docker_host: "-"`, `container.privileged: false` e
  `container.valid_volumes: []`. Usar somente label Docker, rede criada
  para cada job e imagem identificada por digest. Docker sem API TCP.
  Conferir flags, serviços e mounts efetivamente admitidos pelo runner.
  [Acesso ao Docker em Actions](https://forgejo.org/docs/v17.0/admin/actions/docker-access/).
- Fixar a versão do runner com checksum e escolher versão compatível
  com o Forgejo 17, a partir da 13.2 para resumos de job. A imagem
  reproduz as ferramentas da [Etapa 4](../verificacoes-locais.md), com
  Git e o runtime das actions fixadas pelo workflow. O job recebe apenas
  o token temporário do Forgejo com as permissões mínimas do piloto.
  O arquivo de registro fica legível só pelo serviço e pela administração,
  fora do Git e dos mounts. A VM não recebe vault, token de
  provisionamento, chave SSH privada administrativa, credencial de registry
  privado ou acesso a state. A configuração de conexão e o token são
  entregues separadamente dos valores públicos.
  [Registro de runners](https://forgejo.org/docs/v17.0/admin/actions/registration/) ·
  [Resumos de job](https://forgejo.org/2026-10-release-v17-0/#forgejo-actions-job-summaries).
- Orçamento inicial proposto: 2 vCPU, 4 GiB de RAM e 30 GiB de disco,
  capacidade de um job e timeout inicial de 15 minutos. A VM limita o
  consumo agregado. O runtime também limita CPU, memória e PIDs dos
  containers conforme o suporte da versão. O ensaio mede tempo, memória e
  disco com cache desativado. Limites por container sozinhos não limitam
  quantidade de serviços ou uso total de disco.
- Workspace, redes e volumes devem ser descartados após sucesso, falha ou
  cancelamento. O runbook deve cobrir resíduos depois de um crash e impedir
  que um job posterior use esses dados. Verificar espaço e resíduos na
  manutenção, com o runner ocioso, e manter a VM reconstruível pelo código.
  Diante de comprometimento, parar o serviço, revogar o registro e
  reconstruir a VM antes de emitir nova credencial.

## Alternativas avaliadas

- **VM na `vmbr2`:** reutiliza o NAT, mas compartilha camada 2 com os
  experimentos. Isolar um único convidado ali exigiria regras adicionais
  e dependeria da configuração dos demais convidados.
- **LXC ou processo no host do Proxmox:** economiza recursos, mas coloca
  jobs de terceiros no mesmo kernel ou na própria estação de produção.
- **VM por job:** elimina o reaproveitamento da VM entre execuções, ao
  custo de orquestração, provisionamento e limpeza por job.
- **Tráfego do runner direto pela tailnet:** contorna o desafio do Anubis,
  mas cria um caminho para a rede privada e acopla o CI à identidade do
  nó. O caminho público conserva a autenticação do Forgejo e permite
  testar o isolamento sem rotas Tailscale.

## Como aceitar a implementação

1. Antes de registrar o runner, confirmar recursos, VMID, bridge, ACL e
   ordem de inicialização. Validar o filtro na VM e num container com a
   mesma configuração do job. HTTPS externo e DNS público devem
   funcionar. Proxmox, Pi, rede do lab, demais LXCs, serviços da própria
   VM, tailnet e IPv6 devem ficar inacessíveis para conexões novas.
   Conferir contadores ou logs de bloqueio, além da falha do cliente.
2. Conferir o protocolo pelo endereço público. O Ping do Forgejo retorna
   JSON com os dados da sonda e `git ls-remote` retorna o ref esperado.
   A proteção restante é verificada com um pedido anônimo à API que
   continua sujeito ao Anubis. Testar também a conexão autenticada do
   runner, envio de logs e checkout com o token temporário.
3. Em um workflow de ensaio autorizado, comprovar que socket, mounts e
   credencial do serviço ficam indisponíveis. Registrar limites com
   inspeção administrativa do container e provar que o runner rejeita
   pedidos de volume não autorizado, privilégio ou rede do host.
4. Rodar os checks comuns com a imagem fixada, medir recursos e verificar
   limpeza com dois jobs consecutivos, falha, cancelamento e reboot.
   Confirmar que, depois do reboot, a rede continua protegida antes de
   aceitar novos jobs. Registrar comportamento da fila e procedimento de
   recuperação.
5. Se a ativação falhar, parar o serviço e manter a VM desligada até
   restaurar o filtro. Se necessário, desregistrar o runner e reverter
   somente as regras do CI no Anubis. Esse rollback dispensa parar o
   Forgejo.

## Consequências

A separação consome recursos no Proxmox e exige operar um segmento a mais.
Continuam sob revisão a versão e a imagem do runner, o consumo real e as
regras de saída. A implantação e o registro dependem da aprovação de VMID,
faixa, orçamento e regras de rede. O primeiro ensaio registra o Runner só
no `infra`. Adicionar `lab` ou tornar checks obrigatórios pede evidência
nas etapas seguintes.
