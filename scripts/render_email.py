"""Monta o e-mail HTML da auditoria a partir de coleta.json + avaliacao.json.

Uso: python3 scripts/render_email.py data/AAAA-MM-DD [--teste]
Gera data/AAAA-MM-DD/email.html e data/AAAA-MM-DD/assunto.txt.
"""
import json
import os
import statistics
import sys
from datetime import date
from html import escape

MARROM, LARANJA, CREME, BORDA, CINZA = "#56301F", "#E8621E", "#FFF6F1", "#E4D4C8", "#8A7A6E"
VERDE, VERMELHO = "#2F7D4F", "#B23A24"
DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
LETRAS = [("A", "A · Acolher"), ("R", "R · Revelar"), ("O", "O · Orientar"), ("M", "M · Materializar"), ("V", "A · Avançar")]
ALERTAS = {
    "preco_cedo": "preço/mínimo antes de entender o momento",
    "sem_ocasiao": "pulou a pergunta de ocasião",
    "cadastro_cedo": "pediu CNPJ/CEP/e-mail antes do momento",
    "pdf_sozinho": "PDF sem contexto",
    "catalogo": "textão de catálogo",
    "sem_proximo_passo": "sem próximo passo / \"me avise\"",
    "conseguiu_analisar": "\"conseguiu analisar?\"",
    "convite_desconto": "convite a desconto",
    "followup_vazio": "follow-up sem novidade",
    "objecao_mal_tratada": "objeção não isolada",
    "audio_longo": "áudio longo sem o cliente usar áudio",
    "intermediario_sem_resumo": "intermediário sem resumo encaminhável",
}

COMO_TIRAR_100 = [
    ("A · Acolher", ["Responder em até 5 min.", "Apresentar-se pelo nome, como consultora da Can.",
                     "Frase de propósito: \"transformamos momentos especiais em aroma\".",
                     "Fechar com \"é pra qual ocasião?\". Sem preço, mínimo ou cadastro no início."]),
    ("R · Revelar", ["Perguntar ocasião, data, quantidade e quem decide.",
                     "Uma pergunta por mensagem, intercalando com fotos.",
                     "CNPJ, CEP e e-mail só depois de entender o momento."]),
    ("O · Orientar", ["Oferecer 2–3 opções nomeadas (Essencial, Recomendada, Memorável) e dizer por que a do meio.",
                      "Escolher o produto pelo momento, sem despejar catálogo nem os 27 aromas."]),
    ("M · Materializar", ["Antes do PDF: \"deixa eu ver se entendi…\".",
                          "Proposta com mockup, fotos parecidas, aroma e porquê, prazo e sinal. Nunca PDF sozinho."]),
    ("A · Avançar", ["Toda mensagem termina com um próximo passo claro, usando o prazo real de produção.",
                     "Follow-up sempre com algo novo. Nunca \"qualquer coisa me avise\" ou \"conseguiu analisar?\"."]),
]


def fmt(x, casas=1):
    return "—" if x is None else f"{x:.{casas}f}".replace(".", ",")


def barra(pct, cor, altura=12):
    pct = max(0, min(100, pct or 0))
    return f'<div style="background:{cor};width:{pct:.1f}%;min-width:3px;height:{altura}px"></div>'


def link(url):
    return f' <a href="{url}" style="color:{LARANJA}">abrir</a>' if url else ""


def h2(t):
    return f'<h2 style="color:{MARROM};font-size:17px;margin:24px 0 8px">{t}</h2>'


def nota(av):
    vals = [av.get(k) for k, _ in LETRAS if av.get(k) is not None]
    return statistics.mean(vals) * 50 if vals else None


