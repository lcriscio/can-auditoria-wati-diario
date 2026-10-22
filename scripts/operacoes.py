"""Monta o e-mail "Comprar, Produzir e Entregar" (visão gerencial de Compras, Produção e Entrega) a partir do Airtable.

Uso: python3 scripts/operacoes.py --pedidos P1.json [P2.json ...] --compras C1.json [C2.json ...]
                                  [--fornecedores F.json] [--teste] [--hoje AAAA-MM-DD]
Cada arquivo é a resposta de list_records_for_table ({"records": [...]}); páginas extras
viram arquivos extras. Gera data/operacoes/email.html e data/operacoes/assunto.txt.
"""
import argparse
import json
import os
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
BASE, PEDIDOS, VISAO, COMPRAS = "appza7P3RBl5OYQZv", "tblF4spbwfP25MItI", "viwSfm7jEfqBGEcyx", "tblv2skEXMGqivk2W"
SAIDA = "data/operacoes"
ASSUNTO = "📦 Comprar, Produzir e Entregar"

MARROM, LARANJA, CREME, BORDA, CINZA = "#56301F", "#E8621E", "#FFF6F1", "#E4D4C8", "#8A7A6E"
VERMELHO, AMBAR, AZUL, VERDE, ROXO = "#B23A24", "#C77700", "#2F5D7D", "#2F7D4F", "#6B4C9A"
FUNDO, TOPO, BORDA_CARD = "#FFF1E6", "#FFDDC2", "#F6D9C2"
TINTA = {VERMELHO: "#FDE6E1", AMBAR: "#FFF0D4", AZUL: "#E6EFF6", VERDE: "#E3F2E8", ROXO: "#EFE8F7", MARROM: "#F8E9DE", CINZA: "#F1EEEB"}
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

F = {
    "id": "fldZWGWvGg0Y7wdua", "criacao": "fldl9gG0SvY5lmnpe", "contato": "fldXtzo8xOSC6gLsZ",
    "estagio": "fldBIfAlemFpuuo3b", "responsavel": "fldWOPjPp3z3ge1gm", "data_sinal": "fldQNRLwkpIpeTG9w",
    "data_entrega": "fld9IU7JhtIHNA3k7", "faturamento": "flddTylMfbOi6AsO5", "detalhe": "fld50dK0oYiJZ8dts",
    "compras": "fldto6lJU9MzZUgjk", "unidades": "fldBvEKmfBNfUQU8d", "endereco": "fldjrkqdry27k7mWl",
}
FC = {
    "num": "fldAm6AXk5HTkdM3M", "pedido": "fldDpEA16hbhPKYx9", "descricao": "fldR3cLHsmnRyZTPM",
    "qtd": "fldyATyl5Wey2xoXa", "fornecedores": "fldfsaidVlL4aRXq2", "data_compra": "flduEqt3bOWhk6nH2",
    "status": "fld2r7Bk9WvVLvWjW",
}
FF = {"nome": "fld9N6f5G3XQjZuWK"}

# Estágios monitorados: "4. Sinal pago" a "10. Pagamento final realizado".
# Ficam de fora 0, 1, 2, 3 (venda ainda sem sinal) e 11 (perdido).
MONITORADOS = ("4.", "5.", "6.", "7.", "8.", "9.", "10.")
COMPRAR = ("4.", "5.")
PRODUZIR = ("6.", "7.")
ENTREGAR = ("4.", "5.", "6.", "7.")
TIERS = [("alta", "🔴 Urgência alta", "Entrega em até 7 dias (ou já vencida).", VERMELHO),
         ("media", "🟠 Urgência moderada", "Entrega entre 8 e 15 dias.", AMBAR),
         ("baixa", "🔵 Urgência baixa", "Entrega daqui a 16 dias ou mais.", AZUL),
         ("sem", "⚪ Sem data de entrega", "Preencha a data desejada de entrega para o pedido entrar na régua.", CINZA)]


