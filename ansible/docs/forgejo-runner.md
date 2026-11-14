# Forgejo Runner

O [ADR 0027](../../docs/decisoes/0027-runner-do-forgejo-em-vm-com-rede-propria.md)
define os limites do executor. O Terraform cria `forgejo-runner` desligada
e sem partida automática. A VM fica no grupo `forgejo_runners`, com
endereço fixo numa bridge exclusiva. Os parâmetros da rede são lidos de
[`ansible/vars/rede-runner.yml`](../vars/rede-runner.yml). O registro
pertence ao repositório `nextlevelcode/infra`.

## Preparar e criar

Com autorização de aplicação e a revisão mergeada:

1. Conferir no Proxmox espaço em `local-lvm`, disponibilidade do VMID
   e da bridge, ausência de sobreposição de rota e permissões do token
   de provisionamento na VM, storage e rede. Conferir também o
   volume `local:import/ubuntu-26.04-server-cloudimg-amd64.qcow2` com
   `pvesm list local --content import`. A cópia base é importada no
   disco da VM. Se o volume faltar, verifique a imagem cloud pela soma
   publicada pelo Ubuntu e envie pelo storage **local → Import → Upload**
   no Proxmox. A importação pelo Terraform pressupõe o volume no storage.
2. Da pasta `ansible/`, aplicar e conferir a rede dedicada:

   ```bash
   ansible-playbook playbooks/forgejo-runner-rede.yml --ask-vault-pass --limit proxmox
   ssh root@<proxmox_host> 'ip -br addr show vmbr3; nft list table inet forgejo_runner'
   ```

   Confira o endereço do gateway e as chains de entrada, encaminhamento
   e NAT. A bridge carrega a tabela antes de subir. A tabela limita saídas
   ao gateway da uplink observado na aplicação. Se o Proxmox trocar de
   rede, reaplique antes de ligar a VM. Se faltar gateway no boot, a bridge
   pode ficar indisponível até a uplink obter rota e a rede ser reaplicada.
3. Da pasta `terraform/`, rode `terraform plan` e confira que a alteração
   cria apenas a VM e seu host no inventário. Com o plano aprovado, rode
   `terraform apply`. Confirme com `ssh root@<proxmox_host> 'qm status 300'`
   que ela está parada. Depois de conferir a tabela no Proxmox, o operador
   liga a VM com `ssh root@<proxmox_host> 'qm start 300'`. A partida fica
   com o operador devido à dependência da rede e às verificações prévias.
4. Confira a chave de host pelo console Proxmox com
   `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Ao conectar pela
   primeira vez com `ssh -J root@<proxmox_host> ubuntu@10.70.0.2`,
   aceite a chave só se a impressão coincidir. Essa conferência usa
   o console porque é independente do primeiro acesso SSH.
5. Da pasta `ansible/`, prepare o Docker, o filtro local e o serviço:

   ```bash
   ansible-playbook playbooks/forgejo-runner.yml --ask-vault-pass --limit forgejo-runner
   ssh -J root@<proxmox_host> ubuntu@10.70.0.2 'systemctl is-active docker forgejo-runner-firewall; systemctl is-active forgejo-runner'
   ```

   Docker e firewall devem estar ativos. O runner deve aparecer
   `inactive`. Uma reaplicação sem `forgejo_runner_ativar=true`
   mantém o runner parado e desabilitado.

## Conferir rede e HTTPS

Use alvos autorizados e registre os contadores do
`nft list table inet forgejo_runner` no Proxmox. Da VM e de um container
Docker com rede separada, confirme que um resolvedor designado atende
consultas e que um download HTTPS funciona. Faça sondas com timeout de
conexão para LAN, Proxmox, Pi, lab, LXCs, tailnet e destinos IPv6. Todas
devem falhar. No container, confirme também que o gateway Docker e os
serviços da VM não aceitam conexões novas. A falha e o contador do filtro
devem concordar. Confira a interface e a tabela no Proxmox após reboot
antes de voltar a aceitar jobs.

A política da VPS, aplicada separadamente com
`ansible-playbook playbooks/anubis.yml --ask-vault-pass --limit vps` na
pasta `ansible/`, prevê passagem para RPC com os cabeçalhos de runner e
Git de leitura do `infra`. Com a aplicação autorizada, confirme:

```bash
GIT_TERMINAL_PROMPT=0 git -c credential.helper= \
  ls-remote https://forge.nextlevelcode.pro/nextlevelcode/infra.git refs/heads/main
