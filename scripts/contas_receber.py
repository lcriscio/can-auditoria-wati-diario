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
BASE, TABELA = "appza7P3RBl5OYQZv", "tblF4spbwfP25MItI"
SAIDA = "data/contas"
ASSUNTO = "💰 Calendário de Saldos para Cobrarmos"
CORTE_DATA_SALDO = date(2026, 10, 20)  # antes disso não registrávamos a data do saldo

MARROM, LARANJA, CREME, BORDA, CINZA = "#56301F", "#E8621E", "#FFF6F1", "#E4D4C8", "#8A7A6E"
VERMELHO, AMBAR, AZUL = "#B23A24", "#C77700", "#2F5D7D"
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
        "url": f"https://airtable.com/{BASE}/{TABELA}/{rec['id']}",
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
    """Lista de (regra, explicação) para um pedido não perdido."""
    out = []
    cp, ds, cr = p["como_pago"], p["data_saldo"], p["criacao"]
    if cp == "Valor cheio" and (p["pct"] is None or abs(p["pct"] - 1) > 0.001):
        out.append(("Valor cheio sem 100%",
                    f'Pagamento "Valor cheio", mas o percentual pago está em {pct_txt(p["pct"])}. Deveria ser 100%.'))
    if cp == "Sinal + Saldo" and ds:
        if cr and ds <= cr:
            out.append(("Data do saldo ≤ criação",
                        f'Data do saldo ({dt(ds)}) é igual ou anterior à criação do pedido ({dt(cr)}).'))
        elif p["data_sinal"] and ds <= p["data_sinal"]:
            out.append(("Data do saldo ≤ pagamento do sinal",
                        f'Data do saldo ({dt(ds)}) é igual ou anterior ao pagamento do sinal ({dt(p["data_sinal"])}).'))
    if p["data_entrega"] and cr and p["data_entrega"] < cr:
        out.append(("Entrega antes da criação",
                    f'Data desejada de entrega ({dt(p["data_entrega"])}) é anterior à criação do pedido ({dt(cr)}).'))
    if cp == "Sinal + Saldo" and not ds and cr and cr >= CORTE_DATA_SALDO:
        out.append(("Sinal + Saldo sem data do saldo",
                    'Pagamento "Sinal + Saldo", mas a data estimada do saldo está vazia.'))
    return out


def botao(url, texto="Abrir no Airtable →"):
    return (f'<a href="{url}" style="display:inline-block;background:{LARANJA};color:#ffffff;text-decoration:none;'
            f'font-size:12px;font-weight:bold;padding:6px 10px;border-radius:4px;white-space:nowrap">{texto}</a>')


def h2(t, sub):
    return (f'<h2 style="color:{MARROM};font-size:18px;margin:28px 0 2px">{t}</h2>'
            f'<p style="margin:0 0 10px;font-size:12px;color:{CINZA}">{sub}</p>')