def nome(v):
    return v.get("name") if isinstance(v, dict) else v


def data(v):
    return date.fromisoformat(v[:10]) if isinstance(v, str) and len(v) >= 10 else None


def celulas(rec):
    return rec.get("cellValuesByFieldId") or rec.get("fields") or {}


def lookup(v):
    """Valores de um campo lookup ({valuesByLinkedRecordId: {...}}) ou lista simples."""
    if isinstance(v, dict):
        return [x for vs in (v.get("valuesByLinkedRecordId") or {}).values() for x in vs]
    return v if isinstance(v, list) else []


def ler(arquivos):
    vistos, recs = set(), []
    for arq in arquivos or []:
        for rec in json.load(open(arq)).get("records", []):
            if rec["id"] not in vistos:
                vistos.add(rec["id"])
                recs.append(rec)
    return recs


def pedido(rec):
    c = celulas(rec)
    criado = c.get(F["criacao"]) or rec.get("createdTime")
    return {
        "rec": rec["id"],
        "url": f"https://airtable.com/{BASE}/{PEDIDOS}/{VISAO}/{rec['id']}?blocks=hide",
        "id": c.get(F["id"]),
        "cliente": (c.get(F["faturamento"]) or ", ".join(x.get("name", "").strip() for x in c.get(F["contato"]) or []) or "—").strip(),
        "responsavel": ", ".join(dict.fromkeys(lookup(c.get(F["responsavel"])))) or "Sem responsável",
        "estagio": nome(c.get(F["estagio"])) or "",
        "criacao": datetime.fromisoformat(criado.replace("Z", "+00:00")).astimezone(TZ).date() if criado else None,
        "data_sinal": data(c.get(F["data_sinal"])),
        "entrega": data(c.get(F["data_entrega"])),
        "detalhe": (c.get(F["detalhe"]) or "").strip(),
        "compras": [x["id"] for x in c.get(F["compras"]) or []],
        "endereco": (c.get(F["endereco"]) or "").strip(),
    }


def compra(rec, fornecedores):
    c = celulas(rec)
    forn = [fornecedores.get(x.get("id"), "").strip() if isinstance(x, dict) else str(x) for x in lookup(c.get(FC["fornecedores"]))]
    return {
        "rec": rec["id"],
        "url": f"https://airtable.com/{BASE}/{COMPRAS}/{rec['id']}?blocks=hide",
        "num": c.get(FC["num"]),
        "pedidos": [x["id"] for x in c.get(FC["pedido"]) or []],
        "descricao": " / ".join(str(x).strip() for x in lookup(c.get(FC["descricao"]))) or "Item sem produto vinculado",
        "qtd": c.get(FC["qtd"]),
        "fornecedores": [f for f in dict.fromkeys(forn) if f and not f.isdigit()],
        "data_compra": data(c.get(FC["data_compra"])),
        "status": nome(c.get(FC["status"])),
    }


def dt(d):
    return f"{DIAS[d.weekday()]} {d.strftime('%d/%m')}" if d else "sem data"


def faltam(d, hoje):
    if not d:
        return "sem data de entrega"
    n = (d - hoje).days
    if n < 0:
        return f"atrasada há {-n} dia{'s' if n < -1 else ''}"
    return "hoje" if n == 0 else "amanhã" if n == 1 else f"em {n} dias"


def urgencia(d, hoje):
    if not d:
        return "sem"
    n = (d - hoje).days
    return "alta" if n <= 7 else "media" if n <= 15 else "baixa"


def plural(n, s="pedido"):
    if n == 1:
        return f"{n} {s}"
    return f"{n} {s[:-1]}ns" if s.endswith("m") else f"{n} {s}s"


def qtd_txt(q):
    return f"{int(q) if isinstance(q, (int, float)) and float(q).is_integer() else q} ×" if q else "qtd. vazia ×"


# ---------- recomendações ----------

