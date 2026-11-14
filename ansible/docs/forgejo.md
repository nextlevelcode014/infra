# Forgejo no LXC do Proxmox

`playbooks/forgejo.yml` sobe o Forgejo e o Postgres dele no LXC `forgejo`
(vmid 201, `10.50.0.201`), com o backup no borgmatic do próprio LXC.

| O quê | Onde |
|---|---|
| Web e clone HTTPS (público) | `https://forge.nextlevelcode.pro`: Cloudflare → Caddy da VPS → Anubis (`127.0.0.1:8923`) → `forgejo_tailscale_ip:3000` |
| SSH do Git (só tailnet) | `forgejo-lxc:2222` (`forgejo_ssh_domain`), sem passar por Caddy |
| Dados | `/opt/forgejo` (`forgejo_dir`): `forgejo/` (repositórios e config) e `postgres/` |
| Na contingência | no Pi, em `/mnt/secure/appdata/forgejo` (`docs/pi-recuperacao.md`) |

O compose fixa a instalação: `INSTALL_LOCK=true` (sem assistente web),
cadastro fechado (`DISABLE_REGISTRATION=true`) e repositórios públicos
visíveis sem login. O web só existe pelo domínio público: não há rota no
`*.lab`.

Para o executor de Actions, veja o [guia do runner](forgejo-runner.md).

## Antes de aplicar

- **Vault** (`inventory/group_vars/all/vault.yml`, modelo em
  `vault.yml.example`): `vault_forgejo_db_password`, as duas
  `vault_forgejo_signing_ssh_*` (seção "Assinatura dos merges") e as quatro
  `vault_forgejo_borg_*`, que são do Borg de todos os serviços.
- **ACL** (`tailscale/policy.hujson`), já na política: membros da tailnet →
  `tag:forgejo:2222` (Git), `tag:caddy-vps` → `tag:forgejo:3000` (web
  público) e `tag:vps` → `tag:forgejo:2222` (monitor do SSH).
- **Cloudflare:** registro `forge` apontando para o IP público da VPS. Só muda
  com VPS nova (`docs/vps.md`).

## Instalação

1. **LXC pelo Terraform**, em `../terraform/`:

   ```bash
   cd ../terraform && terraform plan && terraform apply
   ```

   Confira: `ansible-inventory --graph lxc` lista `forgejo`.

2. **Base do LXC** (flags, Tailscale, Docker):

   ```bash
   ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,forgejo
   ```

   Confira: o nó `forgejo-lxc` aparece no console do Tailscale.

3. **Tags e IP Tailscale.** No console → Machines → `forgejo-lxc` → Edit ACL
   tags: `tag:proxmox-lxc` e `tag:forgejo`. É manual porque as tags de nó
   ficam no console (`tailscale/README.md`, "Tags"). Depois ponha o IP do nó
   (`ssh root@10.50.0.201 tailscale ip -4`) em `forgejo_tailscale_ip`
   (`inventory/group_vars/all/vars.yml`): a VPS não resolve nomes da
   tailnet, então o Anubis e o Uptime Kuma usam o IP.

   Confira: `ssh root@10.50.0.201 tailscale status --self` mostra as duas
   tags.

4. **Forgejo:**

   ```bash
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass
   ```

   Confira: `ssh root@10.50.0.201 docker compose -f /opt/forgejo/compose.yml ps`
   mostra `forgejo` e `forgejo-db` rodando, e
   `ssh root@10.50.0.201 curl -s localhost:3000/api/healthz` traz
   `"status": "pass"`.

5. **Dados.** Com backup a trazer, este é o momento do restore
   (`docs/forgejo-restore.md`); o admin e os repositórios vêm junto, e o
   passo 6 não se aplica. Instância nova segue para o 6.

