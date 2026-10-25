# 0018. O notebook volta pelo Nextcloud, sem chave privada em disco

- **Status:** Aceita
- **Data:** 2026-10-25

## Contexto

Formatar ou perder o notebook de onde se roda a infra custava uma tarde:
clonar cada repo, restaurar do KeePass os arquivos fora do git e as chaves,
e torcer para nada só no disco ter ficado para trás (projeto sem remote,
branch sem push). O Nextcloud do Pi já existe e já tem backup próprio
(Borg do AIO no BorgBase).

Ao mesmo tempo, o `~/.ssh` misturava dois padrões: a maioria das chaves já
vivia só no agente SSH do Bitwarden, com a `.pub` no `IdentityFile`, mas a
`id_ed25519` dos LXCs (lida pelo `terraform/inventory.tf`) e duas outras
ainda eram arquivo em disco.

## Decisão

O notebook sincroniza `~/.ssh` com `/Laptop/.ssh` e `~/Work` com
`/Laptop/Work` no Nextcloud, sem cache, build nem `.git` (lista em
`~/Work/.sync-exclude.lst`, que vale só para essa pasta e sincroniza junto)
e sem o `sia-projects`. O histórico volta do remote:
o `workflow/bin/repos` guarda pasta e remote de cada repo em
`~/Work/repos.txt` e, na máquina nova, religa cada pasta. Chave privada
fica só no agente do Bitwarden: o `~/.ssh` tem só `.pub`, `config` e
`known_hosts`, e o inventário do Ansible aponta para a `id_ed25519.pub`.

## Alternativas descartadas

- **Sincronizar a home inteira:** apps gravam SQLite, lock e perfil de
  navegador enquanto rodam, e o Nextcloud sincronizando isso ao vivo gera
  conflito e arquivo corrompido. O que é configuração do Omarchy volta com o
  próprio Omarchy; app se reinstala e loga à mão.
- **Sincronizar o `~/.ssh` com as privadas dentro:** as chaves ficariam em
  texto puro no `ncdata` do Pi e no backup do AIO. Com elas só no Bitwarden,
  o que sobe é público.
- **Sincronizar o `.git`:** era metade dos arquivos do `~/Work`, quase todos
  objetos de poucos KB em centenas de diretórios. O upload em paralelo
  travou o Postgres do Nextcloud em deadlock no `oc_filecache`, e o
  histórico já tem cópia no remote.
- **Um par por projeto:** cada projeto novo seria um passo a lembrar, e o
  esquecido é exatamente o que se perde. Um par só no `~/Work`, com lista de
  ignorados, não esquece nada.
- **Incluir o `sia-projects`:** é código do trabalho, num servidor pessoal.
  Ele volta do GitHub.

## Consequências

- O Nextcloud é infra e não conta como cópia fora dela (`fora-da-infra.md`):
  o KeePass continua obrigatório, e a `id_ed25519` privada segue como anexo
  lá, porque o Vaultwarden também é infra.
- Os segredos fora do git que estão no clone (`terraform.tfvars`,
  `*.tfstate`; o `vault.yml` é cifrado) passam a existir também no `ncdata`
  do Pi, dentro do LUKS, e no backup do AIO, cifrado.
- Commit sem push e repo sem remote perdem o histórico numa perda sem
  aviso; os arquivos ficam. O `repos salvar` avisa dos dois, e a lista só
  está em dia até o último `salvar`.
- O Nextcloud não guarda permissão de arquivo: numa máquina nova, os
  scripts voltam sem `+x` e o `repos restaurar` repõe pelo git. Sem privada
  em disco, não há `600` a repor no `~/.ssh`.
- Sem o Bitwarden aberto, nada de SSH: nem Ansible, nem push. O caminho sem
  ele é a privada do KeePass num `ssh-agent` comum (`maquina-nova.md`, "Sem
  o Nextcloud").
- Diretório novo na casa que precise voltar segue a regra: remota é o
  caminho local com `~` trocado por `/Laptop`.