def acao_comprar(p, itens, hoje):
    partes = [f'Comprar {"o insumo" if len(itens) == 1 else f"os {len(itens)} insumos"} abaixo e, em cada linha da tabela Compras (botão "Registrar compra"), '
              'preencher a data da compra, o fornecedor escolhido, o custo unitário e a forma de pagamento, com status "Feito".']
    feitos = [i for i in itens if i["status"] in ("Feito", "Entregue ou Retirada")]
    if feitos:
        partes.append(f'{plural(len(feitos), "item")} já {"está marcado" if len(feitos) == 1 else "estão marcados"} como comprado'
                      f'{"" if len(feitos) == 1 else "s"} no status, mas sem data: só falta preencher a data da compra.')
    if p["estagio"].startswith("4."):
        partes.append('Ao iniciar as compras, mude o Estágio do Pedido para "5. Compra de insumos para produção".')
    partes.append('Com todos os insumos em mãos, mude o Estágio para "6. Produção iniciada".')
    partes.append(prazo(p, hoje))
    return " ".join(x for x in partes if x)


def prazo(p, hoje):
    d = p["entrega"]
    if not d:
        return 'A "Data desejada da Entrega do pedido" está vazia: confirme com o cliente e preencha.'
    n = (d - hoje).days
    if n < 0:
        return (f'A data desejada de entrega ({dt(d)}) já passou: alinhe uma nova data com o cliente e atualize '
                '"[ Preencher ] Data desejada da Entrega do pedido".')
    if n <= 3:
        return f'Entrega {faltam(d, hoje)}: é prioridade do dia. Confirme prazos com fornecedores e, se não fechar, avise o cliente já.'
    return ""


def acao_produzir(p, pendentes, hoje):
    if p["estagio"].startswith("6."):
        partes = ['Produção em andamento: conclua a produção e mude o Estágio para "7. Produção finalizada".']
        if pendentes:
            partes.append(f'Atenção: {plural(len(pendentes), "insumo")} deste pedido ainda {"está" if len(pendentes) == 1 else "estão"} '
                          f'sem data de compra na tabela Compras. Se já {"foi comprado" if len(pendentes) == 1 else "foram comprados"}, preencha a data.')
    else:
        partes = ['Produção pronta: combine a entrega ou retirada com o cliente e, quando entregar, mude o Estágio para "8. Entrega feita".']
        if not p["endereco"]:
            partes.append('O "Endereço Completo de Entrega do Pedido" está vazio: peça ao cliente e preencha.')
    d = p["entrega"]
    if d and d < hoje:
        partes.append(f'A data desejada ({dt(d)}) já passou: se o pedido já foi entregue, mude para "8. Entrega feita"; '
                      'se não, alinhe uma nova data com o cliente e atualize o campo.')
    else:
        partes.append(prazo(p, hoje))
    return " ".join(x for x in partes if x)


def acao_entregar(p, hoje):
    base = (f'A data desejada de entrega era {dt(p["entrega"])} ({faltam(p["entrega"], hoje)}). Se o pedido já foi entregue, mude o Estágio para '
            '"8. Entrega feita". Se ainda não foi, avise o cliente, combine uma nova data e atualize "[ Preencher ] Data desejada da Entrega do pedido".')
    e = p["estagio"]
    if e.startswith(("4.", "5.")):
        extra = "O pedido ainda nem entrou em produção: priorize as compras de insumos (veja a seção Comprar) e já combine o novo prazo."
    elif e.startswith("6."):
        extra = 'A produção ainda está em andamento: priorize a finalização e mude para "7. Produção finalizada" quando terminar.'
    else:
        extra = "A produção já terminou: só falta entregar. Agende a entrega ou retirada hoje."
    return f"{base} {extra}"


# ---------- blocos de HTML (seguros para Gmail: tabelas e estilos inline) ----------

