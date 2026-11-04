#!/usr/bin/env python3
"""Exercita os daemons reais em namespaces sem saída de rede nem acesso ao D-Bus do host.

Requer Linux com user namespaces, iproute2, D-Bus, OpenSSL, systemd e Jinja2/PyYAML.
Os servidores locais simulam os provedores e MagicDNS; nenhuma auth key é usada.
"""
import json
import os
import select
from pathlib import Path
import shutil
import socket
import ssl
import struct
import subprocess as sp
import sys
import tempfile
import threading
import time

ROLE = Path(__file__).resolve().parents[1]


def comando(args):
    root = os.environ.get('LXC_DNS_SYSTEMD_ROOT')
    if root:
        path = args[0] if args[0].startswith('/') else '/usr/bin/' + args[0]
        if args[0] in ('resolvectl', 'networkctl') or path.startswith('/usr/lib/systemd/'):
            return [root + path, *args[1:]]
    return args


def run(*args, **kwargs):
    return sp.run(comando(args), check=True, text=True, stdout=sp.PIPE, stderr=sp.PIPE, **kwargs).stdout


def preparar(base):
    import jinja2
    import yaml
    etc = base / 'etc'
    etc.mkdir()
    for name in ('passwd', 'group', 'nsswitch.conf', 'machine-id', 'os-release'):
        shutil.copyfile('/etc/' + name, etc / name)
    for name in ('systemd/network/eth0.network.d', 'systemd/resolved.conf.d', 'dbus-1'):
        (etc / name).mkdir(parents=True)
    (etc / 'dbus-1/system.conf').write_text('''<busconfig><type>system</type>
<listen>unix:path=/run/dbus/system_bus_socket</listen>
<policy context="default"><allow user="*"/><allow own="*"/><allow send_destination="*"/>
<allow receive_sender="*"/></policy></busconfig>''')
    (etc / 'systemd/network/eth0.network').write_text('''[Match]
Name=eth0
[Network]
Address=192.0.2.10/24
Address=86.54.11.100/32
Address=1.1.1.1/32
LinkLocalAddressing=no
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes
''')
    context = yaml.safe_load((ROLE / 'defaults/main.yml').read_text())
    context.update(lxc_dns_magicdns_active=True, lxc_dns_tailnet_domain='test-tailnet.ts.net',
                   lxc_dns_docker_address='192.0.2.10')
    if (base / 'magic.json').exists():
        context['lxc_dns_tailnet_domain'] = json.loads((base / 'magic.json').read_text())['domain']
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(ROLE / 'templates'),
                             undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    env.filters['bool'] = bool
    for source, target in (
        ('resolved.conf.j2', 'systemd/resolved.conf.d/60-lxc-dns.conf'),
        ('network-dns.conf.j2', 'systemd/network/eth0.network.d/60-lxc-dns.conf'),
    ):
        (etc / target).write_text(env.get_template(source).render(**context))
    (etc / 'resolv.conf').symlink_to('/run/systemd/resolve/stub-resolv.conf')
    # CA fictícia, válida só no namespace, para testar também o DoT estrito.
    run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-keyout', str(base / 'key.pem'), '-out', str(base / 'cert.pem'),
        '-subj', '/CN=dns-fixture', '-addext',
        'subjectAltName=DNS:unfiltered.joindns4.eu,DNS:one.one.one.one')
    (etc / 'ssl/certs').mkdir(parents=True)
    bundle = Path('/etc/ssl/cert.pem').read_bytes() + (base / 'cert.pem').read_bytes()
    (etc / 'ssl/cert.pem').write_bytes(bundle)
    (etc / 'ssl/certs/ca-certificates.crt').write_bytes(bundle)
    run('openssl', 'rehash', str(etc / 'ssl/certs'))


