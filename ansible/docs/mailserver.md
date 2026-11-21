# Docker Mailserver na VPS

`playbooks/mailserver.yml` aplica a stack, configura o certificado e agenda
o backup. `playbooks/mailserver-dns.yml` escreve os registros de cada
subdomínio na Cloudflare em etapas. As caixas do domínio principal continuam
no Proton.

| O quê | Onde |
|---|---|
| Caixas de teste | `ana@piloto-mail.nextlevelcode.pro`, `bruno@piloto-mail.nextlevelcode.pro` |
| Primeira caixa de adoção | `admin@mail.nextlevelcode.pro`, com alias `postmaster@mail.nextlevelcode.pro` |
| SMTP entre servidores | `mx-piloto.nextlevelcode.pro:25`, IPv4 público, STARTTLS oferecido |
| SMTP autenticado | `cliente-piloto.nextlevelcode.pro:587`, tailnet, STARTTLS |
| IMAP | `cliente-piloto.nextlevelcode.pro:993`, tailnet, TLS desde a conexão |
| Dados | `/opt/mailserver/dados` |

## Antes de aplicar

- Confirme que o plano e a aplicação foram aprovados. A liberação de SMTP
  de **saída** é um pedido manual no [console da Hetzner](https://console.hetzner.com/limits),
  pois depende da análise da conta. Da VPS, confira o STARTTLS de saída.

  ```bash
  timeout 12 openssl s_client -4 -starttls smtp -connect gmail-smtp-in.l.google.com:25 -brief </dev/null
  ```

  Confira `CONNECTION ESTABLISHED` e `Verification: OK`.
- Confira no painel da Cloudflare que os nomes de
  [`vars/mailserver.yml`](../vars/mailserver.yml) estão livres para o piloto.
  O DNS reserva esses nomes e converge para um registro por nome e tipo.
  O token da VPS precisa de acesso à zona e edição de DNS. O Certbot grava
  somente os desafios ACME de DNS-01.
- Crie duas senhas no gerenciador de senhas e gere seus hashes interativamente.
  De `ansible/`:

  ```bash
  openssl passwd -6
  openssl passwd -6
  ansible-vault edit inventory/group_vars/all/vault.yml
  ```

  Preencha `vault_mailserver_contas` conforme o exemplo. Confira que o vault
  contém os hashes com prefixo `$6$`. A entrada de senha e o vault são manuais
  porque exigem acesso ao gerenciador e à senha do vault.

## Instalação

1. Aplique a política no console conforme o [guia da tailnet](../tailscale/README.md).
   A aplicação é manual porque o console resolve os aliases privados e
   executa os testes da política. Confira que a VPS tem `tag:vps` e que o
   salvamento aceitou os testes de portas 587 e 993.
2. De `ansible/`, publique os endereços. O A do cliente segue o padrão
   dos sites privados da VPS e aponta para o IP Tailscale. O acesso é
   filtrado pela ACL.

   ```bash
   ansible-playbook playbooks/mailserver-dns.yml --limit hetzner --ask-vault-pass -e mailserver_dns_etapa=enderecos
   dig +short A mx-piloto.nextlevelcode.pro
   dig +short A cliente-piloto.nextlevelcode.pro
   ```

   Confira o IPv4 público da VPS no primeiro e seu IPv4 Tailscale no segundo.
3. De `ansible/`, suba a stack e o monitor de backup.

   ```bash
   ansible-playbook playbooks/mailserver.yml --limit hetzner --ask-vault-pass -e mailserver_ativar=true
   ansible-playbook playbooks/uptime-kuma.yml --limit hetzner --ask-vault-pass
   ssh hetzner@hetzner 'sudo docker compose -f /opt/mailserver/compose.yml ps'
   ssh hetzner@hetzner 'sudo tailscale serve status'
   ```

   Confira o container saudável e os dois encaminhamentos TCP na tailnet.
   O playbook prepara o DKIM do Rspamd com o domínio exato do piloto.
   Se a configuração DKIM do container estiver desatualizada, a aplicação
   recria o serviço com os mesmos volumes.
   O Certbot obtém o certificado para os dois nomes. Confira o agendamento
   com `ssh hetzner@hetzner 'systemctl list-timers certbot.timer'`. O DMS
   detecta a troca do certificado após a renovação.
4. De `terraform/hetzner/`, grave `mailserver_piloto_habilitado = true`
   no `terraform.tfvars` local. Use um plano temporário que só a sua conta
   pode ler.

   ```bash
   umask 077
   plano_dir=$(mktemp -d)
   terraform plan -out="$plano_dir/piloto.tfplan"
   terraform show "$plano_dir/piloto.tfplan"
   ```

   Confira que o plano só acrescenta TCP/25 em IPv4, configura o PTR e
   publica o output de IPv4. A VPS e o firewall devem permanecer os mesmos
   recursos, sem substituição ou destruição. Aplique o plano aprovado.

   ```bash
   terraform apply "$plano_dir/piloto.tfplan"
   dig +short -x "$(terraform output -raw mailserver_ipv4)"
   ```

   Confira `mx-piloto.nextlevelcode.pro.` no PTR e o mesmo IPv4 no A.

## Verificação de rede e entrega

1. De fora da tailnet, em uma rede com saída TCP/25, confira
   STARTTLS e que o servidor rejeita relay sem autenticação. O teste para
   no `RCPT TO` e nunca envia `DATA`.

   ```bash
   python3 - <<'PY'
   import smtplib
   import ssl

   with smtplib.SMTP("mx-piloto.nextlevelcode.pro", 25, timeout=15) as smtp:
       smtp.ehlo()
       smtp.starttls(context=ssl.create_default_context())
       smtp.ehlo()
       assert not smtp.has_extn("auth"), smtp.esmtp_features
       code, reply = smtp.mail("relay-probe@example.org")
       assert code == 250, (code, reply)
       code, reply = smtp.rcpt("relay-probe@example.net")
       print(code, reply.decode(errors="replace"))
       assert code in (450, 454, 550, 554) and b"relay" in reply.lower(), (code, reply)
   PY
   ```

   Confira a rejeição explícita de relay. De fora da tailnet, tente
   `nc -w 5 -vz mx-piloto.nextlevelcode.pro 587` e o mesmo em 993.
   Ambas devem falhar.
2. De um desktop autorizado na tailnet, confira os nomes no TLS.

   ```bash
   openssl s_client -starttls smtp -connect cliente-piloto.nextlevelcode.pro:587 -verify_hostname cliente-piloto.nextlevelcode.pro -verify_return_error -brief </dev/null
   openssl s_client -connect cliente-piloto.nextlevelcode.pro:993 -verify_hostname cliente-piloto.nextlevelcode.pro -verify_return_error -brief </dev/null
   ```

   Confira `Verification: OK` em ambas. No Thunderbird, configure IMAP
   993 com SSL/TLS e SMTP 587 com STARTTLS, ambos com senha normal e o
   endereço completo como usuário. A configuração é manual porque o cliente
   usa as senhas do seu gerenciador.
3. De `ansible/`, publique os TXT de autenticação e o MX, após passar as
   verificações anteriores.

   ```bash
   ansible-playbook playbooks/mailserver-dns.yml --limit hetzner --ask-vault-pass -e mailserver_dns_etapa=entrega
   dig +short MX piloto-mail.nextlevelcode.pro
   dig +short TXT piloto-mail.nextlevelcode.pro
   dig +short TXT mail._domainkey.piloto-mail.nextlevelcode.pro
   dig +short TXT _dmarc.piloto-mail.nextlevelcode.pro
   dig +short MX nextlevelcode.pro
   ```

   Confira o MX de prioridade 10 do piloto, o SPF restrito ao IPv4 da VPS,
   a chave pública DKIM, o DMARC `p=reject` e os MX do Proton no domínio
   principal. Aguarde os registros aparecerem no resolvedor público antes
   de testar entrega.
4. Envie uma mensagem de teste do Thunderbird para uma caixa externa que
   você controla, por exemplo Gmail. Confira `spf=pass`, `dkim=pass` e
   `dmarc=pass` nos cabeçalhos do provedor, com o domínio do piloto
   alinhado. Responda pela caixa externa e confirme que a resposta chegou
   por IMAP. Guarde o `Message-ID` e uma frase do corpo para conferir o
   restore. O teste é manual porque usa uma caixa externa autenticada.

## Adotar mail.nextlevelcode.pro com o piloto ativo

Use o MX, o PTR e o certificado já verificados no piloto. Os clientes usam
`cliente-piloto.nextlevelcode.pro` nas portas 587 e 993 da tailnet, com o
endereço completo da nova caixa como usuário. O MX e o catch-all de
`nextlevelcode.pro` continuam no Proton, onde ficam os endereços públicos
como `work@nextlevelcode.pro` e `support@nextlevelcode.pro`.

1. Na Cloudflare, confira que o nome `mail.nextlevelcode.pro` e os nomes
   `mail._domainkey.mail.nextlevelcode.pro` e `_dmarc.mail.nextlevelcode.pro`
   estão livres de registros explícitos e de uso por outros serviços. O
   curinga da zona pode responder a consultas A antes da publicação. O TXT
   cria um nome explícito e passa a impedir essa resposta para o subdomínio.
   No mesmo terminal em que será feita a comparação após a publicação,
   registre os MX e TXT de autenticação existentes e os CNAME de DKIM do
   Proton.

   ```bash
   dns_antes=$(mktemp)
   dns_depois=$(mktemp)
   ns=$(dig +short NS nextlevelcode.pro | head -n 1)
   registro() {
     printf '%s %s\n' "$1" "$2"
     dig @"$ns" +short "$1" "$2" | sort
   }
   correio_atual() {
     for dominio in nextlevelcode.pro piloto-mail.nextlevelcode.pro; do
       registro MX "$dominio"
       registro TXT "$dominio"
       registro TXT "_dmarc.$dominio"
     done
     registro TXT mail._domainkey.piloto-mail.nextlevelcode.pro
     for seletor in protonmail protonmail2 protonmail3; do
       registro CNAME "$seletor._domainkey.nextlevelcode.pro"
     done
   }
   correio_atual > "$dns_antes"
   cat "$dns_antes"
   ```

   Confira os MX do Proton e do piloto e os registros de autenticação em uso.
2. Crie a senha de `admin@mail.nextlevelcode.pro` no gerenciador. De
   `ansible/`, gere o hash interativamente e adicione-o como `admin` em
   `vault_mailserver_contas_adocao`. O vault atual do piloto já contém o
   mapa `vault_mailserver_contas`. A criação da senha e a edição do vault
   são manuais porque exigem acesso ao gerenciador e a senha do vault.

   ```bash
   openssl passwd -6
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira que a entrada `admin` contém o hash com prefixo `$6$`.
3. Na janela aprovada, aplique a stack na VPS. A troca da configuração DKIM
   recria o container com os mesmos volumes e mantém a chave do piloto.

   ```bash
   ansible-playbook playbooks/mailserver.yml --limit hetzner --ask-vault-pass -e mailserver_ativar=true
   ssh hetzner@hetzner 'sudo docker compose -f /opt/mailserver/compose.yml ps'
   ssh hetzner@hetzner 'sudo docker compose -f /opt/mailserver/compose.yml exec -T mailserver doveadm user admin@mail.nextlevelcode.pro'
   ```

   Confira o container saudável e a caixa reconhecida pelo Dovecot. Do
   desktop autorizado, repita as verificações TLS da instalação nas portas
   587 e 993 e configure a nova conta no Thunderbird. Confira o login por
   IMAP com SSL/TLS.
4. De `ansible/`, publique SPF, DKIM e DMARC e, por último, o MX.

   ```bash
   ansible-playbook playbooks/mailserver-dns.yml --limit hetzner --ask-vault-pass -e mailserver_dns_etapa=entrega -e mailserver_dns_dominio=mail.nextlevelcode.pro
   dig +short MX mail.nextlevelcode.pro
   dig +short TXT mail.nextlevelcode.pro
   dig +short TXT mail._domainkey.mail.nextlevelcode.pro
   dig +short TXT _dmarc.mail.nextlevelcode.pro
   correio_atual > "$dns_depois"
   diff -u "$dns_antes" "$dns_depois"
   ```

   Confira o MX de prioridade 10 apontando para
   `mx-piloto.nextlevelcode.pro.`, o SPF restrito ao IPv4 da VPS, a chave
   DKIM própria do novo domínio, o DMARC com `p=reject` e o `diff` vazio.
5. Envie do Thunderbird pela porta 587 com STARTTLS e autenticação para
   uma caixa externa que você controla. Confira `spf=pass`, `dkim=pass`
   e `dmarc=pass` para `mail.nextlevelcode.pro` nos cabeçalhos do provedor.
   Responda para `postmaster@mail.nextlevelcode.pro` e confirme a leitura
   por IMAP na caixa `admin`. Repita o teste com uma caixa do piloto e
   confira que o DKIM dela continua alinhado a `piloto-mail.nextlevelcode.pro`.
   O teste é manual porque usa uma caixa externa autenticada.
6. Guarde o `Message-ID` e uma frase da resposta recebida na caixa
   `admin`. Faça o [backup](#backup) e repita o
   [restore isolado](#restore-isolado) com essa caixa.

Para suspender a entrega no novo subdomínio, de `ansible/`:

```bash
ansible-playbook playbooks/mailserver-dns.yml --limit hetzner --ask-vault-pass -e mailserver_dns_etapa=retirar-mx -e mailserver_dns_dominio=mail.nextlevelcode.pro
dig +short MX mail.nextlevelcode.pro
dig +short A mail.nextlevelcode.pro
dig +short AAAA mail.nextlevelcode.pro
dig +short MX piloto-mail.nextlevelcode.pro
dig +short MX nextlevelcode.pro
```

Confira que o novo domínio ficou sem MX, A ou AAAA e que os MX do piloto e
do Proton continuam presentes. Preserve o TXT no novo domínio para impedir
que a resposta A do curinga volte a servir de rota SMTP implícita. Mantenha
a caixa ativa durante a expiração do TTL para receber mensagens
encaminhadas com o MX em cache.

## Preparar as caixas do domínio principal

O domínio principal declara as contas e rotas em `vault_mailserver_principal`.
Os campos `pessoal` e `trabalho` identificam as caixas conferidas pela prévia
de migração. Na configuração atual, os aliases pessoais apontam para a
caixa pessoal e `support@nextlevelcode.pro` aponta para `work@nextlevelcode.pro`,
que também recebe os destinatários sem cadastro pelo catch-all. A conta
de serviço `vaultwarden@nextlevelcode.pro` entra no mapa `contas` com senha
própria. Veja a ordem de aplicação
em [Migrar o SMTP para o Mailserver](vaultwarden.md#migrar-o-smtp-para-o-mailserver).

1. Para caixas novas, crie uma senha para cada caixa no gerenciador. Gere
   os hashes e preencha `vault_mailserver_principal` seguindo o
   [exemplo do vault](../inventory/group_vars/all/vault.yml.example).
   Use a parte antes de `@` para a conta e para os aliases pessoais. A
   geração da senha e a edição do vault são manuais porque exigem acesso ao
   gerenciador e a senha do vault. De `ansible/`:

   ```bash
   openssl passwd -6
   openssl passwd -6
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Confira que os hashes têm prefixo `$6$`, que `pessoal` e `trabalho`
   apontam para contas distintas e que todos os destinos em `aliases` e
   `catch_all` existem em `contas`.
2. Confira `mailserver_principal_ativo: true` em
   [`vars/mailserver.yml`](../vars/mailserver.yml) na revisão aprovada.
   A aplicação torna `nextlevelcode.pro` um domínio local no Postfix,
   inclusive para mensagens enviadas pelo próprio Mailserver. Aplique
   a configuração na mesma janela planejada para a troca do MX.
3. Na janela, valide os dois logins e a entrega para um alias pessoal,
   para `work` e para um destinatário sem cadastro. Mantenha o Proton
   disponível durante a propagação e teste links de login ou recuperação
   nos endereços em uso. Trate SPF, DKIM e DMARC do domínio principal no
   plano da troca, pois eles também atendem o e-mail enviado pelo Proton.

Nos domínios com catch-all, o Postfix consulta o mapa de aliases antes da
lista de contas. O role escreve cada conta como destino de si mesma,
depois os aliases explícitos e por último o curinga. Essa ordem preserva
a entrega direta a cada caixa. [Ensaio no lab](https://forge.nextlevelcode.pro/nextlevelcode/lab/pulls/22)

### Converter um vault existente

Converta o vault ao atualizar para a revisão que usa `aliases` e `catch_all`.
Execute de `ansible/` com o SHA aprovado, antes de aplicar a stack.

1. Guarde uma cópia cifrada para reversão e abra o editor do Ansible Vault.
   A edição exige a senha do vault e acesso ao cadastro atual.

   ```bash
   vault_anterior=$(mktemp)
   cp -- inventory/group_vars/all/vault.yml "$vault_anterior"
   ansible-vault edit inventory/group_vars/all/vault.yml
   ```

   Em `vault_mailserver_principal`, preserve `pessoal` e todas as entradas e
   hashes de `contas`. Adicione `trabalho: work`, renomeie `aliases_pessoais`
   para `aliases` preservando cada par e acrescente `support: work` a esse
   mapa. Adicione `catch_all: work` no mesmo nível de `contas`. Confira a
   estrutura no [exemplo do vault](../inventory/group_vars/all/vault.yml.example)
   e revise os valores no editor antes de salvar. Mantenha os mapas do
   piloto e do subdomínio de adoção como estavam.
2. Na janela autorizada, rode a prévia abaixo. Ela consulta a VPS e a
   Cloudflare e compara as duas caixas, os aliases e o catch-all declarados
   com o serviço ativo. Use a etapa de finalizar SPF para verificar o
   domínio com o MX já no Mailserver.

   ```bash
   ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=finalizar-spf --check
   ```

   Confira que as verificações do Dovecot e do Postfix passaram. Se uma
   rota divergir, revise a conversão no editor antes de aplicar.
3. Na aplicação autorizada, use `playbooks/mailserver.yml` conforme o passo 1
   de [Ativar as caixas e trocar o MX](#ativar-as-caixas-e-trocar-o-mx).
   Repita a prévia e verifique a entrega direta às duas caixas, a entrega
   aos aliases pessoal e de suporte e a entrega de um endereço sem cadastro
   à caixa de trabalho. Se for preciso reverter, volte à revisão anterior,
   restaure o vault com `cp -- "$vault_anterior" inventory/group_vars/all/vault.yml`
   na mesma sessão e confira a configuração antes de reaplicar a revisão
   anterior na janela autorizada.

## Migrar o MX do domínio principal

Use `ansible/` e o inventário `inventory/vps.yml` nos comandos desta
seção. Confirme a janela, o SHA aprovado e quem vai testar o recebimento
em cada caixa. Durante a propagação, mantenha o Proton e o Mailserver
disponíveis. Guarde o estado público antes de começar.

```bash
for ns in $(dig +short NS nextlevelcode.pro); do
    dig @"$ns" +norecurse +noall +answer nextlevelcode.pro MX
    dig @"$ns" +norecurse +noall +answer nextlevelcode.pro TXT | awk '/v=spf1/'
done
```

Compare o resultado com [`vars/mailserver-migracao.yml`](../vars/mailserver-migracao.yml).
O plano aceita o conjunto de MX do Proton ou o conjunto do Mailserver.
Os MX do Proton usam TTL automático, que a API representa como `1`.
Na resposta pública, os autoritativos anunciam 300 segundos.
Se os registros divergirem, confira a zona e revise os valores antes de
continuar. Reserve a janela para um único operador escrever no DNS.

### Preparar a autenticação

A etapa gera a chave privada na VPS, publica o TXT de DKIM do Mailserver
em `mail._domainkey.nextlevelcode.pro` e acrescenta o IPv4 da VPS ao SPF
que já autoriza o Proton. O Mailserver pode continuar com o domínio
principal desativado durante essa etapa. O curinga DKIM revogado e os
seletores do Proton continuam válidos em seus próprios nomes. A consulta
pela API distingue o seletor explícito da resposta do curinga.

```bash
ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=autenticacao
dig +short TXT nextlevelcode.pro | awk '/v=spf1/'
dig +short TXT mail._domainkey.nextlevelcode.pro
dig +short TXT '_dmarc.nextlevelcode.pro'
dig +short MX nextlevelcode.pro
```

Confira um SPF com `ip4:` da VPS e `include:_spf.protonmail.ch`, o DKIM com
uma chave pública, o DMARC vigente e os dois MX do Proton. Aguarde a
propagação da autenticação antes de enviar do Mailserver com o domínio
principal. A prévia dessa etapa com `--check` lê a VPS e a Cloudflare e
requer que a chave privada já exista.

### Ativar as caixas e trocar o MX

1. Confirme que o vault contém as duas contas e os aliases acordados.
   Confira `mailserver_principal_ativo: true` no arquivo versionado e use o
   [fluxo de revisão e aplicação](../../docs/fluxo-de-mudanca.md#revisão-merge-e-aplicação)
   antes de rodar o playbook da stack.

   ```bash
   ansible-playbook -i inventory/vps.yml playbooks/mailserver.yml --limit hetzner --ask-vault-pass -e mailserver_ativar=true
   ssh hetzner@hetzner 'sudo docker compose -f /opt/mailserver/compose.yml ps'
   ```

   Confira a saúde do container. No Thunderbird, configure as duas contas
   com os endereços completos, usando `cliente-piloto.nextlevelcode.pro`
   em IMAP 993 com SSL/TLS e SMTP 587 com STARTTLS pela tailnet. Envie de
   ambas para uma caixa externa sob seu controle. Confira `spf=pass`,
   `dkim=pass` com `d=nextlevelcode.pro` e `s=mail`, e `dmarc=pass`.
2. Rode a prévia da troca. Ela consulta a VPS e a Cloudflare, então use
   somente na janela autorizada. O playbook confirma as duas caixas, as
   rotas no Postfix, a chave DKIM e o SPF de transição.

   ```bash
   ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=cortar-mx --check
   ```

   Confira a previsão de atualização do MX primário e remoção do
   secundário. Execute a escrita autorizada.

   ```bash
   ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=cortar-mx
   for ns in $(dig +short NS nextlevelcode.pro); do
       dig @"$ns" +norecurse +noall +answer nextlevelcode.pro MX
   done
   dig +short MX nextlevelcode.pro
   ```

   Confira o MX de prioridade 10 para `mx-piloto.nextlevelcode.pro.` nos
   autoritativos e no resolvedor. A API aplica o lote em uma transação na
   zona, e a distribuição pública propaga os registros individualmente.
   [Comportamento dos lotes na Cloudflare](https://developers.cloudflare.com/dns/manage-dns-records/how-to/batch-record-changes/)
3. Teste uma mensagem de login ou recuperação no alias pessoal e em
   `work`. Envie também de fora para um destinatário fictício sem cadastro
   e confira que ele chegou em `work`. Acompanhe as caixas nos dois
   provedores durante a propagação para localizar entregas feitas por
   remetentes que ainda usam o MX em cache.

### Finalizar o SPF

Depois de confirmar o recebimento pelo Mailserver, verifique que o Proton
já deixou de enviar por `nextlevelcode.pro` e confirme o fim da janela de
reversão. O canal antigo de e-mail do Uptime Kuma usa o SMTP do Proton.
Confira a situação desse canal e de outros envios antes de publicar.

Use `ansible/`. A prévia lê a VPS e a Cloudflare. Ela confere as caixas,
o IPv4, o MX e a chave DKIM publicada. Confira que a prévia mostra
`patches` ou informa que o DNS já converge.

```bash
ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=finalizar-spf --check
ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=finalizar-spf
for ns in $(dig +short NS nextlevelcode.pro); do
    dig @"$ns" +norecurse +noall +answer nextlevelcode.pro TXT | awk '/v=spf1/'
done
dig +short TXT nextlevelcode.pro | awk '/v=spf1/'
```

Execute a escrita apenas na janela aprovada. Confira um único TXT
`v=spf1 ip4:<ipv4_da_vps> -all` em cada autoritativo e no resolvedor. Quando
o cache do SPF anterior expirar, envie uma mensagem pelo Mailserver para
uma caixa externa sob seu controle. No original recebido, confira
`spf=pass`, `dkim=pass` com `d=nextlevelcode.pro` e `s=mail`, e
`dmarc=pass`. Essa conferência é manual porque usa uma caixa externa
autenticada.

### Voltar o MX ao Proton

Na janela autorizada, confira que o Proton hospeda o domínio e tem as
caixas ativas antes de apontar o MX para lá. Execute a volta de `ansible/`.
Essa etapa usa somente a Cloudflare e serve também quando a VPS estiver
indisponível. Se o SPF já for exclusivo da VPS, o mesmo lote restaura
o SPF de transição.

```bash
ansible-playbook -i inventory/vps.yml playbooks/mailserver-migracao.yml --limit hetzner --ask-vault-pass -e mailserver_migracao_etapa=voltar-mx
for ns in $(dig +short NS nextlevelcode.pro); do
    dig @"$ns" +norecurse +noall +answer nextlevelcode.pro MX
    dig @"$ns" +norecurse +noall +answer nextlevelcode.pro TXT | awk '/v=spf1/'
done
dig +short MX nextlevelcode.pro
```

Confira `10 mail.protonmail.ch.`, `20 mailsec.protonmail.ch.` e o
`include:_spf.protonmail.ch` no SPF. Teste a entrega no Proton e mantenha
as duas caixas do Mailserver disponíveis
enquanto houver MX em cache ou mensagens da janela para recuperar. A
volta do MX preserva o SPF de transição, as chaves DKIM e as caixas. A
desativação do domínio local vem depois de reconciliar a fila e as caixas.

Para reexecutar as regressões na estação, de `ansible/`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 roles/mailserver/tests/test_contas.py -v
PYTHONDONTWRITEBYTECODE=1 python3 roles/mailserver/tests/test_migracao_dns.py -v
```

Confira a geração dos mapas, a resolução de destinatários e a validação da
prévia com dados fictícios. A regressão de DNS usa uma API simulada em
loopback para cobrir a prévia, os lotes de mudança, a releitura e os estados
recusados.

## Backup

O Borgmatic copia as caixas, o estado (incluindo a fila) e a configuração
(incluindo hashes e chave DKIM). O SSL vem do Certbot. O backup pausa a stack
durante a captura e a inicia ao concluir o `create`, inclusive no hook de
erro. Faça a primeira execução com janela aprovada.

```bash
ssh hetzner@hetzner 'sudo borgmatic -c /etc/borgmatic/mailserver.yaml create --verbosity 1 --stats'
ssh hetzner@hetzner 'sudo borgmatic -c /etc/borgmatic/mailserver.yaml repo-list'
```

Confira o archive `mailserver-*`, o container saudável depois da operação
e o monitor *Backup Docker Mailserver* no Uptime Kuma.

## Restore isolado

Use um archive criado depois da mensagem de verificação. Na VPS, em uma
sessão root, extraia o archive num diretório novo e use um arquivo Compose
adicional que remove as portas publicadas e isola a rede. A stack restaurada
usa o certificado dedicado só para leitura.

```bash
sudo -i
umask 077
restore=$(mktemp -d /opt/mailserver-restore.XXXXXX)
archive='<archive-mailserver>'
borgmatic -c /etc/borgmatic/mailserver.yaml extract --archive "$archive" --destination "$restore" &&
  cp /opt/mailserver/compose.yml "$restore/opt/mailserver/"
```

Só avance se o comando terminar com sucesso e houver `dados/mail`,
`dados/estado` e `dados/config` sob `$restore/opt/mailserver`.

O `mktemp` pode gerar letras maiúsculas no sufixo. Converta o sufixo para
minúsculas ao montar o nome do projeto, como exige o Compose.

```bash
cd "$restore/opt/mailserver"
cat > restore.yml <<'YAML'
services:
  mailserver:
    restart: "no"
    ports: !reset []
networks:
  default:
    internal: true
YAML
sufixo="${restore##*.}"
projeto="mailserver-restore-${sufixo,,}"
docker compose -p "$projeto" -f compose.yml -f restore.yml config
```

Confira no `config` a rede interna e a ausência de portas publicadas.
Depois, suba a instância restaurada.

```bash
docker compose -p "$projeto" -f compose.yml -f restore.yml up -d --wait
```

Compare o `Message-ID` e o corpo pelo Dovecot na instância restaurada.

```bash
id_mensagem='<Message-ID>'
caixa='ana@piloto-mail.nextlevelcode.pro'
docker compose -p "$projeto" -f compose.yml -f restore.yml exec -T mailserver \
  doveadm fetch -u "$caixa" 'hdr.message-id text' HEADER Message-ID "$id_mensagem"
docker compose -p "$projeto" -f compose.yml -f restore.yml down
```

Para verificar a adoção, use `caixa='admin@mail.nextlevelcode.pro'`. Confira
o mesmo ID e corpo, e em seguida remova a extração temporária após conferir
o caminho.

## Desativação

1. De `ansible/`, retire o MX. Aguarde ao menos seu TTL e confira a fila.

   ```bash
   ansible-playbook playbooks/mailserver-dns.yml --limit hetzner --ask-vault-pass -e mailserver_dns_etapa=retirar-mx
   dig +short MX piloto-mail.nextlevelcode.pro
   ssh hetzner@hetzner 'sudo docker compose -f /opt/mailserver/compose.yml exec -T mailserver postqueue -p'
   ```

   Confira a ausência do MX e a fila vazia antes de parar a stack.
2. Faça um backup final. Na VPS, desative os dois encaminhamentos, o
   backup agendado do serviço e a stack. O passo é manual para coordenar
   o corte com DNS, confirmação da fila e o fim do último backup.

   ```bash
   sudo tailscale serve --tcp=587 off
   sudo tailscale serve --tcp=993 off
   sudo mv /etc/borgmatic/mailserver.yaml /opt/mailserver/borgmatic-desativado.yaml
   sudo docker compose -f /opt/mailserver/compose.yml stop
   ```

   Confira que a stack parou e que `tailscale serve status` não mostra essas
   portas. Reaplique `playbooks/uptime-kuma.yml` para remover o monitor.
3. De `terraform/hetzner/`, volte `mailserver_piloto_habilitado` para
   `false`. Revise `terraform plan` e aplique com `terraform apply`.
   Confira que só o PTR do piloto foi removido e TCP/25 voltou a expirar
   de fora da tailnet. Retire o grant do piloto pelo console da tailnet.
