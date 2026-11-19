# 0029. Caixas pessoal e de trabalho separadas no domínio principal

- **Status:** Proposta
- **Data:** 2026-11-19

## Contexto

Endereços do domínio principal já recebem mensagens de login e de
recuperação em serviços externos. Alguns funcionam graças ao catch-all
do Proton. A migração precisa preservar esses destinatários e separar
o correio pessoal do de trabalho. [Issue #115](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/115)

## Decisão

As duas caixas têm logins próprios. Aliases pessoais apontam para a
caixa pessoal. A caixa de trabalho recebe `support` e os destinatários
do catch-all. Os endereços pessoais e os hashes ficam no vault. O
Ansible declara a precedência das contas e dos aliases sobre o curinga.

A ativação do domínio principal é versionada e começa desligada.
Ativar o domínio no Postfix começa a entrega local mesmo antes da troca
do MX. Por isso, a ativação faz parte da janela de migração do DNS.

## Alternativas descartadas

- **Caixa única.** Misturaria o correio pessoal e de trabalho na mesma caixa.
- **Só endereços cadastrados.** Interromperia a entrega de mensagens para
  endereços usados em cadastros antigos que hoje dependem do catch-all.

## Consequências

Um endereço pessoal identificado depois da migração pode ser apontado
à caixa pessoal com um alias explícito. Antes de compartilhar o acesso
à caixa de trabalho, revise o destino do catch-all, pois ele pode receber
mensagens de recuperação de contas pessoais. [Ensaio de roteamento](https://forge.nextlevelcode.pro/nextlevelcode/lab/pulls/22)
