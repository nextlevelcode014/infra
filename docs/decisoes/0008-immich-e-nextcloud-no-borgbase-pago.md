# 0008. Immich e Nextcloud fazem backup no BorgBase, no plano pago

- **Status:** Aceita, com a exceção da 0016
- **Data:** 2026-10-17

## Contexto

O ADR 0007 pôs o backup do Immich e do Nextcloud AIO num servidor Borg
próprio, num desktop fora de casa com um NVMe livre. Antes da instalação
apareceram dois problemas:

- A máquina é o computador pessoal de outra pessoa e tem que ficar como
  está. O role exigia usuário novo, sshd, regra no UFW e desligar o
  Tailscale SSH dela: com ele ligado, o `tailscaled` atende a porta 22 do
  IP Tailscale e o OpenSSH (o `borg serve` preso a cada repositório) nunca
  recebe a conexão.
- Um NVMe não tem rede própria. Tirar o desktop do caminho exige uma
  máquina dedicada lá (Pi 5 com HAT, ou mini PC), e ela vira mais uma para
  comprar e manter longe de casa.

## Decisão

O plano grátis do BorgBase (10 GB) vira o Small. O Immich volta para o
repositório compartilhado, com prefixo `immich-*`, como os outros serviços.
O Nextcloud AIO usa o Borg dele num repositório separado, `nextcloud-aio`,
na mesma conta.

O servidor Borg próprio sai do repo: role `borg_server`, playbook
`borg-offsite.yml`, inventário `borg.yml`, os `vault_borg_offsite_*` e o
grant de `tag:pi` → `borg-offsite:22` na ACL.

## Alternativas descartadas

- **Seguir com o desktop:** mexe no computador pessoal de outra pessoa, e o
  backup depende de ele estar ligado e acordado de madrugada.
- **Máquina dedicada fora de casa** (Pi 5 com HAT NVMe, ou mini PC usado):
  custo único em vez de mensalidade, mas é hardware novo, mais uma máquina
  para atualizar a distância, e o disco de 512 GB tem limite do mesmo
  jeito.
- **Nextcloud no repositório compartilhado:** o AIO cria o repositório com
  uma senha que ele mesmo gera, e um repositório Borg só tem uma. O
  restore do AIO (*Restore former AIO instance*) também só lê o formato
  dele, então o borgmatic não substitui o Borg do AIO (como no 0007).

## Consequências

- Custo recorrente, que cresce com as fotos. A cota do plano é o limite:
  `docs/backup.md` e a página do repositório no BorgBase mostram o uso.
- Tudo o que tem backup fica num fornecedor só, com uma cópia fora de casa.
- Backup grande do Immich segura a trava do repositório compartilhado por
  horas, então roda à mão, de dia (`docs/immich.md`, "Operação").
- O Nextcloud continua sem monitor no Uptime Kuma; o alerta de
  inatividade do repositório no BorgBase ocupa esse lugar.
