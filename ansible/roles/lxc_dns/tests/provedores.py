#!/usr/bin/env python3
"""Sondagem somente de leitura: DNS/53 e DoT autenticado, sem dependências."""
import json
import secrets
import socket
import ssl
import statistics
import struct
import time

PROVEDORES = (
    ("DNS4EU Unfiltered", "86.54.11.100", "unfiltered.joindns4.eu"),
    ("Cloudflare", "1.1.1.1", "one.one.one.one"),
)


def pergunta(nome="example.com"):
    ident = secrets.randbelow(65536)
    qname = b"".join(bytes([len(p)]) + p.encode() for p in nome.split(".")) + b"\0"
    return struct.pack("!6H", ident, 0x100, 1, 0, 0, 0) + qname + struct.pack("!HH", 1, 1)


def receber(sock, tamanho):
    dados = b""
    while len(dados) < tamanho:
        parte = sock.recv(tamanho - len(dados))
        if not parte:
            raise EOFError("Resposta DNS incompleta")
        dados += parte
    return dados


def consultar(ip, sni=None):
    pacote = pergunta()
    inicio = time.monotonic()
    if sni:
        contexto = ssl.create_default_context()
        with socket.create_connection((ip, 853), timeout=5) as tcp:
            with contexto.wrap_socket(tcp, server_hostname=sni) as tls:
                tls.sendall(struct.pack("!H", len(pacote)) + pacote)
                tamanho = struct.unpack("!H", receber(tls, 2))[0]
                resposta = receber(tls, tamanho)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(5)
            udp.connect((ip, 53))
            udp.send(pacote)
            resposta = udp.recv(65535)
    ident, flags, _, respostas, _, _ = struct.unpack("!6H", resposta[:12])
    if resposta[:2] != pacote[:2] or not flags & 0x8000 or flags & 15 or not respostas:
        raise ValueError(f"Resposta inválida: id={ident}, flags={flags}, respostas={respostas}")
    return round((time.monotonic() - inicio) * 1000, 1)


def main():
    resultado = []
    for nome, ip, sni in PROVEDORES:
        for protocolo in ("UDP/53", "DoT/853"):
            amostras, erros = [], []
            for _ in range(3):
                try:
                    amostras.append(consultar(ip, sni if protocolo == "DoT/853" else None))
                except (OSError, EOFError, ValueError) as erro:
                    erros.append(f"{type(erro).__name__}: {erro}")
            resultado.append({
                "provedor": nome, "ip": ip, "protocolo": protocolo,
                "sucessos": len(amostras), "amostras_ms": amostras,
                "mediana_ms": statistics.median(amostras) if amostras else None,
                "erros": erros,
            })
    print(json.dumps(resultado, indent=2, ensure_ascii=False), flush=True)
    return 0 if all(item["sucessos"] == 3 for item in resultado) else 1


if __name__ == "__main__":
    raise SystemExit(main())
