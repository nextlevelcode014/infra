# Fluxo de mudança e contrato de evidências

Este contrato vale para mudanças no `infra` e para os ensaios do `lab` que
sustentam essas mudanças. As instruções dos agentes ficam nos `AGENTS.md`;
os `CLAUDE.md` apenas encaminham para o arquivo correspondente.

## Antes de mudar

1. Confirme o remote com `git remote -v`, sincronize as referências e leia
   os `AGENTS.md` aplicáveis, os guias e os ADRs relacionados.
2. Defina o resultado da sessão, o escopo e como conferir que funcionou.
   Classifique as verificações pela tabela abaixo antes de executá-las.
3. Trabalhe em branch, com `comecar`. Ao concluir, use `entregar` para abrir
   o PR com evidências e limitações. Dependências novas exigem autorização
   antes da instalação.

## Uso das skills

Skills ajudam em tarefas específicas; não substituem as instruções do
repositório nem as autorizações de execução.

| Situação | Skill | Quando usar |
|---|---|---|
| Questionar um plano ou decisão | `grill-me` | Sob demanda do responsável, antes de decisões com premissas ou riscos relevantes, como isolamento do runner, backup ou migração; mudanças pequenas seguem o fluxo normal |
| Investigar comportamento inesperado | `engineering:debug` | Reproduzir, isolar e diagnosticar uma falha antes de propor a correção |
| Revisar uma mudança | `engineering:code-review` | Quando houver pedido de revisão ou riscos que justifiquem uma análise específica; no infra e no lab, priorizar segurança, idempotência, drift, rollback e impacto operacional |

A `grill-me` adotada é a adaptação compartilhada do `claude-config`, usada
para esclarecer decisões antes da implementação. A entrevista termina com
decisões e dúvidas restantes; não inicia operações por conta própria.
Instalação e manutenção dessa skill pertencem ao `claude-config`; as duas
skills de engenharia são fornecidas pelo plugin de engenharia já disponível.
Se uma skill não estiver disponível, informe a ausência sem alegar que foi
executada e sem instalar dependências automaticamente. As regras deste
contrato continuam válidas.

Planejamento verificável e evidências antes da entrega já fazem parte do
fluxo acima e de `entregar`. TDD pode ajudar em scripts e regressões com
comportamento testável; não é exigência universal para documentação ou
configuração. A escolha dos testes deve corresponder ao risco da mudança.

## Risco e classes de validação

O efeito do comando determina a classe; o nome da ferramenta não basta.

| Classe | Exemplos | Condição para executar |
|---|---|---|
| Local comum | Revisão documental, formatação, validação estática e regressões offline | Sem inventário, vault, state ou credenciais reais; use dependências já disponíveis |
| Integração com requisitos especiais | Namespaces, daemons reais e falhas simuladas | Declare isolamento, privilégios e efeitos locais; confirme a autorização para efeitos colaterais antes de executar |
| Ambiente real | Planos com state/credenciais reais, provisionamento, Ansible remoto, cadastro Tailscale, restart, reboot, restore e rollback | Defina ambiente, alvos, comandos, impacto e recuperação; efeitos colaterais precisam de autorização específica, inclusive no lab |

Uma checagem de sintaxe Ansible usa inventário isolado, sem carregar o vault.
Validação Terraform usa uma cópia de trabalho preparada sem backend real;
`validate` não comprova o resultado de um `plan` ou `apply`. `--check --diff`
com inventário real continua acessando o ambiente e pode revelar segredos.
Se faltarem dependências ou isolamento, registre bloqueio; não trate como
aprovação. Nenhuma classe permite ampliar o acesso do lab à produção.

## Evidência mínima

Para cada execução relevante, registre no PR ou em resultado sanitizado
referenciado por ele:

| Campo | O que registrar |
|---|---|
| Código | Repositório, SHA completo testado e situação da árvore; identifique o patch se houver alterações locais |
| Relação com o lab | SHA do `infra` e do `lab`, origem e hashes da cópia independente quando houver |
| Ambiente | Versões relevantes ou digest da imagem, cenário e diferenças materiais para produção |
| Reprodução | Diretório, comando literal, perfil e parâmetros públicos |
| Resultado | Aprovado, falhou, não executado ou bloqueado; explicite verificações puladas e o motivo |
| Registro | Data e link da execução ou localização dos resultados sanitizados |
| Limites | O que a execução não comprovou e quais riscos permanecem |

Comandos de identificação, na raiz de cada repositório:

```bash
git remote -v
git rev-parse HEAD
git status --short
```

Confira: o remote é do repositório pretendido, o SHA tem 40 caracteres e
as alterações locais aparecem no status. Revise a saída antes de publicar:
não inclua credenciais, vault, state, planos reais, nome da tailnet ou IPs
Tailscale. Use placeholders nos trechos públicos.

O SHA identifica a base do checkout; uma árvore modificada exige identificar
também o patch testado. Um teste anterior não aprova código novo. Mudanças de
dependência, ambiente ou premissa também exigem reavaliar a evidência.
Mudança somente documental pode reutilizar um ensaio do mesmo conteúdo
operacional, desde que essa equivalência fique explícita.

## Ensaio entre repositórios

O `lab` mantém cópias independentes, sem importar roles, módulos, state,
inventário ou segredos de produção. Identifique o SHA completo do head
proposto do `infra`, o SHA do cenário no `lab` e os hashes dos arquivos
copiados. Preserve a origem e os resultados históricos ao atualizar a cópia.
Novo código relevante exige repetir os cenários afetados; sem repetição,
registre “não reexecutado”.

## Revisão, merge e aplicação

O PR apresenta problema, resultado, evidências e limites; os guias guardam
procedimentos reutilizáveis e os ADRs guardam decisões duradouras. Evite
duplicar a matriz completa do ensaio nesses três lugares.

O responsável revisa e faz o squash merge manualmente; agentes não fazem
merge. O fluxo normal é merge antes da aplicação. Aplicar uma branch antes
disso exige autorização explícita para o SHA e conferência posterior do
conteúdo mergeado. Aprovar o plano ou o PR não autoriza, por si só, rollout,
provisionamento ou operações em serviços e dados.

Após o squash, registre no PR o SHA resultante e confira a correspondência
do conteúdo operacional testado, pois os SHAs serão diferentes. A aplicação
precisa de escopo e autorização próprios, conforme o guia do serviço.
Registre depois o resultado observado e eventuais verificações pendentes.
