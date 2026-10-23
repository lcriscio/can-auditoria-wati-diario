"""Forma de pagamento volta para "Sem indicativo" quando o contato parou de responder há mais de 15 dias.

Uso: python3 scripts/inativos.py <pedidos.json> [--dias 15] [--saida data/pagamento/inativos.json]
<pedidos.json> é a resposta crua do list_records_for_table da tabela Pedidos (a mesma do passo 1 do roteiro).
Regra fixa, sem IA: pedido nos estágios 0 a 3, com "Sinal + Saldo" ou "Valor cheio", sem cobrança do Sinal/Valor cheio
paga e cuja última mensagem do contato na WATI (não da equipe nem de automação) tem mais de <dias> dias, ou que não
tem mensagem do contato: "Como esse pedido será pago" vira "Sem indicativo". O percentual não é mexido.
Somente leitura na WATI (GET). Gera <saida> com os lotes prontos para update_records_for_table (até 50 por lote).
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from pagamento import TZ, F_EST, F_FONE, F_FORMA, F_ID, digitos, hora_local, mensagens, quem

S_STATUS = "fldmAdlGqtAXP55IQ"
FORMAS = {"Sinal + Saldo", "Valor cheio"}
ESTAGIOS = ("0.", "1.", "2.", "3.")


def ultima_do_contato(fone):
    itens = mensagens(fone, 3)
    if itens is None:
        return None, True
    ts = [hora_local(it) for it in itens if quem(it) == "C"]
    return max((t for t in ts if t), default=None), False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pedidos")
    ap.add_argument("--dias", type=int, default=15)
    ap.add_argument("--saida", default=os.path.join("data", "pagamento", "inativos.json"))
    args = ap.parse_args()
    limite = datetime.now(TZ) - timedelta(days=args.dias)

    por_fone = {}
    for r in json.load(open(args.pedidos))["records"]:
        v = r["cellValuesByFieldId"]
        if not (v.get(F_EST) or {}).get("name", "").startswith(ESTAGIOS):
            continue
        if (v.get(F_FORMA) or {}).get("name") not in FORMAS or (v.get(S_STATUS) or {}).get("name") == "Pago":
            continue
        for f in {digitos(x) for vals in ((v.get(F_FONE) or {}).get("valuesByLinkedRecordId") or {}).values() for x in vals}:
            por_fone.setdefault(f, []).append(r)

    with ThreadPoolExecutor(6) as ex:
        ultimas = dict(zip(por_fone, ex.map(ultima_do_contato, por_fone)))
    falhas = [f for f, (_, erro) in ultimas.items() if erro]
    if por_fone and len(falhas) == len(por_fone):
        sys.exit("ERRO WATI: todas as leituras falharam")

    updates, resumo, vistos = [], [], set()
    for f, (ult, erro) in sorted(ultimas.items()):
        if erro or (ult and ult >= limite):
            continue
        for r in por_fone[f]:
            if r["id"] in vistos:
                continue
            vistos.add(r["id"])
            v = r["cellValuesByFieldId"]
            updates.append({"id": r["id"], "fields": {F_FORMA: "Sem indicativo"}})
            resumo.append(f"P{v.get(F_ID)} {v[F_FORMA]['name']} → Sem indicativo "
                          f"(contato sem responder desde {ult:%d/%m/%y})" if ult else
                          f"P{v.get(F_ID)} {v[F_FORMA]['name']} → Sem indicativo (sem mensagem do contato na WATI)")

    lotes = [updates[i:i + 50] for i in range(0, len(updates), 50)]
    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    json.dump({"lotes": lotes, "pedidos": resumo}, open(args.saida, "w"), ensure_ascii=False, indent=1)
    print(f"inativos: candidatos={sum(len(p) for p in por_fone.values())} atualizar={len(updates)} "
          f"falhas={falhas} -> {args.saida}")
    for linha in resumo:
        print(" ", linha)


if __name__ == "__main__":
    main()
