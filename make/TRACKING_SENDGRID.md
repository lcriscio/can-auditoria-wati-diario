# Tracking de aberturas e cliques (SendGrid → Make → Airtable)

Cenário Make `6306992` — "Tracking de Aberturas e Cliques SendGrid - Cadências" (blueprint em `tracking_sendgrid_blueprint.json`).

## Fluxo
1. O cenário "Cold Leads - Cadência de Email para Arquitetos" (`6280406`) envia cada email com `custom_args`:
   `record_id` (id do lead em Leads `tblShRRbPPTvvPLe0`), `email_step` e `source = leads_receita`.
2. O Event Webhook do SendGrid (`818f64f0-…`) envia os eventos **open** e **click** para
   `https://hook.us2.make.com/dh08egmsrrs6tkvephavo5vm6aoriuqu`. O Make gera um bundle por evento.
3. O cenário só segue com `source = leads_receita` e `record_id` válido, lê o status atual e atualiza
   `[ Autocomplete ] Status do Lead` (`fldGTAW7Bq39Wtqwj`) sem rebaixar status:

| Evento | Atualiza para | Só quando o status atual é |
|---|---|---|
| open  | Abriu o Email | vazio ou "Sem interação" |
| click (URL fora de `hook.us2.make.com`) | Clicou em algum botão aleatório | qualquer um, exceto Optout / CTA WhatsApp / já "aleatório" |

Cliques no opt-out e no CTA do WhatsApp continuam com os cenários próprios (`6237980` e `6280363`),
que apontam para webhooks do Make — por isso o filtro de URL ignora esses cliques aqui.

Erros de leitura/atualização no Airtable (ex.: lead apagado) são ignorados para o cenário não ser desativado.

## Histórico
A Email Activity API do SendGrid nesta conta guarda só ~3 dias. Em 23/10/2026 foram reprocessadas as
aberturas disponíveis (11 leads marcados como "Abriu o Email"). Aberturas anteriores a 21/10 não
existem mais por destinatário — só no agregado do painel.

## Observação
Opens incluem aberturas automáticas (Apple Mail Privacy Protection, scanners corporativos). O evento do
SendGrid traz `sg_machine_open = true` nesses casos; se quiser ignorá-las, adicione a condição
`{{1.sg_machine_open}}` ≠ `true` no filtro "Registrar abertura".
