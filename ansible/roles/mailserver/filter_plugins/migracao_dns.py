"""Planeja os lotes da Cloudflare para a migração do correio do domínio principal."""

import base64
from ipaddress import IPv4Address
import shlex

from ansible.errors import AnsibleFilterError


def ler_registros(consultas):
    registros = {}
    for consulta in consultas:
        filtro = consulta["item"]["value"]
        corpo = consulta["json"]
        itens = corpo.get("result")
        if (
            corpo.get("success") is not True
            or not isinstance(itens, list)
            or corpo.get("result_info", {}).get("total_count") != len(itens)
            or any(
                item["name"] != filtro["name"] or item["type"] != filtro.get("type", item["type"])
                for item in itens
            )
        ):
            raise AnsibleFilterError("A Cloudflare retornou uma consulta de DNS incompleta ou fora do alvo.")
        registros[consulta["item"]["key"]] = itens
    return registros


def assinatura_mx(registros):
    return sorted(
        (registro["content"].lower().rstrip("."), registro["priority"], registro["ttl"])
        for registro in registros
    )


def planejar_troca_mx(atuais, desejados, zona):
    if assinatura_mx(atuais) == assinatura_mx(desejados):
        return {}

    # Reutilize o registro primário nas duas direções e preserve seus metadados.
    primario = min(atuais, key=lambda registro: registro["priority"])
    novos = sorted(desejados, key=lambda registro: registro["priority"])
    lote = {"patches": [{"id": primario["id"], **novos[0]}]}
    if len(atuais) > 1:
        lote["deletes"] = [{"id": registro["id"]} for registro in atuais if registro is not primario]
    if len(novos) > 1:
        lote["posts"] = [{"name": zona, "type": "MX", **registro} for registro in novos[1:]]
    return lote


def texto_dns(valor):
    valor = valor.strip()
    try:
        return "".join(shlex.split(valor)) if valor.startswith('"') else valor
    except ValueError as erro:
        raise AnsibleFilterError("A Cloudflare retornou um TXT com aspas inválidas.") from erro


def serializar_txt(valor):
    return " ".join(f'"{valor[inicio:inicio + 255]}"' for inicio in range(0, len(valor), 255))


def ipv4_publicado(alvo):
    if len(alvo) != 1 or alvo[0].get("proxied") is not False:
        raise AnsibleFilterError("O registro A do destino MX precisa apontar diretamente para o IPv4 da VPS.")
    try:
        return str(IPv4Address(alvo[0]["content"]))
    except ValueError as erro:
        raise AnsibleFilterError("O registro A do destino MX contém um IPv4 inválido.") from erro


def spfs_mailserver(config, ipv4):
    transicao = f"v=spf1 ip4:{ipv4} {config['spf_proton'].removeprefix('v=spf1 ')}"
    return transicao, f"v=spf1 ip4:{ipv4} -all"


def ler_spf(registros):
    spfs = [
        (item, texto)
        for item in registros["txt"]
        if (texto := texto_dns(item["content"])).lower().split()[:1] == ["v=spf1"]
    ]
    if len(spfs) != 1:
        raise AnsibleFilterError("O domínio principal precisa ter exatamente um SPF previsto na migração.")
    return spfs[0]


def planejar_autenticacao(registros, config, ipv4, dkim_publica, finalizar=False):
    try:
        ipv4 = str(IPv4Address(ipv4))
        if not base64.b64decode(dkim_publica, validate=True):
            raise ValueError("DKIM vazio")
    except ValueError as erro:
        raise AnsibleFilterError("Confira o IPv4 e a chave pública DKIM do Mailserver.") from erro

    if ipv4_publicado(registros["alvo"]) != ipv4:
        raise AnsibleFilterError("O registro A do destino MX precisa apontar diretamente para o IPv4 da VPS.")

    spf_proton = config["spf_proton"]
    spf_transicao, spf_final = spfs_mailserver(config, ipv4)
    registro_spf, spf_atual = ler_spf(registros)
    if spf_atual not in (spf_proton, spf_transicao, spf_final):
        raise AnsibleFilterError("O domínio principal precisa ter exatamente um SPF previsto na migração.")

    mx_aponta_para_vps = assinatura_mx(registros["mx"]) == assinatura_mx([config["mx_mailserver"]])
    if (finalizar or spf_atual == spf_final) and not mx_aponta_para_vps:
        raise AnsibleFilterError("O SPF exclusivo exige que o MX já aponte apenas para o Mailserver.")

    txt_dkim = f"v=DKIM1; k=rsa; p={dkim_publica}"
    chaves = registros["dkim"]
    if chaves and (
        len(chaves) != 1
        or chaves[0]["type"] != "TXT"
        or texto_dns(chaves[0]["content"]) != txt_dkim
    ):
        raise AnsibleFilterError("Há um registro explícito diferente no seletor DKIM. Revise a zona antes de continuar.")

    if finalizar and (not chaves or spf_atual == spf_proton):
        raise AnsibleFilterError("Conclua a transição do SPF e publique o DKIM da VPS antes de finalizar o SPF.")

    spf_desejado = spf_atual
    if finalizar:
        spf_desejado = spf_final
    elif spf_atual == spf_proton:
        spf_desejado = spf_transicao

    lote = {}
    if spf_atual != spf_desejado:
        lote["patches"] = [{"id": registro_spf["id"], "content": serializar_txt(spf_desejado)}]
    if not chaves:
        lote["posts"] = [{
            "name": config["dkim_nome"],
            "type": "TXT",
            "content": serializar_txt(txt_dkim),
            "ttl": config["ttl"],
        }]
    return lote


def planejar_volta(registros, config):
    lote = planejar_troca_mx(registros["mx"], config["mx_proton"], config["zona"])
    registro_spf, spf_atual = ler_spf(registros)
    if spf_atual == config["spf_proton"]:
        return lote

    spf_transicao, spf_final = spfs_mailserver(config, ipv4_publicado(registros["alvo"]))
    if spf_atual == spf_final:
        lote.setdefault("patches", []).append({"id": registro_spf["id"], "content": serializar_txt(spf_transicao)})
    elif spf_atual != spf_transicao:
        raise AnsibleFilterError("O SPF atual difere dos estados previstos. Revise a zona antes de voltar o MX.")
    return lote


def planejar_migracao(consultas, etapa, config, ipv4="", dkim_publica=""):
    registros = ler_registros(consultas)
    mx_proton = config["mx_proton"]
    mx_mailserver = [config["mx_mailserver"]]
    if assinatura_mx(registros["mx"]) not in (assinatura_mx(mx_proton), assinatura_mx(mx_mailserver)):
        raise AnsibleFilterError("O conjunto MX atual difere dos dois estados previstos. Revise a zona antes de escrever.")

    if etapa == "voltar-mx":
        return planejar_volta(registros, config)

    lote_auth = planejar_autenticacao(registros, config, ipv4, dkim_publica, finalizar=etapa == "finalizar-spf")
    if etapa in ("autenticacao", "finalizar-spf"):
        return lote_auth
    if etapa != "cortar-mx":
        raise AnsibleFilterError("Etapa de migração desconhecida.")
    if lote_auth:
        raise AnsibleFilterError("Conclua a etapa de autenticação antes de trocar o MX.")
    return planejar_troca_mx(registros["mx"], mx_mailserver, config["zona"])


class FilterModule:
    def filters(self):
        return {"mailserver_planejar_migracao": planejar_migracao}
