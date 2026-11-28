# 0032. A config do Claude Code específica do infra fica versionada no repo

- **Status:** Aceita
- **Data:** 2026-11-28

## Contexto

A configuração do Claude Code dos projetos pessoais mora no `claude-config`,
carregado como o plugin `nextlevelcode`: os comandos `comecar` e `entregar`,
o hook `proteger-branch-default` e as skills. Tudo ali vale para qualquer
repo pessoal.

A conferência de valores privados é diferente. Ela só faz sentido no infra,
que é público e guarda placeholders no lugar do nome da tailnet e dos IPs
Tailscale. A regra já existe em `verificar.py` e roda na CI, mas a CI roda
depois do push, quando o valor já foi publicado. Antes, a conferência
antecipada dependia de lembrar de rodar o grep do `AGENTS.md`.

## Decisão

Configuração do Claude Code que só vale para este repo fica em `.claude/`,
versionada junto com o código que ela protege: `.claude/settings.json`
registra os hooks e `.claude/hooks/` guarda os scripts. O que vale para
todos os repos pessoais continua no `claude-config`.

O primeiro hook é `grep-de-vazamento.sh`, que chama
`verificar.py privacidade` antes de `git commit` e `git push`. A regra
continua num lugar só: o hook só a antecipa.

## Alternativas descartadas

- **Pôr o hook no plugin do `claude-config`.** Rodaria em todo repo pessoal
  para uma regra que só existe aqui, e a versão do hook ficaria separada da
  versão do `verificar.py` que ele chama.
- **Hook com a regex própria.** Duplicaria a regra da CI, com as exceções
  de fixture e de endereços genéricos, e as duas cópias divergiriam.
- **Hook de git (`pre-commit`, `pre-push`).** Valeria também fora do Claude,
  mas o git não versiona hooks sem `core.hooksPath` configurado à mão em
  cada clone. Fica como opção se o comando manual não bastar.

## Consequências

Mudança no `verificar.py` muda o que o hook bloqueia, no mesmo PR. O
`settings.local.json` e o estado de sessão em `.claude/` ficam fora do git.
Um agente revisor específico do infra, se vier, segue a mesma regra e mora
em `.claude/agents/`. Fora do Claude Code nada roda sozinho: o comando
manual está no `AGENTS.md`.