class Servidor:
    def __init__(self, ip, base, tls=False):
        self.ip, self.base, self.tls = ip, base, tls
        self.mode = 'ok'
        self.consultas = []
        self.sockets = []
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(base / 'cert.pem', base / 'key.pem')
        if not tls:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind((ip, 53))
            threading.Thread(target=self.udp, args=(udp,), daemon=True).start()
        tcp = socket.socket()
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp.bind((ip, 853 if tls else 53))
        tcp.listen()
        threading.Thread(target=self.tcp, args=(tcp,), daemon=True).start()

    def resposta(self, data):
        offset, parts = 12, []
        while data[offset]:
            size = data[offset]
            parts.append(data[offset + 1:offset + 1 + size].decode())
            offset += 1 + size
        offset += 1
        qtype = struct.unpack('!H', data[offset:offset + 2])[0]
        name = '.'.join(parts)
        self.consultas.append(name)
        privado = name.endswith('.test-tailnet.ts.net')
        assert privado == (not self.tls), f'Consulta no caminho errado: {self.ip}: {name}'
        answer = b''
        if qtype == 1:
            address = '192.0.2.90' if privado else '192.0.2.80'
            answer = b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 0, 4) + socket.inet_aton(address)
        return data[:2] + struct.pack('!5H', 0x8180, 1, int(bool(answer)), 0, 0) + data[12:offset + 4] + answer

    def udp(self, sock):
        while True:
            data, client = sock.recvfrom(65535)
            if self.mode == 'ok':
                if (self.base / 'magic.json').exists():
                    with socket.socket(socket.AF_UNIX) as relay:
                        relay.connect(str(self.base / 'magic.sock'))
                        relay.sendall(struct.pack('!H', len(data)) + data)
                        answer = self.receber(relay, struct.unpack('!H', self.receber(relay, 2))[0])
                    # O domínio real fica apenas no diretório privado de runtime.
                    self.consultas.append('<MagicDNS real>')
                else:
                    answer = self.resposta(data)
                sock.sendto(answer, client)

    def tcp(self, sock):
        while True:
            conn, _ = sock.accept()
            threading.Thread(target=self.conexao, args=(conn,), daemon=True).start()

    def conexao(self, conn):
        self.sockets.append(conn)
        try:
            if self.mode == 'reject':
                return
            if self.mode == 'timeout':
                time.sleep(45)
                return
            if self.tls and (self.base / 'rede-real').exists():
                # Só o transporte sai do namespace. TLS/SNI/certificado e DNS
                # continuam entre o resolved de teste e o provedor real.
                with socket.socket(socket.AF_UNIX) as upstream:
                    upstream.connect(str(self.base / (self.ip + '.sock')))
                    self.consultas.append('<conexão TLS ao provedor real>')
                    while self.mode == 'ok':
                        ready, _, _ = select.select([conn, upstream], [], [], .1)
                        for source in ready:
                            data = source.recv(65535)
                            if not data:
                                return
                            (upstream if source is conn else conn).sendall(data)
                return
            if self.tls:
                conn = self.context.wrap_socket(conn, server_side=True)
                self.sockets.append(conn)
            conn.settimeout(45)
            while True:
                header = self.receber(conn, 2)
                data = self.receber(conn, struct.unpack('!H', header)[0])
                if self.mode == 'reject':
                    return
                if self.mode == 'timeout':
                    time.sleep(45)
                    return
                answer = self.resposta(data)
                conn.sendall(struct.pack('!H', len(answer)) + answer)
        except (OSError, EOFError, ValueError):
            pass
        finally:
            conn.close()

    @staticmethod
    def receber(conn, count):
        data = b''
        while len(data) < count:
            block = conn.recv(count - len(data))
            if not block:
                raise EOFError()
            data += block
        return data

    def estado(self, mode):
        self.mode = mode
        for conn in self.sockets:
            try:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            except OSError:
                pass
        self.sockets.clear()


