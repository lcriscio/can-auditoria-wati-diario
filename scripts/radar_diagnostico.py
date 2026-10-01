"""Diagnóstico de cobertura do radar: compara uma lista de telefones (do Airtable)
com o que getContacts/getMessages da WATI devolvem. Só leitura; imprime só os 4 dígitos finais.

Uso: python3 scripts/radar_diagnostico.py AAAA-MM-DD fone1 fone2 ...
"""
import sys
from datetime import datetime, time

import radar_coletar as r


def main():
    dia = datetime.combine(datetime.fromisoformat(sys.argv[1]).date(), time(0, 0), r.TZ)
    fones = sys.argv[2:]
    contatos, pagina = [], 1
    while True:
        d = r.get(f"{r.BASE}/getContacts?pageSize=100&pageNumber={pagina}")
        lote = d.get("contact_list") or []
        contatos += lote
        if pagina == 1:
            print("chaves_resposta:", sorted(d.keys()), "| link:", d.get("link"))
            print("chaves_contato:", sorted(lote[0].keys()) if lote else None)
        if not lote or not (d.get("link") or {}).get("nextPage") or pagina > 60:
            break
        pagina += 1
    print(f"paginas={pagina} contatos={len(contatos)}")
    por_fone = {}
    for c in contatos:
        for k in ("phone", "wAid"):
            if c.get(k):
                por_fone["".join(ch for ch in str(c[k]) if ch.isdigit())] = c
    ativos = sum(1 for c in contatos if c.get("lastUpdated") and
                 datetime.fromisoformat(c["lastUpdated"].replace("Z", "+00:00")).astimezone(r.TZ) >= dia)
    print(f"contatos_com_lastUpdated>={sys.argv[1]}: {ativos}")
    campos_data = [k for k in (contatos[0].keys() if contatos else []) if any(x in k.lower() for x in ("date", "updated", "created", "time", "last"))]
    print("campos_de_data:", campos_data)

    print("final | em_getContacts | lastUpdated | ult_msg | ult_cliente | ult_humano | msgs_no_dia")
    for f in fones:
        c = por_fone.get(f)
        lu = c.get("lastUpdated", "")[:16] if c else "-"
        d = r.get(f"{r.BASE}/getMessages/{f}?pageSize=100&pageNumber=1")
        itens = (d.get("messages") or {}).get("items") or []
        ms = [(r.hora_local(it), r.classificar(it)) for it in itens]
        ms = sorted((t, q) for t, q in ms if t and q != "sistema")
        ult = lambda q: next((t.strftime("%d/%m %H:%M") for t, k in reversed(ms) if q is None or k == q), "-")
        nodia = sum(1 for t, _ in ms if t >= dia)
        print(f"{f[-4:]} | {'sim' if c else 'NAO'} | {lu} | {ult(None)} | {ult('cliente')} | {ult('humano')} | {nodia}")


if __name__ == "__main__":
    main()
