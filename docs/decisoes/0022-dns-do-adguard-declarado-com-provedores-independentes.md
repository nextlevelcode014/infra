# 0022. DNS do AdGuard declarado, com provedores independentes

- **Status:** Aceita
- **Data:** 2026-11-01

## Contexto

O bloqueio do Quad9 na rede de casa derrubou o AdGuard: tanto os upstreams
quanto o bootstrap dependiam dele (#67). A correção pela interface não era
reproduzível pelo Ansible e um backup antigo poderia desfazê-la no restore.

## Decisão

Priorizar arquivos versionados como fonte de verdade da infraestrutura.
O role compartilhado `adguard_dns` declara Quad9 e Mullvad por DoH, bootstrap
Quad9 e Cloudflare e modo `parallel`. A consulta pode chegar aos dois
provedores; aceita-se essa exposição adicional para obter a primeira
resposta sem esperar o provedor indisponível. Bootstrap permanece em DNS
comum, mas não depende de um único provedor.

Deploy e restore mesclam essas três chaves no YAML existente. A edição é
feita com o container parado, relendo o arquivo depois da parada para não
perder o que o AdGuard gravou ao encerrar. O container só é parado quando
há diferença; o role recupera o estado anterior mesmo se a gravação falhar.
O conteúdo privado não aparece em logs nem em diffs do Ansible.

## Alternativas descartadas

- **Configurar somente pela interface:** mantém o conserto fora do código.
- **API autenticada:** seria compatível com valores declarados em arquivos,
  mas exigiria uma credencial adicional no vault e um serviço funcionando.
  Editar o YAML também cobre restore em máquina sem serviço instalado.
- **Template completo:** esta mudança não assume a gestão de usuários,
  filtros e regras. Preservar essas opções evita sobrescrever o backup.
- **Um único provedor ou bootstrap exclusivo do Quad9:** repete a falha.

## Consequências

Uma alteração DNS implica breve interrupção; reaplicar sem diferença não
reinicia o serviço. Instalação nova ainda exige o assistente para criar o
admin, seguido de reaplicação do playbook. Restore reaplica o DNS atual antes
de subir, inclusive sem compose instalado. YAML pode ser reformatado, mas
as opções não gerenciadas são preservadas semanticamente.

Os nomes públicos das variáveis são `adguard_dns_upstreams`,
`adguard_dns_bootstrap` e `adguard_dns_mode`, com o prefixo do role conforme
o padrão do repo. `upstream_dns_file` externo é recusado para evitar uma
lista declarada sem efeito. DNS dos LXCs e ACL permanecem na issue #66.