def filho(base):
    run('mount', '--make-rprivate', '/')
    run('mount', '--bind', str(base / 'etc'), '/etc')
    run('mount', '-t', 'tmpfs', 'tmpfs', '/run')
    run('mount', '-t', 'proc', 'proc', '/proc')
    run('mount', '-t', 'sysfs', 'sysfs', '/sys')
    Path('/run/dbus').mkdir()
    Path('/run/systemd').mkdir()
    run('ip', 'link', 'set', 'lo', 'up')
    run('ip', 'link', 'add', 'eth0', 'type', 'dummy')
    run('ip', 'link', 'set', 'eth0', 'up')
    # O namespace não tem udevd. Marcar a interface fictícia como inicializada
    # permite ao networkd ler seu .network, sem tocar o udev do host.
    Path('/run/udev/data').mkdir(parents=True)
    index = socket.if_nametoindex('eth0')
    Path(f'/run/udev/data/n{index}').write_text('I:1\nE:ID_NET_MANAGED_BY=io.systemd.Network\n')
    for ip in ('86.54.11.100', '1.1.1.1', '100.100.100.100'):
        run('ip', 'addr', 'add', ip + '/32', 'dev', 'eth0' if ip != '100.100.100.100' else 'lo')
    processos, logs = {}, []
    for key in ('NOTIFY_SOCKET', 'WATCHDOG_USEC', 'WATCHDOG_PID', 'LISTEN_FDS', 'LISTEN_PID'):
        os.environ.pop(key, None)
    os.environ.update(SYSTEMD_LOG_LEVEL='debug', SSL_CERT_FILE='/etc/ssl/cert.pem')

    def iniciar(name, *cmd):
        log = open(base / (name + '.log'), 'a')
        logs.append(log)
        processos[name] = sp.Popen(comando(cmd), stdout=log, stderr=log)
        return processos[name]

    def esperar(cmd):
        for _ in range(60):
            try:
                return run(*cmd)
            except sp.CalledProcessError:
                time.sleep(.1)
        raise RuntimeError('Serviço não ficou pronto: ' + str(cmd))

    def reiniciar(name, *cmd):
        processos[name].terminate()
        processos[name].wait(timeout=5)
        iniciar(name, *cmd)
        time.sleep(.5)

    resultados = []
    magic_info = json.loads((base / 'magic.json').read_text()) if (base / 'magic.json').exists() else {
        'short': 'peer', 'domain': 'test-tailnet.ts.net', 'ip': '192.0.2.90'}
    curto, dominio, ip_privado = magic_info['short'], magic_info['domain'], magic_info['ip']

    def consulta(label, name, expected=None, timeout=40):
        run('resolvectl', 'flush-caches')
        start = time.monotonic()
        # ResolveHostname aplica sufixos de busca; --type=A usa ResolveRecord,
        # que é uma consulta de registro literal e não exercita nomes curtos.
        out = run('resolvectl', 'query', '-4', name, timeout=timeout)
        expected = expected if expected is not None else ('' if (base / 'rede-real').exists() else '192.0.2.80')
        assert expected in out, out
        resultados.append({'teste': label, 'segundos': round(time.monotonic() - start, 3)})
        print(json.dumps(resultados[-1], ensure_ascii=False), flush=True)

    try:
        iniciar('dbus', 'dbus-daemon', '--config-file=/etc/dbus-1/system.conf', '--nofork')
        esperar(['busctl', '--system', 'list'])
        providers = [Servidor(ip, base, tls=True) for ip in ('86.54.11.100', '1.1.1.1')]
        magic = Servidor('100.100.100.100', base)
        iniciar('resolved', '/usr/lib/systemd/systemd-resolved')
        esperar(['resolvectl', 'status'])
        iniciar('networkd', '/usr/lib/systemd/systemd-networkd')
        esperar(['networkctl', 'status', 'eth0'])
        time.sleep(1)
        publico = lambda prefix: prefix + '.example.com' if not (base / 'rede-real').exists() else 'example.com'
        consulta('público via eth0', publico('public'))
        consulta('MagicDNS FQDN', curto + '.' + dominio, ip_privado)
        consulta('MagicDNS curto', curto, ip_privado)
        assert ip_privado in run('getent', 'ahostsv4', curto)
        resultados.append({'teste': 'nome curto pela libc/getent', 'resultado': 'ok'})
        listener = run('dig', '@192.0.2.10', 'example.com', '+short', '+time=5', '+tries=1')
        assert listener.strip(), 'Listener para a ponte Docker não respondeu'
        resultados.append({'teste': 'listener da ponte Docker', 'resultado': 'ok'})
        for index in (0, 1):
            for mode in ('reject', 'timeout'):
                for provider in providers:
                    provider.estado('ok')
                # Forçar a seleção inicial pelo primeiro endereço, invertendo a
                # lista só neste ensaio para exercitar a falha de cada provedor.
                config = Path('/etc/systemd/network/eth0.network.d/60-lxc-dns.conf')
                original = config.read_text()
                addresses = ['86.54.11.100#unfiltered.joindns4.eu', '1.1.1.1#one.one.one.one']
                if index == 1:
                    config.write_text(original.replace(' '.join(addresses), ' '.join(reversed(addresses))))
                run('networkctl', 'reload')
                reiniciar('resolved', '/usr/lib/systemd/systemd-resolved')
                consulta('antes da falha', publico(f'before-{index}-{mode}'))
                providers[index].estado(mode)
                run('resolvectl', 'flush-caches')
                consulta(f'failover provedor {index + 1}: {mode}', publico(f'fail-{index}-{mode}'))
                consulta('MagicDNS durante falha pública', curto, ip_privado)
                providers[index].estado('ok')
                run('resolvectl', 'flush-caches')
                consulta('recuperação sem failback obrigatório', publico(f'recover-{index}-{mode}'))
                config.write_text(original)
        reiniciar('resolved', '/usr/lib/systemd/systemd-resolved')
        consulta('público após reiniciar resolved', publico('restart'))
        consulta('privado após reiniciar resolved', curto, ip_privado)
        reiniciar('networkd', '/usr/lib/systemd/systemd-networkd')
        run('resolvectl', 'flush-caches')
        consulta('público após reiniciar networkd', publico('networkd'))
        run('ip', 'link', 'add', 'tailscale0', 'type', 'dummy')
        run('ip', 'link', 'set', 'tailscale0', 'up')
        # Reproduzir o legado real: o resolved guarda estado de resolvectl
        # em /run e o recupera após reiniciar, sem nenhuma unit de reparo.
        run('resolvectl', 'dns', 'tailscale0', '100.100.100.100')
        run('resolvectl', 'domain', 'tailscale0', dominio)
        run('resolvectl', 'dnsovertls', 'tailscale0', 'no')
        run('resolvectl', 'default-route', 'tailscale0', 'no')
        reiniciar('resolved', '/usr/lib/systemd/systemd-resolved')
        assert '100.100.100.100' in run('resolvectl', 'dns', 'tailscale0')
        assert dominio in run('resolvectl', 'domain', 'tailscale0')
        resultados.append({'teste': 'estado legado sobrevive ao restart do resolved', 'resultado': 'ok'})
        run('resolvectl', 'revert', 'tailscale0')
        assert not run('resolvectl', 'dns', 'tailscale0').split(':', 1)[1].strip()
        assert not run('resolvectl', 'domain', 'tailscale0').split(':', 1)[1].strip()
        consulta('público após limpar estado legado de tailscale0', publico('legacy-cleanup'))
        consulta('MagicDNS após limpar tailscale0', curto, ip_privado)
        for provider in providers:
            provider.estado('reject')
        run('resolvectl', 'flush-caches')
        try:
            run('resolvectl', 'query', '-4', publico('all-down'), timeout=40)
        except sp.CalledProcessError:
            resultados.append({'teste': 'ambos indisponíveis: falha sem downgrade ou MagicDNS público', 'resultado': 'ok'})
        else:
            raise AssertionError('DNS público deveria falhar com ambos indisponíveis')
        consulta('MagicDNS com ambos provedores indisponíveis', curto, ip_privado)
        for provider in providers:
            provider.estado('ok')
        consulta('recuperação dos dois provedores', publico('all-back'))
        magic.estado('reject')
        run('resolvectl', 'flush-caches')
        consulta('público com MagicDNS indisponível', publico('no-magic'))
        magic.estado('ok')
        consulta('MagicDNS recuperado', curto, ip_privado)
        assert magic.consultas and all(n.endswith('.test-tailnet.ts.net') or n == '<MagicDNS real>' for n in magic.consultas)
        assert all(p.consultas for p in providers)
        assert all(not n.endswith('.test-tailnet.ts.net') for p in providers for n in p.consultas)
        (base / 'resultado.json').write_text(json.dumps(resultados, indent=2, ensure_ascii=False))
    finally:
        for proc in reversed(list(processos.values())):
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        for log in logs:
            log.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--filho':
        filho(Path(sys.argv[2]))
        return
    base = Path(tempfile.mkdtemp(prefix='lxc-dns-integracao-'))
    print('Artefatos de teste:', base, flush=True)
    if '--magicdns-real' in sys.argv:
        status = json.loads(run('tailscale', 'status', '--json'))
        peer = next(p for p in status['Peer'].values() if p.get('Online') and p.get('HostName') == 'caddy-lxc')
        short, domain = peer['DNSName'].rstrip('.').split('.', 1)
        (base / 'magic.json').write_text(json.dumps({'short': short, 'domain': domain, 'ip': peer['TailscaleIPs'][0]}))
        threading.Thread(target=encaminhar_magic, args=(base,), daemon=True).start()
    preparar(base)
    if '--rede-real' in sys.argv:
        (base / 'rede-real').touch()
        for ip in ('86.54.11.100', '1.1.1.1'):
            threading.Thread(target=encaminhar, args=(base, ip), daemon=True).start()
        time.sleep(.2)
    sp.run(['unshare', '--user', '--map-auto', '--map-root-user', '--mount', '--net', '--pid', '--fork',
            '--kill-child', sys.executable, str(Path(__file__).resolve()), '--filho', str(base)], check=True)


def encaminhar(base, ip):
    def conexao(client):
        try:
            with client, socket.create_connection((ip, 853), timeout=5) as upstream:
                while True:
                    ready, _, _ = select.select([client, upstream], [], [], 45)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65535)
                        if not data:
                            return
                        (upstream if source is client else client).sendall(data)
        except OSError:
            client.close()
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(base / (ip + '.sock')))
        listener.listen()
        while True:
            client, _ = listener.accept()
            threading.Thread(target=conexao, args=(client,), daemon=True).start()


def encaminhar_magic(base):
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(base / 'magic.sock'))
        listener.listen()
        while True:
            client, _ = listener.accept()
            with client, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                size = struct.unpack('!H', Servidor.receber(client, 2))[0]
                data = Servidor.receber(client, size)
                udp.settimeout(5)
                udp.connect(('100.100.100.100', 53))
                udp.send(data)
                answer = udp.recv(65535)
                client.sendall(struct.pack('!H', len(answer)) + answer)


if __name__ == '__main__':
    main()
