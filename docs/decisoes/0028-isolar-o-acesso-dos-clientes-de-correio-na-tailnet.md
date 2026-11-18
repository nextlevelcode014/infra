# 0028. Só o SMTP entre servidores é público no piloto de correio

- **Status:** Proposta
- **Data:** 2026-11-17

## Contexto

O piloto da [issue #85](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/85)
usa a VPS da Hetzner e um subdomínio isolado das caixas atuais. Outros MTAs
precisam encontrar o MX em DNS público e abrir uma conexão na TCP/25. A VPS
já usa o firewall gerenciado pelo Terraform e o Docker publica portas
contornando o UFW.

## Decisão

O MX recebe TCP/25 no IPv4 público da VPS. O IPv4, o PTR e o nome que o
Postfix apresenta identificam o mesmo servidor. A abertura do firewall e o
PTR são ativados pela mesma variável no Terraform. O Ansible usa playbooks
explícitos para o serviço e os registros do piloto.

Os desktops autorizados usam SMTP com autenticação em 587 e IMAPS em 993.
O Tailscale Serve encaminha TCP para portas em loopback. Um certificado
dedicado cobre o nome público e o nome usado pelos clientes. O Certbot
renova por DNS-01 e o Mailserver lê só essa linhagem.

## Alternativas descartadas

- **Publicar as portas dos clientes no IPv4 público.** Aumentaria a
  exposição da autenticação para um piloto com clientes na tailnet.
- **Vincular diretamente o Docker ao IP Tailscale.** O Compose passaria a
  depender da atribuição desse endereço no boot.
- **Usar o certificado curinga do Caddy.** A chave dos sites da VPS ficaria
  acessível dentro do container de correio.

## Consequências

As caixas do piloto usam `piloto-mail.nextlevelcode.pro` com autenticação
de domínio própria. A regra pública da Hetzner passa a proteger a porta
publicada pelo Docker. A ACL protege as portas de cliente. A ativação do
serviço exige a liberação SMTP do provedor, a verificação do certificado e
um teste de rejeição de relay antes da publicação do MX.
