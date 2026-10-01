# Roteiro · Diagnóstico de cobertura do radar (Can Candles · WATI)

Objetivo: descobrir se `scripts/radar_coletar.py` deixa de fora conversas que tiveram mensagens no dia, comparando uma lista de telefones vinda do Airtable com o que a WATI devolve. Somente leitura.

## Segurança
- WATI: apenas GET, sem header Authorization (o proxy injeta a credencial). Não enviar mensagens, e-mails nem notificações.
- Não fazer commit de nada. A saída traz só os 4 dígitos finais dos telefones.

## Passos
1. Leia `scripts/radar_diagnostico.py` e `scripts/radar_coletar.py` para confirmar que só fazem chamadas GET à WATI.
2. Dentro da pasta `scripts`, rode `python3 radar_diagnostico.py <dia> <telefones...>` com o dia e os telefones informados no prompt.
3. Como resposta final, copie a saída inteira do script, literalmente, em um bloco de código. Se der erro, copie o erro. Não resuma.
