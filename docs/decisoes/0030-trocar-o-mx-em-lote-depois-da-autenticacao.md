# 0030. Autenticação antes do corte e troca dos MX em lote

- **Status:** Proposta
- **Data:** 2026-11-19

## Contexto

O domínio principal recebe pelo Proton e usa DMARC com `p=reject`.
Mensagens durante a transição podem ser aceitas em qualquer um dos
servidores conforme o MX em cache. O Proton tem dois MX e seletores DKIM
próprios. O domínio também publica um curinga DKIM com chave vazia.

## Decisão

Prepare um seletor DKIM explícito e um único SPF que autorize o Proton e o
IPv4 do Mailserver antes do corte. Atualize o SPF por ID e preserve os
outros registros TXT. Troque o conjunto MX e faça a volta por lotes na API
da Cloudflare. Cada operação exige um estado anterior esperado e uma
releitura da zona após a escrita.

## Alternativas descartadas

- **Manter MX dos dois provedores como destino primário e reserva.**
  Uma falha temporária mudaria a caixa que recebe a mensagem e tornaria
  menos previsível a entrega dos códigos de acesso.
- **Fazer uma operação independente por MX.** Uma falha parcial poderia
  deixar a zona em um estado intermediário além do período de cache.

## Consequências

A Cloudflare grava cada lote em uma transação, mas os registros
propagam individualmente. Mantenha os dois servidores disponíveis
durante a transição e confira os autoritativos e resolvedores depois
da escrita. Uma volta do MX preserva a autenticação e as caixas do
Mailserver para o tráfego da janela. [Lotes de DNS na Cloudflare](https://developers.cloudflare.com/dns/manage-dns-records/how-to/batch-record-changes/)
