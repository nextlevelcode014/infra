# Padrão de role de serviço

O contrato de todo role que sobe um serviço em Docker Compose, em qualquer
host. Serve para ler um role conhecendo os outros e para criar um novo sem
copiar de um que já divergiu. Os porquês estão nos ADRs de `docs/decisoes/`
(na raiz do repo); os passos que só existem no Pi (rota no Caddy, ACL,
`pi-lab`) estão em `docs/pi.md`, "Adicionar um serviço no Pi".

## Estrutura

```
roles/<svc>/
├── defaults/main.yml       # toda variável do role, com prefixo <svc>_
├── meta/main.yml           # dependências (base do host, borg_client, ...)
├── tasks/main.yml          # compose_stack (dir) + config + backup + compose_stack
├── templates/compose.yml.j2
└── templates/<svc>.env.j2  # se o serviço lê env de arquivo
```

O compose é sempre `templates/compose.yml.j2`, mesmo sem variável nenhuma
hoje: a imagem vem de variável (abaixo), então ele é sempre template.

## Variáveis

| Variável | O que é |
|---|---|
| `<svc>_dir` | onde fica o compose no host: `/opt/<svc>` |
| `<svc>_data_dir` | dados persistentes; no Pi, dentro de `{{ appdata_dir }}` (LUKS) |
| `<svc>_image` | imagem com tag fixa; com mais de uma, `<svc>_<componente>_image` |
| `<svc>_standby` | só em serviço com plano B no Pi (`docs/pi-recuperacao.md`) |
| `<svc>_<segredo>` | sempre `"{{ vault_<svc>_<segredo> }}"`; o valor vive no `vault.yml` |

Toda variável do role tem o prefixo do role, inclusive as internas. Segredo
nunca tem valor no `defaults`, só a referência ao vault.

## Imagem

Tag explícita na variável do role, nunca sem tag (ADR 0005): major por
padrão; versão exata em banco que migra no boot, projeto `0.x` e o que fica
exposto à internet. Imagem que o projeto publica com digest (`@sha256:`) pode
ficar assim. `latest` só para imagem sem tag de major publicada e com volta
barata, listada no ADR 0010 (hoje SearXNG, Tailscale, FlareSolverr e
decluttarr); e as exceções com ADR próprio: o gluetun, pela lista de
servidores (0011), e os *arr, com o backup como volta (0012). Imagem repetida em
várias stacks (`tailscale_image`, `gluetun_image`) é uma variável só, em
`group_vars/all`. Subir versão exata: trocar a variável, ler as notas da
versão e reaplicar o playbook do serviço.

## Compose

O ciclo do compose é do role `compose_stack` (ADR 0006): diretório, render do
`compose.yml.j2` do serviço, `up` com `pull: missing` e, em standby, só o pull
sem container. O role do serviço cuida do resto: arquivos de config, backup,
restart depois de mudar um arquivo que o container só lê ao subir.

São dois `include_role`, porque a config do serviço costuma morar dentro do
diretório da stack e precisa dele antes do `up`:

```yaml
- name: Preparar o diretório da stack
  ansible.builtin.include_role:
    name: compose_stack
    tasks_from: dir
  vars:
    compose_stack_dir: "{{ <svc>_dir }}"

# ... config do serviço e backup ...

- name: Subir o <Svc>
  ansible.builtin.include_role:
    name: compose_stack
  vars:
    compose_stack_dir: "{{ <svc>_dir }}"
    compose_stack_standby: "{{ <svc>_standby }}"  # só se houver standby
```

O template vem sozinho (o `compose.yml.j2` do role que chamou). Dono e modo
do diretório: `compose_stack_owner`, `_group`, `_mode` (padrão `root`,
`0750`). Depois do segundo include, `compose_stack_render is changed` diz se
o compose mudou; nesse caso o `up` já recriou o container, e um restart
próprio do role pode pular (o Forgejo faz assim com a chave de assinatura).

Porta publicada sempre num IP específico, nunca em `0.0.0.0`: no Pi em
`{{ ts_ip }}` (ou `lan_ip`, se a LAN precisa), na VPS em `127.0.0.1` (o Docker
passa por cima do UFW, ver `docs/vps.md`).

## Base do host

| Host | Como a base entra | Por quê |
|---|---|---|
| Pi | `pi_host` no `meta/main.yml` do role | cada playbook do Pi prepara o host sozinho (LUKS, Docker) |
| VPS | `vps_host` antes do serviço, no playbook | o mesmo role (Caddy, Anubis) também roda em outros hosts |
| LXC | `playbooks/lxc.yml` | a base é igual para todo container e vem antes de qualquer serviço |

## Backup e restore

- Backup com `include_role: borg_client, tasks_from: backup` e o monitor em
  `uptime_kuma_backups`; receita em `docs/backup.md`, "Serviço novo".
- Serviço em standby não faz backup (ADR 0004).
- Restore é o role `<svc>_restore`, que usa o `borg_restore` e exige
  `-e <svc>_restore_confirmation=...`, com playbook e doc próprios.

## Doc

Um `docs/<svc>.md` (e `docs/<svc>-restore.md`, se houver restore) no modelo
de `docs/README.md`, com a linha no índice dele.

## Role novo: checklist

1. Estrutura e variáveis acima, imagem com tag fixa.
2. Os dois `include_role` do `compose_stack` no `tasks/main.yml` (seção
   "Compose").
3. Backup e restore, se o serviço guarda dado que importa.
4. Playbook em `playbooks/<svc>.yml` e entrada no `site.yml`.
5. Doc no modelo e linha nos índices (`docs/README.md`, tabela de playbooks e
   de roles no `CLAUDE.md`).
6. Decisão que não é óbvia pelo código: ADR em `docs/decisoes/`.

## Fora do padrão

O que ainda falta migrar. Ao migrar um role, tire a linha daqui. Imagem é a
#17.

| Role | O que diverge |
|---|---|
| `immich` | ciclo do compose próprio; versão por `IMMICH_VERSION` no env, com `release` de reserva no compose |
| `nextcloud` | ciclo do compose próprio; AIO e socket proxy em `latest` (o AIO se atualiza pela própria interface: avaliar se é exceção); coturn no compose |
