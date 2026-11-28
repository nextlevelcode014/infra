#!/usr/bin/env bash
#
# Hook PreToolUse do Claude Code: recusa `git commit` e `git push` quando a
# mudança traz nome de tailnet ou IP Tailscale real. O repo é público
# (AGENTS.md, "O repo é público").
#
# A regra mora em um lugar só: `verificar.py privacidade`, a mesma
# conferência que a CI roda no PR. A CI só roda depois do push, quando o
# valor já foi publicado; o hook antecipa a mesma regra para antes dele.
#
# O que olha:
#   commit -> HEAD contra a árvore de trabalho: o que está staged e o que
#             ainda não está, nos arquivos rastreados. Cobre
#             `git add x && git commit` e `-a`, que o índice sozinho não mostra
#             quando o hook roda. Arquivo novo adicionado no mesmo comando
#             escapa daqui, e por isso o push existe.
#   push   -> tudo que a branch tem a mais que a default do origin. É o push
#             que publica, então esse é o portão que garante a regra.
#
# Contrato: o Claude Code manda um JSON no stdin. Saída 0 libera; saída 2
# bloqueia e o stderr volta ao modelo como motivo. Falha inesperada libera:
# um hook quebrado não pode travar o trabalho, e a CI continua conferindo.

set -uo pipefail

entrada="$(cat)"
comando="$(jq -r '.tool_input.command // empty' <<<"$entrada" 2>/dev/null)" || exit 0
pasta="$(jq -r '.cwd // empty' <<<"$entrada" 2>/dev/null)" || exit 0

re_git='(^|[;&|[:space:]])git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*[[:space:]]+(commit|push)([[:space:]]|$)'
[[ "$comando" =~ $re_git ]] || exit 0
acao="${BASH_REMATCH[4]}"

# O repo avaliado é onde o git roda, não a pasta da sessão: `cd <pasta> &&`
# antes do git muda o alvo (caso de worktree), e `git -C <pasta>` vence.
re_cd='(^|[;&|[:space:]])cd[[:space:]]+([^[:space:];&|]+)'
if [[ "$comando" =~ $re_cd ]]; then
  alvo="${BASH_REMATCH[2]//[\"\']/}"
  alvo="${alvo/#\~/$HOME}"
  [[ "$alvo" == /* ]] || alvo="$pasta/$alvo"
  pasta="$alvo"
fi
re_c='git[[:space:]]+-C[[:space:]]+([^[:space:]]+)'
if [[ "$comando" =~ $re_c ]]; then
  alvo="${BASH_REMATCH[1]}"
  [[ "$alvo" == /* ]] || alvo="$pasta/$alvo"
  pasta="$alvo"
fi
[[ -d "$pasta" ]] || exit 0
raiz="$(git -C "$pasta" rev-parse --show-toplevel 2>/dev/null)" || exit 0

# Só vale para este repo: outro repositório não tem o verificar.py.
[[ -f "$raiz/verificar.py" ]] || exit 0

if [[ "$acao" == commit ]]; then
  revisoes=(HEAD)
else
  default="$(git -C "$raiz" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)"
  base="$(git -C "$raiz" merge-base "${default:-origin/main}" HEAD 2>/dev/null)" || exit 0
  revisoes=("$base" HEAD)
fi

saida="$(python3 "$raiz/verificar.py" privacidade "${revisoes[@]}" 2>&1)"
[[ $? -eq 1 ]] || exit 0

{
  echo "Bloqueado pelo hook grep-de-vazamento ($acao): $saida"
  echo "O repo é público. Use variável no código e placeholder nos docs (<tailnet>.ts.net, <ts_ip>); veja AGENTS.md."
} >&2
exit 2
