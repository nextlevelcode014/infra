# Decisões (ADR)

Cada arquivo aqui é um **ADR** (*Architecture Decision Record*): uma decisão
que mudou como o infra funciona, com o porquê. O código mostra *o que* foi
feito; o ADR guarda *por que*, e o que foi descartado, para que daqui a seis
meses a pergunta "isso foi de propósito?" tenha resposta.

## Quando escrever

Escreva um ADR quando a decisão:

- seria estranha para quem lê o código sem contexto ("por que não tem timer?");
- descartou uma alternativa óbvia;
- vira regra para o que vier depois (padrão de role, onde fica segredo).

Não precisa de ADR para o que o código já explica sozinho, nem para correção
de bug. Na dúvida, um ADR curto custa menos que esquecer.

## Como

1. Copie o modelo abaixo para `NNNN-<decisao-em-kebab-case>.md`, com o
   próximo número livre. O nome diz a decisão, não o assunto:
   `0003-atualizacao-do-pi-sob-demanda.md`, não `0003-atualizacoes.md`.
2. Preencha e acrescente uma linha no índice.
3. Vai no mesmo PR da mudança que ele explica.

**ADR aceito não se reescreve.** Mudou de ideia? Escreva um ADR novo e, no
antigo, troque só o status para `Substituída por NNNN`. O histórico de por que
se mudou de ideia vale tanto quanto a decisão.

Decisão antiga registrada depois do fato leva a data em que foi tomada e a
fonte (PR, commit ou comentário de onde o motivo foi tirado).

## Índice

| ADR | Decisão | Status |
|---|---|---|
| [0001](0001-registrar-decisoes-em-adr.md) | Registrar decisões em ADR | Aceita |
| [0002](0002-terraform-cria-ansible-configura.md) | Terraform cria a máquina, Ansible configura | Aceita |
| [0003](0003-atualizacao-do-pi-sob-demanda.md) | Atualização do Pi sob demanda, só imagem | Aceita |
| [0004](0004-standby-com-imagens-ja-baixadas.md) | Standby com as imagens já baixadas | Aceita |
| [0005](0005-imagem-com-tag-fixa-em-variavel.md) | Imagem com tag fixa, em variável | Aceita, com as exceções da 0010 e da 0013 |
| [0006](0006-role-compose-stack-compartilhado.md) | Um role compartilhado para o ciclo do compose | Aceita |
| [0007](0007-immich-e-nextcloud-num-borg-offsite-proprio.md) | Immich e Nextcloud fazem backup num Borg offsite próprio | Substituída por 0008 |
| [0008](0008-immich-e-nextcloud-no-borgbase-pago.md) | Immich e Nextcloud fazem backup no BorgBase, no plano pago | Aceita, com a exceção da 0016 |
| [0009](0009-lxcs-numa-bridge-propria-do-proxmox-com-nat.md) | LXCs numa bridge própria do Proxmox, com NAT | Aceita |
| [0010](0010-latest-so-sem-tag-de-major-e-com-volta-barata.md) | `latest` só sem tag de major e com volta barata | Aceita, com as exceções da 0011 e da 0012 |
| [0011](0011-gluetun-no-latest-pela-lista-de-servidores.md) | gluetun no `latest`, pela lista de servidores | Aceita |
| [0012](0012-stack-arr-no-latest-com-o-backup-como-volta.md) | Stack Arr no `latest`, com o backup como volta | Aceita |
| [0013](0013-nextcloud-aio-no-latest-ele-se-atualiza.md) | Nextcloud AIO no `latest`: ele se atualiza sozinho | Aceita |
| [0014](0014-backup-do-immich-leva-os-thumbs.md) | O backup do Immich leva os thumbs, não os vídeos re-encodados | Substituída por 0015 |
| [0015](0015-backup-do-immich-leva-os-videos-re-encodados.md) | O backup do Immich leva também os vídeos re-encodados | Aceita |
| [0016](0016-immich-num-repositorio-borg-proprio.md) | O Immich faz backup num repositório Borg próprio | Aceita |
| [0017](0017-timer-no-proxmox-repoe-a-acl-do-lab.md) | Um timer no Proxmox repõe a ACL do lab depois de cada destroy | Aceita |
| [0018](0018-notebook-volta-pelo-nextcloud-sem-chave-privada-em-disco.md) | O notebook volta pelo Nextcloud, sem chave privada em disco | Aceita |
| [0019](0019-state-do-terraform-no-hcp-terraform.md) | O state do Terraform mora no HCP Terraform, com execução local | Aceita |
| [0020](0020-pastas-pessoais-moram-no-nextcloud-com-link-na-casa.md) | As pastas pessoais moram no Nextcloud, com link no lugar de sempre | Aceita |
| [0021](0021-lab-numa-bridge-propria-que-so-sai-para-a-internet.md) | O lab mora numa bridge própria, que só sai para a internet | Aceita |
| [0022](0022-dns-do-adguard-declarado-com-provedores-independentes.md) | DNS do AdGuard declarado, com provedores independentes | Aceita |

## Modelo

```markdown
# NNNN. <Decisão, como frase afirmativa>

- **Status:** Aceita
- **Data:** AAAA-MM-DD
- **Fonte:** <PR/commit, só em decisão registrada depois do fato>

## Contexto

O problema e as forças em jogo, sem a solução ainda.

## Decisão

O que foi decidido, em uma ou duas frases diretas.

## Alternativas descartadas

- **<Alternativa>:** por que não.

## Consequências

O que fica mais fácil, o que fica mais difícil e o que passa a ser regra.
```
