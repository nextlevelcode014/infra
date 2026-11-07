"""Exercita o playbook real contra uma API fictícia só em loopback."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest

import yaml
from ansible.errors import AnsibleFilterError


ANSIBLE = Path(__file__).resolve().parents[3]
ROLE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('planejamento', ROLE / 'filter_plugins/forgejo_repositorios.py')
planejamento = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planejamento)
REPOSITORIOS = yaml.safe_load((ANSIBLE / 'vars/forgejo-repositorios.yml').read_text())['forgejo_repositorios']
DESEJADO = next(r for r in REPOSITORIOS if r['name'] == 'infra')
LAB = next(r for r in REPOSITORIOS if r['name'] == 'lab')
PREFIXO = '/api/v1/repos/nextlevelcode/infra'
TOKEN = 'token-ficticio-somente-testes'


class PlanejamentoTest(unittest.TestCase):
    def test_selecao_explicita_recusa_alvo_inexistente_ou_ambiguo(self):
        self.assertEqual(planejamento.selecionar(REPOSITORIOS, ['nextlevelcode/lab']), [LAB])
        self.assertEqual(planejamento.selecionar(REPOSITORIOS, []), REPOSITORIOS)
        for alvos in ['lab', ['nextlevelcode/inexistente'], ['nextlevelcode/lab'] * 2, [None]]:
            with self.subTest(alvos=alvos), self.assertRaises(AnsibleFilterError):
                planejamento.selecionar(REPOSITORIOS, alvos)

    def test_recusa_configuracao_ambigua_ou_incorreta(self):
        for campo, valor in [('enable_push', 'false'), ('required_approvals', True),
                             ('rule_name', '../main'), ('campo_futuro', True)]:
            with self.subTest(campo=campo):
                repo = copy.deepcopy(DESEJADO)
                repo['rules'][0][campo] = valor
                with self.assertRaises(AnsibleFilterError):
                    planejamento.validar([repo])
        with self.assertRaises(AnsibleFilterError):
            planejamento.validar([DESEJADO, DESEJADO])

    def test_normaliza_null_ordem_e_duplicatas_das_listas(self):
        repo = copy.deepcopy(DESEJADO)
        repo['rules'][0]['status_check_contexts'] = ['b', 'a', 'a']
        atual = copy.deepcopy(repo['rules'][0])
        atual['status_check_contexts'] = ['a', 'b']
        atual['push_whitelist_usernames'] = None
        membros = [{'item': {'key': 'agent'}, 'status': 204}]
        permissoes = [{'item': {'key': 'agent'}, 'status': 200, 'json': {'permission': 'write'}}]
        self.assertFalse(planejamento.planejar(repo, [atual], membros, permissoes)['changed'])
        del atual['enable_push']
        with self.assertRaises(AnsibleFilterError):
            planejamento.planejar(repo, [atual], membros, permissoes)


class ApiFicticia(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def responder(self, status, dados=None):
        corpo = json.dumps(dados).encode() if dados is not None else b''
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def atender(self):
        api = self.server
        api.chamadas.append((self.command, self.path))
        if self.headers.get('Authorization') != f'token {TOKEN}':
            return self.responder(401, {'message': TOKEN})
        partes = self.path.split('/')
        if partes[:5] != ['', 'api', 'v1', 'repos', 'nextlevelcode'] or len(partes) < 6:
            return self.responder(404)
        nome = partes[5]
        estado = api.repositorios.get(nome)
        if estado is None:
            return self.responder(404)
        rota = '/' + '/'.join(partes[6:]) if len(partes) > 6 else ''
        if self.command == 'GET':
            if rota == '':
                return self.responder(200, {'permissions': {'admin': estado.admin}})
            if rota == '/branch_protections':
                return self.responder(200, list(estado.regras.values()))
            if rota.startswith('/collaborators/'):
                usuario = rota.split('/')[2]
                if rota.endswith('/permission'):
                    return self.responder(200, {'permission': estado.membros.get(usuario, 'read')})
                return self.responder(204 if usuario in estado.membros else 404)
            return self.responder(404)
        corpo = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        api.snapshots_antes_de_escrever.append(bool(list(api.backup.glob(f'*/nextlevelcode_{nome}.json'))))
        if estado.negar:
            return self.responder(403, {'message': f'Erro fictício com segredo: {TOKEN}'})
        if self.command == 'POST' and rota == '/branch_protections':
            if not estado.ignorar:
                estado.regras[corpo['rule_name']] = corpo
            return self.responder(201, corpo)
        if self.command == 'PATCH' and rota.startswith('/branch_protections/'):
            nome = rota.split('/')[2]
            estado.regras[nome].update(corpo)
            return self.responder(200, estado.regras[nome])
        if self.command == 'PUT' and rota.startswith('/collaborators/'):
            if not estado.ignorar_colaborador:
                estado.membros[rota.split('/')[2]] = corpo['permission']
            return self.responder(204)
        return self.responder(404)

    do_GET = atender
    do_POST = atender
    do_PATCH = atender
    do_PUT = atender


class PlaybookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='forgejo-repositorios-test-')
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.api = ThreadingHTTPServer(('127.0.0.1', 0), ApiFicticia)
        def novo_estado():
            return SimpleNamespace(regras={}, membros={'outro': 'read'}, admin=True,
                                   negar=False, ignorar=False, ignorar_colaborador=False)
        self.infra = novo_estado()
        self.lab = novo_estado()
        self.api.repositorios = {'infra': self.infra, 'lab': self.lab}
        self.api.chamadas = []
        self.api.backup = self.raiz / 'backup'
        self.api.snapshots_antes_de_escrever = []
        self.thread = threading.Thread(target=self.api.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.fechar)

    def fechar(self):
        self.api.shutdown()
        self.api.server_close()
        self.thread.join()

    def executar(self, check=False, aplicar=True, extras=None, sucesso=True):
        variaveis = {
            'forgejo_repositorios_api_url': f'http://127.0.0.1:{self.api.server_port}/api/v1',
            'forgejo_repositorios_http_local': True,
            'forgejo_repositorios_vault_file': str(ROLE / 'tests/vault.yml'),
            'forgejo_repositorios_backup_dir': str(self.raiz / 'backup'),
            'forgejo_repositorios_aplicar': aplicar,
            'forgejo_repositorios_alvos': ['nextlevelcode/infra'],
            **(extras or {}),
        }
        arquivo = self.raiz / 'variaveis.json'
        arquivo.write_text(json.dumps(variaveis))
        config = self.raiz / 'ansible.cfg'
        config.write_text('[defaults]\n')
        ambiente = {
            **{k: v for k, v in os.environ.items() if not k.startswith('ANSIBLE_')},
            'ANSIBLE_CONFIG': str(config),
            'ANSIBLE_ROLES_PATH': str(ANSIBLE / 'roles'),
            'ANSIBLE_LOCAL_TEMP': str(self.raiz / 'local'),
            'ANSIBLE_REMOTE_TEMP': str(self.raiz / 'remote'),
            'ANSIBLE_NOCOLOR': '1', 'ANSIBLE_STDOUT_CALLBACK': 'default',
            'ANSIBLE_INVENTORY_ENABLED': 'host_list',
        }
        comando = ['ansible-playbook', '-i', 'localhost,', 'playbooks/forgejo-repositorios.yml',
                   '-e', f'@{arquivo}'] + (['--check', '--diff'] if check else [])
        resultado = subprocess.run(comando, cwd=ANSIBLE, env=ambiente, text=True,
                                   capture_output=True, timeout=120)
        saida = resultado.stdout + resultado.stderr
        self.assertNotIn(TOKEN, saida, 'Credencial fictícia apareceu no log.')
        if sucesso:
            self.assertEqual(resultado.returncode, 0, saida)
        else:
            self.assertNotEqual(resultado.returncode, 0, saida)
        return saida

    def escritas(self):
        return [m for m, _ in self.api.chamadas if m != 'GET']

    def test_criacao_check_idempotencia_e_backup(self):
        self.executar(check=True)
        self.assertFalse(self.escritas())
        self.assertFalse((self.raiz / 'backup').exists())
        self.executar()
        self.assertEqual(self.escritas(), ['POST', 'PUT'])
        self.assertEqual(self.infra.regras['main'], DESEJADO['rules'][0])
        self.assertEqual(self.infra.membros, {'outro': 'read', 'agent': 'write'})
        backups = list((self.raiz / 'backup').glob('*/*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(backups[0].parent.stat().st_mode & 0o777, 0o700)
        antes = json.loads(backups[0].read_text())['plan']
        self.assertIsNone(antes['rules'][0]['before'])
        self.assertFalse(antes['collaborators'][0]['before']['member'])
        self.assertNotIn(TOKEN, backups[0].read_text())
        self.assertTrue(all(self.api.snapshots_antes_de_escrever))
        self.api.chamadas.clear()
        self.assertIn('changed=0', self.executar())
        self.assertIn('changed=0', self.executar(check=True))
        self.assertFalse(self.escritas())
        self.assertEqual(len(list((self.raiz / 'backup').glob('*/*.json'))), 1)

    def test_corrige_drift_e_preserva_o_que_nao_gerencia(self):
        atual = copy.deepcopy(DESEJADO['rules'][0])
        atual.update(enable_push=True, campo_futuro='preservar')
        self.infra.regras = {'main': atual, 'outra': {'rule_name': 'outra', 'enable_push': True}}
        self.infra.membros['agent'] = 'admin'
        self.executar(check=True)
        self.assertFalse(self.escritas())
        self.assertTrue(self.infra.regras['main']['enable_push'])
        self.executar()
        self.assertEqual(self.escritas(), ['PATCH', 'PUT'])
        self.assertFalse(self.infra.regras['main']['enable_push'])
        self.assertEqual(self.infra.regras['main']['campo_futuro'], 'preservar')
        self.assertTrue(self.infra.regras['outra']['enable_push'])
        self.assertEqual(self.infra.membros['agent'], 'write')

    def test_falha_http_interrompe_antes_de_conceder_acesso(self):
        self.infra.negar = True
        self.executar(sucesso=False)
        self.assertEqual(self.escritas(), ['POST'])
        self.assertNotIn('agent', self.infra.membros)
        self.assertEqual(len(list((self.raiz / 'backup').glob('*/*.json'))), 1)

    def test_detecta_sucesso_http_sem_aplicacao_da_regra(self):
        self.infra.ignorar = True
        self.executar(sucesso=False)
        self.assertEqual(self.escritas(), ['POST'])
        self.assertNotIn('agent', self.infra.membros)

    def test_recusa_credencial_sem_acesso_administrativo(self):
        self.infra.admin = False
        self.executar(check=True, sucesso=False)
        self.assertEqual(self.api.chamadas, [('GET', PREFIXO)])

    def test_detecta_sucesso_http_sem_aplicacao_da_permissao(self):
        self.infra.regras['main'] = copy.deepcopy(DESEJADO['rules'][0])
        self.infra.membros['agent'] = 'read'
        self.infra.ignorar_colaborador = True
        self.executar(sucesso=False)
        self.assertEqual(self.escritas(), ['PUT'])
        self.assertEqual(self.infra.membros['agent'], 'read')

    def test_aplicacao_sem_confirmacao_e_configuracao_invalida_nao_acessam_api(self):
        self.executar(aplicar=False, sucesso=False)
        self.executar(extras={'forgejo_repositorios_token': 'CHANGE-ME'}, sucesso=False)
        self.executar(extras={'forgejo_repositorios_api_url': 'http://example.invalid/api/v1'}, sucesso=False)
        self.executar(extras={'forgejo_repositorios_alvos': ['nextlevelcode/inexistente']}, sucesso=False)
        self.assertFalse(self.api.chamadas)

    def test_seleciona_lab_sem_consultar_ou_corrigir_infra_com_drift(self):
        self.infra.regras['main'] = {'rule_name': 'main', 'enable_push': True}
        self.infra.membros['agent'] = 'admin'
        antes = copy.deepcopy(vars(self.infra))
        extras = {'forgejo_repositorios_alvos': ['nextlevelcode/lab']}
        self.executar(check=True, extras=extras)
        self.assertFalse(self.escritas())
        self.executar(extras=extras)
        self.assertEqual(self.lab.regras['main'], LAB['rules'][0])
        self.assertEqual(self.lab.membros['agent'], 'write')
        self.assertEqual(vars(self.infra), antes)
        self.assertTrue(all(path.startswith('/api/v1/repos/nextlevelcode/lab')
                            for _, path in self.api.chamadas))
        arquivos = list((self.raiz / 'backup').glob('*/*.json'))
        self.assertEqual([p.name for p in arquivos], ['nextlevelcode_lab.json'])
        self.api.chamadas.clear()
        self.assertIn('changed=0', self.executar(extras=extras))
        self.assertFalse(self.escritas())

    def test_aplica_dois_repositorios_com_estados_e_snapshots_independentes(self):
        extras = {'forgejo_repositorios_alvos': []}
        self.executar(extras=extras)
        self.assertEqual(self.escritas(), ['POST', 'PUT', 'POST', 'PUT'])
        self.assertEqual(self.infra.regras['main'], DESEJADO['rules'][0])
        self.assertEqual(self.lab.regras['main'], LAB['rules'][0])
        arquivos = list((self.raiz / 'backup').glob('*/*.json'))
        self.assertEqual({p.name for p in arquivos}, {'nextlevelcode_infra.json', 'nextlevelcode_lab.json'})
        self.assertTrue(all(self.api.snapshots_antes_de_escrever))
        self.api.chamadas.clear()
        self.assertIn('changed=0', self.executar(extras=extras))
        self.assertFalse(self.escritas())


if __name__ == '__main__':
    unittest.main()
