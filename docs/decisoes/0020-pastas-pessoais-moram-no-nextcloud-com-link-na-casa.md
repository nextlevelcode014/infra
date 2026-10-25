# 0020. As pastas pessoais moram no Nextcloud, com link no lugar de sempre

- **Status:** Aceita
- **Data:** 2026-10-25

## Contexto

O ADR 0018 fez o `~/Work` e o `~/.ssh` voltarem pelo Nextcloud. Os
documentos pessoais tinham o mesmo destino possível, a pasta geral
(`~/Nextcloud`), mas dependiam de lembrar de salvar lá: o diálogo de cada app
e o hábito abrem o `~/Documents`, e o que caía ali ficava só no disco e
sumia numa formatação.

## Decisão

O `~/Documents` vira um link para `~/Nextcloud/Documents`, e o
`XDG_DOCUMENTS_DIR` do `user-dirs.dirs` aponta para o caminho real. Quem faz
é o `workflow/bin/pastas`, que também roda na máquina nova
(`docs/maquina-nova.md`, passo 4). Outras pastas da casa entram com uma
linha no script.

## Alternativas descartadas

- **Um par `~/Documents` ↔ `/Laptop/Documents`:** a pasta ficaria fora da
  pasta geral, que já sincroniza `/Documents`. Seriam dois lugares para
  documento, e o celular e a web só veriam um deles.
- **Só mudar o `user-dirs.dirs`:** os diálogos dos apps passam a abrir no
  Nextcloud, mas `~/Documents` no terminal e em app que grava o caminho fixo
  continuaria sendo uma pasta local.
- **Só o link:** app em flatpak recebe a pasta que o `user-dirs.dirs`
  indica, e nem sempre segue um link para fora dela.
- **`~/Downloads` também:** é o que se baixa de novo, e com 28G encheria o
  Nextcloud e o backup do AIO à toa.

## Consequências

- Tudo que se salva em `~/Documents` sobe para o Pi e entra no backup do AIO
  no BorgBase. Arquivo que não deve sair do disco (um export de cofre, por
  exemplo) vai para outra pasta.
- O link aponta para dentro da pasta geral: sem o cliente do Nextcloud
  configurado, o `pastas` recusa rodar, em vez de criar um link para uma
  pasta que não sincroniza.
- Na máquina nova, o `pastas` só roda depois de a pasta geral terminar de
  baixar; antes disso, o que um app salvar em `~/Documents` fica numa pasta
  local comum, que o script então move sem sobrescrever.
