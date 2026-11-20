import contextlib
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

from ansible.errors import AnsibleFilterError
import yaml

pasta_ansible = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pasta_ansible / "roles/mailserver/filter_plugins"))
from migracao_dns import planejar_migracao, serializar_txt, texto_dns

ZONA = "nextlevelcode.pro"
MX = "mx-piloto.nextlevelcode.pro"
DKIM = "mail._domainkey.nextlevelcode.pro"
IP = "192.0.2.10"
CHAVE = "YWJj" * 98
SPF = "v=spf1 include:_spf.protonmail.ch -all"
SPF_TRANSICAO = f"v=spf1 ip4:{IP} include:_spf.protonmail.ch -all"
SPF_FINAL = f"v=spf1 ip4:{IP} -all"
MX_PROTON = [
    {"content": "mail.protonmail.ch", "priority": 10, "ttl": 1},
    {"content": "mailsec.protonmail.ch", "priority": 20, "ttl": 1},
]
MX_MAILSERVER = {"content": MX, "priority": 10, "ttl": 300}
ID_ZONA = "a" * 32
CONFIG = {
    "zona": ZONA, "dkim_nome": DKIM, "ttl": 300, "spf_proton": SPF,
    "mx_proton": MX_PROTON, "mx_mailserver": MX_MAILSERVER,
}
FILTROS = {
    "mx": {"name": ZONA, "type": "MX"}, "txt": {"name": ZONA, "type": "TXT"},
    "dkim": {"name": DKIM}, "alvo": {"name": MX, "type": "A"},
}


def estado_inicial():
    return [
        {"id": "mx1", "name": ZONA, "type": "MX", **MX_PROTON[0], "comment": "Manter"},
        {"id": "mx2", "name": ZONA, "type": "MX", **MX_PROTON[1]},
        {"id": "spf", "name": ZONA, "type": "TXT", "content": f'"{SPF}"', "ttl": 300, "comment": "Manter"},
        {"id": "verificacao", "name": ZONA, "type": "TXT", "content": "verificacao-sintetica"},
        {"id": "curinga", "name": "*._domainkey." + ZONA, "type": "TXT", "content": "v=DKIM1; p="},
        {"id": "proton", "name": "protonmail._domainkey." + ZONA, "type": "CNAME", "content": "proton.example.test"},
        {"id": "dmarc", "name": "_dmarc." + ZONA, "type": "TXT", "content": "v=DMARC1; p=reject"},
        {"id": "subdominio", "name": "mail." + ZONA, "type": "MX", **MX_MAILSERVER},
        {"id": "alvo", "name": MX, "type": "A", "content": IP, "proxied": False},
    ]


def consultar(estado, filtro):
    encontrados = [registro for registro in estado if all(registro.get(k) == v for k, v in filtro.items())]
    return {"success": True, "result": encontrados, "result_info": {"total_count": len(encontrados)}}


def resultados_dns(estado):
    return [{"item": {"key": chave, "value": filtro}, "json": consultar(estado, filtro)}
            for chave, filtro in FILTROS.items()]


def estado_apos_corte():
    estado = [item for item in estado_inicial() if item["id"] != "mx2"]
    next(item for item in estado if item["id"] == "mx1").update(MX_MAILSERVER)
    next(item for item in estado if item["id"] == "spf")["content"] = serializar_txt(SPF_TRANSICAO)
    estado.append({
        "id": "dkim", "name": DKIM, "type": "TXT", "ttl": 300,
        "content": serializar_txt(f"v=DKIM1; k=rsa; p={CHAVE}"),
    })
    return estado


@contextlib.contextmanager
def cloudflare_simulada():
    estado = estado_inicial()
    reqs = []
    lotes = []
    controle = {"ignorar_escrita": False}

    class API(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def responder(self, corpo, codigo=200):
            conteudo = json.dumps(corpo).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(conteudo)))
            self.end_headers()
            self.wfile.write(conteudo)

        def do_GET(self):
            url = urlsplit(self.path)
            parametros = {chave: valores[0] for chave, valores in parse_qs(url.query).items()}
            reqs.append(("GET", url.path, parametros))
            if self.headers.get("Authorization") != "Bearer token-ficticio":
                self.responder({"success": False}, 403)
            elif url.path == "/client/v4/zones" and parametros == {"name": ZONA, "status": "active"}:
                self.responder({"success": True, "result": [{"name": ZONA, "id": ID_ZONA}]})
            elif url.path == f"/client/v4/zones/{ID_ZONA}/dns_records" and parametros.pop("per_page", None) == "100":
                self.responder(consultar(estado, parametros))
            else:
                self.responder({"success": False}, 404)

        def do_POST(self):
            reqs.append(("POST", self.path, {}))
            if (
                self.headers.get("Authorization") != "Bearer token-ficticio"
                or self.path != f"/client/v4/zones/{ID_ZONA}/dns_records/batch"
            ):
                self.responder({"success": False}, 403)
                return
            lote = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            lotes.append(lote)
            if not controle["ignorar_escrita"]:
                for registro in lote.get("deletes", []):
                    estado.remove(next(item for item in estado if item["id"] == registro["id"]))
                for registro in lote.get("patches", []):
                    next(item for item in estado if item["id"] == registro["id"]).update(registro)
                for indice, registro in enumerate(lote.get("posts", [])):
                    estado.append({"id": f"novo-{len(lotes)}-{indice}", **registro})
            self.responder({"success": True, "result": lote})

    with ThreadingHTTPServer(("127.0.0.1", 0), API) as servidor:
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{servidor.server_port}/client/v4", estado, reqs, lotes, controle
        finally:
            servidor.shutdown()
            thread.join()


class MigracaoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mailserver-dns-teste-")
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        arquivo = self.pasta / "ansible.cfg"
        arquivo.write_text("[defaults]\ninterpreter_python = auto_silent\n")
        self.ambiente = {
            "PATH": os.environ.get("PATH", os.defpath), "ANSIBLE_CONFIG": str(arquivo),
            "ANSIBLE_INVENTORY_ENABLED": "host_list,ini",
            "ANSIBLE_ROLES_PATH": str(pasta_ansible / "roles"),
            "ANSIBLE_LOCAL_TEMP": str(self.pasta / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(self.pasta / "ansible-remote"),
            "ANSIBLE_NOCOLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.inv = self.pasta / "inventory.ini"
        self.inv.write_text("[vps]\nhetzner ansible_host=127.0.0.1 ansible_port=1 ansible_ssh_timeout=2\n")
        self.play = self.pasta / "teste.yml"
        self.play.write_text(yaml.safe_dump([{
            "name": "Ensaiar a escrita em uma Cloudflare simulada", "hosts": "vps",
            "gather_facts": False,
            "vars_files": [str(pasta_ansible / "vars" / n) for n in ("mailserver.yml", "mailserver-migracao.yml")],
            "tasks": [{"ansible.builtin.include_role": {"name": "mailserver", "tasks_from": "migracao-dns"}}],
        }]))

    def executar(self, etapa, api, *, check=False, erro=None, play=None, **variaveis):
        parametros = {
            "mailserver_migracao_etapa": etapa,
            "mailserver_migracao_api": api,
            "mailserver_migracao_http_local": True,
            "mailserver_migracao_token": "token-ficticio",
            "mailserver_migracao_ipv4": IP,
            "mailserver_migracao_dkim_publica": CHAVE,
            **variaveis,
        }
        resultado = subprocess.run(
            ["ansible-playbook", "-i", str(self.inv), str(play or self.play), "-e", json.dumps(parametros)]
            + (["--check"] if check else []),
            env=self.ambiente, text=True, capture_output=True, timeout=45,
        )
        saida = resultado.stdout + resultado.stderr
        if erro is None:
            self.assertEqual(resultado.returncode, 0, saida)
        else:
            self.assertNotEqual(resultado.returncode, 0, saida)
            self.assertIn(erro, saida)

    def test_prepara_corta_e_restaura_somente_o_escopo_de_cada_etapa(self):
        with cloudflare_simulada() as (api, estado, reqs, lotes, _):
            original = deepcopy(estado)
            self.executar("autenticacao", api, check=True)
            self.assertEqual(estado, original)
            self.assertEqual(lotes, [])
            self.executar("cortar-mx", api, erro="Conclua a etapa de autenticação")

            self.executar("autenticacao", api)
            self.assertEqual(lotes[0]["patches"], [{"id": "spf", "content": f'"{SPF_TRANSICAO}"'}])
            chave = lotes[0]["posts"][0]
            self.assertEqual(chave["name"], DKIM)
            self.assertEqual(texto_dns(chave["content"]), f"v=DKIM1; k=rsa; p={CHAVE}")
            self.assertLessEqual(max(len(trecho) for trecho in chave["content"].split('" "')), 257)
            self.assertEqual(set(lotes[0]), {"posts", "patches"})
            self.assertEqual(next(item for item in estado if item["id"] == "spf")["comment"], "Manter")
            self.executar("autenticacao", api)
            self.assertEqual(len(lotes), 1)

            self.executar("cortar-mx", api, check=True)
            self.assertEqual(len(lotes), 1)
            self.executar("cortar-mx", api)
            self.assertEqual(lotes[1], {"deletes": [{"id": "mx2"}], "patches": [{"id": "mx1", **MX_MAILSERVER}]})
            self.executar("cortar-mx", api)
            self.assertEqual(len(lotes), 2)

            reqs.clear()
            self.executar("voltar-mx", api, play=pasta_ansible / "playbooks/mailserver-migracao.yml")
            self.assertEqual(lotes[2], {
                "patches": [{"id": "mx1", **MX_PROTON[0]}],
                "posts": [{"name": ZONA, "type": "MX", **MX_PROTON[1]}],
            })
            self.assertEqual({(q["name"], q["type"]) for metodo, url, q in reqs
                              if metodo == "GET" and url.endswith("/dns_records")},
                             {(ZONA, "MX"), (ZONA, "TXT"), (MX, "A")})
            self.executar("voltar-mx", api)
            self.assertEqual(len(lotes), 3)
            for registro in original:
                if registro["id"] not in {"spf", "mx2"}:
                    self.assertIn(registro, estado)

    def test_finaliza_somente_o_spf_e_restaura_a_autorizacao_na_volta(self):
        with cloudflare_simulada() as (api, estado, _, lotes, _):
            estado[:] = estado_apos_corte()
            transicao = deepcopy(estado)
            self.executar("finalizar-spf", api, check=True)
            self.assertEqual(estado, transicao)
            self.assertEqual(lotes, [])

            self.executar("finalizar-spf", api)
            patch_final = {"id": "spf", "content": serializar_txt(SPF_FINAL)}
            self.assertEqual(lotes, [{"patches": [patch_final]}])
            esperado = deepcopy(transicao)
            next(registro for registro in esperado if registro["id"] == "spf").update(patch_final)
            self.assertEqual(estado, esperado)
            self.executar("finalizar-spf", api)
            self.assertEqual(len(lotes), 1)
            for etapa in ("autenticacao", "cortar-mx"):
                self.assertEqual(planejar_migracao(resultados_dns(estado), etapa, CONFIG, IP, CHAVE), {})

            self.executar("voltar-mx", api, play=pasta_ansible / "playbooks/mailserver-migracao.yml")
            self.assertEqual(lotes[1], {
                "patches": [{"id": "mx1", **MX_PROTON[0]}, {"id": "spf", "content": serializar_txt(SPF_TRANSICAO)}],
                "posts": [{"name": ZONA, "type": "MX", **MX_PROTON[1]}],
            })
            self.assertEqual(planejar_migracao(resultados_dns(estado), "voltar-mx", CONFIG), {})

    def test_finalizacao_exige_mx_na_vps_spf_de_transicao_e_dkim(self):
        with self.assertRaisesRegex(AnsibleFilterError, "MX já aponte apenas para o Mailserver"):
            planejar_migracao(resultados_dns(estado_inicial()), "finalizar-spf", CONFIG, IP, CHAVE)
        for registros in (
            [item for item in estado_apos_corte() if item["id"] != "dkim"],
            [{**item, "content": serializar_txt(SPF)} if item["id"] == "spf" else item
             for item in estado_apos_corte()],
        ):
            with self.assertRaisesRegex(AnsibleFilterError, "Conclua a transição do SPF e publique o DKIM"):
                planejar_migracao(resultados_dns(registros), "finalizar-spf", CONFIG, IP, CHAVE)

    def test_falha_se_a_resposta_de_sucesso_nao_produz_o_estado_esperado(self):
        with cloudflare_simulada() as (api, estado, _, lotes, controle):
            controle["ignorar_escrita"] = True
            self.executar("autenticacao", api, erro="após a escrita divergiu")
            self.assertEqual(len(lotes), 1)
            self.assertEqual(estado, estado_inicial())

    def test_playbook_bloqueia_o_corte_com_o_dominio_desligado(self):
        with cloudflare_simulada() as (api, _, reqs, _, _):
            self.executar("cortar-mx", api, play=pasta_ansible / "playbooks/mailserver-migracao.yml",
                          erro="Ative o domínio principal pelo fluxo versionado", mailserver_principal_ativo=False)
            self.assertEqual(reqs, [])

    def test_estados_inesperados_sao_recusados_antes_do_lote(self):
        for conflitante, registro in (
            ("conjunto MX atual", {"id": "extra", "name": ZONA, "type": "MX", **MX_MAILSERVER}),
            ("exatamente um SPF", {"id": "extra", "name": ZONA, "type": "TXT", "content": "v=spf1 ?all"}),
            ("registro explícito diferente", {"id": "extra", "name": DKIM, "type": "CNAME", "content": "alheio.test"}),
        ):
            with self.subTest(conflitante):
                dados = estado_inicial() + [registro]
                with self.assertRaisesRegex(AnsibleFilterError, conflitante):
                    planejar_migracao(resultados_dns(dados), "autenticacao", CONFIG, IP, CHAVE)
        self.assertEqual(texto_dns(serializar_txt(f"v=DKIM1; k=rsa; p={CHAVE}")), f"v=DKIM1; k=rsa; p={CHAVE}")


if __name__ == "__main__":
    unittest.main()
