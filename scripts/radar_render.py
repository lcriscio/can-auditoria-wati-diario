"""Monta o e-mail do radar a partir de data/radar/coleta.json + avaliacao.json.

Uso: python3 scripts/radar_render.py [--teste]
Gera data/radar/email.html e assunto.txt. Se não houver pendências, imprime pendentes=0 e não gera e-mail.
"""
import html
import json
import os
import sys
from datetime import datetime

D = os.path.join("data", "radar")
ASSUNTO = "⚠️ Atenção: existem contatos esperando nossa resposta"
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
BTN = ("background:#2b2622;color:#ffffff;text-decoration:none;font-size:13px;font-weight:bold;"
       "padding:10px 18px;border-radius:6px;display:inline-block;")


def e(s):
    return html.escape(str(s or ""))


def fone_fmt(f):
    f = "".join(ch for ch in str(f) if ch.isdigit())
    if f.startswith("55") and len(f) >= 12:
        return f"+55 {f[2:4]} {f[4:-4]}-{f[-4:]}"
    return "+" + f


def quando(iso):
    t = datetime.fromisoformat(iso)
    return f"{t:%d/%m} às {t:%H:%M}"


def card(it, cor):
    extra = " (fora do horário)" if it["fora_do_horario"] else ""
    etapa = f" ({e(it['etapa'])})" if it.get("etapa") else ""
    botao = (f'<div style="padding-top:14px;"><a href="{e(it["link"])}" style="{BTN}">Abrir conversa no WATI →</a></div>'
             if it.get("link") else "")
    return f'''<tr><td style="background:#ffffff;padding:8px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #eee5da;border-left:4px solid {cor};border-radius:8px;"><tr><td style="padding:16px 18px;">
<div style="font-size:16px;font-weight:bold;">{e(it["nome"])} <span style="font-weight:normal;color:#7a6f66;font-size:13px;">· {e(fone_fmt(it["fone"]))}</span></div>
<div style="font-size:13px;color:#7a6f66;padding-top:4px;">Atendente: <b style="color:#2b2622;">{e(it["atendente"] or "Sem atendente definido")}</b> · aguardando desde {quando(it["aguardando_desde"])}{extra}</div>
<div style="background:#faf6f0;border-radius:6px;padding:10px 12px;margin-top:10px;font-size:13px;line-height:19px;color:#4a423b;">{e(it["resumo"])}</div>
<div style="font-size:13px;line-height:19px;padding-top:10px;"><b style="color:{cor};">O que fazer{etapa}:</b> {e(it["recomendacao"])}</div>
{botao}
</td></tr></table>
</td></tr>'''


def bloco(rotulo, titulo, sub, itens, cor):
    if not itens:
        return ""
    return f'''<tr><td style="background:#ffffff;padding:24px 28px 8px 28px;">
<div style="font-size:12px;letter-spacing:1.5px;color:{cor};text-transform:uppercase;font-weight:bold;">{rotulo}</div>
<div style="font-size:18px;font-weight:bold;padding-top:4px;">{titulo}</div>
<div style="font-size:13px;color:#7a6f66;padding-top:4px;">{sub}</div>
</td></tr>''' + "".join(card(i, cor) for i in itens)


