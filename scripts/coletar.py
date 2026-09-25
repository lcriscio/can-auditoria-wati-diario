"""Coleta conversas da WATI do último dia útil e gera coleta.json + transcricoes.txt.

Uso: python3 scripts/coletar.py [--data AAAA-MM-DD]
Somente leitura (GET). A credencial da WATI é injetada pelo proxy do ambiente.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://live-mt-server.wati.io/389231/api/v1"
HORA_ABRE, HORA_FECHA = 9, 18


def get(url):
    r = subprocess.run(["curl", "-sS", "-w", "\n%{http_code}", url], capture_output=True, text=True, timeout=90)
    corpo, _, status = r.stdout.rpartition("\n")
    if status != "200":
        sys.exit(f"ERRO WATI: HTTP {status} em {url.split('?')[0]}")
    return json.loads(corpo)


def ultimo_dia_util(hoje):
    d = hoje - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def hora_local(it):
    if it.get("timestamp"):
        return datetime.fromtimestamp(float(it["timestamp"]), tz=timezone.utc).astimezone(TZ)
    if it.get("created"):
        return datetime.fromisoformat(it["created"].replace("Z", "+00:00")).astimezone(TZ)
    return None


def comercial(dt):
    return dt.weekday() < 5 and HORA_ABRE <= dt.hour < HORA_FECHA


def classificar(it):
    if it.get("eventType") != "message":
        return "sistema"
    if not it.get("owner"):
        return "cliente"
    op = (it.get("operatorName") or "").strip()
    if not op or op.lower() == "bot" or it.get("templateId") or it.get("broadcastLinkId"):
        return "automacao"
    return "humano"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    args = ap.parse_args()
    hoje = datetime.now(TZ).date()
    dia = date.fromisoformat(args.data) if args.data else ultimo_dia_util(hoje)
    ini = datetime.combine(dia, time(0, 0), TZ)
    fim = ini + timedelta(days=1)
    segunda = hoje.weekday() == 0 and not args.data
    corte = datetime.combine(hoje - timedelta(days=2), time(0, 0), TZ) if segunda else ini

    contatos, pagina = [], 1
    while True:
        d = get(f"{BASE}/getContacts?pageSize=100&pageNumber={pagina}")
        lote = d.get("contact_list") or []
        contatos += lote
        if not lote or not (d.get("link") or {}).get("nextPage") or pagina > 60:
            break
        pagina += 1

    candidatos = []
    for c in contatos:
        lu = c.get("lastUpdated")
        if lu and datetime.fromisoformat(lu.replace("Z", "+00:00")).astimezone(TZ) >= min(ini, corte):
            candidatos.append(c)

    conversas, fds_sem_resposta, volume_auto = [], 0, 0
    for c in candidatos:
        fone = c.get("phone") or c.get("wAid")
        itens, fim_hist = [], False
        for p in range(1, 4):
            d = get(f"{BASE}/getMessages/{fone}?pageSize=100&pageNumber={p}")
            lote = (d.get("messages") or {}).get("items") or []
            itens += lote
            if len(lote) < 100:
                fim_hist = True
                break
            t = hora_local(lote[-1])
            if t and t < ini - timedelta(days=3):
                break
        conv_id = next((it["conversationId"] for it in itens if it.get("conversationId")), None)
        msgs = []
        for it in itens:
            t = hora_local(it)
            if not t:
                continue
            msgs.append({
                "t": t.isoformat(), "quem": classificar(it),
                "op": (it.get("operatorName") or "").strip(),
                "tipo": it.get("type"), "texto": (it.get("text") or "")[:400],
                "evento": it.get("eventDescription"),
            })
        msgs.sort(key=lambda m: m["t"])
        reais = [m for m in msgs if m["quem"] != "sistema"]
        janela = [m for m in reais if ini.isoformat() <= m["t"] < fim.isoformat()]

        if segunda:
            fds = [m for m in reais if datetime.fromisoformat(m["t"]).date() in (hoje - timedelta(days=2), hoje - timedelta(days=1))]
            ult_cli = max((m["t"] for m in fds if m["quem"] == "cliente"), default=None)
            if ult_cli and not any(m["quem"] == "humano" and m["t"] > ult_cli for m in reais):
                fds_sem_resposta += 1

        volume_auto += sum(1 for m in janela if m["quem"] == "automacao")
        if not any(m["quem"] in ("cliente", "humano") for m in janela):
            continue

        lead_novo = fim_hist and bool(reais) and reais[0]["t"] >= ini.isoformat() and reais[0]["quem"] == "cliente"
        prim_cli = next((m for m in janela if m["quem"] == "cliente"), None)
        resp_min, dentro = None, False
        if prim_cli:
            t0 = datetime.fromisoformat(prim_cli["t"])
            dentro = comercial(t0)
            resp = next((m for m in janela if m["quem"] == "humano" and m["t"] > prim_cli["t"]), None)
            if resp:
                resp_min = round((datetime.fromisoformat(resp["t"]) - t0).total_seconds() / 60, 1)
        ops = {}
        for m in janela:
            if m["quem"] == "humano":
                ops[m["op"]] = ops.get(m["op"], 0) + 1
        ultima = janela[-1]
        nome = ((c.get("firstName") or c.get("fullName") or "Cliente").strip().split() or ["Cliente"])[0].capitalize()
        conversas.append({
            "fone": fone, "nome": nome, "final": fone[-4:], "conversationId": conv_id,
            "link": f"https://live.wati.io/389231/teamInbox/{conv_id}" if conv_id else None,
            "atendente": max(ops, key=ops.get) if ops else None, "operadores": ops,
            "lead_novo": lead_novo, "resp_min": resp_min, "cliente_em_horario": dentro,
            "aguardando_cliente": ultima["quem"] == "humano",
            "contexto": [m for m in reais if m["t"] < ini.isoformat()][-8:],
            "janela": janela,
        })

    saida = os.path.join("data", dia.isoformat())
    os.makedirs(saida, exist_ok=True)
    resumo = {
        "dia": dia.isoformat(), "contatos_com_atividade": len(candidatos), "conversas": conversas,
        "volume_automacao": volume_auto, "segunda": segunda,
        "fim_de_semana_sem_resposta": fds_sem_resposta if segunda else None,
    }
    json.dump(resumo, open(os.path.join(saida, "coleta.json"), "w"), ensure_ascii=False, indent=1)

    with open(os.path.join(saida, "transcricoes.txt"), "w") as f:
        for cv in conversas:
            f.write(f"\n=== {cv['fone']} · {cv['nome']} ••{cv['final']} · atendente {cv['atendente']} · "
                    f"lead_novo={cv['lead_novo']} · 1a_resp={cv['resp_min']} min · cliente_em_horario={cv['cliente_em_horario']}\n")
            for m in cv["contexto"]:
                f.write(f"[ctx {m['t'][5:10]} {m['t'][11:16]}] {rot(m)}\n")
            for m in cv["janela"]:
                f.write(f"{m['t'][11:16]} {rot(m)}\n")
    print(f"dia={dia} contatos_ativos={len(candidatos)} conversas_avaliaveis={len(conversas)} -> {saida}")


def rot(m):
    quem = {"cliente": "CLIENTE", "humano": f"TIME({m['op']})", "automacao": "AUTO"}[m["quem"]]
    corpo = m["texto"].replace("\n", " ") if m["tipo"] == "text" else f"[{m['tipo']}]"
    return f"{quem}: {corpo}"


if __name__ == "__main__":
    main()
