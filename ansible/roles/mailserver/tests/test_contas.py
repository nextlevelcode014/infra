from copy import deepcopy
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

import yaml


ANSIBLE = Path(__file__).resolve().parents[3]
PRINCIPAL = "nextlevelcode.pro"
PILOTO = "piloto-mail.nextlevelcode.pro"
ADOCAO = "mail.nextlevelcode.pro"
HASH = "$6$salficticio$" + "a" * 86
CONFIG = {
    "pessoal": "caixa-pessoal", "trabalho": "work",
    "contas": dict.fromkeys(("caixa-pessoal", "work", "vaultwarden"), HASH),
    "aliases": {"hello": "caixa-pessoal", "support": "work"}, "catch_all": "work",
}


class ContasTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory(prefix="mailserver-contas-teste-")
        self.addCleanup(temporario.cleanup)
        self.pasta = Path(temporario.name)
        config = self.pasta / "ansible.cfg"
        config.write_text("[defaults]\ninterpreter_python = auto_silent\n")
        self.ambiente = {
            "PATH": os.environ.get("PATH", os.defpath),
            "ANSIBLE_CONFIG": str(config), "ANSIBLE_ROLES_PATH": str(ANSIBLE / "roles"),
            "ANSIBLE_LOCAL_TEMP": str(self.pasta / "local"),
            "ANSIBLE_REMOTE_TEMP": str(self.pasta / "remoto"),
            "ANSIBLE_INVENTORY_ENABLED": "host_list", "ANSIBLE_NOCOLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def executar(self, config, *, previa=False, erro=None, **variaveis):
        tarefas = [{"ansible.builtin.include_role": {
            "name": "mailserver", "tasks_from": "migracao-conferir-caixas" if previa else "validar",
            "public": True,
        }}]
        if not previa:
            for mapa in ("postfix-accounts.cf", "postfix-virtual.cf"):
                tarefas.append({"ansible.builtin.template": {
                    "src": str(ANSIBLE / "roles/mailserver/templates" / (mapa + ".j2")),
                    "dest": str(self.pasta / mapa), "mode": "0600",
                }})
        play = self.pasta / "teste.yml"
        play.write_text(yaml.safe_dump([{
            "hosts": "localhost", "connection": "local", "gather_facts": False,
            "vars_files": [str(ANSIBLE / "vars/mailserver.yml")],
            "vars": {
                "vault_mailserver_principal": config,
                "vault_mailserver_contas": dict.fromkeys(("ana", "bruno"), HASH),
                "vault_mailserver_contas_adocao": {"admin": HASH},
                "mailserver_dir": str(self.pasta),
            },
            "environment": {"PATH": f"{self.pasta}:{self.ambiente['PATH']}"},
            "tasks": tarefas,
        }]))
        resultado = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", str(play), "-e", json.dumps(variaveis)]
            + (["--check"] if previa else []),
            cwd=self.pasta, env=self.ambiente, text=True, capture_output=True, timeout=45,
        )
        saida = resultado.stdout + resultado.stderr
        if erro is None:
            self.assertEqual(resultado.returncode, 0, saida)
        else:
            self.assertNotEqual(resultado.returncode, 0, saida)
            self.assertIn(f"TASK [mailserver : {erro}]", saida)
            self.assertNotIn("TASK [mailserver : Conferir as duas caixas no Dovecot", saida)

    def ler_mapas(self):
        contas = dict(linha.split("|") for linha in (self.pasta / "postfix-accounts.cf").read_text().splitlines())
        aliases = dict(linha.split() for linha in (self.pasta / "postfix-virtual.cf").read_text().splitlines())
        return contas, aliases

    def test_entrega_direta_aliases_e_catch_all_por_dominio(self):
        self.executar(CONFIG)
        contas, aliases = self.ler_mapas()
        esperadas = {
            "caixa-pessoal@" + PRINCIPAL, "work@" + PRINCIPAL, "vaultwarden@" + PRINCIPAL,
            "ana@" + PILOTO, "bruno@" + PILOTO, "admin@" + ADOCAO,
        }
        self.assertEqual(contas, dict.fromkeys(esperadas, "{SHA512-CRYPT}" + HASH))

        def entregar(usuario, dominio):
            endereco = f"{usuario}@{dominio}"
            destino = aliases.get(endereco, aliases.get("@" + dominio, endereco))
            return destino if destino in contas else None

        for endereco in esperadas:
            self.assertEqual(entregar(*endereco.split("@")), endereco)
        self.assertEqual(entregar("hello", PRINCIPAL), "caixa-pessoal@" + PRINCIPAL)
        self.assertEqual(entregar("support", PRINCIPAL), "work@" + PRINCIPAL)
        self.assertEqual(entregar("sem-cadastro", PRINCIPAL), "work@" + PRINCIPAL)
        self.assertEqual(entregar("postmaster", PILOTO), "ana@" + PILOTO)
        self.assertEqual(entregar("postmaster", ADOCAO), "admin@" + ADOCAO)
        for dominio in (PILOTO, ADOCAO):
            self.assertIsNone(entregar("sem-cadastro", dominio))

    def test_piloto_sem_dominio_principal_ou_adocao(self):
        self.executar({}, mailserver_principal_ativo=False, vault_mailserver_contas_adocao={})
        contas, aliases = self.ler_mapas()
        self.assertEqual(set(contas), {"ana@" + PILOTO, "bruno@" + PILOTO})
        self.assertEqual(aliases, {"postmaster@" + PILOTO: "ana@" + PILOTO})

    def test_previa_confere_os_destinos_declarados_em_check_mode(self):
        config = deepcopy(CONFIG)
        config["trabalho"] = "equipe"
        config["contas"]["equipe"] = config["contas"].pop("work")
        config["aliases"]["support"] = "caixa-pessoal"
        config["catch_all"] = "vaultwarden"
        self.executar(config)
        _, aliases = self.ler_mapas()
        self.assertEqual(aliases["support@" + PRINCIPAL], "caixa-pessoal@" + PRINCIPAL)
        self.assertEqual(aliases["@" + PRINCIPAL], "vaultwarden@" + PRINCIPAL)

        # Simula apenas as consultas do Docker, lendo os mapas renderizados.
        docker = self.pasta / "docker"
        docker.write_text(f"#!{sys.executable}\n" + """\
from pathlib import Path
import sys

assert sys.argv[1:7] == ['compose', '-f', 'compose.yml', 'exec', '-T', 'mailserver']
with Path('consultas').open('a') as consultas:
    consultas.write(sys.argv[7] + ' ' + sys.argv[9] + '\\n')
if sys.argv[7:9] == ['doveadm', 'user']:
    contas = dict(linha.split('|') for linha in Path('postfix-accounts.cf').read_text().splitlines())
    sys.exit(0 if sys.argv[9] in contas else 1)
assert sys.argv[7:9] == ['postmap', '-q'] and sys.argv[10] == 'texthash:/etc/postfix/virtual'
aliases = dict(linha.split() for linha in Path('postfix-virtual.cf').read_text().splitlines())
print(aliases[sys.argv[9]])
""")
        docker.chmod(0o700)
        self.executar(config, previa=True)
        self.assertCountEqual((self.pasta / "consultas").read_text().splitlines(), [
            f"doveadm {conta}@{PRINCIPAL}" for conta in ("caixa-pessoal", "equipe")
        ] + [
            f"postmap {rota}@{PRINCIPAL}" for rota in ("hello", "support", "caixa-pessoal", "equipe", "")
        ])

    def test_recusa_declaracoes_invalidas(self):
        estrutura = "Validar a declaração do domínio principal quando estiver ativo"
        mapas = "Validar usuários, destinos dos aliases e hashes por domínio"
        for alteracao, erro in (
            ({"trabalho": "caixa-pessoal"}, estrutura),
            ({"trabalho": "inexistente"}, estrutura),
            ({"pessoal": "inexistente"}, estrutura),
            ({"catch_all": "inexistente"}, estrutura),
            ({"aliases": {"hello": "inexistente"}}, mapas),
            ({"aliases": {"work": "caixa-pessoal"}}, mapas),
            ({"contas": {**CONFIG["contas"], "work": "hash-invalido"}}, mapas),
        ):
            with self.subTest(alteracao=alteracao):
                self.executar({**CONFIG, **alteracao}, erro=erro)
        self.executar({**CONFIG, "catch_all": "inexistente"}, previa=True, erro=estrutura)
        self.executar({**CONFIG, "aliases": {"hello": "inexistente"}}, previa=True, erro=mapas)


if __name__ == "__main__":
    unittest.main()
