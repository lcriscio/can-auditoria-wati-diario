"""Campos das cobranças (Sinal/Valor cheio e Saldo) dos Pedidos por regra fixa, sem IA e sem WATI.

Uso: python3 scripts/cobrancas.py <pedidos.json> [--saida data/pagamento/cobrancas.json]
<pedidos.json> é a resposta crua do list_records_for_table da tabela Pedidos (todos os estágios).
Gera <saida> com os lotes prontos para update_records_for_table (até 50 por lote) e os protegidos.

Regras, da mais forte para a mais fraca:
1. Status da Cobrança do Saldo "Pago": não mexe nas cobranças (no estágio 11 só grava a forma de pagamento, regra 2).
2. Estágio "11. Perdido": "Como esse pedido será pago" vira "O Contato do Pedido desistiu" (sempre, mesmo com
   cobrança paga). E, a não ser que o Status da Cobrança do Sinal/Valor cheio seja "Pago" (aí não mexe nas cobranças):
   "Pedido perdido, campo desnecessário" nos 6 campos do Sinal/Valor cheio e nos 6 do Saldo.
   A Data do Pagamento do Sinal é campo de data e não recebe texto: fica como está.
3. Fora do estágio 11, cobrança do saldo já pedida ou emitida (Emitir = "Sim, emitir agora", Status "Pendente",
   URL/Link ID/Order Code reais ou data de pagamento do saldo): não mexe no Saldo.
4. "Sinal + Saldo": "Aguardando para emitir" em Emitir, Método, Status, Link ID e Order Code do Saldo; URL vazia
   (a Automação B só emite com a URL vazia). Método já escolhido (Link de pagamento, Boleto, PIX) é mantido.
   "Valor cheio": "Não há necessidade de emitir cobrança" nos mesmos campos; URL https://nao-ha-cobranca.local.
   Outras formas: não mexe no Saldo.
5. Pedido que saiu do estágio 11: limpa o "Pedido perdido, campo desnecessário" que tiver sobrado nos campos, para
   as Automações A e B voltarem a emitir (elas exigem a URL vazia).
"""
import argparse
import json
import os

F_ID, F_EST, F_FORMA = "fldZWGWvGg0Y7wdua", "fldBIfAlemFpuuo3b", "fldtCRpgKQJy8WOsA"
# Sinal ou Valor cheio
S_EMITIR, S_METODO, S_URL = "fldv2KYVAFCagKsQY", "fldQmm6zDPgYAyj8m", "fldpUbsRoboOCtPq2"
S_LINK, S_ORDER, S_STATUS = "fldnBPZ77k4AeHGfz", "fldSQ9VYKsUglicEk", "fldmAdlGqtAXP55IQ"
SINAL = (S_EMITIR, S_METODO, S_URL, S_LINK, S_ORDER, S_STATUS)
# Saldo
F_EMITIR, F_METODO, F_URL = "fldI7UM3FwCbRkuir", "fldYd66kGsvRX5VGM", "fld1lUmEPy6k44yKB"
F_STATUS, F_LINK, F_ORDER, F_DATA = "fldfDI9vLsR9hqNg2", "fldzG9b6zPuioEFRG", "fld9lsboriTPqtn5U", "fldyeNOWfdh5Du0HY"
SALDO = (F_EMITIR, F_METODO, F_URL, F_STATUS, F_LINK, F_ORDER)

AGUARDANDO, SEM_COBRANCA = "Aguardando para emitir", "Não há necessidade de emitir cobrança"
PERDIDO = "Pedido perdido, campo desnecessário"
DESISTIU = "O Contato do Pedido desistiu"
URL_SEM_COBRANCA = "https://nao-ha-cobranca.local"
METODOS_REAIS = {"Link de pagamento", "Boleto", "PIX"}
MARCADORES = {AGUARDANDO, SEM_COBRANCA, PERDIDO, "A definir", "Não há necessidade", "Sem cobrança criada"}


def texto(v):
    return (v.get("name") if isinstance(v, dict) else v or "").strip()