6. **Admin, só em instância nova.** Com `INSTALL_LOCK` e o cadastro fechado,
   a interface não cria o primeiro usuário: ele sai pela CLI. É manual porque
   a senha não deve passar pelo repo; a CLI gera uma e mostra uma vez.

   ```bash
   ssh -t root@10.50.0.201 docker exec -it forgejo \
     forgejo admin user create --admin --username <usuário> --email <email> --random-password
   ```

   Confira: o login em `https://forge.nextlevelcode.pro` (passo 7) funciona
   com a senha impressa. Troque-a na interface e guarde no Vaultwarden.

7. **VPS: Anubis, Caddy e monitores.** Só é preciso se o
   `forgejo_tailscale_ip` mudou no passo 3: o Anubis e o monitor do SSH
   apontam para ele.

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   Confira: `https://forge.nextlevelcode.pro` abre (depois do desafio do
   Anubis), e os monitores *Forgejo* e *Forgejo (SSH)* ficam verdes.

8. **Cliente SSH**, em cada computador que faz push (`~/.ssh/config`):

   ```
   Host forgejo forgejo-lxc
       HostName forgejo-lxc
       Port 2222
       User git
       IdentityFile <sua chave>
       IdentitiesOnly yes
   ```

   Confira: `ssh -T forgejo` responde com o seu usuário, e
   `git ls-remote origin` funciona num clone (`ssh://git@forgejo-lxc:2222/<org>/<repo>.git`).

## Permissões dos repositórios