def main():
    pasta = sys.argv[1]
    teste = "--teste" in sys.argv
    col = json.load(open(os.path.join(pasta, "coleta.json")))
    ava = json.load(open(os.path.join(pasta, "avaliacao.json")))
    dia = date.fromisoformat(col["dia"])
    rotulo_dia = f"{DIAS[dia.weekday()]}, {dia.strftime('%d/%m/%Y')}"

    convs = [c for c in col["conversas"] if c["fone"] in ava["conversas"]]
    for c in convs:
        c["av"] = ava["conversas"][c["fone"]]
        c["nota"] = nota(c["av"])
        c["rot"] = f"{escape(c['nome'])} ••{c['final']}"
    atendentes = sorted({c["atendente"] for c in convs if c["atendente"]})
    por_fone = {c["fone"]: c for c in convs}

    def media_letra(lista, k):
        v = [c["av"][k] for c in lista if c["av"].get(k) is not None]
        return (statistics.mean(v) * 50, len(v)) if v else (None, 0)

    notas = [c["nota"] for c in convs if c["nota"] is not None]
    nota_geral = statistics.mean(notas) if notas else None
    resp = [c for c in convs if c["lead_novo"] and c["cliente_em_horario"] and c["resp_min"] is not None]
    tempos = [c["resp_min"] for c in resp]
    ok5 = sum(1 for t in tempos if t <= 5)
    passo_claro = sum(1 for c in convs if c["av"].get("proximo_passo") == "claro")
    mapa = sum(1 for c in convs if c["av"].get("mapa_momento"))
    alertas = {}
    for c in convs:
        for a in c["av"].get("alertas", []):
            alertas[a] = alertas.get(a, 0) + 1
    com_alerta = sum(1 for c in convs if c["av"].get("alertas"))
    pct = lambda a, b: f"{round(100 * a / b)}%" if b else "—"

    H = []
    H.append(f'<div style="font-family:Arial,Helvetica,sans-serif;color:#3B2A22;font-size:14px;line-height:1.5;max-width:680px;margin:0 auto">')
    H.append(f'<div style="background:{MARROM};color:#fff;padding:16px 20px"><div style="font-size:18px;font-weight:bold">Can Candles &amp; Wellness · Auditoria de Atendimento</div>'
             f'<div style="font-size:13px;opacity:.85">WhatsApp (WATI) · {rotulo_dia} · Método AROMA</div></div>')

    tiles = [(str(len(convs)), "conversas avaliadas"), (pct(ok5, len(tempos)), "1ª resposta ≤ 5 min"),
             (fmt(nota_geral), "nota AROMA (0–100)"), (pct(passo_claro, len(convs)), "com próximo passo claro")]
    H.append(f'<div style="background:{CREME};padding:16px 20px"><p style="margin:0 0 10px">Bom dia, time! Aqui está a auditoria do atendimento de ontem no WhatsApp.</p>'
             '<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;text-align:center"><tr>')
    for n, l in tiles:
        H.append(f'<td style="padding:8px;border:1px solid {BORDA};background:#fff"><div style="font-size:24px;font-weight:bold;color:{LARANJA}">{n}</div><div style="font-size:11px">{l}</div></td>')
    H.append(f'</tr></table><p style="margin:12px 0 0"><b>Veredito:</b> {escape(ava["veredito"])}</p></div>')

    H.append(h2("Como avaliamos: o método AROMA"))
    H.append('<p style="margin:0 0 8px">Cada conversa recebe uma nota de 0 a 100 pelas cinco letras do AROMA, do playbook '
             '"De tirador de pedidos a consultor de momentos". Para tirar 100 na próxima auditoria:</p>')
    H.append(f'<table cellpadding="6" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:13px">')
    for i, (letra, itens) in enumerate(COMO_TIRAR_100):
        fundo = CREME if i % 2 == 0 else "#fff"
        lis = "".join(f"<li>{escape(x)}</li>" for x in itens)
        H.append(f'<tr style="background:{fundo}"><td width="120" valign="top" style="font-weight:bold;color:{LARANJA}">{letra}</td>'
                 f'<td><ul style="margin:0;padding-left:16px">{lis}</ul></td></tr>')
    H.append("</table>")

    H.append(h2("Por atendente"))
    for a in atendentes:
        mine = [c for c in convs if c["atendente"] == a]
        ns = [c["nota"] for c in mine if c["nota"] is not None]
        ts = [c["resp_min"] for c in resp if c["atendente"] == a]
        info = ava["atendentes"].get(a, {})
        cab = f'{escape(a)} · {len(mine)} conversa{"s" if len(mine) != 1 else ""} · nota {fmt(statistics.mean(ns) if ns else None)}'
        if ts:
            cab += f' · 1ª resposta mediana {fmt(statistics.median(ts))} min ({sum(1 for t in ts if t <= 5)} de {len(ts)} ≤ 5 min)'
        if len(mine) < 3:
            cab += " · amostra pequena"
        H.append(f'<div style="border:1px solid {BORDA};padding:12px 16px;margin-bottom:12px"><div style="font-weight:bold;color:{LARANJA};font-size:15px">{cab}</div>')
        for titulo, chave, cor in (("Highlights", "highlights", VERDE), ("Lowlights", "lowlights", VERMELHO)):
            itens = info.get(chave, [])
            if not itens:
                continue
            H.append(f'<p style="margin:8px 0 4px;color:{cor}"><b>{titulo}</b></p><ul style="margin:0;padding-left:18px">')
            for it in itens:
                c = por_fone.get(it["fone"], {})
                melhor = f' <i>Melhor:</i> {escape(it["melhor"])}' if it.get("melhor") else ""
                H.append(f'<li><b>{c.get("rot", "")}</b> ({escape(it.get("horario", ""))}): {escape(it["texto"])}{melhor}{link(c.get("link"))}</li>')
            H.append("</ul>")
        if info.get("acao"):
            H.append(f'<p style="margin:8px 0 0"><b>Ação hoje:</b> {escape(info["acao"])}</p>')
        H.append("</div>")

    H.append(h2("Nota AROMA por letra"))
    colunas = [("Consolidado", convs)] + [(a.split()[0], [c for c in convs if c["atendente"] == a]) for a in atendentes]
    H.append(f'<table cellpadding="5" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:13px">'
             f'<tr style="background:{MARROM};color:#fff"><td>Letra</td>' + "".join(f"<td>{n}</td>" for n, _ in colunas) + "</tr>")
    for i, (k, nome) in enumerate(LETRAS + [("_", "Nota geral")]):
        fundo = CREME if i % 2 == 0 else "#fff"
        linha = f'<tr style="background:{fundo}"><td width="120"><b>{nome}</b></td>'
        for j, (_, lista) in enumerate(colunas):
            if k == "_":
                ns = [c["nota"] for c in lista if c["nota"] is not None]
                v, n = (statistics.mean(ns), len(ns)) if ns else (None, 0)
            else:
                v, n = media_letra(lista, k)
            cor = MARROM if j == 0 else LARANJA
            linha += (f'<td><b>{fmt(v, 0)}</b> <span style="font-size:10px;color:{CINZA}">(n={n})</span>{barra(v, cor, 8) if v is not None else ""}</td>')
        H.append(linha + "</tr>")
    H.append(f'</table><p style="font-size:11px;color:{CINZA};margin:4px 0 0">n = conversas em que a letra se aplicou no dia (sem evidência = N/A, fora da média).</p>')

    if resp:
        H.append(h2("1ª resposta por lead novo (minutos)"))
        mx = max(tempos) or 1
        H.append('<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:12px">')
        for c in sorted(resp, key=lambda c: c["resp_min"]):
            t = c["resp_min"]
            cor = VERDE if t <= 5 else (LARANJA if t <= 25 else VERMELHO)
            ini = (c["atendente"] or "?")[0]
            H.append(f'<tr><td width="160">{c["rot"]} ({ini})</td><td>{barra(100 * t / mx, cor, 10)}</td><td width="44" align="right">{fmt(t)}</td></tr>')
        H.append(f'</table><p style="font-size:11px;color:{CINZA};margin:4px 0 0">Meta: até 5 min. Mediana {fmt(statistics.median(tempos))} · média {fmt(statistics.mean(tempos))} · '
                 f'{ok5} de {len(tempos)} dentro da meta. Só leads novos cuja 1ª mensagem chegou em horário comercial.</p>')

    H.append(h2("Todas as conversas avaliadas"))
    H.append(f'<table cellpadding="4" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:12px"><tr style="background:{MARROM};color:#fff">'
             '<td>Cliente</td><td>Atendente</td><td align="right">1ª resp.</td><td align="right">Nota</td><td></td></tr>')
    curta = False
    for i, c in enumerate(sorted(convs, key=lambda c: -(c["nota"] or -1))):
        n_let = sum(1 for k, _ in LETRAS if c["av"].get(k) is not None)
        marca = "*" if n_let <= 1 else ""
        curta |= bool(marca)
        fundo = CREME if i % 2 else "#fff"
        H.append(f'<tr style="background:{fundo}"><td>{c["rot"]}</td><td>{escape((c["atendente"] or "—").split()[0])}</td>'
                 f'<td align="right">{fmt(c["resp_min"]) if c["lead_novo"] else "—"}</td><td align="right">{fmt(c["nota"], 0)}{marca}</td><td>{link(c["link"])}</td></tr>')
    H.append("</table>")
    if curta:
        H.append(f'<p style="font-size:11px;color:{CINZA};margin:4px 0 0">* Conversa curta, com só uma letra avaliável. Leia como sinal, não como veredito.</p>')

    at = ava.get("airtable", {})
    outros = [f'Ocasião, data e quantidade perguntadas ou registradas: <b>{pct(mapa, len(convs))}</b> (meta 90%)',
              f'Conversas com pelo menos um alerta: {pct(com_alerta, len(convs))}' +
              (" · " + " · ".join(f"{ALERTAS.get(k, k)} ({v})" for k, v in sorted(alertas.items(), key=lambda x: -x[1])) if alertas else "")]
    if at:
        outros.append(escape(at.get("resumo", "")))
    outros.append(f'Contatos com atividade: {col["contatos_com_atividade"]} · conversas com mensagem de cliente ou do time: {len(col["conversas"])} · '
                  f'mensagens automáticas no dia: {col["volume_automacao"]} (fora da nota)')
    if col.get("fim_de_semana_sem_resposta") is not None:
        outros.append(f'Fim de semana: {col["fim_de_semana_sem_resposta"]} contato(s) escreveram e ainda não tiveram resposta (só estatística).')
    H.append(h2("Outros números do dia"))
    H.append('<ul style="margin:0;padding-left:18px;font-size:13px">' + "".join(f"<li>{o}</li>" for o in outros if o) + "</ul>")

    if ava.get("followups"):
        H.append(h2("Follow-ups para hoje"))
        H.append('<ol style="margin:0;padding-left:18px;font-size:13px">')
        for f in ava["followups"]:
            c = por_fone.get(f["fone"], {})
            H.append(f'<li><b>{c.get("rot", "")}</b> ({escape((c.get("atendente") or "").split(" ")[0])}): {escape(f["texto"])}{link(c.get("link"))}</li>')
        H.append("</ol>")
    if ava.get("insight"):
        H.append(h2("Insight do dia"))
        H.append(f'<p style="margin:0">{escape(ava["insight"])}</p>')

    H.append(f'<p style="font-size:11px;color:{CINZA};margin:22px 0 0;border-top:1px solid {BORDA};padding-top:10px">Metodologia: conversas da WATI de '
             f'{dia.strftime("%d/%m")} (00:00–23:59, horário de Brasília). Só mensagens humanas são avaliadas; bot, templates e eventos de ticket ficam de fora. '
             'A nota de cada conversa é a média das letras AROMA aplicáveis (0–2), convertida para 0–100. Clientes aparecem só com o primeiro nome e os 4 últimos dígitos. '
             + escape(ava.get("limitacoes", "")) + "</p>")
    H.append('<p style="margin:10px 0 0">Auditoria de atendimento · Can Candles</p></div>')

    open(os.path.join(pasta, "email.html"), "w").write("\n".join(H))
    assunto = f'Auditoria de atendimento Can · {DIAS[dia.weekday()]} {dia.strftime("%d/%m")}'
    open(os.path.join(pasta, "assunto.txt"), "w").write(("[TESTE] " if teste else "") + assunto)
    print(f"ok: {len(convs)} conversas, nota {fmt(nota_geral)}, {len(''.join(H))} caracteres")


if __name__ == "__main__":
    main()
