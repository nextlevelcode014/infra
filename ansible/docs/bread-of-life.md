# Bread of Life no LXC do Proxmox

`playbooks/bread-of-life.yml` sobe o servidor de sincronização no LXC
`bread-of-life` (VMID 204, `10.50.0.204`).

| O quê | Onde |
|---|---|
| URL dos clientes | `https://bread-of-life.lab.nextlevelcode.pro` pelo Caddy do Proxmox |
| Backend | `bread-of-life-lxc:4000` no IPv4 Tailscale do LXC, acessível pelo Caddy |
| Dados | `/opt/bread-of-life/data/sync.db` e arquivos auxiliares do SQLite em WAL |

O servidor é o código oficial do [release v0.5.2](https://github.com/matt-shearing/bread-of-life/releases/tag/v0.5.2),
fixado por commit e SHA-256. `/health` identifica o servidor como `0.5.0`.
Os clientes da série 0.5 negociam os recursos anunciados nesse endpoint.
O ensaio operacional usa os clientes v0.5.2 no celular e no notebook.
Consulte a [documentação do servidor](https://github.com/matt-shearing/bread-of-life/tree/2f3a5fc35c7f6477fd5f138f83e635cb59aa434e/deploy/sync-server).

## Antes de aplicar

1. **Política e DNS.** Aplique [a política versionada](../tailscale/README.md)
   após o merge. Confira que os testes passam ao salvar e que o wildcard
   `*.lab.nextlevelcode.pro` aponta para o Caddy do Proxmox. A publicação da
   política depende do console autenticado. O Caddy usa o wildcard e o
   certificado DNS-01 já configurados.
2. **Vault.** O LXC usa a chave compartilhada `vault_tailscale_authkey`
   para entrar na tailnet. Em `ansible/`, gere o segredo de assinatura
   e inclua-o no vault cifrado. Preencha
   `vault_bread_of_life_client_ips` com os IPs Tailscale exatos dos dois
   aparelhos. Use `tailscale ip -4` e `tailscale ip -6` no notebook ou
   consulte os nós em **Machines**. Inclua IPv4 e IPv6 conforme o acesso
   ao Caddy.

   ```bash
   openssl rand -hex 32
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira no editor `vault_bread_of_life_token_secret` e a lista de IPs.
   Preserve uma cópia cifrada do vault fora do homelab. Mantenha o mesmo
   segredo em reinstalações e restores. Trocá-lo invalida os tokens emitidos.

## Instalação

1. **Provisionar.** Em `terraform/`, com autorização para o ambiente real:

   ```bash
   plano_bread_of_life=$(mktemp)
   terraform plan -out="$plano_bread_of_life"
   # Revise o plano antes de rodar as duas linhas seguintes.
   terraform apply "$plano_bread_of_life"
   rm "$plano_bread_of_life"
   ```

   Antes do apply, confira que o plano cria apenas o LXC 204 e seu
   `ansible_host`. Se houver outra alteração, investigue antes de aplicar.
   O plano contém dados do ambiente: mantenha-o fora do Git. Depois, em
   `ansible/`, confira com `ansible-inventory --graph lxc --ask-vault-pass`.
2. **Configurar a base.** Reautentique o salto SSH com
   `ssh root@<proxmox_host> true` se solicitado pelo Tailscale SSH. A etapa
   depende da identidade do operador. Em `ansible/`:

   ```bash
   ansible-playbook playbooks/lxc.yml --ask-vault-pass --limit proxmox,bread-of-life -e '{"lxc_flags_alvos":["bread-of-life"]}'
   ```

   Confira que a tarefa de flags itera somente `bread-of-life` e que
   **Machines** mostra `bread-of-life-lxc`.
3. **Atribuir a tag.** Em **Machines → bread-of-life-lxc → Edit tags**,
   atribua apenas `tag:proxmox-lxc` e salve. A atribuição usa a sessão
   administrativa do console, conforme a [política da tailnet](../tailscale/README.md).
   Confira a tag no nó. O playbook do servidor exige essa identidade
   antes de publicar o backend.
4. **Subir o servidor.** Em `ansible/`:

   ```bash
   ansible-playbook playbooks/bread-of-life.yml --ask-vault-pass --limit bread-of-life
   ansible-playbook playbooks/caddy.yml --ask-vault-pass --limit caddy
   curl -fsS 'https://bread-of-life.lab.nextlevelcode.pro/health'
   ```

   Confira `ok: true`, `version: "0.5.0"` e `features` no notebook
   autorizado e no celular com Tailscale ativo. Teste IPv4 e IPv6 com
   `curl -4` e `curl -6` conforme os registros DNS disponíveis. No
   notebook, `curl --connect-timeout 5 http://bread-of-life-lxc:4000/health`
   deve falhar. Repita o acesso HTTPS com Tailscale desligado. De um
   terceiro nó com acesso ao Caddy, se disponível, confira HTTP 403
   inclusive com um cabeçalho `X-Forwarded-For` de cliente autorizado.
5. **Conectar clientes.** No celular e no notebook, use **Settings → Sync →
   Self-hosted**, informe a URL HTTPS e crie a conta em um aparelho. Entre
   com a mesma conta no outro. O passo é manual porque o app guarda as
   credenciais localmente. Use dados descartáveis para o aceite.
6. **Validar sincronização.** Crie duas notas de teste no celular e confira
   no notebook. Edite a primeira no notebook e confira no celular. Exclua a
   primeira no celular e confira a exclusão no notebook.
7. **Validar persistência.** Com autorização para interromper o serviço:

   ```bash
   ssh -J root@<proxmox_host> root@10.50.0.204 'docker compose -f /opt/bread-of-life/compose.yml restart sync'
   curl -fsS --retry 5 --retry-delay 2 --connect-timeout 5 'https://bread-of-life.lab.nextlevelcode.pro/health'
   ```

   Confira a saúde, que as sessões continuam válidas e que a primeira nota
   segue excluída. Em um perfil de teste limpo, entre na mesma conta e
   confirme que a segunda nota é baixada do servidor. Edite a segunda nota
   e confira que a edição chega ao outro cliente. Registre versões e
   resultados no PR, com dados de teste.

## Operação

Para inspecionar o serviço, use no LXC
`docker compose -f /opt/bread-of-life/compose.yml ps`.
Para suspender o acesso, esvazie `vault_bread_of_life_client_ips` no vault e
reaplique `ansible-playbook playbooks/caddy.yml --ask-vault-pass --limit caddy`.
Confira HTTP 403 na URL. Para parar também o backend, execute no LXC
`docker compose -f /opt/bread-of-life/compose.yml stop sync`.
Para retomar, reaplique o playbook do serviço e restaure a lista de IPs no
vault antes de reaplicar o Caddy.

Para atualizar, confira a compatibilidade dos clientes e as migrações do
SQLite. Atualize o commit e o SHA-256 em
`roles/bread_of_life/defaults/main.yml`, teste e reaplique o playbook.
Antes de atualizar uma instância com dados, preserve um snapshot consistente
do SQLite e o vault para recuperação.

## Backup

A automação, a retenção e o playbook de restore estão na
[issue #89](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/89).
O diretório persistente sobrevive ao restart e à recriação do container
Docker. Destruir o LXC também apaga seu disco.
