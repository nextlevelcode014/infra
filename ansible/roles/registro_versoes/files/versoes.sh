#!/bin/bash
# Registro de versões dos containers, para os playbooks de atualização
# (role registro_versoes). Com tag flutuante o compose não diz o que está
# rodando, e o prune do fim apaga a imagem anterior: o digest gravado aqui é
# o que permite voltar (image: <repo>@sha256:<digest> no compose).
#
#   versoes.sh antes  <arquivo>                 grava o estado atual
#   versoes.sh depois <arquivo-antes> <log>     grava o log e imprime o que mudou
set -uo pipefail

# Uma linha por container rodando: nome|referência|digest|versão. A versão
# vem do label OCI (ou do label-schema antigo); muita imagem não tem nenhum,
# e aí o resumo usa a tag da referência.
estado() {
  docker ps --format '{{.Names}}' | sort | while read -r c; do
    IFS='|' read -r ref id < <(docker inspect -f '{{.Config.Image}}|{{.Image}}' "$c" 2>/dev/null) || continue
    docker image inspect -f "$c|$ref|{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}|{{with .Config.Labels}}{{or (index . \"org.opencontainers.image.version\") (index . \"org.label-schema.version\")}}{{end}}" "$id" 2>/dev/null
  done
}

# Compara dois estados e imprime só o que mudou, uma linha por container.
mudancas() {
  awk -F'|' '
    function versao(v, ref,   t) {
      if (v != "") return v
      t = ref; sub(/^.*\//, "", t)
      return (t ~ /:/) ? substr(t, index(t, ":") + 1) : "sem tag"
    }
    function curto(d) { return (d ~ /@sha256:/) ? substr(d, index(d, "@sha256:") + 8, 12) : "sem digest" }
    NR == FNR { antes[$1] = $0; next }
    {
      visto[$1] = 1
      if (!($1 in antes)) { print $1 ": novo, " versao($4, $2) " (" curto($3) ")"; next }
      split(antes[$1], o, "|")
      if (o[3] != $3)
        print $1 ": " versao(o[4], o[2]) " → " versao($4, $2) "  (" curto(o[3]) " → " curto($3) ")"
    }
    END { for (c in antes) if (!(c in visto)) print c ": não está mais rodando" }
  ' "$1" "$2"
}

case "${1:-}" in
  antes)
    estado > "$2"
    ;;
  depois)
    antes=$2; log=$3
    depois=$(mktemp); trap 'rm -f "$depois"' EXIT
    estado > "$depois"
    resumo=$(mudancas "$antes" "$depois")
    {
      echo "# $(date '+%F %T') $(hostname)"
      echo
      echo "## O que mudou"
      echo "${resumo:-nada}"
      echo
      echo "## Antes (nome|referência|digest|versão)"
      cat "$antes"
      echo
      echo "## Depois"
      cat "$depois"
    } > "$log"
    rm -f "$antes"
    echo "${resumo:-nenhuma imagem mudou}"
    ;;
  *)
    echo "uso: $0 antes <arquivo> | depois <arquivo-antes> <log>" >&2
    exit 2
    ;;
esac
