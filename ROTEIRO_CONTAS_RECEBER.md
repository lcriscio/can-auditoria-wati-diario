# Roteiro · Calendário de Saldos para Cobrarmos (Can Candles · Airtable)

Você monta, todo dia útil às 8h, o relatório de contas a receber da Can Candles & Wellness a partir da tabela Pedidos do Airtable e envia por e-mail. Tudo em português do Brasil. Seja econômico em tokens: não imprima JSON bruto.

## Configuração
- MODO_TESTE = SIM
- Envio oficial: para leo@cancandles.com.br, jessica@cancandles.com.br, comercial@cancandles.com.br e atendimento@cancandles.com.br.
- Modo teste: só leo@cancandles.com.br e `--teste` no script (coloca "[TESTE]" no assunto).
- Airtable (somente leitura): base `appza7P3RBl5OYQZv`, tabela Pedidos `tblF4spbwfP25MItI`.

## Segurança
- Airtable: só leitura. Nunca crie, altere ou apague registros.
- `data/` contém dados de clientes: nunca faça commit dessa pasta.
- Se o Airtable ou o script falhar: NÃO envie ao time. Mande só para leo@cancandles.com.br um e-mail curto com o erro, no máximo uma vez, e encerre.

## Passos
1. Consulte o Airtable com `list_records_for_table` (base e tabela acima), `pageSize` 1000, filtro `{"operands":[{"operator":"isNoneOf","operands":["fldBIfAlemFpuuo3b",["selFVXgzq9blpShSC"]]}]}` (exclui "11. Perdido") e `fieldIds` exatamente:
   `["fldZWGWvGg0Y7wdua","fldl9gG0SvY5lmnpe","fldXtzo8xOSC6gLsZ","fldBIfAlemFpuuo3b","fldWOPjPp3z3ge1gm","fldZNp21mjPqXIY6Y","fldtCRpgKQJy8WOsA","fldRbERwNA5K243C2","fldVul9O74meoWwdd","fldQNRLwkpIpeTG9w","fldfDI9vLsR9hqNg2","fldGRw3BPVdSkwSMi","fld9IU7JhtIHNA3k7","flddTylMfbOi6AsO5"]`.
   A resposta é grande e costuma ser salva automaticamente em um arquivo: copie esse arquivo para `data/contas/pedidos1.json` (crie a pasta com `mkdir -p data/contas`). Se vier inline, grave o JSON em `data/contas/pedidos1.json`. Se houver `nextCursor`, busque as próximas páginas e grave como `pedidos2.json`, `pedidos3.json`…
2. `python3 scripts/contas_receber.py data/contas/pedidos*.json` (acrescente `--teste` se MODO_TESTE = SIM). O script aplica todas as regras (tiers do Bloco 1 e inconsistências do Bloco 2) e gera `data/contas/email.html` e `data/contas/assunto.txt`. Não recalcule nem edite o HTML à mão.
3. Envie com o conector Gmail (`send_message`): `htmlBody` = conteúdo de `data/contas/email.html`, `subject` = conteúdo de `data/contas/assunto.txt`, destinatários da configuração (`to`). Sem anexos. O e-mail vai mesmo que todos os blocos estejam vazios.
4. Resuma em 1–2 linhas: a linha `ok:` do script e os destinatários.
