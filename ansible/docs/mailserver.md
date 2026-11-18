# Docker Mailserver na VPS

`playbooks/mailserver.yml` aplica a stack, configura o certificado e agenda
o backup. `playbooks/mailserver-dns.yml` escreve os registros do piloto na
Cloudflare em etapas. As caixas do domínio principal continuam no Proton.

| O quê | Onde |
|---|---|
| Caixas de teste | `ana@piloto-mail.nextlevelcode.pro`, `bruno@piloto-mail.nextlevelcode.pro` |
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
projeto="mailserver-restore-${restore##*.}"
docker compose -p "$projeto" -f compose.yml -f restore.yml config
docker compose -p "$projeto" -f compose.yml -f restore.yml up -d --wait
```

Confira a rede interna e zero portas publicadas no `config` antes do
`up`. Compare o `Message-ID` e corpo pelo Dovecot na instância restaurada.

```bash
id_mensagem='<Message-ID>'
docker compose -p "$projeto" -f compose.yml -f restore.yml exec -T mailserver \
  doveadm fetch -u ana@piloto-mail.nextlevelcode.pro 'hdr.message-id text' HEADER Message-ID "$id_mensagem"
docker compose -p "$projeto" -f compose.yml -f restore.yml down
```

Substitua a caixa no comando se ela for outra. Confira o mesmo ID e corpo,
e em seguida remova a extração temporária após conferir o caminho.

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
