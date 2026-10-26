/*
 * Can Candles · rastreio dos cliques no WhatsApp com nº de atendimento.
 *
 * Em todo clique num link de WhatsApp do site (botões, Elementor, widget flutuante):
 *   1. gera um nº de atendimento de 4 dígitos;
 *   2. acrescenta "✨\nAtendimento nº 1234" ao texto pronto da mensagem
 *      (ou usa MENSAGEM_PADRAO quando o botão não tem texto);
 *   3. envia para a Make (webhook tracking_whatsapp_click) o nº, a página de entrada,
 *      a página do clique, as UTMs e a categoria de origem.
 * A automação P do Airtable lê o nº na mensagem que chega pelo WATI e liga o contato ao clique.
 */
(function () {
  var WEBHOOK = 'https://hook.us2.make.com/aqmle7pbbm5hkce6vbomhvi1lm9rhrc7';
  var MENSAGEM_PADRAO = 'Ol\u00e1! Gostaria de saber mais sobre o servi\u00e7o de Identidade Olfativa';
  var CHAVE = 'can_origem_visita';
  var UTMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
  var IDS_PAGOS = ['gclid', 'gbraid', 'wbraid', 'fbclid', 'msclkid', 'ttclid', 'li_fat_id'];

  function ler() {
    try { return JSON.parse(sessionStorage.getItem(CHAVE)); } catch (e) { return null; }
  }

  function gravar(v) {
    try { sessionStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {}
  }

  // Guarda a origem da visita: a primeira página, ou a página que chegou com uma campanha nova.
  function registrarEntrada() {
    var params = new URLSearchParams(location.search);
    var temCampanha = UTMS.some(function (k) { return params.get(k); }) ||
      IDS_PAGOS.some(function (k) { return params.get(k); });
    if (ler() && !temCampanha) return;
    var v = { landing_page: location.href, referrer: document.referrer || '' };
    UTMS.concat(IDS_PAGOS).forEach(function (k) { v[k] = params.get(k) || ''; });
    gravar(v);
  }

  function hostDe(url) {
    try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return ''; }
  }

  function classificar(v) {
    var medium = (v.utm_medium || '').toLowerCase();
    var pago = IDS_PAGOS.some(function (k) { return v[k]; }) ||
      /cpc|ppc|paid|ads|display|cpm|cpv/.test(medium);
    if (pago) return 'Paga';
    if (v.utm_source) return /referral|parceiro|afiliado/.test(medium) ? 'Referral' : 'Org\u00e2nica';
    var ref = hostDe(v.referrer);
    if (!ref || ref === location.hostname.replace(/^www\./, '')) return 'Direta';
    if (/google\.|bing\.|yahoo\.|duckduckgo\.|ecosia\.|instagram\.|facebook\.|linkedin\.|t\.co$|pinterest\.|youtube\./.test(ref)) return 'Org\u00e2nica';
    return 'Referral';
  }

  function payload(numero) {
    var v = ler() || { landing_page: location.href, referrer: document.referrer || '' };
    var categoria = classificar(v);
    var ref = hostDe(v.referrer);
    var direto = categoria === 'Direta';
    return {
      atendimento_id: numero,
      canal_conversao: 'WhatsApp',
      status_tracking: 'pendente',
      origem_categoria: categoria,
      utm_source: v.utm_source || (direto ? 'direto' : ref || (v.gclid || v.gbraid || v.wbraid ? 'google' : '')),
      utm_medium: v.utm_medium || (direto ? 'direto' : ref ? 'referral' : ''),
      utm_campaign: v.utm_campaign || (direto ? 'direto' : ''),
      utm_content: v.utm_content || '',
      landing_page: v.landing_page,
      pagina_clique: location.href
    };
  }

  function enviar(dados) {
    var corpo = new URLSearchParams(dados);
    if (navigator.sendBeacon && navigator.sendBeacon(WEBHOOK, corpo)) return;
    fetch(WEBHOOK, { method: 'POST', body: corpo, keepalive: true, mode: 'no-cors' }).catch(function () {});
  }

  function ehWhatsApp(url) {
    return /^(https?:\/\/)?(wa\.me|(api|web|chat)\.whatsapp\.com)\b|^whatsapp:/i.test(url || '');
  }

  function novoNumero() {
    var a = new Uint16Array(1);
    (window.crypto || window.msCrypto).getRandomValues(a);
    return String(1000 + (a[0] % 9000));
  }

  // Devolve a URL do WhatsApp com o nº de atendimento no texto e avisa a Make.
  // Se a URL já tem um nº (clique repetido no mesmo botão), gera outro.
  function marcar(url) {
    var u;
    try { u = new URL(url, location.href); } catch (e) { return url; }
    var texto = (u.searchParams.get('text') || '')
      .replace(/\s*\u2728?\s*Atendimento n\u00ba \d{4}\s*$/, '').replace(/\s*\u2728\s*$/, '').trim();
    if (!texto) texto = MENSAGEM_PADRAO;
    var numero = novoNumero();
    u.searchParams.set('text', texto + ' \u2728\nAtendimento n\u00ba ' + numero);
    enviar(payload(numero));
    return u.toString();
  }

  registrarEntrada();

  // Links e botões (inclusive os do Elementor): troca o href antes do navegador abrir o link.
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (a && ehWhatsApp(a.href)) a.href = marcar(a.href);
  }, true);

  // Widgets que abrem o WhatsApp por window.open em vez de link.
  var abrir = window.open;
  window.open = function (url) {
    var args = Array.prototype.slice.call(arguments);
    if (typeof url === 'string' && ehWhatsApp(url)) args[0] = marcar(url);
    return abrir.apply(window, args);
  };
})();
