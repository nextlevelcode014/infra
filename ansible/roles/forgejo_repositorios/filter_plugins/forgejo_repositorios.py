"""Planejamento puro; sem rede, arquivos ou credenciais."""
import re

from ansible.errors import AnsibleFilterError


BOOLEANOS = {
    'apply_to_admins', 'block_on_official_review_requests',
    'block_on_outdated_branch', 'block_on_rejected_reviews',
    'dismiss_stale_approvals', 'enable_approvals_whitelist',
    'enable_merge_whitelist', 'enable_push', 'enable_push_whitelist',
    'enable_status_check', 'ignore_stale_approvals', 'push_whitelist_deploy_keys',
    'require_signed_commits',
}
LISTAS = {
    'approvals_whitelist_teams', 'approvals_whitelist_username',
    'merge_whitelist_teams', 'merge_whitelist_usernames',
    'push_whitelist_teams', 'push_whitelist_usernames', 'status_check_contexts',
}
TEXTOS = {'rule_name', 'protected_file_patterns', 'unprotected_file_patterns'}
CAMPOS = BOOLEANOS | LISTAS | TEXTOS | {'required_approvals'}
MODOS_MERGE = {
    'merge': 'allow_merge_commits',
    'rebase': 'allow_rebase',
    'rebase-merge': 'allow_rebase_explicit',
    'squash': 'allow_squash_merge',
    'fast-forward-only': 'allow_fast_forward_only_merge',
}
CONFIGURACOES = {'default_merge_style', 'default_delete_branch_after_merge'}
NOME = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')


def exigir(condicao, mensagem):
    if not condicao:
        raise AnsibleFilterError(mensagem)


def normalizar(regra):
    resultado = dict(regra)
    for campo in LISTAS & regra.keys():
        resultado[campo] = sorted(set(regra[campo] or []))
    return resultado


def validar(repositorios):
    exigir(isinstance(repositorios, list) and repositorios, 'Declare os repositórios explicitamente.')
    nomes = []
    for repo in repositorios:
        exigir(isinstance(repo, dict), 'Repositório deve ser um mapa.')
        obrigatorios = {'owner', 'name', 'collaborators', 'rules'}
        exigir(obrigatorios <= repo.keys() <= obrigatorios | {'settings'}, 'Campos inesperados no repositório.')
        configuracao = repo.get('settings', {})
        exigir(isinstance(configuracao, dict) and configuracao.keys() <= CONFIGURACOES,
               'Configuração de merge inválida ou com campo não suportado.')
        if 'default_merge_style' in configuracao:
            modo = configuracao['default_merge_style']
            exigir(isinstance(modo, str) and modo in MODOS_MERGE, 'Método de merge padrão não suportado.')
        if 'default_delete_branch_after_merge' in configuracao:
            exigir(type(configuracao['default_delete_branch_after_merge']) is bool,
                   'default_delete_branch_after_merge deve ser booleano YAML.')
        for campo in ('owner', 'name'):
            exigir(isinstance(repo[campo], str) and NOME.fullmatch(repo[campo]), f'{campo} inválido.')
        nomes.append(f"{repo['owner']}/{repo['name']}")
        exigir(isinstance(repo['collaborators'], dict), 'collaborators deve ser um mapa.')
        for usuario, permissao in repo['collaborators'].items():
            exigir(isinstance(usuario, str) and NOME.fullmatch(usuario), 'Colaborador inválido.')
            exigir(usuario.lower() != repo['owner'].lower(), 'Não gerenciar o proprietário como colaborador.')
            exigir(permissao in ('read', 'write'), 'Colaboradores gerenciados aceitam somente read ou write.')
        exigir(isinstance(repo['rules'], list) and (repo['rules'] or configuracao),
               'Declare pelo menos uma regra ou uma preferência de merge.')
        regras = []
        for regra in repo['rules']:
            exigir(isinstance(regra, dict) and 'rule_name' in regra, 'Regra sem rule_name.')
            exigir(not (regra.keys() - CAMPOS), 'Campo de proteção não suportado; confira a API antes de ampliar.')
            exigir(isinstance(regra['rule_name'], str) and NOME.fullmatch(regra['rule_name']),
                   'Esta entrada gerencia somente nomes literais de branches, sem glob ou barras.')
            regras.append(regra['rule_name'].lower())
            for campo, valor in regra.items():
                if campo in BOOLEANOS:
                    exigir(type(valor) is bool, f'{campo} deve ser booleano YAML.')
                elif campo in LISTAS:
                    exigir(isinstance(valor, list) and all(isinstance(v, str) for v in valor),
                           f'{campo} deve ser uma lista de textos.')
                elif campo in TEXTOS:
                    exigir(isinstance(valor, str), f'{campo} deve ser texto.')
                else:
                    exigir(isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0,
                           'required_approvals deve ser inteiro não negativo.')
        exigir(len(regras) == len(set(regras)), 'Regras duplicadas.')
    exigir(len(nomes) == len(set(n.lower() for n in nomes)), 'Repositórios duplicados.')
    return repositorios