`playbooks/forgejo-repositorios.yml` administra somente os colaboradores e
as regras declarados em `vars/forgejo-repositorios.yml`, pela API HTTPS.
Roda na estação de operação com inventário local; não faz parte do deploy
da stack ou do `site.yml`. A decisão está no [ADR 0025](../../docs/decisoes/0025-permissoes-do-forgejo-aplicadas-por-playbook-local.md).
Os campos e métodos seguem o [contrato da API do Forgejo 17.0.1](https://codeberg.org/forgejo/forgejo/src/tag/v17.0.1/templates/swagger/v1_json.tmpl).

O YAML declara `nextlevelcode/infra` e `nextlevelcode/lab`, compartilhando
a mesma política por uma âncora YAML: colaborador `agent` com `write`;
`main` sem push direto, merge restrito a `nextlevelcode`, restrições para
administradores e commits assinados obrigatórios. Não exige aprovações ou
checks. Declarar não aplica a regra: a ativação é uma execução autorizada.
Antes da primeira proteção de um repositório, execute o ensaio temporário
abaixo; depois aplique à `main`.
Itens não declarados são preservados; remover um item do YAML não o exclui
no servidor. As operações não são uma transação: em caso de falha, confira
o que já foi aplicado e o snapshot antes de repetir.

### Preparar conta e credencial

1. **Conta do agente.** Em instância com cadastro fechado, crie a conta sem
   privilégios administrativos pela CLI, somente se ainda não existir:

   ```bash
   ssh -t root@10.50.0.201 docker exec -it forgejo \
     forgejo admin user create --username agent --email <email> --random-password
   ```

   Confira: o login da conta funciona e ela não é administradora. É manual
   porque envolve uma senha inicial e sua guarda no Bitwarden. Não repita a
   criação de uma conta existente. A conta `agent` e seu token são para os
   agentes de desenvolvimento; não são a identidade do runner de CI.

2. **Token de operação.** Na conta que administra o repositório, gere um
   token em **Settings → Applications**, com escopo `write:repository`.
   Em acesso a repositórios, selecione **All (public, private, and limited)**:
   tokens para repositórios específicos têm limitações administrativas,
   incluindo a inclusão de colaboradores. O token acompanha o alcance da
   conta; reserve-o para estas operações e não o compartilhe com o agente ou
   runner. Não precisa do escopo `admin` da instância. Confira a
   [documentação de escopos](https://forgejo.org/docs/v17.0/user/authentication/token-scope/).
   Não use o token de `agent`, que não administra o repositório.

   É manual para manter a emissão e revogação sob controle do responsável.
   Guarde o token no Bitwarden e, a partir de `ansible/`, no vault:

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Preencha `vault_forgejo_repositorios_token`, conforme o `.example`.
   Confira abrindo novamente o vault no editor, sem imprimir o token no
   terminal. As chamadas autenticadas usam `no_log`, TLS validado, sem
   redirecionamentos, proxy ou leitura de `.netrc`. O token fica na estação,
   não é instalado no servidor nem fornecido ao runner.

3. **Chave SSH da conta `agent`.** No Bitwarden, crie um item de chave SSH
   exclusivo e disponibilize-o pelo agente SSH. É manual porque exige acesso
   ao cofre e confirmação do usuário. Cadastre a pública em **Settings →
   SSH / GPG Keys** da conta `agent` e salve somente a pública em
   `~/.ssh/agent.pub`. A privada permanece no cofre ([ADR 0018](../../docs/decisoes/0018-notebook-volta-pelo-nextcloud-sem-chave-privada-em-disco.md)).

   A entrada adicional no `~/.ssh/config` é:

   ```sshconfig
   Host forgejo-agent
       HostName forgejo-lxc
       Port 2222
       User git
       IdentityFile ~/.ssh/agent.pub
       IdentitiesOnly yes
   ```

   Confira: `ssh -T forgejo-agent` identifica `agent`. O alias não troca os
   remotes ou o login padrão do `tea`. A conta separada não isola credenciais
   se o agente continua no ambiente do responsável; investigação na
   [issue #78](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/78).

### Ensaio operacional em branch temporária

Exige autorização própria para criar branches, regra e PR de teste no
repositório escolhido. Execute depois do merge da configuração. O exemplo
usa `lab`; para repetir no `infra`, altere somente a variável do passo 1.
Preserve qualquer regra de `main` já existente. O merge positivo é manual
pelo responsável. Os comandos não provisionam ambientes do laboratório.

1. No terminal usado para todo o ensaio, selecione o repositório. Confira que
   as duas branches e a regra temporária ainda não existem; se existirem,
   interrompa antes de criar ou sobrescrever recursos. Salve as regras atuais
   para comparar ao final.

   ```bash
   export FORGEJO_ENSAIO_REPO=lab
   git remote -v
   git ls-remote "ssh://git@forgejo-lxc:2222/nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" refs/heads/teste-protecao-main refs/heads/teste-protecao-origem
   tea api --login forgejo --method GET "repos/nextlevelcode/${FORGEJO_ENSAIO_REPO}/branch_protections" > "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}-regras-antes.json"
   git clone "ssh://git@forgejo-lxc:2222/nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}"
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" remote -v
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" switch -c teste-protecao-main origin/main
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push "forgejo-agent:nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" HEAD:refs/heads/teste-protecao-main
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" switch -c teste-protecao-origem
   test ! -e "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}/teste-protecao.txt"
   printf 'Ensaio temporário de proteção de branch.\n' > "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}/teste-protecao.txt"
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" add teste-protecao.txt
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" commit -S -m "Exercite a proteção em branch temporária"
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push "forgejo-agent:nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" HEAD:refs/heads/teste-protecao-origem
   ```

   Confira: os pushes funcionam como `agent`; o commit de origem está
   assinado (`git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" log -1 --show-signature`).
   Falha de conexão, autenticação ou assinatura invalida o controle positivo.

2. A partir de `ansible/`, copie somente a entrada selecionada e troque
   apenas o nome da regra. O arquivo público contém um único repositório;
   a cópia profunda evita alterar a política compartilhada pelo outro.

   ```bash
   python - <<'PY'
   import copy, json, os, yaml
   from pathlib import Path
   nome = os.environ['FORGEJO_ENSAIO_REPO']
   assert nome in ('infra', 'lab')
   declarados = yaml.safe_load(Path('vars/forgejo-repositorios.yml').read_text())
   repo = copy.deepcopy(next(r for r in declarados['forgejo_repositorios']
                             if (r['owner'], r['name']) == ('nextlevelcode', nome)))
   assert len(repo['rules']) == 1 and repo['rules'][0]['rule_name'] == 'main'
   repo['rules'][0]['rule_name'] = 'teste-protecao-main'
   config = {'forgejo_repositorios': [repo],
             'forgejo_repositorios_alvos': [f'nextlevelcode/{nome}']}
   Path(f'/tmp/forgejo-ensaio-{nome}-vars.json').write_text(json.dumps(config))
   PY
   ansible-playbook -i localhost, playbooks/forgejo-repositorios.yml --ask-vault-pass -e "@/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}-vars.json" --check --diff
   ansible-playbook -i localhost, playbooks/forgejo-repositorios.yml --ask-vault-pass -e "@/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}-vars.json" -e forgejo_repositorios_aplicar=true
   ansible-playbook -i localhost, playbooks/forgejo-repositorios.yml --ask-vault-pass -e "@/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}-vars.json" -e forgejo_repositorios_aplicar=true
   ```

   Confira: criação da regra temporária, depois `changed=0`. Somente o
   repositório selecionado aparece no plano; regras de `main` e do outro
   repositório permanecem intactas. Revise diferenças antes da aplicação:
   o colaborador declarado também pertence ao escopo desta execução.

3. Teste as operações que devem ser recusadas por proteção:

   ```bash
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push "forgejo-agent:nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" HEAD:refs/heads/teste-protecao-main
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push "forgejo-agent:nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" :refs/heads/teste-protecao-main
   tea pr create --login forgejo-agent --repo "nextlevelcode/${FORGEJO_ENSAIO_REPO}" --base teste-protecao-main --head teste-protecao-origem --title 'Teste temporário de proteção' --description 'Ensaio autorizado; destino temporário, sem alteração em main.'
   tea api --include --login forgejo-agent --method POST "repos/nextlevelcode/${FORGEJO_ENSAIO_REPO}/pulls/<numero-do-pr>/merge" --data '{"Do":"squash"}'
   ```

   Confira: push e exclusão rejeitados pelo Forgejo; criação do PR permitida;
   merge pela conta `agent` rejeitado. Substitua `<numero-do-pr>` pelo PR
   recém-criado. Use o status HTTP e a mensagem de proteção/allowlist como
   evidência; erro de rede, token, assinatura ou PR sem diferença não
   comprova bloqueio de merge.

4. Revise e faça o squash merge do PR pela sua conta, manualmente na web.
   A origem pode ser excluída após o merge; preserve o clone local até o fim.
   Confira que o destino avançou e a branch local ainda aponta para o commit
   anterior. O primeiro comando de ancestralidade deve retornar 0; o inverso,
   1. Só então teste a reescrita realmente não fast-forward:

   ```bash
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" fetch origin
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" merge-base --is-ancestor teste-protecao-main origin/teste-protecao-main
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" merge-base --is-ancestor origin/teste-protecao-main teste-protecao-main
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push --force "forgejo-agent:nextlevelcode/${FORGEJO_ENSAIO_REPO}.git" refs/heads/teste-protecao-main:refs/heads/teste-protecao-main
   ```

   Confira: o servidor recusa voltar ao commit anterior ao squash; o SHA
   remoto continua no squash humano. Não tente esse teste em `main`.

5. Após guardar evidências sanitizadas, remova somente a regra e a branch de
   destino de teste pela identidade humana, com autorização para a limpeza:

   ```bash
   tea api --login forgejo --method DELETE "repos/nextlevelcode/${FORGEJO_ENSAIO_REPO}/branch_protections/teste-protecao-main"
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push origin --delete teste-protecao-main
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" ls-remote origin refs/heads/teste-protecao-origem
   ```

   Se a última consulta ainda listar a origem, remova-a:

   ```bash
   git -C "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}" push origin --delete teste-protecao-origem
   ```

   Confira: branches e regra temporárias ausentes. Reconsulte as proteções:

   ```bash
   tea api --login forgejo --method GET "repos/nextlevelcode/${FORGEJO_ENSAIO_REPO}/branch_protections"
   ```

   O resultado deve corresponder ao JSON salvo antes do ensaio. O PR mergeado
   permanece como registro. Depois de guardar as evidências, remova o clone
   e as variáveis temporárias:

   ```bash
   rm -r "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}"
   rm "/tmp/forgejo-ensaio-${FORGEJO_ENSAIO_REPO}-vars.json"
   ```

   Confira: os dois caminhos não existem mais. Não exclua a proteção de
   `main`. Com o ensaio aprovado, siga para sua ativação na seção seguinte.


### Conferir e aplicar

Os comandos desta seção rodam **dentro de `ansible/`**, depois do merge,
do ensaio temporário e com autorização para os alvos. Mesmo `--check`
consulta o serviço real. O exemplo seleciona somente `nextlevelcode/lab`.
Troque pelo identificador completo do `infra` para operá-lo separadamente.
Sem `forgejo_repositorios_alvos` (ou com lista vazia), os dois são
processados; alvo desconhecido ou duplicado falha antes de consultar a API.

1. Confira o YAML público, o SHA do checkout e as diferenças:

   ```bash
   git remote -v
   git rev-parse HEAD
   git status --short
   ansible-playbook -i localhost, playbooks/forgejo-repositorios.yml \
     --ask-vault-pass --check --diff \
     -e '{"forgejo_repositorios_alvos":["nextlevelcode/lab"]}'
   ```

   Confira: só aparecem os repositórios, regras e colaboradores declarados.
   A simulação faz somente GET; não grava snapshot ou altera a API. Se o
   estado já corresponder ao YAML, o resumo mostra `changed=0`. Erro de
   autenticação, permissão, resposta inesperada ou campo ausente interrompe
   a execução, sem ser tratado como ausência de regra.

2. Com as diferenças revisadas e autorização para aplicar:

   ```bash
   ansible-playbook -i localhost, playbooks/forgejo-repositorios.yml \
     --ask-vault-pass -e forgejo_repositorios_aplicar=true \
     -e '{"forgejo_repositorios_alvos":["nextlevelcode/lab"]}'
   ```

   Confira: antes da primeira escrita em cada repositório, aparece o caminho
   do snapshot em `~/.local/state/forgejo-repositorios/<execução>/`.
   Diretório `0700`, arquivo `0600`; contém o estado anterior e desejado dos
   itens gerenciados, sem tokens. A proteção é criada/ajustada e reconsultada
   antes de conceder permissões aos colaboradores. Permissões também são
   reconsultadas ao final. Não apaga e recria uma regra existente.

3. Repita exatamente o comando de aplicação do passo 2.

   Confira: `changed=0`, sem novas escritas na API ou novo snapshot. Consulte
   também a regra pela identidade humana:

   ```bash
   tea api --login forgejo --method GET repos/nextlevelcode/lab/branch_protections/main
   ```

   Essa leitura confirma a configuração; a eficácia dos bloqueios exige o
   ensaio anterior. Mantenha os snapshots fora do Git e registre no PR o SHA,
   comandos, resultados e limites, sem credenciais.

### Recuperação administrativa

Se uma alteração de proteção bloquear o fluxo esperado, interrompa novas
aplicações. Mantenha uma sessão humana com acesso às configurações. A
recuperação pode ser feita pela API ou em **Settings → Branches**, com a
autorização do responsável, mudando somente a regra problemática.

Para restaurar os campos gerenciados de uma regra que já existia, a partir
de `ansible/`, selecione o repositório e o snapshot informado na execução.
O exemplo usa `lab`; para o `infra`, ajuste a seleção. A asserção impede
usar o snapshot de um repositório para restaurar o outro:

```bash
export FORGEJO_RECUPERACAO_REPO=lab
export FORGEJO_RECUPERACAO_SNAPSHOT=/caminho/do/snapshot.json
python - "$FORGEJO_RECUPERACAO_SNAPSHOT" "$FORGEJO_RECUPERACAO_REPO" main <<'PY'
import json, sys
from pathlib import Path
snapshot = json.loads(Path(sys.argv[1]).read_text())
assert sys.argv[2] in ('infra', 'lab')
assert snapshot['repository'] == f'nextlevelcode/{sys.argv[2]}'
regra = next(r for r in snapshot['plan']['rules'] if r['name'] == sys.argv[3])
assert regra['before'] is not None, 'Regra não existia; avaliar a recuperação manualmente.'
payload = {k: regra['before'][k] for k in regra['after'] if k != 'rule_name'}
Path('/tmp/forgejo-regra-anterior.json').write_text(json.dumps(payload))
PY
tea api --login forgejo --method PATCH "repos/nextlevelcode/${FORGEJO_RECUPERACAO_REPO}/branch_protections/main" --data @/tmp/forgejo-regra-anterior.json
tea api --login forgejo --method GET "repos/nextlevelcode/${FORGEJO_RECUPERACAO_REPO}/branch_protections/main"
```

Confira: os campos voltaram aos valores do snapshot; preserve a proteção
contra push direto. O snapshot de uma criação tem `before: null`: sua
remoção exige decisão própria; no ensaio, use somente a exclusão da regra
temporária descrita acima. Se a API estiver indisponível, use a sessão web;
se faltar acesso, recupere primeiro a conta administrativa pelos procedimentos
da instância, sem alterar diretamente o banco para contornar a proteção.

Permissões de colaboradores ficam em `plan.collaborators[].before` no mesmo
snapshot. Confira esse registro antes de restaurar **somente** o usuário
afetado; para uma associação anterior com `permission: write`:

```bash
tea api --login forgejo --method PUT "repos/nextlevelcode/${FORGEJO_RECUPERACAO_REPO}/collaborators/agent" --data '{"permission":"write"}'
tea api --login forgejo --method GET "repos/nextlevelcode/${FORGEJO_RECUPERACAO_REPO}/collaborators/agent/permission"
```

Se o usuário não era colaborador (`member: false`), remover a associação
nova é uma operação separada, após revisão e autorização:

```bash
tea api --login forgejo --method DELETE "repos/nextlevelcode/${FORGEJO_RECUPERACAO_REPO}/collaborators/agent"
tea api --login forgejo --method GET "repos/nextlevelcode/${FORGEJO_RECUPERACAO_REPO}/collaborators/agent"
```

Confira: HTTP 404 na associação; acesso de leitura pública pode continuar
existindo. Atualize o YAML aprovado antes da próxima aplicação para não
reintroduzir o problema. Registre a recuperação e confira as regras ao final.

### Verificações locais

Sem inventário, vault ou API reais; usa Ansible, Python e PyYAML já
instalados. Os testes abrem um servidor fictício em `127.0.0.1`, usam token
fictício e diretórios temporários, encerrados e removidos ao final:

```bash
ansible-playbook -i localhost, playbooks/forgejo-repositorios.yml -e forgejo_repositorios_vault_file=../roles/forgejo_repositorios/tests/vault.yml --syntax-check
python roles/forgejo_repositorios/tests/test_api.py -v
```

Confira: sintaxe aprovada e todos os testes sem skips. Eles verificam
criação, atualização, idempotência, `--check` sem escritas, preservação de
itens não gerenciados, snapshot, falhas e ocultação do token nos logs.
Também verificam seleção sem consultar o outro repositório (mesmo com
divergências nele), rejeição de alvo inexistente e estados/snapshots
independentes na aplicação dos dois.
Não comprovam a autorização do Forgejo real nem o bloqueio de push/merge.
Ambiente sem permissão para sockets precisa liberar somente a execução
local desse teste; falta de dependência ou socket bloqueado é falha/bloqueio,
nunca aprovação.

## Assinatura dos merges

O squash merge de um PR não reaproveita o commit da branch: o Forgejo cria um
commit novo no servidor, e a chave de quem escreveu não está lá. Por isso ele
assina esses commits com uma chave **da instância** (`[repository.signing]`
no compose, `MERGES=always`). A assinatura diz "mergeado por este Forgejo";
a autoria continua no autor do commit e na assinatura dele na branch. Autor
e committer do merge não mudam: continuam sendo quem escreveu e quem
mergeou. O `forgejo_signing_name` e o `forgejo_signing_email`
(`roles/forgejo/defaults/main.yml`) são obrigatórios na config, mas não
aparecem nesses commits.

A chave fica em `forgejo/signing/` (`key` e `key.pub`), escrita pelo role a
partir do vault, e entra no backup com o resto de `forgejo/`. Na contingência
o Pi assina com a mesma chave.

### Chave nova (uma vez, ou para trocar)

É manual porque a chave privada não pode passar pelo repo, e o vault só se
edita com a senha dele.

1. **Gerar**, sem passphrase (o Forgejo assina sem ninguém digitar nada):

   ```bash
   ssh-keygen -t ed25519 -N '' -C forgejo-signing -f /tmp/forgejo-signing
   ```

2. **Pôr no vault** o conteúdo de `/tmp/forgejo-signing` em
   `vault_forgejo_signing_ssh_private_key` (bloco `|`, como no `.example`) e o
   de `/tmp/forgejo-signing.pub` em `vault_forgejo_signing_ssh_public_key`:

   ```bash
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira: `ansible-vault view inventory/group_vars/all/vault.yml | grep -c forgejo_signing`
   dá `2`. Guarde a chave também no Vaultwarden e apague as duas de `/tmp`.

3. **Aplicar** onde o Forgejo está no ar. Reinicia o Forgejo: o push e a web
   caem por alguns segundos. Qual dos dois vale é o `proxmox_fora` do
   `inventory/group_vars/all/vars.yml`.

   - `proxmox_fora: false`, Forgejo no LXC do Proxmox:

     ```bash
     ansible-playbook playbooks/forgejo.yml --ask-vault-pass
     ```

   - `proxmox_fora: true`, Forgejo no Pi (contingência). Não há playbook só
     do Forgejo no Pi: o `pi-recuperacao.yml` reaplica também o `pi_host` e o
     Vaultwarden, então olhe o diff antes. Fora a chave e o compose do
     Forgejo, ele não deve mudar nada:

     ```bash
     ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi --check --diff
     ansible-playbook playbooks/pi-recuperacao.yml --ask-vault-pass --limit rpi
     ```

   Confira, com `<host>` sendo `forgejo` (Proxmox) ou `rpi` (Pi):

   ```bash
   ansible <host> --ask-vault-pass -m command -a 'curl -s localhost:3000/api/v1/signing-key.ssh'
   ```

   devolve a chave pública que está no vault.

4. **Testar com um merge:** depois do próximo squash merge,

   ```bash
   git fetch origin && git log -1 --format='%G? %GK' origin/main
   ```

   mostra `U` e a impressão digital da chave: assinado, mas por uma chave que
   o seu git ainda não conhece. Ela tem que ser a mesma de
   `ssh-keygen -lf /tmp/forgejo-signing.pub` (ou da chave pública do vault).
   `N` quer dizer que o Forgejo não assinou: olhe o log do container.

5. **Confiar na chave**, em cada computador que confere assinatura: uma linha
   no `gpg.ssh.allowedSignersFile` (`git config gpg.ssh.allowedSignersFile`
   mostra qual é). O e-mail na frente é só o nome da chave nesse arquivo: o
   git acha a linha pela chave, não pelo committer.

   ```bash
   pub=$(ansible-vault view inventory/group_vars/all/vault.yml \
     | sed -n 's/^vault_forgejo_signing_ssh_public_key: "\(.*\)"$/\1/p')
   echo "forgejo@nextlevelcode.pro namespaces=\"git\" $pub" \
     >> "$(git config gpg.ssh.allowedSignersFile)"
   ```

   Confira: o `git log` do passo 4 passa a mostrar `G`. Os merges anteriores
   a esta mudança continuam `N`: assinatura não se põe em commit que já
   existe sem reescrever o histórico.

## Backup

Prefixo `forgejo-*`, no borgmatic do LXC às 02:00 (`docs/backup.md`). Antes do
`borg create`, um `pg_dump` com o banco no ar (vai para `/tmp`, que o
borgmatic.service tem privado) e depois a stack **para**: o Forgejo fica fora
do ar enquanto o Borg copia `forgejo/`, alguns minutos. Sobe de novo no fim,
também quando o backup falha. Fica de fora `*.tmp`, `*.log` e `cache/`; o
`postgres/` não entra, porque o dump é o que restaura.

Monitor *Backup Forgejo*. Em standby (o Pi fora da contingência) não há
backup: um archive `forgejo-*` do Pi viraria o mais recente para o restore.
Restore: `docs/forgejo-restore.md`.

## Operação

- **Monitores:** *Forgejo* (`/api/healthz` pelo domínio público, o único
  caminho que o Anubis libera sem desafio) e *Forgejo (SSH)* (porta 2222 em
  `forgejo_tailscale_ip`).
- **Proxmox fora:** o Pi assume, `docs/pi-recuperacao.md`.

### Atualizar o Forgejo no LXC

Faça em janela autorizada, com os usuários avisados para suspender escritas
até a verificação. O Forgejo migra o banco na primeira subida. Os passos
ficam manuais para conferir o backup antes da migração e permitir que o
responsável decida se o serviço pode voltar a receber escritas.

1. Confira as notas das versões envolvidas e o
   [guia de atualização](https://forgejo.org/docs/latest/admin/upgrade/).
   No LXC, esvazie a fila e gere um archive novo com o servidor parado
   e o PostgreSQL ativo. O borgmatic volta a subir a stack antiga ao terminar.

   ```bash
   sudo docker exec forgejo forgejo manager flush-queues
   sudo docker compose -f /opt/forgejo/compose.yml stop server
   sudo borgmatic -c /etc/borgmatic/forgejo.yaml create --verbosity 1 --stats
   sudo borgmatic -c /etc/borgmatic/forgejo.yaml repo-list
   ```

   Confira o sucesso do backup e anote o archive `forgejo-*` da janela.
   Se falhar, interrompa a atualização e confira se a stack antiga voltou
   com `sudo docker compose -f /opt/forgejo/compose.yml ps`.

2. Fixe a versão da imagem em `forgejo_image`, nos defaults do role.
   Mantenha também a imagem do PostgreSQL fixada em `forgejo_db_image`.
   Após o merge, no diretório `ansible/`, aplique no LXC Forgejo.

   ```bash
   ansible-playbook playbooks/forgejo.yml --ask-vault-pass --limit forgejo
   ```

3. No LXC, confira versão, saúde, migrações e diagnóstico. No clone do
   `infra`, rode `git remote -v` e `git ls-remote --exit-code origin refs/heads/main`
   para conferir a leitura por SSH. Confira também a escrita com `git push`
   na branch do PR, usando um commit da mudança. Na web, abra o PR e a aba Actions.

   ```bash
   sudo docker exec forgejo forgejo --version
   sudo docker logs --tail 100 forgejo
   sudo docker exec forgejo sh -ec '
     forgejo doctor check --config "${GITEA_APP_INI:?}" --default --log-file /tmp/doctor.log
   '
   sudo docker exec forgejo cat /tmp/doctor.log
   ```

   Da estação de trabalho, confira o endpoint público.

   ```bash
   curl -fsS https://forge.nextlevelcode.pro/api/healthz
   ```

4. Se a migração falhar, siga [o runbook de restore](forgejo-restore.md) com
   o código anterior à atualização e confira se o restore selecionará o
   archive anotado antes de confirmar. Restaurar repõe banco e arquivos em
   conjunto. Combine a recuperação com o responsável antes de aceitar escritas.

Para atualizar a contingência no Pi, siga [o runbook do Pi](pi-recuperacao.md).
