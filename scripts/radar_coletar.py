"""Radar de contatos sem atendimento: lê as conversas da WATI de ontem e de hoje
e separa as que podem estar esperando resposta do time.

Uso: python3 scripts/radar_coletar.py [--agora AAAA-MM-DDTHH:MM] [--forcar]
Somente leitura (GET). A credencial da WATI é injetada pelo proxy do ambiente.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://live-mt-server.wati.io/389231/api/v1"
INBOX = "https://live.wati.io/389231/teamInbox"
HORA_ABRE, HORA_FECHA = 9, 18
HORA_PRIMEIRO_EMAIL = 9
TOL_NOVO_MIN = 5     # contato novo: entra no alerta após esse tempo sem o primeiro atendimento
TOL_ANTIGO_MIN = 30  # contato antigo: entra no alerta após esse tempo sem resposta do time
SAIDA = os.path.join("data", "radar")


def get(url):
    r = subprocess.run(["curl", "-sS", "-w", "\n%{http_code}", url], capture_output=True, text=True, timeout=90)
    corpo, _, status = r.stdout.rpartition("\n")
    if status != "200":
        sys.exit(f"ERRO WATI: HTTP {status} em {url.split('?')[0]}")
    return json.loads(corpo)


def hora_local(it):
    if it.get("timestamp"):
        return datetime.fromtimestamp(float(it["timestamp"]), tz=timezone.utc).astimezone(TZ)
    if it.get("created"):
        return datetime.fromisoformat(it["created"].replace("Z", "+00:00")).astimezone(TZ)
    return None


def classificar(it):
    if it.get("eventType") != "message":
        return "sistema"
    if not it.get("owner"):
        return "cliente"
    op = (it.get("operatorName") or "").strip()
    if not op or op.lower() == "bot" or it.get("templateId") or it.get("broadcastLinkId"):
        return "automacao"
    return "humano"


def dia_util(d):
    return d.weekday() < 5


def dia_util_anterior(d):
    d -= timedelta(days=1)
    while not dia_util(d):
        d -= timedelta(days=1)
    return d


def elegivel_em(t, tol, forcar=False):
    """Momento a partir do qual a mensagem do cliente pode entrar no alerta."""
    if forcar or (dia_util(t.date()) and HORA_ABRE <= t.hour < HORA_FECHA):
        return t + timedelta(minutes=tol)
    # fora do horário: entra no primeiro e-mail (9h) do próximo dia útil
    d = t.date() if (dia_util(t.date()) and t.hour < HORA_ABRE) else t.date() + timedelta(days=1)
    while not dia_util(d):
        d += timedelta(days=1)
    return max(datetime.combine(d, time(HORA_PRIMEIRO_EMAIL, 0), TZ), t + timedelta(minutes=tol))


def rot(m):
    quem = {"cliente": "CLIENTE", "humano": f"TIME({m['op']})", "automacao": "AUTO"}[m["quem"]]
    corpo = m["texto"].replace("\n", " ") if m["tipo"] == "text" else f"[{m['tipo']}] {m['texto']}".strip()
    return f"{quem}: {corpo}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agora")
    ap.add_argument("--forcar", action="store_true", help="roda mesmo fora da janela 9h-18h (para testes)")
    ap.add_argument("--fones", help="arquivo com telefones extras (um por linha), vindos do Airtable")
    args = ap.parse_args()
    agora = datetime.fromisoformat(args.agora).replace(tzinfo=TZ) if args.agora else datetime.now(TZ)

    na_janela = dia_util(agora.date()) and (
        HORA_PRIMEIRO_EMAIL <= agora.hour < HORA_FECHA or (agora.hour == HORA_FECHA and agora.minute < 15))
    if not na_janela and not args.forcar:
        print("fora_da_janela=1 candidatos=0")
        return

    # janela de leitura: dia útil anterior (inclui o fim de semana, se houver) + hoje
    ini = datetime.combine(dia_util_anterior(agora.date()), time(0, 0), TZ)

    contatos, pagina = [], 1
    while True:
        d = get(f"{BASE}/getContacts?pageSize=100&pageNumber={pagina}")
        lote = d.get("contact_list") or []
        contatos += lote
        if not lote or not (d.get("link") or {}).get("nextPage") or pagina > 60:
            break
        pagina += 1

    so_digitos = lambda x: "".join(ch for ch in str(x or "") if ch.isdigit())
    ativos, vistos = [], set()
    for c in contatos:
        lu = c.get("lastUpdated")
        if lu and datetime.fromisoformat(lu.replace("Z", "+00:00")).astimezone(TZ) >= ini:
            ativos.append(c)
            vistos.add(so_digitos(c.get("phone") or c.get("wAid")))
    # o lastUpdated da WATI não acompanha as mensagens: completa com os telefones
    # que o Airtable registrou com mensagem recebida nos últimos dias
    extras = 0
    if args.fones and os.path.exists(args.fones):
        por_fone = {so_digitos(c.get("phone") or c.get("wAid")): c for c in contatos}
        for linha in open(args.fones):
            f = so_digitos(linha)
            if len(f) >= 10 and f not in vistos:
                vistos.add(f)
                ativos.append(por_fone.get(f) or {"phone": f})
                extras += 1

    candidatos = []
    for c in ativos:
        fone = c.get("phone") or c.get("wAid")
        d = get(f"{BASE}/getMessages/{fone}?pageSize=100&pageNumber=1")
        itens = (d.get("messages") or {}).get("items") or []
        conv_id = next((it["conversationId"] for it in itens if it.get("conversationId")), None)
        msgs = []
        for it in itens:
            t = hora_local(it)
            quem = classificar(it)
            if not t or quem == "sistema":
                continue
            msgs.append({"t": t, "quem": quem, "op": (it.get("operatorName") or "").strip(),
                         "tipo": it.get("type"), "texto": (it.get("text") or "")[:500]})
        msgs.sort(key=lambda m: m["t"])
        if not any(m["t"] >= ini and m["quem"] in ("cliente", "humano") for m in msgs):
            continue

        humanos = [m for m in msgs if m["quem"] == "humano"]
        clientes = [m for m in msgs if m["quem"] == "cliente"]
        ult = next((m for m in reversed(msgs) if m["quem"] in ("cliente", "humano")), None)
        ult_cli = clientes[-1] if clientes else None
        ult_hum = humanos[-1] if humanos else None

        if ult["quem"] == "cliente":
            # primeira mensagem do cliente que ficou sem resposta humana
            desde = next(m for m in clientes if not ult_hum or m["t"] > ult_hum["t"])
            # contato novo = nunca recebeu resposta de uma atendente; antigo = já recebeu
            novo = not ult_hum
            tol = TOL_NOVO_MIN if novo else TOL_ANTIGO_MIN
            if desde["t"] < ini or elegivel_em(desde["t"], tol, args.forcar) > agora:
                continue
            situacao = "contato_novo" if novo else "contato_antigo_sem_resposta"
        else:
            # última palavra foi do time: só interessa se pode ser uma promessa de retorno não cumprida
            if ult_hum["t"] < ini or agora - ult_hum["t"] < timedelta(minutes=TOL_ANTIGO_MIN):
                continue
            desde = ult_hum
            situacao = "time_falou_por_ultimo"

        nome = (c.get("fullName") or c.get("firstName") or "Contato").strip()
        candidatos.append({
            "fone": fone, "nome": nome, "situacao": situacao,
            "atendente": ult_hum["op"] if ult_hum else None,
            "aguardando_desde": desde["t"].isoformat(),
            "fora_do_horario": not (dia_util(desde["t"].date()) and HORA_ABRE <= desde["t"].hour < HORA_FECHA),
            "link": f"{INBOX}/{conv_id}" if conv_id else None,
            "ultimas": [{"t": m["t"].isoformat(), "linha": rot(m)} for m in msgs[-12:]],
        })

    candidatos.sort(key=lambda x: x["aguardando_desde"])
    os.makedirs(SAIDA, exist_ok=True)
    json.dump({"agora": agora.isoformat(), "desde": ini.isoformat(), "candidatos": candidatos},
              open(os.path.join(SAIDA, "coleta.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(SAIDA, "transcricoes.txt"), "w") as f:
        for cv in candidatos:
            f.write(f"\n=== {cv['fone']} · {cv['nome']} · situacao={cv['situacao']} · atendente={cv['atendente']} · "
                    f"aguardando_desde={cv['aguardando_desde'][:16]} · fora_do_horario={cv['fora_do_horario']}\n")
            for m in cv["ultimas"]:
                f.write(f"{m['t'][5:10]} {m['t'][11:16]} {m['linha']}\n")
    print(f"agora={agora.isoformat()[:16]} contatos_ativos={len(ativos)} (extras_airtable={extras}) "
          f"candidatos={len(candidatos)} -> {SAIDA}")


if __name__ == "__main__":
    main()