def tier(H, titulo, descricao, cor, itens, hoje, vazio):
    total = sum(p["saldo"] for p in itens)
    H.append(f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:14px 0 0">'
             f'<tr><td bgcolor="{cor}" style="background:{cor};color:#ffffff;padding:10px 14px">'
             f'<span style="font-size:15px;font-weight:bold">{titulo}</span>'
             f'<span style="float:right;font-size:15px;font-weight:bold">{brl(total)} · {len(itens)} pedido{"s" if len(itens) != 1 else ""}</span>'
             f'<div style="font-size:12px;opacity:.9">{descricao}</div></td></tr></table>')
    if not itens:
        H.append(f'<p style="margin:0;padding:10px 14px;border:1px solid {BORDA};border-top:0;font-size:13px;color:{CINZA}">{vazio}</p>')
        return
    H.append(f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;border:1px solid {BORDA};border-top:0;font-size:13px">')
    dia_atual = None
    for p in sorted(itens, key=lambda p: (p["data_saldo"], p["id"] or 0)):
        d = p["data_saldo"]
        if d != dia_atual:
            dia_atual = d
            do_dia = [x for x in itens if x["data_saldo"] == d]
            delta = (d - hoje).days
            rel = "hoje" if delta == 0 else (f"venceu há {-delta} dia{'s' if delta < -1 else ''}" if delta < 0 else f"em {delta} dia{'s' if delta > 1 else ''}")
            H.append(f'<tr><td colspan="3" bgcolor="{CREME}" style="background:{CREME};padding:6px 14px;border-top:1px solid {BORDA}">'
                     f'<b style="color:{cor}">📅 {dt(d)}</b> <span style="color:{CINZA};font-size:12px">· {rel} · {brl(sum(x["saldo"] for x in do_dia))}</span></td></tr>')
        H.append(f'<tr><td style="padding:8px 14px;border-top:1px solid {BORDA}">'
                 f'<b>Pedido #{p["id"]}</b> · {escape(p["cliente"])}'
                 f'<div style="font-size:12px;color:{CINZA}">{escape(p["responsavel"])} · status do saldo: {escape(p["status_saldo"] or "vazio")}</div></td>'
                 f'<td align="right" style="padding:8px 8px;border-top:1px solid {BORDA};white-space:nowrap"><b style="font-size:14px">{brl(p["saldo"])}</b></td>'
                 f'<td align="right" width="150" style="padding:8px 14px 8px 0;border-top:1px solid {BORDA}">{botao(p["url"])}</td></tr>')
    H.append("</table>")


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

    H = [f'<div style="font-family:Arial,Helvetica,sans-serif;color:#3B2A22;font-size:14px;line-height:1.5;max-width:700px;margin:0 auto">']
    H.append(f'<div style="background:{MARROM};color:#ffffff;padding:18px 20px">'
             f'<div style="font-size:20px;font-weight:bold">💰 Calendário de Saldos para Cobrarmos</div>'
             f'<div style="font-size:13px;opacity:.85">Can Candles &amp; Wellness · {DIAS[hoje.weekday()]} {hoje.strftime("%d/%m/%Y")} · fonte: Pedidos no Airtable</div></div>')

    tiles = [(brl(sum(p["saldo"] for p in vencidos)), f"🔴 vencidos ({len(vencidos)})", VERMELHO),
             (brl(sum(p["saldo"] for p in proximos)), f"🟠 próximos 7 dias ({len(proximos)})", AMBAR),
             (brl(sum(p["saldo"] for p in futuros)), f"🔵 futuros ({len(futuros)})", AZUL),
             (str(len(problemas)), "⚠️ pedidos com inconsistência", MARROM)]
    H.append(f'<div style="background:{CREME};padding:16px 20px"><p style="margin:0 0 10px">Bom dia, time! Este é o mapa do que temos a receber de saldos e dos pedidos que precisam de ajuste no CRM.</p>'
             '<table cellpadding="0" cellspacing="6" width="100%" style="text-align:center"><tr>')
    for v, rot, cor in tiles:
        H.append(f'<td width="25%" style="padding:10px 4px;border:1px solid {BORDA};background:#ffffff">'
                 f'<div style="font-size:17px;font-weight:bold;color:{cor}">{v}</div><div style="font-size:11px">{rot}</div></td>')
    H.append(f'</tr></table><p style="margin:10px 0 0;font-size:13px"><b>Total em aberto:</b> {brl(sum(p["saldo"] for p in receber))} em {len(receber)} pedido{"s" if len(receber) != 1 else ""}.</p></div>')

    H.append(h2("Bloco 1 · O que temos que cobrar", "Responsável: Área de Contas a Receber · pedidos com data estimada do saldo preenchida e status do saldo diferente de \"Pago\""))
    tier(H, "🔴 Urgente · casos que venceram", "Data do saldo anterior a hoje: cobrar já.", VERMELHO, vencidos, hoje, "Nenhum saldo vencido. 🎉")
    tier(H, "🟠 Importante · próximos 7 dias", f"Data do saldo entre hoje e {(hoje + timedelta(days=7)).strftime('%d/%m')}: preparar a cobrança.", AMBAR, proximos, hoje, "Nenhum saldo previsto para os próximos 7 dias.")
    tier(H, "🔵 Contas futuras · casos distantes", "Data do saldo daqui a mais de 7 dias: só para visibilidade.", AZUL, futuros, hoje, "Nenhum saldo futuro mapeado.")

    H.append(h2("Bloco 2 · Inconsistências para ajustar", "Responsável: Área de Vendas · cada pessoa ajusta os pedidos sob sua responsabilidade"))
    if not problemas:
        H.append(f'<p style="margin:0;padding:10px 14px;border:1px solid {BORDA};font-size:13px;color:{CINZA}">Nenhuma inconsistência encontrada. CRM em dia! 🎉</p>')
    for resp in sorted(por_resp, key=lambda r: (r == "Sem responsável", r)):
        itens = sorted(por_resp[resp], key=lambda x: x[0]["id"] or 0)
        H.append(f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:14px 0 0;border:1px solid {BORDA};font-size:13px">'
                 f'<tr><td colspan="2" bgcolor="{MARROM}" style="background:{MARROM};color:#ffffff;padding:8px 14px;font-weight:bold">'
                 f'👤 {escape(resp)} · {len(itens)} pedido{"s" if len(itens) != 1 else ""} para ajustar</td></tr>')
        for p, inc in itens:
            lis = "".join(f'<li style="margin:2px 0"><b style="color:{VERMELHO}">{escape(r)}:</b> {escape(t)}</li>' for r, t in inc)
            H.append(f'<tr><td style="padding:8px 14px;border-top:1px solid {BORDA}"><b>Pedido #{p["id"]}</b> · {escape(p["cliente"])}'
                     f'<span style="font-size:12px;color:{CINZA}"> · {escape(p["estagio"])}</span>'
                     f'<ul style="margin:4px 0 0;padding-left:18px">{lis}</ul></td>'
                     f'<td align="right" valign="top" width="150" style="padding:8px 14px 8px 0;border-top:1px solid {BORDA}">{botao(p["url"], "Ajustar no Airtable →")}</td></tr>')
        H.append("</table>")

    H.append(f'<div style="font-size:11px;color:{CINZA};margin:24px 0 0;border-top:1px solid {BORDA};padding-top:10px">'
             '<p style="margin:0 0 4px"><b>Como lemos o CRM.</b> Bloco 1: pedidos com "Data estimada para Pagamento do Saldo" preenchida, saldo a pagar maior que zero e '
             '"Status da Cobrança do Saldo" diferente de "Pago". O valor é o campo "Montante a ser pago no Saldo".</p>'
             '<p style="margin:0 0 4px">Bloco 2: (1) "Valor cheio" com percentual diferente de 100%; (2) "Sinal + Saldo" com data do saldo igual ou anterior à criação do pedido '
             'ou ao pagamento do sinal; (3) data desejada de entrega anterior à criação do pedido; (4) "Sinal + Saldo" sem data do saldo, só para pedidos criados a partir de '
             f'{CORTE_DATA_SALDO.strftime("%d/%m/%Y")}.</p>'
             '<p style="margin:0">Pedidos perdidos (estágio "11. Perdido") ficam de fora dos dois blocos. Datas no horário de Brasília.</p></div>')
    H.append('<p style="margin:12px 0 0;font-size:13px">Contas a Receber · Can Candles</p></div>')

    os.makedirs(SAIDA, exist_ok=True)
    open(os.path.join(SAIDA, "email.html"), "w").write("\n".join(H))
    open(os.path.join(SAIDA, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + ASSUNTO)
    print(f"ok: pedidos={len(pedidos)} ativos={len(ativos)} vencidos={len(vencidos)} proximos7={len(proximos)} "
          f"futuros={len(futuros)} inconsistencias={len(problemas)} total_aberto={brl(sum(p['saldo'] for p in receber))}")


if __name__ == "__main__":
    main()
