"""Exporta o histórico completo de conversas da WATI para atualizar a base do agente de vendas.

Uso: python3 scripts/exportar_conversas.py --fones data/agente/fones_ganhos.txt
O arquivo de telefones (um por linha) vem do Airtable: os contatos dos pedidos ganhos
(estágios de "3. Venda concluída" a "10. Pagamento final realizado").
Gera data/agente/conversas/<fone>.json e data/agente/txt/<4 últimos dígitos>.txt.
Somente leitura (GET). A credencial da WATI é injetada pelo proxy do ambiente.
data/ contém dados pessoais: nunca faça commit dessa pasta.
"""
import argparse
import json
import os
import subprocess

from coletar import BASE, classificar, hora_local


def get(url):
    r = subprocess.run(["curl", "-sS", "-w", "\n%{http_code}", url], capture_output=True, text=True, timeout=90)
    corpo, _, status = r.stdout.rpartition("\n")
    return json.loads(corpo) if status == "200" else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fones", required=True)
    ap.add_argument("--saida", default=os.path.join("data", "agente"))
    args = ap.parse_args()
    so_digitos = lambda x: "".join(ch for ch in str(x) if ch.isdigit())
    fones = sorted({so_digitos(l) for l in open(args.fones) if len(so_digitos(l)) >= 10})
    os.makedirs(os.path.join(args.saida, "conversas"), exist_ok=True)
    os.makedirs(os.path.join(args.saida, "txt"), exist_ok=True)

    vazios = 0
    for fone in fones:
        itens = []
        for p in range(1, 11):
            d = get(f"{BASE}/getMessages/{fone}?pageSize=100&pageNumber={p}")
            lote = ((d or {}).get("messages") or {}).get("items") or []
            itens += lote
            if len(lote) < 100:
                break
        msgs = []
        for it in itens:
            t = hora_local(it)
            quem = classificar(it)
            if not t or quem == "sistema":
                continue
            msgs.append({"t": t.isoformat()[:16], "quem": quem, "op": (it.get("operatorName") or "").strip(),
                         "tipo": it.get("type"), "texto": it.get("text") or ""})
        msgs.sort(key=lambda m: m["t"])
        if not msgs:
            vazios += 1
            continue
        json.dump(msgs, open(os.path.join(args.saida, "conversas", f"{fone}.json"), "w"), ensure_ascii=False)
        with open(os.path.join(args.saida, "txt", f"{fone[-4:]}.txt"), "w") as f:
            for m in msgs:
                quem = {"cliente": "C", "humano": f"T({(m['op'].split() or ['?'])[0]})", "automacao": "AUTO"}[m["quem"]]
                corpo = m["texto"].replace("\n", " / ") if m["tipo"] == "text" else f"[{m['tipo']}] {m['texto'][:120]}"
                f.write(f"{m['t'][2:]} {quem}: {corpo}\n")
    print(f"fones={len(fones)} exportados={len(fones) - vazios} sem_historico={vazios} -> {args.saida}")


if __name__ == "__main__":
    main()