def main():
    teste = "--teste" in sys.argv
    coleta = json.load(open(os.path.join(D, "coleta.json")))
    aval = json.load(open(os.path.join(D, "avaliacao.json")))
    por_fone = {c["fone"]: c for c in coleta["candidatos"]}
    itens = []
    for a in aval.get("itens", []):
        c = por_fone.get(a.get("fone"))
        if not c or a.get("bloco") not in (1, 2):
            continue
        itens.append({**c, **{k: v for k, v in a.items() if v}, "atendente": a.get("atendente") or c.get("atendente")})
    itens.sort(key=lambda x: x["aguardando_desde"])
    b1 = [i for i in itens if i["bloco"] == 1]
    b2 = [i for i in itens if i["bloco"] == 2]
    for nome in ("email.html", "assunto.txt"):
        if os.path.exists(os.path.join(D, nome)):
            os.remove(os.path.join(D, nome))
    if not itens:
        print("pendentes=0 (não enviar e-mail)")
        return

    agora = datetime.fromisoformat(coleta["agora"])
    por_at = {}
    for i in itens:
        k = (i["atendente"] or "Sem atendente").split()[0]
        por_at[k] = por_at.get(k, 0) + 1
    at_html = "<br>".join(f"<b>{e(k)}:</b> {v}" for k, v in sorted(por_at.items(), key=lambda x: -x[1]))
    n = len(itens)
    titulo = f"{n} contato esperando nossa resposta" if n == 1 else f"{n} contatos esperando nossa resposta"
    faixa = ('<tr><td style="background:#fff7d6;border:1px dashed #c9a227;border-radius:10px;padding:10px 16px;'
             'font-size:13px;color:#6b5300;"><b>TESTE.</b> Enviado só para o Leo, com conversas reais lidas no WATI.'
             '</td></tr><tr><td style="height:16px;"></td></tr>') if teste else ""

    corpo = f'''<div style="margin:0;padding:0;background:#f6f1ea;font-family:Helvetica,Arial,sans-serif;color:#2b2622;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f1ea;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">
{faixa}
<tr><td style="background:#2b2622;border-radius:14px 14px 0 0;padding:26px 28px;">
<div style="font-size:12px;letter-spacing:2px;color:#e8a87c;text-transform:uppercase;">Can Candles &amp; Wellness · Radar de atendimento</div>
<div style="font-size:24px;line-height:30px;color:#ffffff;font-weight:bold;padding-top:8px;">{titulo}</div>
<div style="font-size:14px;color:#cfc6bd;padding-top:6px;">{DIAS[agora.weekday()]}, {agora:%d/%m} · {agora:%H:%M} · conversas desde {datetime.fromisoformat(coleta["desde"]):%d/%m}</div>
</td></tr>
<tr><td style="background:#ffffff;padding:20px 28px;border-bottom:1px solid #eee5da;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td width="33%" align="center" style="padding:6px;"><div style="font-size:28px;font-weight:bold;color:#c2410c;">{len(b1)}</div><div style="font-size:12px;color:#7a6f66;">sem boas-vindas</div></td>
<td width="33%" align="center" style="padding:6px;border-left:1px solid #eee5da;"><div style="font-size:28px;font-weight:bold;color:#b45309;">{len(b2)}</div><div style="font-size:12px;color:#7a6f66;">sem resposta</div></td>
<td width="34%" align="center" style="padding:6px;border-left:1px solid #eee5da;"><div style="font-size:13px;line-height:20px;color:#2b2622;">{at_html}</div><div style="font-size:12px;color:#7a6f66;">por atendente</div></td>
</tr></table>
</td></tr>
{bloco("Bloco 1 · A de Acolher", "Chegaram e ainda não receberam boas-vindas", "Meta do método: 1ª resposta em até 5 min no horário comercial.", b1, "#c2410c")}
{bloco("Bloco 2 · Conversas em aberto", "Pediram algo e ficaram sem resposta", "Inclui casos em que prometemos retornar. Regra de ouro: nunca terminar sem um próximo passo.", b2, "#b45309")}
<tr><td style="background:#ffffff;height:16px;"></td></tr>
<tr><td style="background:#2b2622;border-radius:0 0 14px 14px;padding:20px 28px;">
<div style="font-size:14px;color:#ffffff;font-style:italic;">“Toda conversa é o começo de um momento feliz de alguém.”</div>
<div style="font-size:12px;color:#cfc6bd;padding-top:8px;line-height:18px;">Acolher · Revelar · Orientar · Materializar · Avançar<br>Alerta automático em dias úteis, das 8h às 18h. Só é enviado quando existe alguém esperando.</div>
</td></tr>
</table>
</td></tr></table>
</div>'''
    open(os.path.join(D, "email.html"), "w").write(corpo)
    open(os.path.join(D, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + ASSUNTO)
    print(f"pendentes={n} bloco1={len(b1)} bloco2={len(b2)} -> {D}/email.html")


if __name__ == "__main__":
    main()
