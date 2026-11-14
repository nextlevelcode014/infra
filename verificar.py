#!/usr/bin/env python3
"""Executa verificações locais sobre o conteúdo de um commit."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parent
TAILNET = re.compile(r"(?<![\w-])[a-zA-Z0-9-]+\.ts\.net\b", re.IGNORECASE)
IP_TAILSCALE = re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+\b")
IPS_GENERICOS = {"100.100.100.100", "100.127.255.255"}

FIXTURES_DNS = {"b/ansible/roles/lxc_dns/tests/integracao.py"}
ROOTS = {Path("terraform"), Path("terraform/hetzner")}
MODULO_LXC = Path("terraform/modules/lxc")
CHAVE_PUBLICA_FICTICIA = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE2KoaFI8P7vBpDODBgikCziATYb8eyH1rXXicOIQWnY verificacao-local"
)


def git(*args):
    return subprocess.check_output(["git", "-C", REPO, *args])


def conferir_privacidade(base, head):
    arquivo = ""
    suspeitos = set()
    patch = git(
        "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-color",
        "--src-prefix=a/", "--dst-prefix=b/", "-U0", base, head, "--",
    )
    em_bloco = False
    for linha in patch.decode(errors="replace").splitlines():
        if linha.startswith("diff --git "):
            em_bloco = False
        elif linha.startswith("+++ ") and not em_bloco:
            arquivo = linha[4:].removesuffix("\t")
        elif linha.startswith("@@ "):
            em_bloco = True
        elif em_bloco and linha.startswith("+"):
            texto = linha[1:].replace("100.64.0.0/10", "")
            dominios = set(TAILNET.findall(texto.lower()))
            if arquivo in FIXTURES_DNS:
                dominios.discard("test-tailnet" + ".ts.net")
            if dominios or set(IP_TAILSCALE.findall(texto)) - IPS_GENERICOS:
                suspeitos.add(arquivo)
    if suspeitos:
        raise ValueError("Possível valor privado em " + ", ".join(sorted(suspeitos)))


def executar(comando, pasta, ambiente):
    print(f"[{pasta}] {shlex.join(map(str, comando))}", flush=True)
    subprocess.run(comando, cwd=pasta, env=ambiente, check=True)


def terraform(copia, roots, formatar, ambiente, espelho):
    if not roots and not formatar:
        return

    config = Path(ambiente["HOME"]) / "terraform.rc"
    if espelho:
        config.write_text(
            "provider_installation {\n"
            f"  filesystem_mirror {{ path = {json.dumps(str(espelho))} }}\n"
            "}\n"
        )
    else:
        config.touch()
    ambiente = {**ambiente, "TF_CLI_CONFIG_FILE": str(config), "TF_IN_AUTOMATION": "1"}
    executar(["terraform", "version"], copia, ambiente)
    for pasta in sorted(formatar):
        executar(["terraform", "fmt", "-check", "-diff", "-no-color"], copia / pasta, ambiente)
    for pasta in sorted(roots):
        executar(
            ["terraform", "init", "-backend=false", "-input=false", "-lockfile=readonly", "-no-color"],
            copia / pasta, ambiente,
        )
        executar(["terraform", "validate", "-no-color"], copia / pasta, ambiente)


def ambiente_ansible(ambiente, temporario, pasta, colecoes):
    config = temporario / "ansible.cfg"
    config.write_text("[defaults]\n")
    return {
        **ambiente,
        "ANSIBLE_CONFIG": str(config),
        "ANSIBLE_ROLES_PATH": str(pasta / "roles"),
        "ANSIBLE_COLLECTIONS_PATH": str(colecoes),
        "ANSIBLE_LOCAL_TEMP": str(temporario / "ansible-local"),
        "ANSIBLE_REMOTE_TEMP": str(temporario / "ansible-remote"),
        "ANSIBLE_INVENTORY_ENABLED": "host_list",
        "ANSIBLE_NOCOLOR": "1",
    }


def sintaxe(pasta, playbooks, ambiente):
    executar(["ansible-playbook", "--version"], pasta, ambiente)
    comando = ["ansible-playbook", "-i", "localhost,", "--syntax-check"]
    for playbook in sorted(playbooks):
        executar([*comando, playbook], pasta, ambiente)


def verificar(copia, caminhos, args, temporario, ambiente):
    roots = set()
    conferir_ansible = False
    if args.perfil == "completo" or Path("verificar.py") in caminhos:
        roots.update(ROOTS)
        conferir_ansible = True

    for caminho in caminhos:
        if caminho.suffix == ".md" or caminho.name == ".gitignore" or caminho == Path("verificar.py"):
            continue
        if caminho.is_relative_to("terraform/hetzner"):
            roots.add(Path("terraform/hetzner"))
        elif caminho.parent == Path("terraform") or caminho.is_relative_to(MODULO_LXC):
            roots.add(Path("terraform"))
        elif caminho.is_relative_to("ansible/tailscale"):
            print(f"Revisão manual da política Tailscale: {caminho}")
        elif caminho.is_relative_to("ansible"):
            conferir_ansible = True
        else:
            raise ValueError(f"Caminho sem regra de seleção: {caminho}")

    print("Terraform:", ", ".join(map(str, sorted(roots))) or "sem roots selecionados", flush=True)
    print("Ansible:", "sintaxe e regressões locais" if conferir_ansible else "sem alteração", flush=True)
    if conferir_ansible:
        pasta = copia / "ansible"
        env = ambiente_ansible(ambiente, temporario, pasta, args.colecoes.resolve())
        playbooks = [Path("site.yml")]
        playbooks.extend(
            p.relative_to(pasta) for p in (pasta / "playbooks").iterdir()
            if p.is_file() and p.suffix in {".yml", ".yaml"}
        )
        sintaxe(pasta, playbooks, env)
        executar(["systemctl", "--version"], pasta, env)
        executar([sys.executable, "roles/lxc_dns/tests/test_estado.py", "-v"], pasta, env)
        executar([sys.executable, "roles/forgejo_repositorios/tests/test_api.py", "-v"], pasta, env)
        executar(
            ["ansible-playbook", "-i", "localhost,", "-c", "local", "roles/adguard_dns/tests/test.yml"],
            pasta, env,
        )

    formatos = set(roots)
    if Path("terraform") in roots:
        # local.tf lê uma chave pública durante o carregamento do root.
        ssh = Path(ambiente["HOME"]) / ".ssh"
        ssh.mkdir(mode=0o700)
        chave = CHAVE_PUBLICA_FICTICIA + "\n"
        (ssh / "id_ed25519.pub").write_text(chave)
        formatos.add(MODULO_LXC)
    terraform(copia, roots, formatos, ambiente, args.espelho_providers and args.espelho_providers.resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("perfil", choices=["pr", "completo"])
    parser.add_argument("base", help="Revisão de destino do PR")
    parser.add_argument("head", help="Revisão proposta, igual ao HEAD do checkout")
    parser.add_argument("--espelho-providers", type=Path, help="Espelho local exclusivo do Terraform")
    parser.add_argument(
        "--colecoes", type=Path, default=Path.home() / ".ansible/collections",
        help="Diretório pai de ansible_collections para coleções adicionais",
    )
    args = parser.parse_args()

    try:
        head = git("rev-parse", "--verify", "--end-of-options", f"{args.head}^{{commit}}").decode().strip()
        base = git("rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}").decode().strip()
        if head != git("rev-parse", "HEAD").decode().strip():
            raise ValueError("A revisão proposta deve estar no HEAD do checkout.")
        if Path(__file__).read_bytes() != git("show", f"{head}:verificar.py"):
            raise ValueError("verificar.py precisa corresponder à versão do HEAD.")
        comum = git("merge-base", base, head).decode().strip()
        print(f"Perfil {args.perfil} | base {base} | head {head} | ancestral comum {comum}", flush=True)
        conferir_privacidade(comum, head)
        alterados = git("diff", "--name-only", "--no-renames", "-z", comum, head, "--")
        caminhos = [Path(os.fsdecode(nome)) for nome in alterados.split(b"\0") if nome]
        if args.espelho_providers and not args.espelho_providers.is_dir():
            raise ValueError("O diretório do espelho de providers não existe.")

        with tempfile.TemporaryDirectory(prefix="verificar-") as diretorio:
            temporario = Path(diretorio)
            copia = temporario / "checkout"
            copia.mkdir()
            print("Verificando cópia exclusiva dos arquivos versionados no head.", flush=True)
            with subprocess.Popen(["git", "-C", REPO, "archive", head], stdout=subprocess.PIPE) as arquivo:
                with tarfile.open(fileobj=arquivo.stdout, mode="r|") as tar:
                    tar.extractall(copia, filter="data")
                if arquivo.wait():
                    raise ValueError("Falha ao extrair o commit.")
            casa = temporario / "home"
            casa.mkdir()
            tmp = temporario / "tmp"
            tmp.mkdir()
            ambiente = {
                "PATH": os.environ["PATH"],
                "HOME": str(casa),
                "TMPDIR": str(tmp),
                "CHECKPOINT_DISABLE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            verificar(copia, caminhos, args, temporario, ambiente)
        print("Verificações selecionadas concluídas.")
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as erro:
        print(f"Verificação interrompida. {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
