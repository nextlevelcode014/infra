# Máquina nova

O desktop de onde se roda a infra não é só um clone do repo: ele guarda
o state do Terraform, os segredos fora do git, a chave que entra como root
nos LXCs, e é o IP dele que a ACL da tailnet deixa administrar as máquinas.
Este doc é a ida e a volta de uma formatação: o que salvar antes, e como
deixar a máquina nova rodando `terraform plan` e `ansible-playbook` de novo.

Os arquivos e senhas sem os quais nada se reconstrói estão em
[`fora-da-infra.md`](fora-da-infra.md); aqui só se usa a entrada `infra` do
KeePass que ele descreve.

## Antes de formatar

Os comandos rodam da raiz do clone, salvo quando o passo diz outro lugar.

1. **Nada só no disco.** Branch sem push some com a formatação:

   ```bash
   git status --short
   git log --branches --not --remotes --oneline
   ```

   Confira: as duas saídas vazias.

2. **Entrada `infra` do KeePass em dia.** Salve os anexos `vault.yml`,
   `terraform.tfvars` e `hetzner.tfvars` em `/tmp` e compare com os do repo:

   ```bash
   cmp ansible/inventory/group_vars/all/vault.yml /tmp/vault.yml && echo igual
   cmp terraform/terraform.tfvars /tmp/terraform.tfvars && echo igual
   cmp terraform/hetzner/terraform.tfvars /tmp/hetzner.tfvars && echo igual
   ```

   Confira: três `igual`. Anexo diferente se troca antes de seguir.

3. **Anexe o que ainda não tem cópia** na mesma entrada `infra`:

   | Arquivo | Anexo |
   |---|---|
   | `terraform/terraform.tfstate` | `terraform.tfstate` |
   | `terraform/hetzner/terraform.tfstate` | `hetzner.tfstate` |
   | `~/.ssh/id_ed25519` e `~/.ssh/id_ed25519.pub` | os mesmos nomes |

   O state é o inventário dos LXCs para o Ansible (`terraform/CLAUDE.md`,
   seção Estado); sem ele, o Terraform acha que os containers não existem.
   A `id_ed25519` é a chave de root nos LXCs (`terraform/inventory.tf`), e o
   `terraform/local.tf` lê a `.pub` para gravar nos containers: com uma
   chave nova, o plan quer mudar os quatro.

   Confira com o mesmo `cmp` do passo 2, um arquivo por vez.

4. **Anexe também os dotfiles que o git e o SSH usam.** Não são segredo (as
   privadas ficam no agente do Bitwarden), mas sem eles o remote
   `forgejo-lxc` não resolve e os commits saem sem assinatura:
   `~/.ssh/config`, `~/.ssh/allowed_signers`, `~/.ssh/*.pub` e
   `~/.config/git/config`.

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

Os comandos supõem Arch Linux. Em outra distro, os mesmos pacotes pelo
gerenciador dela.

1. **Pacotes:**

   ```bash
   sudo pacman -S --needed git ansible terraform tea tailscale keepassxc
   ```

   O pacote `ansible` já traz `community.general`, `community.docker` e
   `ansible.posix`; o resto vem do `requirements.yml` no passo 7.

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

   Confira: `tailscale ip -4` mostra o IP anotado, e
   `ssh root@<proxmox_host> true` entra sem pedir nada além da chave.

3. **KeePass:** abra o `.kdbx` no `keepassxc` e salve os anexos da entrada
   `infra` dos passos 3 e 4 de antes nos caminhos de origem. Depois:

   ```bash
   chmod 600 ~/.ssh/id_ed25519 ~/.ssh/config
   ```

   Confira: `ssh-keygen -y -f ~/.ssh/id_ed25519 | cmp - <(cut -d' ' -f1,2 ~/.ssh/id_ed25519.pub) && echo par`
   mostra `par`.

4. **Agente SSH do Bitwarden.** Passo manual: o app pede login e senha
   mestra. As chaves `git-push` e `git-signing` só existem no cofre.

   1. Instale o app desktop do Bitwarden, aponte para
      `https://vault.lab.nextlevelcode.pro` (precisa do Tailscale do passo 2)
      e faça login.
   2. **Settings → Enable SSH agent.**
   3. No `~/.bashrc`:

      ```bash
      export SSH_AUTH_SOCK="$HOME/.bitwarden-ssh-agent.sock"
      ```

   Confira, num terminal novo: `ssh-add -l` lista as chaves, e
   `ssh -T forgejo` responde com o usuário do Forgejo.

5. **Clone:**

   ```bash
   git clone ssh://git@forgejo-lxc:2222/nextlevelcode/infra.git
   cd infra
   ```

   Confira: `git log --show-signature -1` mostra
   `Good "git" signature`. O `No principal matched` logo abaixo é esperado
   no `main`: o squash merge é assinado pela chave da instância do Forgejo,
   que não está no `allowed_signers`.

6. **Os arquivos fora do git**, da entrada `infra` para o repo:

   | Anexo | Caminho |
   |---|---|
   | `vault.yml` | `ansible/inventory/group_vars/all/vault.yml` |
   | `terraform.tfvars` | `terraform/terraform.tfvars` |
   | `hetzner.tfvars` | `terraform/hetzner/terraform.tfvars` |
   | `terraform.tfstate` | `terraform/terraform.tfstate` |
   | `hetzner.tfstate` | `terraform/hetzner/terraform.tfstate` |

   Confira: `ansible-vault view ansible/inventory/group_vars/all/vault.yml`
   abre com a senha do campo da entrada.

7. **Dependências do Ansible**, de dentro de `ansible/`:

   ```bash
   ansible-galaxy install -r requirements.yml
   ```

   Os roles vendidos já estão no git; isto baixa as collections.

8. **Terraform**, nas duas stacks:

   ```bash
   (cd terraform && terraform init && terraform plan)
   (cd terraform/hetzner && terraform init && terraform plan)
   ```

   Confira: os dois terminam em `No changes.` Qualquer diff aqui é arquivo
   restaurado errado (state velho, outra `id_ed25519`), não mudança a
   aplicar: **não rode `apply`**, refaça o passo 3 ou 6.

9. **Ansible**, de dentro de `ansible/`:

   ```bash
   ansible-inventory --graph --ask-vault-pass
   ansible all -m ansible.builtin.ping --ask-vault-pass --limit 'all:!pi_staging'
   ```

   Confira: o grafo tem `proxmox`, `lxc` (com `caddy`, `forgejo`,
   `vaultwarden`, `pi-lab`), `pi_hosts` e `vps`, e o ping responde `pong` em
   todos.

10. **`tea`.** Passo manual: o token se gera na interface web do Forgejo.

    1. `https://forge.nextlevelcode.pro` → **Settings → Applications →
       Generate new token**, com escopo de leitura e escrita em `repository`
       e `issue`.
    2. ```bash
       tea login add --name forgejo --url https://forge.nextlevelcode.pro --token <token>
       ```

    Confira: `tea issues list --repo nextlevelcode/infra` lista as issues.