def saldo_em_andamento(v):
    """Motivo para não mexer nos campos do Saldo fora do estágio 11, ou None."""
    if texto(v.get(F_STATUS)) == "Pendente":
        return "cobrança do saldo pendente"
    if texto(v.get(F_EMITIR)) == "Sim, emitir agora":
        return "emissão do saldo pedida"
    if texto(v.get(F_URL)) not in ("", URL_SEM_COBRANCA, PERDIDO):
        return "URL de cobrança do saldo real"
    if any(texto(v.get(f)) not in MARCADORES | {""} for f in (F_LINK, F_ORDER)):
        return "cobrança Pagar.me do saldo registrada"
    if v.get(F_DATA):
        return "data de pagamento do saldo preenchida"
    return None


def desejado_saldo(v):
    forma = texto(v.get(F_FORMA))
    if forma == "Sinal + Saldo":
        alvo = {F_EMITIR: AGUARDANDO, F_STATUS: AGUARDANDO, F_LINK: AGUARDANDO, F_ORDER: AGUARDANDO, F_URL: None}
        if texto(v.get(F_METODO)) not in METODOS_REAIS:
            alvo[F_METODO] = AGUARDANDO
        return alvo
    if forma == "Valor cheio":
        return {F_EMITIR: SEM_COBRANCA, F_METODO: SEM_COBRANCA, F_STATUS: SEM_COBRANCA,
                F_LINK: SEM_COBRANCA, F_ORDER: SEM_COBRANCA, F_URL: URL_SEM_COBRANCA}
    return {}


def plano(v):
    """(campos a gravar, motivo de proteção)."""
    if texto(v.get(F_EST)).startswith("11."):
        if texto(v.get(F_STATUS)) == "Pago" or texto(v.get(S_STATUS)) == "Pago":
            return {F_FORMA: DESISTIU}, "cobrança paga"
        return {F_FORMA: DESISTIU, **{f: PERDIDO for f in SINAL + SALDO}}, None
    if texto(v.get(F_STATUS)) == "Pago":
        return {}, "cobrança paga"
    # Fora do estágio 11: limpa sobras de "Pedido perdido" (pedido reaberto)
    alvo = {f: None for f in SINAL + SALDO if texto(v.get(f)) == PERDIDO}
    saldo = desejado_saldo(v)
    motivo = saldo_em_andamento(v) if saldo else None
    if saldo and not motivo:
        alvo.update(saldo)
    return alvo, motivo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pedidos")
    ap.add_argument("--saida", default=os.path.join("data", "pagamento", "cobrancas.json"))
    args = ap.parse_args()

    updates, protegidos = [], []
    for r in json.load(open(args.pedidos))["records"]:
        v = r["cellValuesByFieldId"]
        alvo, motivo = plano(v)
        mudar = {f: x for f, x in alvo.items() if (texto(v.get(f)) or None) != x}
        if motivo and motivo != "cobrança paga":
            protegidos.append(f"P{v.get(F_ID)} {texto(v.get(F_EST))[:3].strip()} {texto(v.get(F_FORMA))}: {motivo}")
        if mudar:
            perdido = texto(v.get(F_EST)).startswith("11.")
            sobrescreve = [f for f in mudar if perdido and f != F_FORMA
                           and texto(v.get(f)) not in MARCADORES | {"", URL_SEM_COBRANCA}]
            updates.append({"id": r["id"], "fields": mudar, "resumo": f"P{v.get(F_ID)} "
                            + ("perdido" if perdido else texto(v.get(F_FORMA)) or "reaberto")
                            + (f" (sobrescreveu {len(sobrescreve)} campos com valor real)" if sobrescreve else "")})

    lotes = [[{"id": u["id"], "fields": u["fields"]} for u in updates[i:i + 50]] for i in range(0, len(updates), 50)]
    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    json.dump({"lotes": lotes, "pedidos": [u["resumo"] for u in updates], "protegidos": protegidos},
              open(args.saida, "w"), ensure_ascii=False, indent=1)
    print(f"cobrancas: atualizar={len(updates)} lotes={len(lotes)} protegidos={len(protegidos)} -> {args.saida}")
    for u in updates:
        if "sobrescreveu" in u["resumo"]:
            print("  atenção", u["resumo"])
    for p in protegidos:
        print("  protegido", p)


if __name__ == "__main__":
    main()
