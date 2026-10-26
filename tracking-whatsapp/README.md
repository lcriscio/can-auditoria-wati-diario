# Rastreio dos cliques no WhatsApp com nº de atendimento

Liga cada contato que chega pelo WATI ao clique do site que o originou, sem depender do horário.

1. **Site** (`whatsapp-atendimento.js`): em todo clique num link de WhatsApp, gera um nº de 4 dígitos,
   coloca na mensagem pronta e envia o clique para a Make.
   Mensagem: `Olá! Gostaria de saber mais sobre o serviço de Identidade Olfativa ✨` + `Atendimento nº 1234`.
2. **Make** · cenário `tracking_whatsapp_click`: grava o clique em *Tracking de Origem*, agora com
   `atendimento_id` e `pagina_clique`.
3. **Airtable** · *Automação P* (`airtable-ligar-atendimento.js`): quando a mensagem gravada no contato
   traz "Atendimento nº", procura o clique com esse número (últimos 3 dias) e liga os dois.
   Landing Page, UTMs e origem do contato vêm pelos lookups que já existem.

O cenário da Make que associa por horário (5326283) continua como reserva para quem apagar o número.

## Instalação no WordPress

1. Snippets → Adicionar novo → tipo **HTML**, local **rodapé do site (footer)**, em todas as páginas.
2. Colar `<script>` + conteúdo de `whatsapp-atendimento.js` + `</script>`.
3. Desativar o snippet antigo de tracking do WhatsApp (o que chama o mesmo webhook), senão cada clique conta duas vezes.
4. LiteSpeed Cache → Limpar todo o cache.
5. Ligar a *Automação P* no Airtable.

## Teste

Abrir o site numa janela anônima com `?utm_source=teste`, clicar no WhatsApp e enviar a mensagem.
Em até 1 minuto: o clique aparece em *Tracking de Origem* com o nº, e o contato fica com Landing Page preenchida.
