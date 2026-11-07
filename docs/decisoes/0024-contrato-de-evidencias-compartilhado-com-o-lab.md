# 0024. Contrato de evidências compartilhado com o lab

- **Status:** Aceita
- **Data:** 2026-11-07

## Contexto

Um ensaio no `lab` pode sustentar um PR do `infra`, mas cada repositório tem
seu próprio código e estado. Sem uma origem identificada e o resultado da
execução, uma sessão posterior pode atribuir ao código novo um teste antigo.
Repetir as mesmas regras nos arquivos de cada ferramenta também permite
que elas divirjam.

## Decisão

Manter as instruções dos agentes nos `AGENTS.md`, com `CLAUDE.md` como
encaminhamento. O contrato comum de risco e evidências fica em
[`docs/fluxo-de-mudanca.md`](../fluxo-de-mudanca.md) no `infra`, referenciado
pelo `lab`. Cada PR registra o código testado, a reprodução, os resultados
e os limites; o merge manual e a autorização de aplicação são separados.

## Alternativas descartadas

- **Regras completas por ferramenta e repositório:** as cópias podem divergir.
- **Evidência apenas na conversa ou no plano local:** não acompanha a mudança
  para quem revisa o PR ou reproduz um ensaio em outra sessão.

## Consequências

O `lab` referencia uma revisão identificada do contrato, sem importar código
ou acesso de produção. Alterar essa referência permite revisar a adoção de
novas regras. Guias conservam procedimentos e ADRs conservam decisões;
resultados de execuções ficam no PR ou em evidências sanitizadas referenciadas.
