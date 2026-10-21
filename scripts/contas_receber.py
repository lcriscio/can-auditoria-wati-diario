"""Monta o e-mail "Calendário de Saldos para Cobrarmos" a partir dos Pedidos do Airtable.

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
ASSUNTO = "💰 Calendário de Saldos para Cobrarmos"
CORTE_DATA_SALDO = date(2026, 10, 20)  # antes disso não registrávamos a data do saldo

MARROM, LARANJA, CREME, BORDA, CINZA = "#56301F", "#E8621E", "#FFF6F1", "#E4D4C8", "#8A7A6E"
VERMELHO, AMBAR, AZUL = "#B23A24", "#C77700", "#2F5D7D"
FUNDO, TOPO, BORDA_CARD = "#FFF1E6", "#FFDDC2", "#F6D9C2"  # laranja bem claro, faixa do topo e bordas
TINTA = {VERMELHO: "#FDE6E1", AMBAR: "#FFF0D4", AZUL: "#E6EFF6", MARROM: "#F8E9DE"}  # fundo claro de cada cor
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

F = {
    "id": "fldZWGWvGg0Y7wdua", "criacao": "fldl9gG0SvY5lmnpe", "contato": "fldXtzo8xOSC6gLsZ",
    "estagio": "fldBIfAlemFpuuo3b", "responsavel": "fldWOPjPp3z3ge1gm", "preco": "fldZNp21mjPqXIY6Y",
    "como_pago": "fldtCRpgKQJy8WOsA", "pct": "fldRbERwNA5K243C2", "saldo": "fldVul9O74meoWwdd",
    "data_sinal": "fldQNRLwkpIpeTG9w", "status_saldo": "fldfDI9vLsR9hqNg2",
    "data_saldo": "fldGRw3BPVdSkwSMi", "data_entrega": "fld9IU7JhtIHNA3k7", "faturamento": "flddTylMfbOi6AsO5",
}


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

    receber = [p for p in ativos if p["data_saldo"] and p["status_saldo"] != "Pago" and (p["saldo"] or 0) > 0.005]
    vencidos = [p for p in receber if p["data_saldo"] < hoje]
    proximos = [p for p in receber if hoje <= p["data_saldo"] <= hoje + timedelta(days=7)]
    futuros = [p for p in receber if p["data_saldo"] > hoje + timedelta(days=7)]

    problemas = [(p, inconsistencias(p)) for p in ativos]
    problemas = [(p, i) for p, i in problemas if i]
    por_resp = {}
    for p, i in problemas:
        por_resp.setdefault(p["responsavel"], []).append((p, i))

    H = [f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="{FUNDO}" style="background:{FUNDO};border-collapse:collapse"><tr><td align="center" style="padding:16px 8px">'
         f'<table cellpadding="0" cellspacing="0" width="100%" bgcolor="#ffffff" style="max-width:640px;border-collapse:separate;background:#ffffff;'
         f'border:1px solid {BORDA_CARD};border-radius:10px"><tr><td align="left" style="font-family:Arial,Helvetica,sans-serif;color:#3B2A22;font-size:14px;line-height:1.5">']
    H.append(f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse"><tr>'
             f'<td bgcolor="{TOPO}" style="background:{TOPO};border-radius:10px 10px 0 0;border-bottom:3px solid {LARANJA};padding:18px 20px">'
             f'<div style="font-size:21px;font-weight:bold;color:{MARROM}">💰 Calendário de Saldos para Cobrarmos</div>'
             f'<div style="font-size:13px;color:#7A4A2E;margin:2px 0 0">Can Candles &amp; Wellness · {DIAS[hoje.weekday()]} {hoje.strftime("%d/%m/%Y")}</div></td></tr></table>')

    tiles = [(brl(sum(p["saldo"] for p in vencidos)), f"🔴 vencidos · {plural(len(vencidos))}", VERMELHO),
             (brl(sum(p["saldo"] for p in proximos)), f"🟠 próximos 7 dias · {plural(len(proximos))}", AMBAR),
             (brl(sum(p["saldo"] for p in futuros)), f"🔵 futuros · {plural(len(futuros))}", AZUL),
             (str(len(problemas)), "⚠️ pedidos com inconsistência", MARROM)]
    cel = lambda v, rot, cor: (f'<td width="50%" bgcolor="{TINTA[cor]}" style="background:{TINTA[cor]};border-radius:8px;padding:12px 8px;text-align:center">'
                               f'<div style="font-size:19px;font-weight:bold;color:{cor}">{v}</div><div style="font-size:12px;color:#3B2A22">{rot}</div></td>')
    H.append('<div style="padding:16px 20px 4px"><p style="margin:0 0 12px">Bom dia, time! Este é o mapa do que temos a receber de saldos e dos pedidos que precisam de ajuste no CRM.</p>'
             '<table cellpadding="0" cellspacing="6" width="100%" style="border-collapse:separate">'
             f'<tr>{cel(*tiles[0])}{cel(*tiles[1])}</tr><tr>{cel(*tiles[2])}{cel(*tiles[3])}</tr></table>'
             f'<p style="margin:8px 0 0;font-size:14px"><b>Total em aberto:</b> {brl(sum(p["saldo"] for p in receber))} em {plural(len(receber))}.</p></div>')

    H.append('<div style="padding:0 16px 20px">')
    H.append(h2("Bloco 1 · O que temos que cobrar", "Responsável: Área de Contas a Receber · pedidos com data estimada do saldo preenchida e status do saldo diferente de \"Pago\""))
    tier(H, "🔴 Urgente · casos que venceram", "Data do saldo anterior a hoje: cobrar já.", VERMELHO, vencidos, hoje, "Nenhum saldo vencido. 🎉")
    tier(H, "🟠 Importante · próximos 7 dias", f"Data do saldo entre hoje e {(hoje + timedelta(days=7)).strftime('%d/%m')}: preparar a cobrança.", AMBAR, proximos, hoje, "Nenhum saldo previsto para os próximos 7 dias.")
    tier(H, "🔵 Contas futuras · casos distantes", "Data do saldo daqui a mais de 7 dias: só para visibilidade.", AZUL, futuros, hoje, "Nenhum saldo futuro mapeado.")

    H.append(h2("Bloco 2 · Inconsistências para ajustar", "Responsável: Área de Vendas · cada pessoa ajusta os pedidos sob sua responsabilidade"))
    if not problemas:
        H.append(f'<p style="margin:0;padding:10px 14px;background:#ffffff;border:1px solid {BORDA};font-size:13px;color:{CINZA}">Nenhuma inconsistência encontrada. CRM em dia! 🎉</p>')
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
             '<p style="margin:0 0 4px"><b>Como lemos o CRM.</b> Bloco 1: pedidos com "Data estimada para Pagamento do Saldo" preenchida, saldo a pagar maior que zero e '
             '"Status da Cobrança do Saldo" diferente de "Pago". O valor é o campo "Montante a ser pago no Saldo".</p>'
             '<p style="margin:0 0 4px">Bloco 2: (1) "Valor cheio" com percentual diferente de 100% ou com data do saldo preenchida; (2) "Sinal + Saldo" com data do saldo igual ou anterior à criação do pedido '
             'ou ao pagamento do sinal; (3) data desejada de entrega anterior à criação do pedido; (4) "Sinal + Saldo" sem data do saldo, só para pedidos criados a partir de '
             f'{CORTE_DATA_SALDO.strftime("%d/%m/%Y")}.</p>'
             '<p style="margin:0">Pedidos perdidos (estágio "11. Perdido") ficam de fora dos dois blocos. Datas no horário de Brasília.</p></div>')
    H.append('<p style="margin:12px 0 0;font-size:13px">Contas a Receber · Can Candles</p></div></td></tr></table></td></tr></table>')

    os.makedirs(SAIDA, exist_ok=True)
    open(os.path.join(SAIDA, "email.html"), "w").write("\n".join(H))
    open(os.path.join(SAIDA, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + ASSUNTO)
    print(f"ok: pedidos={len(pedidos)} ativos={len(ativos)} vencidos={len(vencidos)} proximos7={len(proximos)} "
          f"futuros={len(futuros)} inconsistencias={len(problemas)} total_aberto={brl(sum(p['saldo'] for p in receber))}")


if __name__ == "__main__":
    main()
