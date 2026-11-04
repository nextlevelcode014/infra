"""Garantias do rollback de arquivos; usa somente uma árvore temporária."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location('estado', Path(__file__).resolve().parents[1] / 'files/estado.py')
estado = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(estado)


class EstadoTest(unittest.TestCase):
    def test_preserva_link_quebrado_arquivo_permissoes_e_ausencias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'etc/docker').mkdir(parents=True)
            link = root / 'etc/resolv.conf'
            link.symlink_to('/alvo-inexistente')
            docker = root / 'etc/docker/daemon.json'
            docker.write_text('{"data-root":"/dados", "dns":["192.0.2.1"]}')
            docker.chmod(0o600)
            antes = estado.ler_arquivos(root, 'eth0')
            link.unlink()
            link.write_text('nameserver 192.0.2.2')
            docker.write_text('{}')
            marker = root / 'etc/.pve-ignore.resolv.conf'
            marker.touch()
            estado.restaurar_arquivos(root, antes, 'eth0')
            self.assertEqual(estado.ler_arquivos(root, 'eth0'), antes)
            self.assertFalse(marker.exists())
            self.assertEqual(link.readlink(), Path('/alvo-inexistente'))
            self.assertEqual(docker.stat().st_mode & 0o777, 0o600)

    def test_recusa_manifesto_inesperado_antes_de_alterar_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'etc').mkdir()
            resolv = root / 'etc/resolv.conf'
            resolv.write_text('original')
            antes = estado.ler_arquivos(root, 'eth0')
            antes['/fora-do-escopo'] = None
            with self.assertRaises(ValueError):
                estado.restaurar_arquivos(root, antes, 'eth0')
            self.assertEqual(resolv.read_text(), 'original')

    def test_recusa_diretorio_no_lugar_de_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'etc/resolv.conf').mkdir(parents=True)
            with self.assertRaises(ValueError):
                estado.ler_arquivos(root, 'eth0')

    @unittest.skipUnless(shutil.which('systemctl'), 'Requer systemctl para testar links reais')
    def test_rollback_retira_habilitacao_permanente_quando_antes_era_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = 'systemd-resolved.service'
            units = root / 'usr/lib/systemd/system'
            units.mkdir(parents=True)
            (units / unit).write_text(
                '[Service]\nExecStart=/bin/true\n[Install]\nWantedBy=multi-user.target\n')

            def systemctl(*args):
                return subprocess.run(['systemctl', '--root', tmp, *args],
                                      check=True, text=True, capture_output=True)

            systemctl('enable', unit)  # Estado permanente deixado pelo role.
            arquivos = dict.fromkeys(estado.caminhos('eth0'))
            manifest = root / 'estado.json'
            manifest.write_text(json.dumps({
                'versao': 1, 'interface': 'eth0', 'arquivos': arquivos,
                'accept_dns': None, 'docker_ativo': False,
                'units': {unit: {'is-enabled': 'enabled-runtime', 'is-active': 'active'}},
            }))
            snapshot = MagicMock()
            snapshot.stat.return_value.st_uid = 0
            snapshot.stat.return_value.st_mode = 0o700
            snapshot.__truediv__.return_value = manifest

            def executar(*args, **kwargs):
                if args[0] == 'systemctl' and args[1] in ('enable', 'disable') and args[-1] == unit:
                    return systemctl(*args[1:])
                return subprocess.CompletedProcess(args, 0, '', '')

            with patch.object(estado, 'ler_arquivos', return_value=arquivos), \
                    patch.object(estado, 'restaurar_arquivos'), \
                    patch.object(estado, 'executar', side_effect=executar):
                estado.restaurar(snapshot)
            self.assertEqual(systemctl('is-enabled', unit).stdout.strip(), 'enabled-runtime')
            self.assertFalse((root / f'etc/systemd/system/multi-user.target.wants/{unit}').is_symlink())
            self.assertTrue((root / f'run/systemd/system/multi-user.target.wants/{unit}').is_symlink())


if __name__ == '__main__':
    unittest.main()
