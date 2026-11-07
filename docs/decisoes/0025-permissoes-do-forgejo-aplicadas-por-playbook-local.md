# 0025. Permissões do Forgejo aplicadas por playbook local

- **Status:** Aceita
- **Data:** 2026-11-07

## Contexto

Permissões e proteções definidas só pela interface não têm configuração
desejada revisável no Git. Incorporá-las ao deploy da stack misturaria
mudanças administrativas de repositórios com instalação e recuperação do
serviço, além de exigir uma credencial de API em operações que não precisam
dela. A conta dedicada ao agente não elimina o acesso às credenciais humanas
quando ambos compartilham o mesmo ambiente.

## Decisão

Declarar colaboradores e proteção dos repositórios em YAML e reconciliar
pela API com um playbook local, executado separadamente e sob autorização.
O escopo inicial é o `infra`; os próximos repositórios entram explicitamente.
O playbook preserva itens não declarados, salva o estado gerenciado antes de
escrever e exige correspondência após aplicar. `--check` só consulta e
compara. Tokens ficam no vault, fora do Git e dos logs.

Merge permanece manual, restrito ao responsável pela proteção. O fluxo de
identidade atual é mantido; a conta `agent` pode ser usada explicitamente
nos ensaios. Seu isolamento é investigado na
[issue #78](https://forge.nextlevelcode.pro/nextlevelcode/infra/issues/78),
separadamente do runner e da proteção dos repositórios.

## Alternativas descartadas

- **Somente configuração manual:** dificulta revisão, reprodução e detecção
  de divergência.
- **Acoplar ao deploy ou ao `site.yml`:** mistura escopos e disponibiliza a
  credencial administrativa em execuções que não a exigem.
- **Remover regras antes de reaplicá-las:** abre uma janela desprotegida.
  Criação e bloqueios serão ensaiados em branch temporária equivalente.
- **Reconciliação destrutiva ou rollback automático:** poderia remover regras
  alheias ao escopo ou desfazer uma alteração legítima concorrente. A
  recuperação é uma operação específica, revisada pelo responsável.

## Consequências

A configuração fica revisável e a aplicação idempotente, mas a API continua
sendo uma operação real, inclusive para leitura autenticada. Os testes
fictícios não substituem o ensaio de permissões no servidor. O responsável
precisa guardar a credencial de operação, revisar diferenças e conferir o
estado após falhas; não há transação entre as chamadas. A primeira versão
gerencia nomes literais sem barras/globs e colaboradores `read`/`write`;
ampliar esse contrato requer revisar a API e os testes.
