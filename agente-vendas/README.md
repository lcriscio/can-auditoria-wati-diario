# Agente de Vendas · Can Candles & Wellness

Base de conhecimento do agente que vai atender, no WhatsApp (via WATI), os contatos que chegam pedindo orçamento, fazendo o trabalho que hoje é feito pela Barbara, pela Hellen e pela Jéssica.

> **Status: EM CONSTRUÇÃO / MODO TESTE.** O agente ainda não fala com clientes. Primeiro ele roda em teste: lê a conversa real e escreve a resposta que daria, sem enviar. O time compara essas respostas com as respostas reais. Só depois de aprovado ele entra em operação, aos poucos (ver "Fases" abaixo).

## De onde veio este conteúdo

- **76 pedidos ganhos** no Airtable (estágios de "3. Venda concluída" até "10. Pagamento final realizado"), criados de 18/05 a 20/10/2026, de **62 contatos**.
- **45 conversas completas da WATI** lidas do começo ao fim. As outras 17 não existem mais na WATI (contato apagado ou trocado de número).
- **276 pedidos perdidos**, usados para entender o que não funciona (55% "Lead sumiu").
- Tabela **Produtos** (163 itens), as **automações** do Airtable (proposta, estruturação, política de desconto) e o roteiro AROMA da auditoria diária (`ROTEIRO.md`).

Nenhum arquivo daqui contém telefone, CNPJ, e-mail ou nome completo de cliente. Os casos aparecem anonimizados. As conversas brutas ficam em `data/agente/`, que está no `.gitignore` e nunca vai para o repositório.

## Os arquivos e a ordem de leitura

| # | Arquivo | Para que serve |
|---|---|---|
| 1 | [`01-identity.md`](01-identity.md) | Quem o agente é, como fala, o tom da Can |
| 2 | [`02-context.md`](02-context.md) | Como as vendas que deram certo aconteceram: padrões, números e 12 casos reais |
| 3 | [`03-skills-vendas-spin.md`](03-skills-vendas-spin.md) | Método SPIN adaptado à Can, banco de perguntas, objeções e fechamento |
| 4 | [`04-modo-operacional.md`](04-modo-operacional.md) | O passo a passo: qualificar → produto → logo → 3 opções → orçamento no Airtable → passagem para o time |
| 5 | [`05-guardrails.md`](05-guardrails.md) | O que pode e o que não pode, alçadas e quando chamar a Jéssica |
| 6 | [`06-base-de-conhecimento.md`](06-base-de-conhecimento.md) | Fatos de produto: tamanhos, medidas, fragrâncias, prazos, pagamento, entrega |

O sexto arquivo não estava na lista original. Ele entrou porque o agente precisa de fatos (medidas, prazos, formas de pagamento) para não inventar nada, e esses fatos não cabem bem em "Context" nem em "Modo Operacional".

Na hora de montar o agente, os arquivos 01, 03, 04 e 05 entram no prompt de sistema. O 02 e o 06 podem entrar inteiros (são curtos) ou ser consultados sob demanda.

## Fases sugeridas

1. **Sombra (teste puro):** o agente lê as conversas do dia e escreve a resposta que daria, sem enviar nada. A auditoria diária (AROMA) avalia essas respostas lado a lado com as respostas do time.
2. **Rascunho assistido:** o agente escreve na WATI como nota interna. Alguém do time aprova, edita ou descarta antes de enviar.
3. **Operação parcial:** o agente responde sozinho só em parte das conversas (por exemplo, fora do horário comercial ou leads novos de ticket baixo). O time assume pelos gatilhos de escalonamento.
4. **Operação plena:** o agente atende todos os leads novos até a proposta. Fechamento, cobrança e NF continuam com o time até decisão em contrário.

## Decisões que ainda são suas (Leonardo / Jéssica)

1. **Nome e apresentação do agente.** Os arquivos usam `{{NOME_DO_AGENTE}}`. Regra fixa: ele nunca diz que é humano. Se perguntarem, responde que é a assistente virtual da Can e que o time acompanha a conversa.
2. **Até onde o agente vai.** Sua frase terminou em "popular o airtable, até o passo…". Assumi que ele vai **até a proposta enviada e a aprovação do cliente**, e que cobrança, NF e produção seguem com o time. Confirme ou ajuste.
3. **Canal de casos críticos.** Você falou em "um contato no WhatsApp para casos críticos". Assumi que é um número (da Jéssica ou de um grupo do time) para onde o agente manda um alerta curto. Falta definir o número.
4. **Alçada de desconto.** Já existe uma política oficial na Automação 2' (teto por faixa de valor). Proposta: na fase de teste o agente não concede desconto nenhum sozinho; depois, pode dar o primeiro degrau da escada e o resto passa pela Jéssica (detalhes em `05-guardrails.md`).
5. **Três propostas por cliente.** Um Pedido para cada opção apresentada infla o funil: as duas opções não escolhidas viram "perdidas". Sugestão: criar o motivo de perda "Opção não escolhida (cliente fechou outra)" para não contaminar a métrica de "Lead sumiu".
6. **Fotos dos produtos.** Só 13 dos 163 produtos têm imagem no Airtable (todos são velas). Sem foto, o agente não consegue gerar mockup com IA para difusor, home spray, kit ou embalagem. Vale cadastrar fotos pelo menos dos 20 produtos mais vendidos.
7. **Sinal de 50% ou 70%.** As duas regras aparecem nas conversas. O agente precisa de uma regra única (ou de um critério).

## Como atualizar

O conteúdo de `02-context.md` envelhece. A cada trimestre, rode de novo a extração das conversas ganhas (`scripts/exportar_conversas.py`, descrito no topo do script) e revise os padrões e os casos.