def o_que_fazer(texto, cor):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:10px 0 0"><tr>'
            f'<td bgcolor="#FFF7EC" style="background:#FFF7EC;border-left:3px solid {cor};padding:8px 12px;font-size:13px;line-height:1.5;color:#3B2A22">'
            f'<b>👉 O que fazer:</b> {escape(texto)}</td></tr></table>')


def botao(url, texto, cor=LARANJA, pequeno=False):
    pad, fs = ("5px 10px", 12) if pequeno else ("9px 16px", 13)
    return (f'<table cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:{6 if pequeno else 10}px 0 0"><tr>'
            f'<td bgcolor="{cor}" style="background:{cor};border-radius:6px;padding:{pad}">'
            f'<a href="{url}" target="_blank" style="color:#ffffff;text-decoration:none;font-size:{fs}px;font-weight:bold;'
            f'font-family:Arial,Helvetica,sans-serif;white-space:nowrap;display:block">{texto}</a></td></tr></table>')


def secao(emoji, titulo, sub, cor, qtd):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:30px 0 4px"><tr>'
            f'<td bgcolor="{cor}" style="background:{cor};border-radius:8px;padding:12px 16px">'
            f'<div style="font-size:20px;font-weight:bold;color:#ffffff">{emoji} {titulo} '
            f'<span style="font-size:14px;font-weight:normal;opacity:.9">· {plural(qtd)}</span></div>'
            f'<div style="font-size:12px;color:#ffffff;opacity:.9;margin:2px 0 0">{sub}</div></td></tr></table>')


def faixa(titulo, linha2, descricao, cor):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:14px 0 0"><tr>'
            f'<td bgcolor="{TINTA[cor]}" style="background:{TINTA[cor]};border-left:5px solid {cor};border-radius:6px 6px 0 0;padding:9px 14px">'
            f'<div style="font-size:15px;font-weight:bold;color:{cor if cor != CINZA else "#5A4A40"}">{titulo} '
            f'<span style="color:#3B2A22;font-weight:normal;font-size:13px">· {linha2}</span></div>'
            + (f'<div style="font-size:12px;color:#5A4A40;margin:2px 0 0">{descricao}</div>' if descricao else "")
            + '</td></tr></table>')


def cartao(conteudo):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#ffffff" style="border-collapse:collapse;background:#ffffff;'
            f'border:1px solid {BORDA_CARD};border-top:0"><tr><td style="padding:14px 16px">{conteudo}</td></tr></table>')


def vazio(texto):
    return cartao(f'<span style="font-size:13px;color:{CINZA}">{texto}</span>')


def cabeca_pedido(p, hoje, cor):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse"><tr>'
            f'<td valign="top" style="font-size:15px;font-weight:bold;color:#3B2A22">Pedido #{p["id"]} · {escape(p["cliente"])}</td>'
            f'<td valign="top" align="right" style="font-size:13px;font-weight:bold;color:{cor};white-space:nowrap">📅 {dt(p["entrega"])}<br>'
            f'<span style="font-size:11px;font-weight:normal">{faltam(p["entrega"], hoje)}</span></td></tr></table>'
            f'<div style="font-size:12px;color:{CINZA};margin:2px 0 0">Responsável: {escape(p["responsavel"])} · {escape(p["estagio"])}'
            + (f' · sinal pago em {p["data_sinal"].strftime("%d/%m")}' if p["data_sinal"] else "") + '</div>'
            + (f'<div style="font-size:12px;color:#5A4A40;margin:6px 0 0">{escape(p["detalhe"][:220])}</div>' if p["detalhe"] else ""))


