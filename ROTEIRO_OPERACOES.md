# Roteiro · Comprar, Produzir e Entregar (Compras, Produção e Entrega · Can Candles · Airtable)

Você monta, todo dia útil às 7h, a visão gerencial de Compras, Produção e Entrega da Can Candles & Wellness a partir das tabelas Pedidos e Compras do Airtable e envia por e-mail. O retrato é o do Airtable no momento da execução, ou seja, tudo o que o time registrou até o fim do dia anterior; prazos e urgências contam a partir do dia do envio. Tudo em português do Brasil. Seja econômico em tokens: não imprima JSON bruto.

## Configuração
- MODO_TESTE = NAO
- Envio oficial: para jessica@cancandles.com.br, comercial@cancandles.com.br e atendimento@cancandles.com.br.
- Modo teste: só leo@cancandles.com.br e `--teste` no script (coloca "[TESTE]" no assunto).
- Airtable (somente leitura): base `appza7P3RBl5OYQZv`, Pedidos `tblF4spbwfP25MItI`, Compras `tblv2skEXMGqivk2W`, Fornecedores `tblsO71cn5M3m7qnl`.

## Segurança
- Airtable: só leitura. Nunca crie, altere ou apague registros.
- `data/` contém dados de clientes: nunca faça commit dessa pasta.
- Se o Airtable ou o script falhar: NÃO envie ao time. Mande só para leo@cancandles.com.br um e-mail curto com o erro, no máximo uma vez, e encerre.

## Passos
Crie a pasta com `mkdir -p data/operacoes`. Em cada consulta, a resposta grande costuma ser salva automaticamente em um arquivo: copie esse arquivo para o destino indicado. Se vier inline, grave o JSON no destino. Se houver `nextCursor`, busque as próximas páginas e grave como `...2.json`, `...3.json`…

1. **Pedidos** · `list_records_for_table` (base e tabela Pedidos acima), `pageSize` 1000, filtro dos estágios 4 a 7 (pedidos ainda não entregues)
   `{"operands":[{"operator":"isAnyOf","operands":["fldBIfAlemFpuuo3b",["selayNJjucgfO6jgj","sela8tfpLZIN7Il5a","selqs5qw6KhuSctFF","selm6UHsmUWkZaiBD"]]}]}`
   e `fieldIds` exatamente:
   `["fldZWGWvGg0Y7wdua","fldl9gG0SvY5lmnpe","fldXtzo8xOSC6gLsZ","fldBIfAlemFpuuo3b","fldWOPjPp3z3ge1gm","fldQNRLwkpIpeTG9w","fld9IU7JhtIHNA3k7","flddTylMfbOi6AsO5","fld50dK0oYiJZ8dts","fldto6lJU9MzZUgjk","fldjrkqdry27k7mWl"]`.
   Destino: `data/operacoes/pedidos1.json`.
2. **Compras** · junte os IDs de registro (`rec...`) do campo `fldto6lJU9MzZUgjk` de todos os pedidos do passo 1. Se não houver nenhum, grave `{"records":[]}` em `data/operacoes/compras1.json` e pule para o passo 3. Senão, `list_records_for_table` na tabela Compras com `recordIds` = essa lista (até 100 por chamada; mais que isso, divida em `compras2.json`…), `pageSize` 1000, filtro (sem data da compra)
   `{"operands":[{"operator":"isEmpty","operands":["flduEqt3bOWhk6nH2"]}]}`
   e `fieldIds` exatamente:
   `["fldAm6AXk5HTkdM3M","fldDpEA16hbhPKYx9","fldR3cLHsmnRyZTPM","fldyATyl5Wey2xoXa","fldfsaidVlL4aRXq2","flduEqt3bOWhk6nH2","fld2r7Bk9WvVLvWjW"]`.
   Destino: `data/operacoes/compras1.json`.
3. **Fornecedores** · `list_records_for_table` na tabela Fornecedores, `pageSize` 1000, `fieldIds` `["fldlMhT1L5IAbpmbC","fld9N6f5G3XQjZuWK"]`. Destino: `data/operacoes/fornecedores.json`. Se falhar, siga sem esse arquivo (o e-mail só perde os nomes dos fornecedores).
4. `python3 scripts/operacoes.py --pedidos data/operacoes/pedidos*.json --compras data/operacoes/compras*.json --fornecedores data/operacoes/fornecedores.json` (acrescente `--teste` se MODO_TESTE = SIM). O script aplica todas as regras (Comprar, Produzir, Entregar, urgências e recomendações) e gera `data/operacoes/email.html` e `data/operacoes/assunto.txt`. Não recalcule nem edite o HTML à mão.
5. Envie com o conector Gmail (`send_message`): `htmlBody` = conteúdo de `data/operacoes/email.html`, `subject` = conteúdo de `data/operacoes/assunto.txt`, destinatários da configuração (`to`). Sem anexos. O e-mail vai mesmo que as três seções estejam vazias.
6. Resuma em 1–2 linhas: a linha `ok:` do script e os destinatários.

## Regras aplicadas pelo script (referência)
- Universo: todos os pedidos de "4. Sinal pago" a "7. Produção finalizada". Os estágios 8, 9 e 10 já foram entregues e não entram em nenhuma frente, por isso nem são consultados. Ficam de fora "0. Proposta criada", "1. Proposta enviada", "2. Combatendo objeções", "3. Venda concluída" e "11. Perdido".
- Urgência pela "[ Preencher ] Data desejada da Entrega do pedido", contada a partir do dia do envio: alta até 7 dias (inclui datas vencidas), moderada de 8 a 15 dias, baixa a partir de 16 dias. Sem data: faixa própria, com pedido para preencher.
- **Comprar**: linhas de Compras sem "[ Preencher ] Data que a compra foi realizada", ligadas a pedidos em "4. Sinal pago" ou "5. Compra de insumos para produção". Agrupadas por pedido, com botão para cada linha de compra e para o pedido.
- **Produzir**: pedidos em "6. Produção iniciada" ou "7. Produção finalizada" com "[ Autocomplete ] Data do Pagamento do Sinal ou Valor Cheio deste Pedido" preenchida.
- **Entregar**: pedidos em 4, 5, 6 ou 7 com a data desejada de entrega anterior ao dia do envio.
- **Pontos de atenção**: pedido em 4/5 sem nenhum insumo cadastrado em Compras; pedido em 4/5 com todos os insumos já comprados; pedido em 6/7 sem a data do pagamento do sinal (ficaria fora de Produzir).
