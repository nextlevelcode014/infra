#!/usr/bin/env python3
"""Snapshot e rollback explícitos do DNS. Nunca executado periodicamente pelo role."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import stat
import subprocess


UNITS = ('lxc-magicdns.timer', 'lxc-magicdns.service', 'systemd-resolved.service')


def executar(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)


def caminhos(interface):
    return (
        '/etc/resolv.conf', '/etc/.pve-ignore.resolv.conf',
        '/etc/systemd/resolved.conf.d/60-lxc-dns.conf',
        f'/etc/systemd/network/{interface}.network.d/60-lxc-dns.conf',
        '/etc/docker/daemon.json', '/usr/local/sbin/lxc-magicdns',
        '/etc/systemd/system/lxc-magicdns.service',
        '/etc/systemd/system/lxc-magicdns.timer',
        '/etc/systemd/system/sys-subsystem-net-devices-tailscale0.device.wants/lxc-magicdns.service',
    )


def ler_arquivos(root, interface):
    arquivos = {}
    for nome in caminhos(interface):
        path = root / nome.lstrip('/')
        if not path.exists() and not path.is_symlink():
            arquivos[nome] = None
            continue
        info = path.lstat()
        if not (stat.S_ISLNK(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError(f'Não é arquivo regular nem link: {nome}')
        arquivos[nome] = {
            'link': os.readlink(path) if path.is_symlink() else None,
            'dados': None if path.is_symlink() else base64.b64encode(path.read_bytes()).decode(),
            'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid,
        }
    return arquivos


def restaurar_arquivos(root, arquivos, interface):
    if set(arquivos) != set(caminhos(interface)):
        raise ValueError('Manifesto não corresponde aos caminhos gerenciados')
    for nome, item in arquivos.items():
        path = root / nome.lstrip('/')
        if path.exists() or path.is_symlink():
            path.unlink()
        if item is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if item['link'] is not None:
            path.symlink_to(item['link'])
        else:
            path.write_bytes(base64.b64decode(item['dados'], validate=True))
            path.chmod(item['mode'])
        os.chown(path, item['uid'], item['gid'], follow_symlinks=False)


def salvar(destino, interface):
    # Não sobrescrever a referência de rollback em reaplicações.
    destino.mkdir(mode=0o700)
    estado = {'versao': 1, 'interface': interface, 'arquivos': ler_arquivos(Path('/'), interface)}
    estado['units'] = {
        unit: {cmd: executar('systemctl', cmd, unit, check=False).stdout.strip()
               for cmd in ('is-active', 'is-enabled')}
        for unit in UNITS
    }
    estado['docker_ativo'] = executar('systemctl', 'is-active', 'docker', check=False).returncode == 0
    estado['accept_dns'] = None
    if Path('/usr/bin/tailscale').exists():
        estado['accept_dns'] = json.loads(executar('tailscale', 'debug', 'prefs').stdout)['CorpDNS']
    manifest = destino / 'estado.json'
    manifest.write_text(json.dumps(estado, indent=2))
    manifest.chmod(0o600)
    print(f'Snapshot salvo em {manifest}; contém configuração privada, não publique.')


def restaurar(destino):
    info = destino.stat()
    if info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Snapshot precisa pertencer ao root e ser privado (0700)')
    estado = json.loads((destino / 'estado.json').read_text())
    if estado['versao'] != 1 or not re.fullmatch(r'[a-zA-Z0-9_-]+', estado['interface']):
        raise ValueError('Snapshot incompatível')
    # Validar o manifesto antes de parar serviços ou alterar arquivos.
    if set(estado['arquivos']) != set(caminhos(estado['interface'])):
        raise ValueError('Caminhos inesperados no snapshot')
    docker_antes = ler_arquivos(Path('/'), estado['interface'])['/etc/docker/daemon.json']
    for unit in UNITS[:2]:
        if Path('/etc/systemd/system/' + unit).exists():
            executar('systemctl', 'disable', '--now', unit)
    restaurar_arquivos(Path('/'), estado['arquivos'], estado['interface'])
    executar('systemctl', 'daemon-reload')
    executar('networkctl', 'reload')
    executar('networkctl', 'reconfigure', estado['interface'])
    executar('systemctl', 'restart', 'systemd-resolved')
    if estado['accept_dns'] is not None:
        executar('tailscale', 'set', '--accept-dns=' + str(estado['accept_dns']).lower())
    for unit, config in estado['units'].items():
        if config['is-enabled'] in ('enabled', 'enabled-runtime', 'disabled'):
            args = ['systemctl', 'enable' if config['is-enabled'].startswith('enabled') else 'disable']
            if config['is-enabled'] == 'enabled-runtime':
                # O role habilita resolved permanentemente. enable --runtime
                # sozinho acrescenta links em /run sem retirar os de /etc.
                executar('systemctl', 'disable', unit)
                args.append('--runtime')
            executar(*args, unit)
        if config['is-active'] == 'active':
            executar('systemctl', 'start', unit)
        elif unit == 'systemd-resolved.service':
            executar('systemctl', 'stop', unit)
    if estado['docker_ativo'] and docker_antes != estado['arquivos']['/etc/docker/daemon.json']:
        executar('systemctl', 'try-restart', 'docker')
    print('Estado anterior restaurado. Confira DNS, Docker e serviços pelo acesso de contingência.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', choices=('salvar', 'restaurar'))
    parser.add_argument('diretorio', type=Path)
    parser.add_argument('--interface', default='eth0')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Execute como root no LXC, pela bridge ou console do Proxmox')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.interface):
        parser.error('Interface inválida')
    if not args.diretorio.is_absolute():
        parser.error('Use um caminho absoluto para o snapshot')
    if args.acao == 'salvar':
        salvar(args.diretorio, args.interface)
    else:
        restaurar(args.diretorio)


if __name__ == '__main__':
    main()