curl -sS -o /dev/null -w '%{content_type}\n' https://forge.nextlevelcode.pro/api/v1/version
```

O Git deve imprimir a ref. A API anônima continua sob o desafio. Confira
também um fetch real por HTTPS e o envio de logs do runner no piloto.

## Publicar a imagem e registrar

O Anubis encaminha descoberta e emissão de token OCI no endereço público
do Forgejo. O tráfego de manifests, blobs e uploads fica restrito ao
pacote `nextlevelcode/infra-ci`. Depois de aplicar a política, confira com
`curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' https://forge.nextlevelcode.pro/v2/`
que a resposta é a do registry (200 ou 401), e confira o pull anônimo pelo
digest depois da publicação. Para escrever, autentique o Docker com
`docker login forge.nextlevelcode.pro` usando um token com acesso de
escrita ao pacote. Faça o login na estação de build.

1. Com autorização de publicação, construa a imagem de ferramentas e
   publique no registry público escolhido, de uma máquina com Docker,
   acesso de escrita ao registry e checkout da revisão preparada:

   ```bash
   export IMAGEM_CI='forge.nextlevelcode.pro/nextlevelcode/infra-ci:piloto-1'
   docker build --platform linux/amd64 --tag "$IMAGEM_CI" ansible/roles/forgejo_runner/files
   docker push "$IMAGEM_CI"
   docker image inspect "$IMAGEM_CI" --format '{{json .RepoDigests}}'
   ```

   Guarde a referência `imagem@sha256:...` exibida e confirme que o pull
   anônimo funciona. A publicação depende do registry e da conta escolhidos
   pelo responsável. A VM não recebe credencial do registry.
2. Com autorização de registro, abra **Settings → Actions → Runners →
   Create new runner** no repositório `nextlevelcode/infra`. Copie UUID e
   token. Use `ansible-vault edit inventory/group_vars/all/vault.yml` na
   pasta `ansible/` para guardar o token em `vault_forgejo_runner_token`.
   O passo na interface usa o escopo do repositório e entrega o segredo
   diretamente ao responsável.
3. Nessa pasta, ative com os valores públicos do registro e da imagem:

   ```bash
   ansible-playbook playbooks/forgejo-runner.yml --ask-vault-pass --limit forgejo-runner \
     -e forgejo_runner_ativar=true -e forgejo_runner_uuid=<uuid-do-registro> \
     -e forgejo_runner_imagem=<imagem@sha256:digest>
   ```

   Confira que o registro específico ficou online e anunciou a label
   `infra-ci`. O token fica num arquivo local root-only e o systemd entrega
   a credencial ao controlador por `LoadCredential`.

## Piloto, atualização e recuperação

No piloto, observe dois jobs sucessivos com a label `infra-ci`, uma
falha deliberada, um cancelamento e recuperação após reboot. Confira
os limites e os mounts com `docker inspect <id-do-container>` enquanto o
job roda. No job, o socket Docker, a credencial e os arquivos da VM
devem estar inacessíveis. Use um marcador fictício para conferir que o
workspace de um job não aparece no próximo. Meça tempo e disco com
`df -h /var/lib/docker; sudo docker system df`.

Para interrupção ou manutenção, execute na VM
`sudo systemctl stop forgejo-runner` e confira que ficou inativo.
Inventarie resíduos com `sudo docker ps -a; sudo docker network ls;
sudo docker volume ls`. Remova só os resíduos identificados com
`sudo docker rm <container>`, `sudo docker network rm <rede>` ou
`sudo docker volume rm <volume>`. Para atualizar, revise a versão e
o SHA256 no role e o digest da imagem, reaplique com a ativação e rode
novamente o piloto. Para rotacionar, pare o serviço, revogue o registro
no mesmo painel e repita o registro e a ativação.

Se o isolamento falhar, pare o serviço, desligue a VM e revogue o
registro. Confirme o estado com `qm status 300` no Proxmox e pelo painel
do Forgejo. A reconstrução repete a preparação da rede, o provisionamento
e o registro novo. Se precisar remover a exceção do Anubis, reverta as
regras específicas do CI e reaplique o playbook da VPS. Confira o desafio
e o acesso normal ao Forgejo depois da reaplicação.
