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
  var PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
    'gclid', 'gbraid', 'wbraid', 'gad_source', 'gad_campaignid'];

  function ler() {
    try { return JSON.parse(sessionStorage.getItem(CHAVE)); } catch (e) { return null; }
  }

  function gravar(v) {
    try { sessionStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {}
  }

  // Guarda a origem da visita: a primeira página, ou a página que chegou com uma campanha nova.
  // Assim quem entra por um anúncio e clica no WhatsApp em outra página continua como "Paga".
  function registrarEntrada() {
    var params = new URLSearchParams(location.search);
    var temCampanha = PARAMS.some(function (k) { return params.get(k); });
    if (ler() && !temCampanha) return;
    var v = { landing_page: location.href, referrer: document.referrer || '' };
    PARAMS.forEach(function (k) { v[k] = params.get(k) || ''; });
    gravar(v);
  }

  // Mesma regra do snippet anterior ("Wordpress <> MAKE, mandar para Webhook"),
  // aplicada à página de entrada da visita.
  function classificar(v) {
    var utmMedium = v.utm_medium || '';
    var r = { source: '', medium: '', campaign: '', categoria: '' };

    if (v.gclid || v.gbraid || v.wbraid || v.gad_source || v.gad_campaignid) {
      r = { source: 'google', medium: 'cpc', campaign: v.utm_campaign || v.gad_campaignid || 'google-ads-auto', categoria: 'Paga' };
    } else if (utmMedium && ['cpc', 'paid', 'ppc', 'paid_social', 'paid-social', 'ads', 'pago'].indexOf(utmMedium.toLowerCase()) >= 0) {
      r = { source: v.utm_source || '', medium: utmMedium, campaign: v.utm_campaign || '', categoria: 'Paga' };
    } else if (v.utm_source || utmMedium || v.utm_campaign) {
      var m = utmMedium.toLowerCase();
      r = { source: v.utm_source || '', medium: utmMedium || 'referral', campaign: v.utm_campaign || '',
        categoria: m === 'organic' ? 'Org\u00e2nica' : m === 'direto' ? 'Direta' : 'Referral' };
    } else if (/google\.|bing\.|yahoo\.|duckduckgo\.|baidu\./i.test(v.referrer)) {
      r = { source: 'google', medium: 'organic', campaign: 'organic-search', categoria: 'Org\u00e2nica' };
    } else if (v.referrer && v.referrer.indexOf(location.hostname) < 0) {
      var host = 'referral';
      try { host = new URL(v.referrer).hostname; } catch (e) {}
      r = { source: host, medium: 'referral', campaign: 'referral', categoria: 'Referral' };
    } else {
      r.categoria = 'Direta';
    }

    if (r.categoria === 'Direta') r.source = r.medium = r.campaign = 'direto';
    return r;
  }

  function payload(numero) {
    var v = ler() || { landing_page: location.href, referrer: document.referrer || '' };
    var o = classificar(v);
    return {
      atendimento_id: numero,
      canal_conversao: 'WhatsApp',
      status_tracking: 'pendente',
      origem_categoria: o.categoria,
      utm_source: o.source,
      utm_medium: o.medium,
      utm_campaign: o.campaign,
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
