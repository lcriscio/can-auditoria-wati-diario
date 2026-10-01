"""Monta o e-mail do radar a partir de data/radar/coleta.json + avaliacao.json.

Uso: python3 scripts/radar_render.py [--teste]
Gera data/radar/email.html e assunto.txt. Se não houver pendências, imprime pendentes=0 e não gera e-mail.
As cores de fundo vão no atributo bgcolor: o Gmail descarta `background` do style.
"""
import html
import json
import os
import sys
from datetime import datetime

D = os.path.join("data", "radar")
ASSUNTO = "⚠️ Atenção: existem contatos esperando nossa resposta"
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
FUNDO, PAPEL, AREIA = "#f1dfcb", "#fbf1e4", "#f3dcc0"
LARANJA, TERRACOTA, MARROM, TEXTO, SUAVE = "#b3470d", "#9a3412", "#4a2c17", "#3b2a1e", "#7d6552"
PESSEGO, MOSTARDA, ARGILA = "#f9d4b4", "#f3dfa6", "#e9c9b3"
T = 'role="presentation" cellpadding="0" cellspacing="0" border="0"'
# atributos em constantes: Python < 3.12 não aceita aspas iguais às da f-string dentro de {}
AC, W6, SELO, TILE = 'align="center"', 'width="6"', 'align="center" width="1"', 'align="center" width="31%"'


def e(s):
    return html.escape(str(s or ""))


def td(cor, estilo="", extra=""):
    return f'<td bgcolor="{cor}" style="background-color:{cor};{estilo}" {extra}>'


def fone_fmt(f):
    f = "".join(ch for ch in str(f) if ch.isdigit())
    if f.startswith("55") and len(f) >= 12:
        return f"+55 {f[2:4]} {f[4:-4]}-{f[-4:]}"
    return "+" + f


def quando(iso):
    t = datetime.fromisoformat(iso)
    return f"{t:%d/%m} às {t:%H:%M}"