def item_compra(i, cor):
    forn = f'<br><span style="font-size:11px;color:{CINZA}">Fornecedores possíveis: {escape(", ".join(i["fornecedores"]))}</span>' if i["fornecedores"] else ""
    st = f' · status: {escape(i["status"])}' if i["status"] else ""
    return (f'<tr><td valign="top" style="padding:8px 0;border-top:1px solid {BORDA};font-size:13px;color:#3B2A22">'
            f'<b>{qtd_txt(i["qtd"])} {escape(i["descricao"])}</b> <span style="font-size:11px;color:{CINZA}">(compra #{i["num"]}{st})</span>{forn}</td>'
            f'<td valign="top" align="right" width="150" style="padding:2px 0 8px 8px;border-top:1px solid {BORDA}">'
            f'{botao(i["url"], "Registrar compra →", cor, pequeno=True)}</td></tr>')


def tiers(H, itens, hoje, render, vazio_txt):
    """itens: lista de pedidos; render(p, cor) devolve o HTML do cartão."""
    if not itens:
        H.append(vazio(vazio_txt))
        return
    for chave, titulo, descricao, cor in TIERS:
        grupo = sorted([p for p in itens if urgencia(p["entrega"], hoje) == chave], key=lambda p: (p["entrega"] or date.max, p["id"] or 0))
        if not grupo and chave == "sem":
            continue
        H.append(faixa(titulo, plural(len(grupo)), descricao, cor))
        if not grupo:
            H.append(vazio("Nada aqui hoje."))
        for p in grupo:
            H.append(render(p, cor))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pedidos", nargs="+", required=True)
    ap.add_argument("--compras", nargs="+", required=True)
    ap.add_argument("--fornecedores", nargs="*")
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--hoje")
    a = ap.parse_args()
    hoje = date.fromisoformat(a.hoje) if a.hoje else datetime.now(TZ).date()

    fornecedores = {r["id"]: str(celulas(r).get(FF["nome"]) or "") for r in ler(a.fornecedores)}
    todos = [pedido(r) for r in ler(a.pedidos)]
    pedidos = [p for p in todos if p["estagio"].startswith(MONITORADOS)]
    por_rec = {p["rec"]: p for p in pedidos}
    compras = [compra(r, fornecedores) for r in ler(a.compras)]
    pendentes = {}  # pedido -> compras sem data
    for c in compras:
        if c["data_compra"]:
            continue
        for pr in c["pedidos"]:
            if pr in por_rec:
                pendentes.setdefault(pr, []).append(c)

    # Grupo 1 · Comprar: compras sem data, de pedidos em 4 ou 5
    g1 = [p for p in pedidos if p["estagio"].startswith(COMPRAR) and pendentes.get(p["rec"])]
    # Grupo 2 · Produzir: sinal/valor cheio pago e estágio 6 ou 7
    g2 = [p for p in pedidos if p["estagio"].startswith(PRODUZIR) and p["data_sinal"]]
    # Grupo 3 · Entregar: data desejada já passou e o pedido ainda não foi entregue
    g3 = [p for p in pedidos if p["estagio"].startswith(ENTREGAR) and p["entrega"] and p["entrega"] < hoje]

    # Pontos de atenção: pedidos que ficariam fora das três frentes por inconsistência no CRM
    atencao = []
    for p in sorted(pedidos, key=lambda p: p["id"] or 0):
        if p["estagio"].startswith(COMPRAR) and not p["compras"]:
            atencao.append((p, "Pedido em compras sem nenhum insumo cadastrado na tabela Compras.",
                            'Cadastre os insumos na tabela Compras (ligados a este pedido). Se não há nada a comprar, mude o Estágio para "6. Produção iniciada".'))
        elif p["estagio"].startswith(COMPRAR) and not pendentes.get(p["rec"]):
            atencao.append((p, "Todos os insumos já têm data de compra, mas o estágio continua em compras.",
                            'Quando os insumos chegarem e a produção começar, mude o Estágio para "6. Produção iniciada".'))
        if p["estagio"].startswith(PRODUZIR) and not p["data_sinal"]:
            atencao.append((p, "Pedido em produção sem a data do pagamento do sinal ou valor cheio.",
                            'Confira se o sinal foi pago e se a "Data do Pagamento do Sinal ou Valor Cheio" foi registrada. Sem ela o pedido não aparece em Produzir.'))

    def render_comprar(p, cor):
        itens = sorted(pendentes[p["rec"]], key=lambda i: i["num"] or 0)
        linhas = "".join(item_compra(i, cor) for i in itens)
        return cartao(cabeca_pedido(p, hoje, cor)
                      + f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:10px 0 0">{linhas}</table>'
                      + o_que_fazer(acao_comprar(p, itens, hoje), cor) + botao(p["url"], "Abrir pedido no Airtable →"))

    def render_produzir(p, cor):
        return cartao(cabeca_pedido(p, hoje, cor) + o_que_fazer(acao_produzir(p, pendentes.get(p["rec"], []), hoje), cor)
                      + botao(p["url"], "Abrir pedido no Airtable →"))

    def render_entregar(p, cor):
        return cartao(cabeca_pedido(p, hoje, cor) + o_que_fazer(acao_entregar(p, hoje), cor) + botao(p["url"], "Abrir pedido no Airtable →"))

    n_itens = sum(len(pendentes[p["rec"]]) for p in g1)
    estagios = {}
    for p in pedidos:
        estagios[p["estagio"]] = estagios.get(p["estagio"], 0) + 1

    H = [f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="{FUNDO}" style="background:{FUNDO};border-collapse:collapse"><tr><td align="center" style="padding:16px 8px">'
         f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#ffffff" style="max-width:660px;border-collapse:separate;background:#ffffff;'
         f'border:1px solid {BORDA_CARD};border-radius:10px"><tr><td align="left" style="font-family:Arial,Helvetica,sans-serif;color:#3B2A22;font-size:14px;line-height:1.5">']
    H.append(f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse"><tr>'
             f'<td bgcolor="{TOPO}" style="background:{TOPO};border-radius:10px 10px 0 0;border-bottom:3px solid {LARANJA};padding:18px 20px">'
             f'<div style="font-size:21px;font-weight:bold;color:{MARROM}">📦 Comprar, Produzir e Entregar</div>'
             f'<div style="font-size:13px;color:#7A4A2E;margin:2px 0 0">Visão gerencial de Compras, Produção e Entrega · Can Candles &amp; Wellness · '
             f'{DIAS[hoje.weekday()]} {hoje.strftime("%d/%m/%Y")}</div></td></tr></table>')

    def cel(v, rot, cor):
        return (f'<td width="33%" bgcolor="{TINTA[cor]}" style="background:{TINTA[cor]};border-radius:8px;padding:12px 6px;text-align:center">'
                f'<div style="font-size:24px;font-weight:bold;color:{cor}">{v}</div><div style="font-size:12px;color:#3B2A22">{rot}</div></td>')
    alta = lambda g: sum(1 for p in g if urgencia(p["entrega"], hoje) == "alta")
    H.append('<div style="padding:16px 20px 4px"><p style="margin:0 0 12px">Bom dia, time! Este é o mapa do que precisa andar hoje nos pedidos já vendidos: '
             'o que comprar, o que produzir e o que entregar. Cada caso tem a ação recomendada e o botão que abre o registro no Airtable.</p>'
             '<table cellpadding="0" cellspacing="6" width="100%" style="border-collapse:separate"><tr>'
             f'{cel(len(g1), f"🛒 pedidos a comprar<br>({plural(n_itens, "item")} · {alta(g1)} urgentes)", AMBAR)}'
             f'{cel(len(g2), f"🕯️ pedidos a produzir<br>({alta(g2)} urgentes)", AZUL)}'
             f'{cel(len(g3), "🚚 entregas atrasadas<br>(data já passou)", VERMELHO)}</tr></table>'
             + (f'<p style="margin:8px 0 0;font-size:13px">⚠️ <b>{plural(len(atencao), "ponto")} de atenção</b> no CRM no fim do e-mail.</p>' if atencao else "")
             + '</div>')

    H.append('<div style="padding:0 16px 20px">')
    H.append(secao("🛒", "Comprar", 'Insumos da tabela Compras sem "Data que a compra foi realizada", de pedidos em "4. Sinal pago" ou "5. Compra de insumos para produção"',
                   AMBAR, len(g1)))
    tiers(H, g1, hoje, render_comprar, "Nenhum insumo pendente de compra. 🎉")

    H.append(secao("🕯️", "Produzir", 'Pedidos com sinal ou valor cheio pago em "6. Produção iniciada" ou "7. Produção finalizada"', AZUL, len(g2)))
    tiers(H, g2, hoje, render_produzir, "Nenhum pedido em produção agora.")

    H.append(secao("🚚", "Entregar", 'Pedidos com data desejada de entrega já vencida e ainda não entregues (estágios 4 a 7)', VERDE, len(g3)))
    if not g3:
        H.append(vazio("Nenhuma entrega atrasada. 🎉"))
    for p in sorted(g3, key=lambda p: (p["entrega"], p["id"] or 0)):
        H.append(render_entregar(p, VERMELHO))

    if atencao:
        H.append(secao("⚠️", "Pontos de atenção no CRM", "Pedidos que ficariam fora das três frentes por falta de informação ou estágio parado", MARROM, len({p["rec"] for p, _, _ in atencao})))
        for p, prob, fazer in atencao:
            H.append(cartao(cabeca_pedido(p, hoje, MARROM)
                            + f'<div style="margin:10px 0 0;font-size:13px"><b style="color:{VERMELHO}">⚠️ {escape(prob)}</b></div>'
                            + o_que_fazer(fazer, MARROM) + botao(p["url"], "Ajustar no Airtable →")))

    resumo = " · ".join(f"{escape(e)}: {n}" for e, n in sorted(estagios.items(), key=lambda x: int(x[0].split(".")[0])))
    H.append(f'<div style="font-size:11px;color:{CINZA};margin:24px 0 0;border-top:1px solid {BORDA};padding-top:10px">'
             f'<p style="margin:0 0 4px"><b>Pedidos monitorados ({len(pedidos)}):</b> {resumo or "nenhum"}.</p>'
             '<p style="margin:0 0 4px"><b>Como lemos o CRM.</b> Todos os pedidos nos estágios "4. Sinal pago" a '
             '"10. Pagamento final realizado" (ficam de fora 0, 1, 2, 3 e 11). Urgência pela "Data desejada da Entrega do pedido" contada a partir de hoje: '
             'alta até 7 dias (inclui datas vencidas), moderada de 8 a 15 dias e baixa a partir de 16 dias.</p>'
             '<p style="margin:0">Comprar: linhas da tabela Compras sem data da compra, ligadas a pedidos em 4 ou 5. Produzir: pedidos em 6 ou 7 com a data do pagamento do sinal '
             'ou valor cheio preenchida. Entregar: pedidos em 4, 5, 6 ou 7 com a data desejada de entrega anterior a hoje. Datas no horário de Brasília.</p></div>')
    H.append('<p style="margin:12px 0 0;font-size:13px">Compras, Produção e Entrega · Can Candles</p></div></td></tr></table></td></tr></table>')

    os.makedirs(SAIDA, exist_ok=True)
    open(os.path.join(SAIDA, "email.html"), "w").write("\n".join(H))
    open(os.path.join(SAIDA, "assunto.txt"), "w").write(("[TESTE] " if a.teste else "") + f'{ASSUNTO} · {DIAS[hoje.weekday()]} {hoje.strftime("%d/%m")}')
    print(f"ok: monitorados={len(pedidos)} comprar={len(g1)} (itens={n_itens}, alta={alta(g1)}) produzir={len(g2)} (alta={alta(g2)}) "
          f"entregar={len(g3)} atencao={len(atencao)}")


if __name__ == "__main__":
    main()
