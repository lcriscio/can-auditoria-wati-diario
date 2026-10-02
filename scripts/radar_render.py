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
BRANCO, CREME, LINHA = "#ffffff", "#fdf6ee", "#f0e2d3"
LARANJA, TERRACOTA, TEXTO, SUAVE = "#c2571a", "#9a3412", "#3b2a1e", "#8a7565"
PESSEGO, MOSTARDA = "#fdebdc", "#fbf3d9"
T = 'role="presentation" cellpadding="0" cellspacing="0" border="0"'
# atributos em constantes: Python < 3.12 não aceita aspas iguais às da f-string dentro de {}
AC, SELO, TILE = 'align="center"', 'align="right" width="1"', 'align="center" width="31%"'


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
    abrir = ""
    if it.get("link"):
        url = e(it["link"])
        abrir = (f' · <a href="{url}" target="_blank" style="color:{LARANJA};font-weight:normal;font-size:13px;'
                 f'text-decoration:underline;white-space:nowrap;">abrir conversa no WATI &#8599;</a>')
    return f'''<tr>{td(BRANCO, "padding:8px 28px;")}
<table {T} width="100%"><tr>
{td(BRANCO, f"padding:16px 18px;border:1px solid {LINHA};border-left:3px solid {cor};border-radius:8px;")}
<table {T} width="100%"><tr>
<td style="font-size:16px;font-weight:bold;color:{TEXTO};">{e(it["nome"])} <span style="font-weight:normal;color:{SUAVE};font-size:13px;">· {e(fone_fmt(it["fone"]))}</span>{abrir}</td>
{td(PESSEGO, f"padding:3px 10px;border-radius:12px;font-size:12px;color:{TERRACOTA};white-space:nowrap;", SELO)}⏳ {espera(it["aguardando_desde"], agora)}</td>
</tr></table>
<div style="font-size:13px;color:{SUAVE};padding-top:6px;">Atendente: <b style="color:{TEXTO};">{e(it["atendente"] or "Sem atendente definido")}</b> · aguardando desde {quando(it["aguardando_desde"])}{extra}</div>
<div style="font-size:13px;line-height:20px;color:{TEXTO};padding-top:10px;"><b>O que aconteceu:</b> {e(it["resumo"])}</div>
<table {T} width="100%" style="margin-top:10px;"><tr>{td(CREME, f"padding:10px 12px;border-radius:6px;font-size:13px;line-height:20px;color:{TEXTO};")}<b style="color:{cor};">O que fazer{etapa}:</b> {e(it["recomendacao"])}</td></tr></table>
</td></tr></table>
</td></tr>'''


def bloco(rotulo, titulo, sub, itens, cor, agora):
    if not itens:
        return ""
    return f'''<tr>{td(BRANCO, "padding:26px 28px 6px 28px;")}
<div style="font-size:11px;letter-spacing:1.5px;color:{cor};text-transform:uppercase;font-weight:bold;">{rotulo}</div>
<div style="font-size:18px;font-weight:bold;color:{TEXTO};padding-top:3px;">{titulo}</div>
<div style="font-size:13px;color:{SUAVE};padding-top:3px;">{sub}</div>
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
    faixa = (f'<tr>{td(MOSTARDA, "border-radius:8px;padding:9px 16px;font-size:12px;color:#6b5300;")}'
             f'<b>TESTE.</b> Enviado só para o Leo, com conversas reais lidas no WATI.</td></tr>'
             f'<tr><td style="height:12px;font-size:1px;">&nbsp;</td></tr>') if teste else ""

    def tile(cor, numero, legenda, cor_num):
        return (f'{td(cor, "padding:12px 8px;border-radius:10px;", TILE)}'
                f'<div style="font-size:26px;font-weight:bold;color:{cor_num};">{numero}</div>'
                f'<div style="font-size:12px;color:{SUAVE};">{legenda}</div></td>')

    corpo = f'''<table {T} width="100%" bgcolor="{BRANCO}" style="background-color:{BRANCO};font-family:Helvetica,Arial,sans-serif;color:{TEXTO};"><tr>{td(BRANCO, "padding:20px 12px;", AC)}
<table {T} width="640" style="max-width:640px;width:100%;">
{faixa}
<tr>{td(CREME, f"border-radius:12px 12px 0 0;border-bottom:2px solid {LARANJA};padding:24px 28px;")}
<div style="font-size:11px;letter-spacing:2px;color:{LARANJA};text-transform:uppercase;">Can Candles &amp; Wellness · Radar de atendimento</div>
<div style="font-size:23px;line-height:30px;color:{TEXTO};font-weight:bold;padding-top:8px;">{titulo}</div>
<div style="font-size:13px;color:{SUAVE};padding-top:5px;">{DIAS[agora.weekday()]}, {agora:%d/%m} · {agora:%H:%M} · conversas desde {datetime.fromisoformat(coleta["desde"]):%d/%m}</div>
</td></tr>
<tr>{td(BRANCO, "padding:18px 28px 0 28px;")}
<table {T} width="100%"><tr>
{tile(PESSEGO, len(b1), "contatos novos", TERRACOTA)}
<td width="3.5%">&nbsp;</td>
{tile(MOSTARDA, len(b2), "contatos antigos", LARANJA)}
<td width="3.5%">&nbsp;</td>
{td(CREME, "padding:12px 8px;border-radius:10px;", TILE)}<div style="font-size:13px;line-height:19px;color:{TEXTO};">{at_html}</div><div style="font-size:12px;color:{SUAVE};">por atendente</div></td>
</tr></table>
</td></tr>
{bloco("Contatos novos · A de Acolher", "Chegaram e ainda não receberam o primeiro atendimento", "Primeira mensagem no WhatsApp da Can há mais de 5 minutos, sem resposta de uma atendente.", b1, TERRACOTA, agora)}
{bloco("Contatos antigos · Conversas em aberto", "Já em conversa conosco e esperando nossa resposta", "Sem resposta há mais de 30 minutos, ou com retorno prometido por nós e prazo vencido.", b2, LARANJA, agora)}
<tr>{td(BRANCO, f"padding:22px 28px 8px 28px;")}
<div style="border-top:1px solid {LINHA};padding-top:14px;font-size:13px;color:{TEXTO};font-style:italic;">“Toda conversa é o começo de um momento feliz de alguém.”</div>
<div style="font-size:11px;color:{SUAVE};padding-top:6px;line-height:17px;">Acolher · Revelar · Orientar · Materializar · Avançar<br>Alerta automático em dias úteis, a cada 1h30, das 9h às 18h. Contato novo entra após 5 minutos sem atendimento; contato antigo, após 30 minutos sem resposta.</div>
</td></tr>
</table>
</td></tr></table>'''
    open(os.path.join(D, "email.html"), "w").write(corpo)
    open(os.path.join(D, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + ASSUNTO)
    print(f"pendentes={n} bloco1={len(b1)} bloco2={len(b2)} -> {D}/email.html")


if __name__ == "__main__":
    main()
