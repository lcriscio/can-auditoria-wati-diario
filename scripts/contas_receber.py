"""Monta o e-mail "Calendário de Contas a Receber e Ajustes necessários em Cobranças" a partir dos Pedidos do Airtable.

Uso: python3 scripts/contas_receber.py ARQUIVO.json [ARQUIVO2.json ...] [--teste] [--hoje AAAA-MM-DD]
Cada arquivo é a resposta de list_records_for_table ({"records": [...]}); páginas extras
viram arquivos extras. Gera data/contas/email.html e data/contas/assunto.txt.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
BASE, TABELA, VISAO = "appza7P3RBl5OYQZv", "tblF4spbwfP25MItI", "viwSfm7jEfqBGEcyx"
SAIDA = "data/contas"
ASSUNTO = "💰: Calendário de Contas a Receber e Ajustes necessários em Cobranças"
CORTE_DATA_SALDO = date(2026, 10, 20)  # antes disso não registrávamos a data do saldo

MARROM, LARANJA, CREME, BORDA, CINZA = "#56301F", "#E8621E", "#FFF6F1", "#E4D4C8", "#8A7A6E"
VERMELHO, AMBAR, AZUL = "#B23A24", "#C77700", "#2F5D7D"
FUNDO, TOPO, BORDA_CARD = "#FFF1E6", "#FFDDC2", "#F6D9C2"  # laranja bem claro, faixa do topo e bordas
LARANJA_T = "#D9541A"  # laranja do bloco de sinal (texto legível sobre fundo claro)
TINTA = {VERMELHO: "#FDE6E1", AMBAR: "#FFF0D4", AZUL: "#E6EFF6", MARROM: "#F8E9DE", LARANJA_T: "#FFE3D1"}  # fundo claro de cada cor
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

F = {
    "id": "fldZWGWvGg0Y7wdua", "criacao": "fldl9gG0SvY5lmnpe", "contato": "fldXtzo8xOSC6gLsZ",
    "estagio": "fldBIfAlemFpuuo3b", "responsavel": "fldWOPjPp3z3ge1gm", "preco": "fldZNp21mjPqXIY6Y",
    "como_pago": "fldtCRpgKQJy8WOsA", "pct": "fldRbERwNA5K243C2", "saldo": "fldVul9O74meoWwdd",
    "data_sinal": "fldQNRLwkpIpeTG9w", "status_saldo": "fldfDI9vLsR9hqNg2",
    "data_saldo": "fldGRw3BPVdSkwSMi", "data_entrega": "fld9IU7JhtIHNA3k7", "faturamento": "flddTylMfbOi6AsO5",
    "status_sinal": "fldmAdlGqtAXP55IQ", "metodo_sinal": "fldQmm6zDPgYAyj8m", "montante_sinal": "fld736aM0Lxpe4yp3",
    "data_venda": "fldFRaZsSYXi8YsTU",
}
VENDIDO = ("3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.")  # estágios de venda concluída em diante
SINAL_EMITIDO = ("Pendente", "Pago")


def nome(v):
    return v.get("name") if isinstance(v, dict) else v


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def data(v):
    return date.fromisoformat(v[:10]) if isinstance(v, str) and len(v) >= 10 else None


def pedido(rec):
    c = rec.get("cellValuesByFieldId") or rec.get("fields") or {}
    resp = c.get(F["responsavel"]) or {}
    nomes = [n for vs in (resp.get("valuesByLinkedRecordId") or {}).values() for n in vs] if isinstance(resp, dict) else []
    criado = c.get(F["criacao"]) or rec.get("createdTime")
    return {
        "rec": rec["id"],
        "url": f"https://airtable.com/{BASE}/{TABELA}/{VISAO}/{rec['id']}?blocks=hide",
        "id": c.get(F["id"]),
        "cliente": c.get(F["faturamento"]) or ", ".join(x.get("name", "") for x in c.get(F["contato"]) or []) or "—",
        "responsavel": ", ".join(dict.fromkeys(nomes)) or "Sem responsável",
        "estagio": nome(c.get(F["estagio"])) or "",
        "como_pago": nome(c.get(F["como_pago"])),
        "pct": num(c.get(F["pct"])),
        "preco": num(c.get(F["preco"])),
        "saldo": num(c.get(F["saldo"])),
        "status_saldo": nome(c.get(F["status_saldo"])),
        "criacao": datetime.fromisoformat(criado.replace("Z", "+00:00")).astimezone(TZ).date() if criado else None,
        "data_sinal": data(c.get(F["data_sinal"])),
        "data_saldo": data(c.get(F["data_saldo"])),
        "data_entrega": data(c.get(F["data_entrega"])),
        "status_sinal": nome(c.get(F["status_sinal"])),
        "metodo_sinal": nome(c.get(F["metodo_sinal"])),
        "montante_sinal": num(c.get(F["montante_sinal"])),
        "data_venda": datetime.fromisoformat(c[F["data_venda"]].replace("Z", "+00:00")).astimezone(TZ).date() if c.get(F["data_venda"]) else None,
    }


def perdido(p):
    return p["estagio"].startswith("11.") or p["status_saldo"] == "Pedido perdido, campo desnecessário"


def brl(v):
    s = f"{v or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def dt(d):
    return f"{DIAS[d.weekday()]} {d.strftime('%d/%m')}" if d else "vazio"


def pct_txt(v):
    return "vazio" if v is None else f"{round(v * 100)}%"


def inconsistencias(p):
    """Lista de (regra, problema, o que fazer) para um pedido não perdido."""
    out = []
    cp, ds, cr = p["como_pago"], p["data_saldo"], p["criacao"]
    if cp == "Sinal + Saldo" and ds and p["status_sinal"] != "Pago":
        if p["status_sinal"] in SINAL_EMITIDO:
            fazer = ('A cobrança do sinal já foi emitida, mas ainda não foi paga. Confirme que a "Data estimada para Pagamento do Saldo" '
                     'é mesmo a data do saldo (a segunda parcela, normalmente perto da entrega) e não a do sinal; se for a do sinal, corrija para a data do saldo.')
        else:
            fazer = ('A data do saldo parece ter sido preenchida pensando no sinal. Primeiro emita a cobrança do sinal: em '
                     '"Emitir cobrança do Sinal ou Valor Cheio deste pedido" escolha "Sim, emitir agora" e preencha '
                     '"Método de pagamento do Sinal ou Valor Cheio deste pedido" (Boleto, Link de pagamento ou PIX). '
                     'Depois ajuste a "Data estimada para Pagamento do Saldo" para quando a segunda parcela será paga.')
        out.append(("Data do saldo sem sinal pago",
                    f'Pagamento "Sinal + Saldo" com data do saldo em {dt(ds)}, mas o sinal ainda não foi pago '
                    f'(status da cobrança do sinal: {p["status_sinal"] or "vazio"}). O saldo só vem depois do sinal.', fazer))
    if cp == "Valor cheio" and (p["pct"] is None or abs(p["pct"] - 1) > 0.001):
        out.append(("Valor cheio sem 100%",
                    f'Pagamento "Valor cheio", mas o percentual pago está em {pct_txt(p["pct"])}.',
                    'Se o cliente paga tudo de uma vez, mude "Percentual pago como Sinal ou Valor cheio" para 100%. '
                    'Se ele paga em duas partes, troque "Como esse pedido será pago" para "Sinal + Saldo" e preencha a data estimada do saldo.'))
    if cp == "Valor cheio" and ds:
        out.append(("Valor cheio com data de saldo",
                    f'Pagamento "Valor cheio", mas a data estimada do saldo está preenchida ({dt(ds)}). '
                    'Essa data só deve existir em pedidos "Sinal + Saldo".',
                    'Se o cliente paga tudo de uma vez, apague a "Data estimada para Pagamento do Saldo". '
                    'Se existe saldo a receber, troque "Como esse pedido será pago" para "Sinal + Saldo" e ajuste o percentual do sinal.'))
    if cp == "Sinal + Saldo" and ds:
        if cr and ds <= cr:
            out.append(("Data do saldo ≤ criação",
                        f'Data do saldo ({dt(ds)}) é igual ou anterior à criação do pedido ({dt(cr)}).',
                        'Confirme com o cliente quando o saldo será pago e corrija a "Data estimada para Pagamento do Saldo" '
                        '(normalmente perto da entrega, sempre depois do sinal).'))
        elif p["data_sinal"] and ds <= p["data_sinal"]:
            out.append(("Data do saldo ≤ pagamento do sinal",
                        f'Data do saldo ({dt(ds)}) é igual ou anterior ao pagamento do sinal ({dt(p["data_sinal"])}).',
                        'Corrija a "Data estimada para Pagamento do Saldo" para a data combinada com o cliente, depois do pagamento do sinal.'))
    if p["data_entrega"] and cr and p["data_entrega"] < cr:
        out.append(("Entrega antes da criação",
                    f'Data desejada de entrega ({dt(p["data_entrega"])}) é anterior à criação do pedido ({dt(cr)}).',
                    'Confirme com o cliente a data em que ele quer receber e corrija a "Data desejada da Entrega do pedido".'))
    if cp == "Sinal + Saldo" and not ds and cr and cr >= CORTE_DATA_SALDO:
        out.append(("Sinal + Saldo sem data do saldo",
                    'Pagamento "Sinal + Saldo", mas a data estimada do saldo está vazia.',
                    'Preencha a "Data estimada para Pagamento do Saldo" com a data combinada com o cliente. '
                    'Sem ela, o saldo não entra no calendário de cobrança.'))
    return out


def acao_cobranca(p, hoje):
    """O que o Contas a Receber precisa fazer com um saldo em aberto."""
    d, st = p["data_saldo"], p["status_saldo"]
    emitida = st == "Pendente"
    if d < hoje:
        if emitida:
            return ("Cobrar hoje: a cobrança já foi emitida e não foi paga. Reenvie o link de pagamento ao cliente pelo WhatsApp, "
                    "confirme uma nova data e, se ele já pagou por outro meio, atualize o status do saldo para \"Pago\".")
        return ("Cobrar hoje: o saldo venceu e a cobrança ainda não foi emitida. Em \"Emitir cobrança do Saldo deste pedido\" escolha "
                "\"Sim, emitir agora\", envie o link ao cliente pelo WhatsApp e, se ele já pagou, marque o status do saldo como \"Pago\".")
    if d <= hoje + timedelta(days=7):
        quando = "hoje" if d == hoje else f"até {dt(d)}"
        if emitida:
            return f"Cobrança já emitida: lembre o cliente pelo WhatsApp de que o saldo vence {quando} e reenvie o link de pagamento."
        return (f"Preparar a cobrança: emita o link do saldo (\"Emitir cobrança do Saldo deste pedido\" = \"Sim, emitir agora\") "
                f"e envie ao cliente para pagamento {quando}.")
    return "Nenhuma ação agora. Só confira se a data continua valendo; a cobrança entra em \"Importante\" 7 dias antes."


def a_cobrar_sinal(p):
    """Venda concluída (ou adiante) com Sinal/Valor cheio ainda não pago."""
    return (p["estagio"].startswith(VENDIDO) and p["como_pago"] in ("Sinal + Saldo", "Valor cheio")
            and p["status_sinal"] != "Pago" and (p["montante_sinal"] or 0) > 0.005)


def acao_sinal(p):
    tipo = "do sinal" if p["como_pago"] == "Sinal + Saldo" else "do valor cheio"
    entregue = "Pedido já entregue e sem pagamento registrado. " if p["estagio"].startswith(("8.", "9.", "10.")) else ""
    st, met = p["status_sinal"], p["metodo_sinal"]
    if st == "Pendente":
        return (f'{entregue}Cobrança {tipo} emitida{f" ({met})" if met else ""} e ainda não paga. Lembre o cliente pelo WhatsApp e reenvie '
                'o link; se ele já pagou por outro meio, confirme o recebimento e atualize o status da cobrança para "Pago".')
    if st == "Pagamento não encontrado":
        return (f'{entregue}O pagamento {tipo} não foi encontrado. Confira com o cliente e no extrato; se não houve pagamento, '
                'emita uma nova cobrança e envie ao cliente.')
    metodo = (f'confirme o "Método de pagamento do Sinal ou Valor Cheio deste pedido" (hoje: {met})' if met else
              'preencha "Método de pagamento do Sinal ou Valor Cheio deste pedido" (Boleto, Link de pagamento ou PIX)')
    return (f'{entregue}Emita a cobrança {tipo}: em "Emitir cobrança do Sinal ou Valor Cheio deste pedido" escolha "Sim, emitir agora", '
            f'{metodo} e envie a cobrança ao cliente pelo WhatsApp.')


def o_que_fazer(texto, cor):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:10px 0 0"><tr>'
            f'<td bgcolor="#FFF7EC" style="background:#FFF7EC;border-left:3px solid {cor};padding:8px 12px;font-size:13px;line-height:1.5;color:#3B2A22">'
            f'<b>👉 O que fazer:</b> {escape(texto)}</td></tr></table>')


def botao(url, texto="Abrir no Airtable →"):
    return (f'<table cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:10px 0 0"><tr>'
            f'<td bgcolor="{LARANJA}" style="background:{LARANJA};border-radius:6px;padding:9px 16px">'
            f'<a href="{url}" target="_blank" style="color:#ffffff;text-decoration:none;font-size:13px;font-weight:bold;'
            f'font-family:Arial,Helvetica,sans-serif;white-space:nowrap;display:block">{texto}</a></td></tr></table>')


def h2(t, sub):
    return (f'<h2 style="color:{MARROM};font-size:19px;margin:28px 0 2px">{t}</h2>'
            f'<p style="margin:0 0 6px;font-size:13px;color:{CINZA}">{sub}</p>')


def faixa(titulo, linha2, descricao, cor):
    """Cabeçalho de grupo: fundo claro da cor, borda lateral forte e texto escuro (legível em qualquer cliente)."""
    return (f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:16px 0 0"><tr>'
            f'<td bgcolor="{TINTA[cor]}" style="background:{TINTA[cor]};border-left:5px solid {cor};border-radius:6px 6px 0 0;padding:10px 14px">'
            f'<div style="font-size:16px;font-weight:bold;color:{cor}">{titulo}</div>'
            + (f'<div style="font-size:15px;font-weight:bold;color:#3B2A22;margin:2px 0 0">{linha2}</div>' if linha2 else "")
            + (f'<div style="font-size:12px;color:#5A4A40;margin:2px 0 0">{descricao}</div>' if descricao else "")
            + '</td></tr></table>')


def cartao(conteudo):
    return (f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#ffffff" style="border-collapse:collapse;background:#ffffff;'
            f'border:1px solid {BORDA_CARD};border-top:0"><tr><td style="padding:14px 16px">{conteudo}</td></tr></table>')


def plural(n, s="pedido"):
    return f'{n} {s}{"s" if n != 1 else ""}'


def tier(H, titulo, descricao, cor, itens, hoje, vazio):
    H.append(faixa(titulo, f'{brl(sum(p["saldo"] for p in itens))} · {plural(len(itens))}', descricao, cor))
    if not itens:
        H.append(cartao(f'<span style="font-size:13px;color:{CINZA}">{vazio}</span>'))
        return
    dia_atual = None
    for p in sorted(itens, key=lambda p: (p["data_saldo"], p["id"] or 0)):
        d = p["data_saldo"]
        if d != dia_atual:
            dia_atual = d
            do_dia = [x for x in itens if x["data_saldo"] == d]
            delta = (d - hoje).days
            rel = "hoje" if delta == 0 else (f"venceu há {-delta} dia{'s' if delta < -1 else ''}" if delta < 0 else f"em {delta} dia{'s' if delta > 1 else ''}")
            H.append(f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="{CREME}" style="border-collapse:collapse;background:{CREME};border:1px solid {BORDA_CARD};border-top:0">'
                     f'<tr><td style="padding:7px 16px;font-size:13px"><b style="color:{cor}">📅 {dt(d)}</b> '
                     f'<span style="color:{CINZA}">· {rel} · {brl(sum(x["saldo"] for x in do_dia))}</span></td></tr></table>')
        H.append(cartao(
            f'<div style="font-size:15px;font-weight:bold;color:#3B2A22">Pedido #{p["id"]} · {escape(p["cliente"])}</div>'
            f'<div style="font-size:12px;color:{CINZA};margin:2px 0 0">Responsável: {escape(p["responsavel"])} · Status do saldo: {escape(p["status_saldo"] or "vazio")}</div>'
            f'<div style="margin:8px 0 0;font-size:13px;color:#5A4A40">Saldo a cobrar <b style="font-size:20px;color:{cor}">{brl(p["saldo"])}</b></div>'
            f'{o_que_fazer(acao_cobranca(p, hoje), cor)}{botao(p["url"])}'))


def bloco_sinal(H, titulo, descricao, cor, itens, hoje, vazio):
    H.append(faixa(titulo, f'{brl(sum(p["montante_sinal"] for p in itens))} · {plural(len(itens))}', descricao, cor))
    if not itens:
        H.append(cartao(f'<span style="font-size:13px;color:{CINZA}">{vazio}</span>'))
        return
    for p in sorted(itens, key=lambda p: (p["data_venda"] or p["criacao"] or hoje, p["id"] or 0)):
        ref = p["data_venda"] or p["criacao"]
        dias = (hoje - ref).days if ref else None
        quando = (f'{"venda" if p["data_venda"] else "pedido criado"} em {dt(ref)}'
                  + (f' · há {dias} dia{"s" if dias != 1 else ""}' if dias and dias > 0 else " · hoje" if dias == 0 else "")) if ref else ""
        rotulo = "Sinal a cobrar" if p["como_pago"] == "Sinal + Saldo" else "Valor cheio a cobrar"
        detalhe = f'{p["como_pago"]}' + (f' ({pct_txt(p["pct"])} de sinal)' if p["como_pago"] == "Sinal + Saldo" else "")
        H.append(cartao(
            f'<div style="font-size:15px;font-weight:bold;color:#3B2A22">Pedido #{p["id"]} · {escape(p["cliente"])}</div>'
            f'<div style="font-size:12px;color:{CINZA};margin:2px 0 0">Responsável: {escape(p["responsavel"])} · {escape(detalhe)} · '
            f'Status da cobrança: {escape(p["status_sinal"] or "vazio")} · {escape(p["estagio"])}{" · " + quando if quando else ""}</div>'
            f'<div style="margin:8px 0 0;font-size:13px;color:#5A4A40">{rotulo} <b style="font-size:20px;color:{cor}">{brl(p["montante_sinal"])}</b></div>'
            f'{o_que_fazer(acao_sinal(p), cor)}{botao(p["url"])}'))


def main():
    args = sys.argv[1:]
    teste = "--teste" in args
    hoje = datetime.now(TZ).date()
    if "--hoje" in args:
        hoje = date.fromisoformat(args[args.index("--hoje") + 1])
    arquivos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--hoje")]
    if not arquivos:
        sys.exit("uso: contas_receber.py ARQUIVO.json [...] [--teste] [--hoje AAAA-MM-DD]")

    vistos, pedidos = set(), []
    for arq in arquivos:
        for rec in json.load(open(arq)).get("records", []):
            if rec["id"] not in vistos:
                vistos.add(rec["id"])
                pedidos.append(pedido(rec))
    ativos = [p for p in pedidos if not perdido(p)]

    # Bloco 1: sinal / valor cheio de vendas concluídas que ainda não foi pago
    sinais = [p for p in ativos if a_cobrar_sinal(p)]
    sinal_emitir = [p for p in sinais if p["status_sinal"] != "Pendente"]
    sinal_aguardando = [p for p in sinais if p["status_sinal"] == "Pendente"]

    # Bloco 2: saldo; em "Sinal + Saldo" o saldo só conta depois que o sinal foi pago
    receber = [p for p in ativos if p["data_saldo"] and p["status_saldo"] != "Pago" and (p["saldo"] or 0) > 0.005
               and not (p["como_pago"] == "Sinal + Saldo" and p["status_sinal"] != "Pago")]
    vencidos = [p for p in receber if p["data_saldo"] < hoje]
    proximos = [p for p in receber if hoje <= p["data_saldo"] <= hoje + timedelta(days=7)]
    futuros = [p for p in receber if p["data_saldo"] > hoje + timedelta(days=7)]

    problemas = [(p, inconsistencias(p)) for p in ativos]
    problemas = [(p, i) for p, i in problemas if i]
    por_resp = {}
    for p, i in problemas:
        por_resp.setdefault(p["responsavel"], []).append((p, i))

    total_sinal = sum(p["montante_sinal"] for p in sinais)
    total_saldo = sum(p["saldo"] for p in receber)

    H = [f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="{FUNDO}" style="background:{FUNDO};border-collapse:collapse"><tr><td align="center" style="padding:16px 8px">'
         f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#ffffff" style="max-width:640px;border-collapse:separate;background:#ffffff;'
         f'border:1px solid {BORDA_CARD};border-radius:10px"><tr><td align="left" style="font-family:Arial,Helvetica,sans-serif;color:#3B2A22;font-size:14px;line-height:1.5">']
    H.append(f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse"><tr>'
             f'<td bgcolor="{TOPO}" style="background:{TOPO};border-radius:10px 10px 0 0;border-bottom:3px solid {LARANJA};padding:18px 20px">'
             f'<div style="font-size:21px;font-weight:bold;color:{MARROM}">💰 Calendário de Contas a Receber</div>'
             f'<div style="font-size:13px;color:#7A4A2E;margin:2px 0 0">e ajustes necessários em cobranças · Can Candles &amp; Wellness · {DIAS[hoje.weekday()]} {hoje.strftime("%d/%m/%Y")}</div></td></tr></table>')

    cel = lambda v, rot, cor, span=1: (f'<td{" colspan=2" if span == 2 else ""} width="{50 * span}%" bgcolor="{TINTA[cor]}" style="background:{TINTA[cor]};border-radius:8px;padding:12px 8px;text-align:center">'
                                       f'<div style="font-size:19px;font-weight:bold;color:{cor}">{v}</div><div style="font-size:12px;color:#3B2A22">{rot}</div></td>')
    H.append('<div style="padding:16px 20px 4px"><p style="margin:0 0 12px">Bom dia, time! Este é o mapa do que temos a receber (sinais, valores cheios e saldos) e dos pedidos que precisam de ajuste no CRM.</p>'
             '<table cellpadding="0" cellspacing="6" width="100%" style="border-collapse:separate">'
             f'<tr>{cel(brl(total_sinal), f"💳 sinal / valor cheio · {plural(len(sinais))}", LARANJA_T, 2)}</tr>'
             f'<tr>{cel(brl(sum(p["saldo"] for p in vencidos)), f"🔴 saldos vencidos · {plural(len(vencidos))}", VERMELHO)}'
             f'{cel(brl(sum(p["saldo"] for p in proximos)), f"🟠 saldos em 7 dias · {plural(len(proximos))}", AMBAR)}</tr>'
             f'<tr>{cel(brl(sum(p["saldo"] for p in futuros)), f"🔵 saldos futuros · {plural(len(futuros))}", AZUL)}'
             f'{cel(str(len(problemas)), "⚠️ pedidos para ajustar", MARROM)}</tr></table>'
             f'<p style="margin:8px 0 0;font-size:14px"><b>Total a receber:</b> {brl(total_sinal + total_saldo)} '
             f'({brl(total_sinal)} em sinais/valores cheios + {brl(total_saldo)} em saldos).</p></div>')

    H.append('<div style="padding:0 16px 20px">')
    H.append(h2("Bloco 1 · Sinal / Valor cheio a cobrar", "Responsável: Área de Contas a Receber · vendas concluídas cujo sinal ou valor cheio ainda não foi pago"))
    bloco_sinal(H, "🔴 Emitir a cobrança", "A cobrança ainda não foi emitida (ou o pagamento não foi encontrado).", VERMELHO, sinal_emitir, hoje,
                "Nenhuma cobrança de sinal ou valor cheio por emitir. 🎉")
    bloco_sinal(H, "🟠 Cobrança emitida, aguardando pagamento", "O cliente já recebeu a cobrança: acompanhar até o pagamento.", AMBAR, sinal_aguardando, hoje,
                "Nenhuma cobrança aguardando pagamento.")

    H.append(h2("Bloco 2 · Saldo a cobrar", "Responsável: Área de Contas a Receber · data estimada do saldo preenchida, sinal já pago e saldo diferente de \"Pago\""))
    tier(H, "🔴 Urgente · casos que venceram", "Data do saldo anterior a hoje: cobrar já.", VERMELHO, vencidos, hoje, "Nenhum saldo vencido. 🎉")
    tier(H, "🟠 Importante · próximos 7 dias", f"Data do saldo entre hoje e {(hoje + timedelta(days=7)).strftime('%d/%m')}: preparar a cobrança.", AMBAR, proximos, hoje, "Nenhum saldo previsto para os próximos 7 dias.")
    tier(H, "🔵 Contas futuras · casos distantes", "Data do saldo daqui a mais de 7 dias: só para visibilidade.", AZUL, futuros, hoje, "Nenhum saldo futuro mapeado.")

    H.append(h2("Bloco 3 · Inconsistências para ajustar", "Responsável: Área de Vendas · cada pessoa ajusta os pedidos sob sua responsabilidade"))
    if not problemas:
        H.append(cartao(f'<span style="font-size:13px;color:{CINZA}">Nenhuma inconsistência encontrada. CRM em dia! 🎉</span>'))
    for resp in sorted(por_resp, key=lambda r: (r == "Sem responsável", r)):
        itens = sorted(por_resp[resp], key=lambda x: x[0]["id"] or 0)
        H.append(faixa(f"👤 {escape(resp)}", f"{plural(len(itens))} para ajustar", "", MARROM))
        for p, inc in itens:
            probs = "".join(f'<div style="margin:10px 0 0;font-size:13px"><b style="color:{VERMELHO}">⚠️ {escape(r)}:</b> {escape(t)}</div>'
                            f'{o_que_fazer(a, VERMELHO)}' for r, t, a in inc)
            H.append(cartao(f'<div style="font-size:15px;font-weight:bold;color:#3B2A22">Pedido #{p["id"]} · {escape(p["cliente"])}</div>'
                            f'<div style="font-size:12px;color:{CINZA};margin:2px 0 0">Estágio: {escape(p["estagio"])}</div>'
                            f'{probs}{botao(p["url"], "Ajustar no Airtable →")}'))

    H.append(f'<div style="font-size:11px;color:{CINZA};margin:24px 0 0;border-top:1px solid {BORDA};padding-top:10px">'
             '<p style="margin:0 0 4px"><b>Como lemos o CRM.</b> Bloco 1: pedidos de "3. Venda concluída" em diante, com pagamento "Sinal + Saldo" ou "Valor cheio" e '
             '"Status da Cobrança do Sinal ou Valor Cheio" diferente de "Pago". O valor é o campo "Montante a ser pago no Sinal ou Valor cheio".</p>'
             '<p style="margin:0 0 4px">Bloco 2: pedidos com "Data estimada para Pagamento do Saldo" preenchida, saldo maior que zero e "Status da Cobrança do Saldo" '
             'diferente de "Pago". Em "Sinal + Saldo", o saldo só entra depois que o sinal foi pago. O valor é o campo "Montante a ser pago no Saldo".</p>'
             '<p style="margin:0 0 4px">Bloco 3: (1) "Sinal + Saldo" com data do saldo preenchida e sinal ainda não pago; (2) "Valor cheio" com percentual diferente de 100% ou com data do saldo preenchida; '
             '(3) "Sinal + Saldo" com data do saldo igual ou anterior à criação do pedido ou ao pagamento do sinal; (4) data desejada de entrega anterior à criação do pedido; '
             f'(5) "Sinal + Saldo" sem data do saldo, só para pedidos criados a partir de {CORTE_DATA_SALDO.strftime("%d/%m/%Y")}.</p>'
             '<p style="margin:0">Pedidos perdidos (estágio "11. Perdido") ficam de fora. Datas no horário de Brasília.</p></div>')
    H.append('<p style="margin:12px 0 0;font-size:13px">Contas a Receber · Can Candles</p></div></td></tr></table></td></tr></table>')

    os.makedirs(SAIDA, exist_ok=True)
    open(os.path.join(SAIDA, "email.html"), "w").write("\n".join(H))
    open(os.path.join(SAIDA, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + ASSUNTO)
    print(f"ok: pedidos={len(pedidos)} ativos={len(ativos)} sinal_emitir={len(sinal_emitir)} sinal_aguardando={len(sinal_aguardando)} "
          f"saldo_vencidos={len(vencidos)} saldo_proximos7={len(proximos)} saldo_futuros={len(futuros)} inconsistencias={len(problemas)} "
          f"total_sinal={brl(total_sinal)} total_saldo={brl(total_saldo)}")


if __name__ == "__main__":
    main()
