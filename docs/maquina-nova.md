# Máquina nova

O desktop de onde se roda a infra não é só um clone do repo: ele guarda
os segredos fora do git e o login do HCP Terraform (onde mora o state, ADR
0019), e é o IP dele que a ACL da tailnet deixa administrar as máquinas.
Este doc é a ida e a volta de uma formatação: o que conferir antes, e como
deixar a máquina nova rodando `terraform plan` e `ansible-playbook` de novo.

A casa do notebook mora no Nextcloud do Pi (ADR 0018): `~/.ssh` em
`/Laptop/.ssh` e `~/Work` em `/Laptop/Work`, sincronizados o tempo todo, sem
cache, build nem `.git`. Chave privada não fica em disco nenhum: só no agente
SSH do Bitwarden, e o `~/.ssh` tem só as `.pub` e o `config`. Numa máquina
nova, o Nextcloud devolve os arquivos (inclusive os fora do git), o
`workflow/bin/repos` religa cada pasta ao remote dela, e o Bitwarden devolve
as chaves.

O Nextcloud é infra: não conta como cópia fora dela. Os arquivos e senhas sem
os quais nada se reconstrói continuam na entrada `infra` do KeePass, como diz
[`fora-da-infra.md`](fora-da-infra.md), e são o caminho
[sem o Nextcloud](#sem-o-nextcloud).

## Antes de formatar

Os comandos rodam da raiz do clone, salvo quando o passo diz outro lugar.

1. **Nada só no disco.** O Nextcloud não leva o `.git`: o histórico volta do
   remote, e commit sem push some. A lista de repos que o passo 4 da próxima
   seção usa para religar cada pasta sai daqui:

   ```bash
   ~/Work/dev/workflow/bin/repos salvar
   ```

   Ela grava `~/Work/repos.txt` (pasta, remote, branch default, branch e
   commit atuais), que o Nextcloud leva junto.

   Confira: nenhuma linha `aviso:` (commit sem push), e `sem remote` só para
   repo cujo histórico pode se perder (hoje, o `ansible_quickstart`).

2. **Nextcloud em dia.** No ícone da bandeja, as pastas `~/.ssh` e `~/Work`
   aparecem como sincronizadas, e em *Atividade → Não sincronizado* só há
   item ignorado (cache, build, link simbólico). Nenhuma chave privada em
   `~/.ssh`, porque tudo ali sobe para o Pi:

   ```bash
   grep -l 'PRIVATE KEY' ~/.ssh/* ; echo "fim"
   ```

   Confira: só `fim`.

3. **Entrada `infra` do KeePass em dia.** Salve os anexos `vault.yml`,
   `terraform.tfvars`, `hetzner.tfvars` e `id_ed25519` em `/tmp` e compare:

   ```bash
   cmp ansible/inventory/group_vars/all/vault.yml /tmp/vault.yml && echo igual
   cmp terraform/terraform.tfvars /tmp/terraform.tfvars && echo igual
   cmp terraform/hetzner/terraform.tfvars /tmp/hetzner.tfvars && echo igual
   ssh-keygen -y -f /tmp/id_ed25519 | cmp - <(cut -d' ' -f1,2 ~/.ssh/id_ed25519.pub) && echo par
   rm /tmp/vault.yml /tmp/*.tfvars /tmp/id_ed25519
   ```

   Confira: três `igual` e um `par`, e o login do HCP Terraform da entrada
   abre `app.terraform.io` no navegador. Anexo diferente se troca antes de
   seguir. O state não precisa de cópia: ele mora no HCP. A `id_ed25519` é
   a chave de root nos LXCs, e o `terraform/local.tf` lê a `.pub` para
   gravar nos containers: com uma chave nova, o plan quer mudar os quatro.

4. **Anexe o `~/.config/git/config`** na mesma entrada, como `gitconfig`.
   Ele não está no `~/.ssh` nem no `~/Work`, e sem ele os commits saem sem
   assinatura.

5. **Anote o IP Tailscale deste desktop** num campo da entrada `infra`:

   ```bash
   tailscale ip -4
   ```

   É o `infra-admin-1` da ACL (`ansible/tailscale/policy.hujson`): só esse IP
   chega no SSH do Proxmox, do Pi, da VPS e dos LXCs. A máquina nova vai
   receber o mesmo IP no passo 2 da próxima seção, e a ACL não muda.

6. **Copie o `.kdbx` para outro aparelho** e abra ele lá. Confira: os anexos
   dos passos 3 e 4 aparecem na cópia, não só na máquina que vai ser
   formatada.

## Na máquina nova

Os comandos supõem Arch Linux (Omarchy). Em outra distro, os mesmos pacotes
pelo gerenciador dela.

1. **Pacotes:**

   ```bash
   sudo pacman -S --needed git ansible terraform tea tailscale keepassxc nextcloud-client zen-browser-bin
   ```

   O `zen-browser-bin` vem do repositório `omarchy`. O pacote `ansible` já
   traz `community.general`, `community.docker` e `ansible.posix`; o resto
   vem do `requirements.yml` no passo 7.

   Confira: `terraform version` e `ansible --version` respondem.

2. **Tailscale com o IP antigo.** Passo manual: o login e a troca de IP são
   pelo navegador, no console.

   1. Console → **Machines** → o nó antigo (`<desktop>`, offline) →
      **Remove**. Antes do login, para o nome ficar livre (senão o novo
      vira `<desktop>-1`).
   2. Na máquina nova:

      ```bash
      sudo systemctl enable --now tailscaled
      sudo tailscale up --hostname=<desktop>
      ```

   3. Console → o nó novo → **Edit machine IPv4** → o IP anotado no passo 5
      de antes.

   Confira: `tailscale ip -4` mostra o IP anotado.

3. **Agente SSH do Bitwarden.** Passo manual: o app pede login e senha
   mestra. As chaves privadas (`git-push`, `git-signing`, a `id_ed25519` dos
   LXCs) só existem no cofre.

   1. Instale o app desktop do Bitwarden, aponte para
      `https://vault.lab.nextlevelcode.pro` (precisa do Tailscale do passo 2)
      e faça login.
   2. **Settings → Enable SSH agent.**
   3. No `~/.bashrc`:

      ```bash
      export SSH_AUTH_SOCK="$HOME/.bitwarden-ssh-agent.sock"
      ```

   Confira, num terminal novo: `ssh-add -l` lista as chaves, entre elas
   `forgejo` e a dos LXCs.

4. **Nextcloud.** Passo manual: o login é pelo navegador (webflow), com a
   senha da conta.

   1. Abra o Nextcloud, **Entrar**, servidor
      `https://nextcloud.lab.nextlevelcode.pro`, e autorize no navegador.
      Na tela das pastas, pule a configuração: os pares entram abaixo.
   2. **Configurações → Geral → Editar arquivos ignorados:** marque só
      *Sincronizar arquivos ocultos* (o `.gitignore`, o `.env.example` e o
      próprio `~/.ssh` são ocultos). A lista de ignorados do `~/Work` não se
      digita: ela é o `~/Work/.sync-exclude.lst`, que vale só para aquela
      pasta e volta junto com ela no primeiro download. O que ela ignora
      (`.git/`, `node_modules/`, `.terraform/`, `dist/`, `sia-projects/`,
      `*.img`, …) a ferramenta refaz, volta do remote ou se baixa de novo. O
      `.git` fica de fora porque, sincronizado, era metade dos arquivos:
      milhares de objetos pequenos que travavam o Postgres do Nextcloud em
      deadlock. Na lista global, um padrão como `*.img` passaria a ignorar
      também os arquivos da pasta geral.

      **Padrão novo na lista não limpa o servidor, e não apague no servidor
      o que o cliente passou a ignorar.** O cliente guarda no journal
      (`.sync_*.db` na raiz da pasta) tudo que já sincronizou; se um item
      ignorado depois some do servidor, ele apaga a cópia local também. Já
      custou o `.git` de cinco repos. Para tirar do servidor algo que subiu
      antes do padrão: tire a pasta do par (*Remover conexão*, o local
      fica), apague no servidor, e adicione o par de novo.
   3. Se usar também a pasta geral (`~/Nextcloud` ↔ `/`), em *Escolher o que
      sincronizar* dela, desmarque `Laptop` **antes** de adicionar os pares
      abaixo. Senão o `/Laptop` desce duas vezes, uma em cada pasta, e uma
      edição numa cópia sobe por cima da outra. Desmarcado depois, o
      cliente para de sincronizar mas deixa a pasta local se ela tiver
      arquivo ignorado dentro: apague `~/Nextcloud/Laptop` à mão.
   4. **Adicionar pasta para sincronizar**, com a pasta local **ainda
      inexistente**, para o cliente só baixar (pasta local com arquivos e um
      journal novo pode gerar cópias de conflito):

      | Local | Remota |
      |---|---|
      | `~/.ssh` | `/Laptop/.ssh` |
      | `~/Work` | `/Laptop/Work` |

      Pasta nova da casa segue a mesma regra: a remota é o caminho local com
      `~` trocado por `/Laptop`, e a lista de ignorados dela é um
      `.sync-exclude.lst` na raiz.
   5. **Pastas pessoais**, depois que a pasta geral terminar de sincronizar
      (ADR 0020). O `~/Documents` mora em `~/Nextcloud/Documents`, e o
      script troca a pasta da casa por um link para lá:

      ```bash
      bash ~/Work/dev/workflow/bin/pastas simular
      bash ~/Work/dev/workflow/bin/pastas
      ```

      O `bash` na frente é porque o script voltou sem `+x`. Ele move o que
      a pasta local já tiver sem sobrescrever nada (nome repetido fica onde
      está, com aviso, e o link não é feito), e aponta o `user-dirs.dirs`
      para o caminho real: app em flatpak nem sempre segue um link.

   Confira: as duas pastas aparecem como sincronizadas,
   `~/Work/.sync-exclude.lst` existe, `xdg-user-dir DOCUMENTS` mostra
   `~/Nextcloud/Documents`, e `ssh -T forgejo` responde com o usuário do
   Forgejo (o `~/.ssh/config` voltou e o agente tem a chave).

5. **Repos de volta.** Cada pasta de `~/Work/repos.txt` volta a ser repo:
   `git init`, `fetch` do remote e `reset` para a branch e o commit em que
   ele estava (ou a ponta da default, se eles não chegaram ao remote), sem
   tocar nos arquivos. Pasta da lista que não veio é clonada. O script também
   repõe o `+x`: o Nextcloud não guarda permissão de arquivo, e o git sabe
   quais eram executáveis.

   ```bash
   bash ~/Work/dev/workflow/bin/repos restaurar
   ```

   O `bash` na frente é pelo mesmo motivo: o próprio script voltou sem `+x`.

   Confira: uma linha `religado:` por repo, `git -C ~/Work/dev/infra status --short`
   mostra só o que estava sem commit antes de formatar, e
   `ssh root@<proxmox_host> true` entra sem pedir senha.

6. **KeePass:** abra o `.kdbx` no `keepassxc` e salve o anexo `gitconfig` do
   passo 4 de antes em `~/.config/git/config`.

   Confira, de dentro de `~/Work/dev/infra`: `git log --show-signature -1`
   mostra `Good "git" signature`. O `No principal matched` logo abaixo é
   esperado no `main`: o squash merge é assinado pela chave da instância do
   Forgejo, que não está no `allowed_signers`.

7. **Dependências do Ansible**, de dentro de `ansible/`:

   ```bash
   ansible-galaxy install -r requirements.yml
   ```

   Os roles vendidos já estão no git; isto baixa as collections.

8. **Terraform.** Passo manual: o `terraform login` gera o token pelo
   navegador, com o login do HCP Terraform da entrada `infra`.

   1. ```bash
      terraform login
      ```

      Confirme com `yes`, gere o token na página que abrir e cole no
      terminal. Ele fica em `~/.terraform.d/credentials.tfrc.json`, fora
      do `~/Work`.
   2. Nas duas stacks (o `.terraform/` não sincroniza, então o `init` baixa
      os providers de novo e liga a pasta ao workspace dela):

      ```bash
      (cd terraform && terraform init && terraform plan)
      (cd terraform/hetzner && terraform init && terraform plan)
      ```

   Confira: os dois terminam em `No changes.` Qualquer diff aqui é arquivo
   restaurado errado (outra `id_ed25519.pub`, `tfvars` velho), não mudança
   a aplicar: **não rode `apply`**, confira o `/Laptop/Work` ou use o
   caminho sem o Nextcloud. Se o `init` perguntar se migra um state local,
   responda `no`: o state que vale é o do HCP.

9. **Ansible**, de dentro de `ansible/`:

   ```bash
   ansible-inventory --graph --ask-vault-pass
   ansible all -m ansible.builtin.ping --ask-vault-pass --limit 'all:!pi_staging'
   ```

   Confira: o grafo tem `proxmox`, `lxc` (com `caddy`, `forgejo`,
   `vaultwarden`, `pi-lab`), `pi_hosts` e `vps`, e o ping responde `pong` em
   todos. O inventário aponta para a `id_ed25519.pub`
   (`terraform/inventory.tf`): o ssh pede a privada ao agente.

10. **`tea`.** Passo manual: o token se gera na interface web do Forgejo.

    1. `https://forge.nextlevelcode.pro` → **Settings → Applications →
       Generate new token**, com escopo de leitura e escrita em `repository`
       e `issue`.
    2. ```bash
       tea login add --name forgejo --url https://forge.nextlevelcode.pro --token <token>
       ```

    Confira: `tea issues list --repo nextlevelcode/infra` lista as issues.

11. **Claude Code e o `claude-config`.** O clone voltou com o `~/Work`, mas o
    `~/.claude` não: o `CLAUDE.md` global, os comandos (`/comecar`,
    `/entregar`) e as skills só valem depois de ligados de novo. Passo
    manual: o login do Claude Code abre no navegador.

    1. Instale o app (repositório `omarchy`) e o CLI (pelo mise, como neste
       notebook), e faça login:

       ```bash
       sudo pacman -S --needed claude-desktop
       mise use -g claude@latest
       ```

    2. Abra o Claude Code **dentro** de `~/Work/dev/claude-config` e rode
       `/instalar`. O comando é do próprio repo (só existe dentro do clone)
       e conduz o resto: roda o `instalar.sh`, explica cada aviso dele e
       confere o Tailscale e o `tea`, que a esta altura já estão de pé. Sem
       o Nextcloud, clone antes
       (`git clone ssh://git@forgejo-lxc:2222/nextlevelcode/claude-config.git ~/Work/dev/claude-config`).
       Sem o Claude Code à mão, o mesmo link sai direto:

       ```bash
       bash ~/Work/dev/claude-config/instalar.sh
       ```

    A memória automática (`~/.claude/projects/*/memory/`) é de cada máquina e
    começa vazia: o que vale para sempre mora no `claude/CLAUDE.md` do repo.

    Confira: `~/Work/dev/claude-config/instalar.sh status` lista tudo com
    `✓`, e numa sessão **nova** do Claude Code o `/comecar` aparece (a
    sessão em que o `/instalar` rodou já tinha carregado o `~/.claude` de
    antes).

## Sem o Nextcloud

Com o Pi fora, o `~/Work` e o `~/.ssh` vêm do KeePass e do Forgejo. Com o
Vaultwarden fora também, a chave dos LXCs vem do KeePass para um agente
comum. Troque os passos 3 a 6 acima por:

1. **Chave dos LXCs**, só se o Bitwarden não abrir: salve o anexo
   `id_ed25519` em `/tmp` e ponha num agente comum, sem gravar em `~/.ssh`:

   ```bash
   eval "$(ssh-agent)"
   ssh-add /tmp/id_ed25519 && rm /tmp/id_ed25519
   ```

   Confira: `ssh-add -l` lista a chave. O agente some com o terminal: os
   passos seguintes rodam nele.

2. **`~/.ssh`:** recrie as `.pub` e o `config` à mão (as `.pub` saem do
   Bitwarden, em cada item de chave SSH).

3. **Clone e arquivos fora do git:**

   ```bash
   git clone ssh://git@forgejo-lxc:2222/nextlevelcode/infra.git ~/Work/dev/infra
   ```

   | Anexo | Caminho |
   |---|---|
   | `vault.yml` | `ansible/inventory/group_vars/all/vault.yml` |
   | `terraform.tfvars` | `terraform/terraform.tfvars` |
   | `hetzner.tfvars` | `terraform/hetzner/terraform.tfvars` |
   | `gitconfig` | `~/.config/git/config` |

   O state não é anexo: ele volta do HCP Terraform no passo 8.

   Confira: `ansible-vault view ansible/inventory/group_vars/all/vault.yml`
   abre com a senha do campo da entrada.

Depois, siga do passo 7.