def espera(iso, agora):
    m = int((agora - datetime.fromisoformat(iso)).total_seconds() // 60)
    if m < 60:
        return f"{m} min"
    h = m // 60
    return f"{h} h" if h < 24 else f"{h // 24} d {h % 24} h"


def card(it, cor, agora):
    extra = " (fora do horário)" if it["fora_do_horario"] else ""
    etapa = f" · {e(it['etapa'])}" if it.get("etapa") else ""
    nome = e(it["nome"])
    botao = ""
    if it.get("link"):
        url = e(it["link"])
        nome = f'<a href="{url}" style="color:{TEXTO};text-decoration:underline;">{nome}</a>'
        botao = (f'<table {T} style="margin-top:14px;"><tr>{td(cor, "border-radius:6px;padding:11px 20px;", AC)}'
                 f'<a href="{url}" target="_blank" style="color:#ffffff;text-decoration:none;font-size:14px;font-weight:bold;">'
                 f'Abrir conversa no WATI &rarr;</a></td></tr></table>')
    return f'''<tr>{td(PAPEL, "padding:8px 24px;")}
<table {T} width="100%"><tr>
{td(cor, "width:6px;font-size:1px;", W6)}&nbsp;</td>
{td("#fffaf3", f"padding:16px 18px;border:1px solid {ARGILA};border-left:0;")}
<table {T} width="100%"><tr>
<td style="font-size:17px;font-weight:bold;color:{TEXTO};">{nome} <span style="font-weight:normal;color:{SUAVE};font-size:13px;">· {e(fone_fmt(it["fone"]))}</span></td>
{td(PESSEGO, f"padding:4px 10px;border-radius:12px;font-size:12px;font-weight:bold;color:{TERRACOTA};white-space:nowrap;", SELO)}⏳ {espera(it["aguardando_desde"], agora)}</td>
</tr></table>
<div style="font-size:13px;color:{SUAVE};padding-top:6px;">Atendente: <b style="color:{TEXTO};">{e(it["atendente"] or "Sem atendente definido")}</b> · aguardando desde {quando(it["aguardando_desde"])}{extra}</div>
<table {T} width="100%" style="margin-top:10px;"><tr>{td(AREIA, f"padding:10px 12px;border-radius:6px;font-size:13px;line-height:19px;color:{TEXTO};")}<b>O que aconteceu:</b> {e(it["resumo"])}</td></tr></table>
<table {T} width="100%" style="margin-top:8px;"><tr>{td(MOSTARDA, f"padding:10px 12px;border-radius:6px;font-size:13px;line-height:19px;color:{TEXTO};")}<b style="color:{TERRACOTA};">O que fazer{etapa}:</b> {e(it["recomendacao"])}</td></tr></table>
{botao}
</td></tr></table>
</td></tr>'''


def bloco(rotulo, titulo, sub, itens, cor, agora):
    if not itens:
        return ""
    return f'''<tr>{td(PAPEL, "padding:22px 24px 6px 24px;")}
<table {T} width="100%"><tr>{td(cor, "padding:12px 16px;border-radius:8px;")}
<div style="font-size:11px;letter-spacing:1.5px;color:{PESSEGO};text-transform:uppercase;font-weight:bold;">{rotulo}</div>
<div style="font-size:18px;font-weight:bold;color:#ffffff;padding-top:3px;">{titulo}</div>
<div style="font-size:13px;color:#fbe9d7;padding-top:3px;">{sub}</div>
</td></tr></table>
</td></tr>''' + "".join(card(i, cor, agora) for i in itens)


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
    faixa = (f'<tr>{td(MOSTARDA, "border:1px dashed #b98a1a;border-radius:10px;padding:10px 16px;font-size:13px;color:#6b5300;")}'
             f'<b>TESTE.</b> Enviado só para o Leo, com conversas reais lidas no WATI.</td></tr>'
             f'<tr><td style="height:14px;font-size:1px;">&nbsp;</td></tr>') if teste else ""

    def tile(cor, numero, legenda, cor_num):
        return (f'{td(cor, "padding:14px 8px;border-radius:10px;", TILE)}'
                f'<div style="font-size:30px;font-weight:bold;color:{cor_num};">{numero}</div>'
                f'<div style="font-size:12px;color:{TEXTO};">{legenda}</div></td>')

    corpo = f'''<table {T} width="100%" bgcolor="{FUNDO}" style="background-color:{FUNDO};font-family:Helvetica,Arial,sans-serif;color:{TEXTO};"><tr>{td(FUNDO, "padding:24px 12px;", AC)}
<table {T} width="640" style="max-width:640px;width:100%;">
{faixa}
<tr>{td(TERRACOTA, "border-radius:14px 14px 0 0;padding:26px 28px;")}
<div style="font-size:12px;letter-spacing:2px;color:{PESSEGO};text-transform:uppercase;">Can Candles &amp; Wellness · Radar de atendimento</div>
<div style="font-size:25px;line-height:31px;color:#ffffff;font-weight:bold;padding-top:8px;">⚠️ {titulo}</div>
<div style="font-size:14px;color:#fbe9d7;padding-top:6px;">{DIAS[agora.weekday()]}, {agora:%d/%m} · {agora:%H:%M} · conversas desde {datetime.fromisoformat(coleta["desde"]):%d/%m}</div>
</td></tr>
<tr>{td(AREIA, "padding:18px 24px;")}
<table {T} width="100%"><tr>
{tile(PESSEGO, len(b1), "sem boas-vindas", TERRACOTA)}
<td width="3.5%">&nbsp;</td>
{tile(MOSTARDA, len(b2), "sem resposta", LARANJA)}
<td width="3.5%">&nbsp;</td>
{td(ARGILA, "padding:14px 8px;border-radius:10px;", TILE)}<div style="font-size:13px;line-height:20px;color:{TEXTO};">{at_html}</div><div style="font-size:12px;color:{TEXTO};">por atendente</div></td>
</tr></table>
</td></tr>
{bloco("Bloco 1 · A de Acolher", "Chegaram e ainda não receberam boas-vindas", "Meta do método: 1ª resposta em até 5 min no horário comercial.", b1, TERRACOTA, agora)}
{bloco("Bloco 2 · Conversas em aberto", "Pediram algo e ficaram sem resposta", "Inclui casos em que prometemos retornar. Nunca terminar sem um próximo passo.", b2, LARANJA, agora)}
<tr>{td(PAPEL, "height:18px;font-size:1px;")}&nbsp;</td></tr>
<tr>{td(MARROM, "border-radius:0 0 14px 14px;padding:20px 28px;")}
<div style="font-size:14px;color:#ffffff;font-style:italic;">“Toda conversa é o começo de um momento feliz de alguém.”</div>
<div style="font-size:12px;color:{ARGILA};padding-top:8px;line-height:18px;">Acolher · Revelar · Orientar · Materializar · Avançar<br>Alerta automático em dias úteis, de hora em hora, das 8h às 18h. Só entra quem espera há mais de 30 minutos.</div>
</td></tr>
</table>
</td></tr></table>'''
    open(os.path.join(D, "email.html"), "w").write(corpo)
    open(os.path.join(D, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + ASSUNTO)
    print(f"pendentes={n} bloco1={len(b1)} bloco2={len(b2)} -> {D}/email.html")


if __name__ == "__main__":
    main()