def selecionar(repositorios, alvos):
    validar(repositorios)
    exigir(isinstance(alvos, list) and all(isinstance(a, str) for a in alvos),
           'alvos deve ser uma lista de identificadores owner/repo.')
    exigir(len(alvos) == len(set(alvos)), 'Alvos duplicados.')
    declarados = {f"{r['owner']}/{r['name']}" for r in repositorios}
    exigir(not (set(alvos) - declarados), 'Alvo não declarado; confira owner/repo antes de aplicar.')
    return [r for r in repositorios if not alvos or f"{r['owner']}/{r['name']}" in alvos]


def planejar(repo, regras, membros, permissoes, configuracao_atual=None):
    """Considera só os itens declarados e preserva os demais campos/regras."""
    validar([repo])
    exigir(isinstance(regras, list), 'Resposta de proteções não é uma lista.')
    por_nome = {}
    for regra in regras:
        exigir(isinstance(regra, dict) and isinstance(regra.get('rule_name'), str), 'Resposta de regra inválida.')
        chave = regra['rule_name'].lower()
        exigir(chave not in por_nome, 'API retornou regras com nomes duplicados.')
        por_nome[chave] = regra
    desejada = repo.get('settings', {})
    anterior = {}
    if desejada:
        exigir(isinstance(configuracao_atual, dict) and desejada.keys() <= configuracao_atual.keys(),
               'API omitiu uma configuração de merge gerenciada.')
        anterior = {k: configuracao_atual[k] for k in desejada}
        exigir(all(isinstance(anterior[k], bool if isinstance(v, bool) else str) for k, v in desejada.items()),
               'Tipo inesperado na configuração de merge retornada pela API.')
        if 'default_merge_style' in desejada:
            permissao = MODOS_MERGE[desejada['default_merge_style']]
            exigir(configuracao_atual.get(permissao) is True,
                   'O método de merge desejado precisa estar habilitado no repositório.')
    patch = {k: v for k, v in desejada.items() if anterior[k] != v}
    plano = {'rules': [], 'collaborators': [],
             'settings': {'before': anterior, 'patch': patch}, 'changed': False}
    for desejada in repo['rules']:
        atual = por_nome.get(desejada['rule_name'].lower())
        depois = normalizar(desejada)
        if atual is not None:
            exigir(not (desejada.keys() - atual.keys()), 'API omitiu um campo gerenciado da proteção.')
            antes = normalizar({k: atual[k] for k in desejada})
            # Nomes literais são case-insensitive no Forgejo; não renomear via PATCH.
            depois['rule_name'] = atual['rule_name']
        else:
            antes = None
        campos = [k for k in depois if antes is None or antes[k] != depois[k]]
        plano['rules'].append({
            'name': depois['rule_name'], 'before': atual, 'after': depois,
            'fields': campos, 'changed': bool(campos),
        })
    membros = {r['item']['key']: r for r in membros}
    permissoes = {r['item']['key']: r for r in permissoes}
    for usuario, desejada in repo['collaborators'].items():
        membro = membros[usuario]['status']
        exigir(membro in (204, 404), 'Resposta inesperada na consulta de colaborador.')
        permissao = permissoes[usuario]
        exigir(permissao['status'] == 200, 'Não foi possível consultar a permissão do usuário existente.')
        atual = permissao['json']['permission']
        exigir(atual in ('none', 'read', 'write', 'admin', 'owner'), 'Permissão inesperada da API.')
        plano['collaborators'].append({
            'name': usuario, 'before': {'member': membro == 204, 'permission': atual},
            'after': desejada, 'changed': membro != 204 or atual != desejada,
        })
    plano['changed'] = bool(patch) or any(x['changed'] for x in plano['rules'] + plano['collaborators'])
    return plano


class FilterModule:
    def filters(self):
        return {
            'forgejo_repositorios_validar': validar,
            'forgejo_repositorios_selecionar': selecionar,
            'forgejo_repositorios_planejar': planejar,
        }
