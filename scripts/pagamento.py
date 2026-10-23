"""Monta a revisão de forma de pagamento: pedidos abertos (Airtable) + conversas da WATI.

Uso: python3 scripts/pagamento.py <pedidos.json> --contatos <contatos.json> [--minutos 40 | --dia-anterior | --tudo]
<pedidos.json> é a resposta crua do list_records_for_table da tabela Pedidos; <contatos.json>, a da tabela Contatos
(WhatsApp Ajustado e "[ Autocomplete/Preencher ] Último contato").
Quem entra na revisão: telefones com "Último contato" a partir do corte que têm pedido nos estágios 0 a 9, mais os
pedidos 0 a 9 que ainda não foram classificados (campo vazio) ou que voltaram do "11. Perdido" ainda marcados como
"O Contato do Pedido desistiu". Só esses telefones são lidos na WATI.
Somente leitura (GET). A credencial da WATI é injetada pelo proxy do ambiente.
Gera data/pagamento/<carimbo>/revisao.txt com, por telefone: os pedidos e seus valores atuais,
as linhas da conversa que falam de pagamento (histórico todo) e as linhas novas da janela (marcadas com *).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://live-mt-server.wati.io/389231/api/v1"
F_ID, F_FONE, F_EST, F_DET = "fldZWGWvGg0Y7wdua", "fldRY3JUX3BKdopLf", "fldBIfAlemFpuuo3b", "fld50dK0oYiJZ8dts"
F_VALOR, F_FORMA, F_PCT = "fldZNp21mjPqXIY6Y", "fldtCRpgKQJy8WOsA", "fldRbERwNA5K243C2"
C_FONE, C_ULTIMO = "fldig06GoIW20QBRc", "fldaGJGn1A5FqnCtl"
DESISTIU = "O Contato do Pedido desistiu"
ESTAGIOS = tuple(f"{n}." for n in range(10))
KW = re.compile(
    r"sinal|saldo|entrada|metade|\d+ ?%|por ?cento|restante|a vista|integral|valor (total|cheio)|pix|boleto|cart[ao]|"
    r"parcel|pagament|pagar|pago\b|paga\b|pagam|pague|faturad|link de|comprovante|adiantad|antecipad|quita|deposit|"
    r"transferenc|na entrega|apos a entrega|depois da entrega|50 ?/ ?50|forma de|condic|prazo de pag|nota fiscal|\bnf\b")


def get(url):
    r = subprocess.run(["curl", "-sS", "-w", "\n%{http_code}", url], capture_output=True, text=True, timeout=120)
    corpo, _, status = r.stdout.rpartition("\n")
    return json.loads(corpo) if status == "200" else None


def mensagens(fone, paginas):
    itens = []
    for p in range(1, paginas + 1):
        d = get(f"{BASE}/getMessages/{fone}?pageSize=100&pageNumber={p}")
        if d is None:
            return None
        lote = (d.get("messages") or {}).get("items") or []
        itens += lote
        if len(lote) < 100:
            break
    return itens


def hora_local(it):
    if it.get("timestamp"):
        return datetime.fromtimestamp(float(it["timestamp"]), tz=timezone.utc).astimezone(TZ)
    if it.get("created"):
        return datetime.fromisoformat(it["created"].replace("Z", "+00:00")).astimezone(TZ)
    return None


def quem(it):
    if it.get("eventType") != "message":
        return None
    if not it.get("owner"):
        return "C"
    op = (it.get("operatorName") or "").strip()
    if not op or op.lower() == "bot" or it.get("templateId") or it.get("broadcastLinkId"):
        return "AUTO"
    return "A"


def linhas(itens):
    out = []
    for it in itens:
        t, q = hora_local(it), quem(it)
        if not t or not q or (q == "AUTO" and it.get("type") != "text"):
            continue
        x = (it.get("text") or "").replace("\n", " ").strip() if it.get("type") == "text" \
            else f"[{it.get('type')}] " + (it.get("text") or "")[:60]
        out.append((t, q, x))
    return sorted(out, key=lambda m: m[0])


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def digitos(x):
    return "".join(c for c in str(x or "") if c.isdigit())


def sem_forma(v):
    """Pedido aberto que ainda precisa de uma primeira classificação."""
    forma = (v.get(F_FORMA) or {}).get("name")
    return not forma or forma == DESISTIU


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pedidos")
    ap.add_argument("--contatos", help="resposta crua da tabela Contatos com o Último contato")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--minutos", type=int, default=40)
    g.add_argument("--dia-anterior", action="store_true", help="1ª execução do dia: desde 17h30 de ontem")
    g.add_argument("--tudo", action="store_true", help="todas as conversas, sem janela (pente-fino)")
    args = ap.parse_args()
    if not args.tudo and not args.contatos:
        ap.error("--contatos é obrigatório, a não ser com --tudo")
    agora = datetime.now(TZ)
    if args.tudo:
        corte = datetime(2000, 1, 1, tzinfo=TZ)
    elif args.dia_anterior:
        corte = datetime.combine(agora.date() - timedelta(days=1), time(17, 30), TZ)
    else:
        corte = agora - timedelta(minutes=args.minutos)

    # telefones com mensagem recente, pelo "Último contato" da tabela Contatos
    recentes = set()
    for r in (json.load(open(args.contatos))["records"] if args.contatos else []):
        v = r["cellValuesByFieldId"]
        ult = v.get(C_ULTIMO)
        if ult and digitos(v.get(C_FONE)) and datetime.fromisoformat(ult.replace("Z", "+00:00")) >= corte:
            recentes.add(digitos(v.get(C_FONE)))

    por_fone, sem_fone = {}, []
    for r in json.load(open(args.pedidos))["records"]:
        v = r["cellValuesByFieldId"]
        if not (v.get(F_EST) or {}).get("name", "").startswith(ESTAGIOS):
            continue
        fones = {digitos(x) for vals in ((v.get(F_FONE) or {}).get("valuesByLinkedRecordId") or {}).values() for x in vals}
        for f in fones or [None]:
            (por_fone.setdefault(f, []) if f else sem_fone).append(r)

    alvo = []
    for f, pedidos in por_fone.items():
        novo = args.tudo or f in recentes
        if novo or any(sem_forma(r["cellValuesByFieldId"]) for r in pedidos):
            alvo.append((f, novo))
    with ThreadPoolExecutor(6) as ex:
        historicos = dict(zip([f for f, _ in alvo], ex.map(lambda a: mensagens(a[0], 10), alvo)))
    falhas = [f for f, it in historicos.items() if it is None]
    if alvo and len(falhas) == len(alvo):
        sys.exit("ERRO WATI: todas as leituras falharam")

    saida = os.path.join("data", "pagamento", agora.strftime("%Y-%m-%d_%H%M"))
    os.makedirs(saida, exist_ok=True)
    n_novos = 0
    with open(os.path.join(saida, "revisao.txt"), "w") as out:
        for f, novo in sorted(alvo):
            L = linhas(historicos.get(f) or [])
            n_novos += novo
            janela = {k for k, (t, q, _) in enumerate(L) if t >= corte}
            hits = {k for k, (t, q, x) in enumerate(L) if q != "AUTO" and KW.search(norm(x))}
            keep = sorted(janela | {j for k in hits for j in (k - 1, k, k + 1) if 0 <= j < len(L)})[-150:]
            out.write(f"\n##### {f} | {len(L)} msgs | novidade={'sim' if novo else 'nao'} | {len(hits)} trechos de pagamento\n")
            for r in sorted(por_fone[f], key=lambda r: r["cellValuesByFieldId"].get(F_ID) or 0):
                v = r["cellValuesByFieldId"]
                out.write(f"P{v.get(F_ID)} {r['id']} cri={r.get('createdTime', '')[:10]} est={(v.get(F_EST) or {}).get('name', '')[:3]} "
                          f"R${round(v[F_VALOR], 2) if isinstance(v.get(F_VALOR), (int, float)) else v.get(F_VALOR)} atual={(v.get(F_FORMA) or {}).get('name')}/{v.get(F_PCT)} | "
                          f"{(v.get(F_DET) or '').replace(chr(10), ' ')[:160]}\n")
            ant = -2
            for k in keep:
                if k != ant + 1:
                    out.write("  ...\n")
                t, q, x = L[k]
                out.write(f"{'*' if k in janela else ' '}{'>' if k in hits else ' '}{t:%d/%m/%y %H:%M} {q}: {x[:320]}\n")
                ant = k
        for r in sem_fone:
            v = r["cellValuesByFieldId"]
            out.write(f"\n##### sem telefone\nP{v.get(F_ID)} {r['id']} atual={(v.get(F_FORMA) or {}).get('name')}/{v.get(F_PCT)}\n")
    print(f"corte={corte:%d/%m %H:%M} contatos_recentes={len(recentes)} telefones={len(por_fone)} revisar={len(alvo)} com_novidade={n_novos} "
          f"sem_telefone={len(sem_fone)} falhas={falhas} -> {saida}/revisao.txt")


if __name__ == "__main__":
    main()
