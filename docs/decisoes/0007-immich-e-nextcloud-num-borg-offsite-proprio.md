# 0007. Immich e Nextcloud fazem backup num Borg offsite próprio

- **Status:** Aceita
- **Data:** 2026-10-17

## Contexto

O Immich (~30 GB de fotos) e o Nextcloud AIO estavam sem backup de verdade:
o repositório Borg compartilhado (BorgBase) tem cota de 10 GB, o Immich só
tinha uma cópia avulsa de setembro, e o backup do AIO ia para o celular
(Termux). Há uma máquina fora de casa, um desktop Omarchy de uso normal com
um NVMe de 512 GB livre, ligada na hora do backup e na tailnet.

## Decisão

Essa máquina vira um servidor Borg offsite (role `borg_server`, host
`borg-offsite`) com um repositório por cliente: o Immich pelo borgmatic do
Pi (`borg_backup_repo`), e o Nextcloud pelo Borg embutido do AIO, apontado
para um repositório remoto. Os outros serviços continuam no BorgBase.

- Cada chave do `authorized_keys` só roda `borg serve
  --restrict-to-repository` no seu repositório: o AIO não alcança o do
  Immich, e vice-versa.
- O disco não tem LUKS: o Borg já cifra no cliente (`repokey-blake2`, e o
  AIO com a senha dele), então a máquina, que fica com outra pessoa, só
  guarda texto cifrado e volta de uma queda de luz sem ninguém digitar
  passphrase.
- A máquina fica sem tag na tailnet, em `hosts.borg-offsite` da ACL, como o
  desktop de administração.
- O Ansible entra com um usuário próprio (`infra`), e o sshd só aceita ele e
  o `borg`, vindos da tailnet.
- O repo não guarda nome nem dono da máquina: ela é `borg-offsite`, e o
  endereço vem do vault. Trocar de máquina é mudar o vault e copiar
  `/srv/borg`.

## Alternativas descartadas

- **Plano maior no BorgBase:** custo recorrente para guardar fotos que
  crescem todo mês, numa máquina que já existe e está fora de casa.
- **AIO com backup local no Pi e borgmatic copiando:** o Pi precisaria de
  espaço para uma segunda cópia inteira do Nextcloud, e o restore ganharia
  um passo (trazer o repositório de volta antes de o AIO enxergá-lo). O AIO
  já fala com repositório remoto.
- **Nextcloud pelo borgmatic, sem o Borg do AIO:** o restore do AIO
  (*Restore former AIO instance*) só lê o formato dele.
- **Tag na máquina:** com tag o nó sai de `autogroup:member`, e o desktop
  perde o acesso aos serviços da tailnet.
- **Ansible com o usuário do desktop:** o sudo dele pede senha, e a
  automação ficaria presa à conta pessoal de quem usa a máquina.
- **`ListenAddress` no IP Tailscale:** o sshd sobe antes do `tailscaled` e
  falha no boot (armadilha já vista no Caddy do Pi); o `AllowUsers` com as
  faixas da tailnet fecha o mesmo sem depender da ordem.
- **Append-only:** protegeria contra um Pi comprometido apagando os
  archives, mas o prune do borgmatic e o do AIO não liberam espaço nesse
  modo, e o disco enche. Fica para quando houver como compactar fora do Pi.

## Consequências

- Backup grande vai para o Borg offsite; o BorgBase fica para o que cabe
  nele. Serviço novo escolhe o repositório pelo `borg_backup_repo`.
- O Immich e o Nextcloud ficam com uma cópia fora de casa, e só uma.
- O backup depende de a máquina estar ligada e acordada na janela da noite,
  num lugar que não se controla; noite perdida aparece no monitor do Immich
  e no aviso do AIO.
- Primeiro host Arch da infra: o `borg_server` não segue o padrão dos roles
  de base Ubuntu, e o Borg dele atualiza com o Arch, não com o Pi.
