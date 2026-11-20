# 0031. O SPF passa a autorizar só a VPS ao encerrar a transição

- **Status:** Proposta
- **Data:** 2026-11-20

## Contexto

O [ADR 0030](0030-trocar-o-mx-em-lote-depois-da-autenticacao.md) autoriza o
Mailserver e o Proton durante o corte do domínio principal. Depois da
transição, o Proton deixa de ser remetente autorizado do domínio.

## Decisão

Remova o Proton do SPF em uma etapa explícita, após o fim da janela de
reversão. A etapa exige o MX exclusivo do Mailserver, o DKIM já publicado
e o SPF de transição ou final. Altere o TXT de SPF pelo ID existente.

Se for necessário reativar o Proton depois disso, a volta do MX restaura
também o SPF de transição no mesmo lote da Cloudflare, sem acessar a VPS.
O domínio e as caixas precisam estar ativos no Proton antes dessa volta.

## Alternativas descartadas

- **Retirar o Proton no mesmo lote do corte original.** A autenticação
  dos envios do Proton ainda era necessária durante a janela de transição.
- **Manter a autorização indefinidamente.** O SPF continuaria reconhecendo
  um provedor sem função de envio para o domínio.

## Consequências

O SPF do domínio principal termina com `-all` e autoriza o IPv4 publicado
do Mailserver. Valide a entrega em uma caixa externa após a propagação.
