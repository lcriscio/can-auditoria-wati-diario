// Automação do Airtable "Ligar contato ao clique pelo nº de atendimento" (tabela Contatos).
// Dispara quando "[ Autocomplete/Preencher ] Última mensagem WATI" contém "Atendimento".
// Cópia versionada do script; a versão que roda está na própria automação.
const cfg = input.config();
const texto = cfg.texto || '';
const m = texto.match(/atendimento\s*n?\s*[º°o.]*\s*(\d{4})/i);
if (!m) {
  output.set('resultado', 'sem número de atendimento na mensagem');
} else {
  const numero = m[1];
  const contatos = base.getTable('tblHsfwLoB7CiG6Ji');
  const tracking = base.getTable('tbliSlSIgVftDdQ0e');
  const contato = await contatos.selectRecordAsync(cfg.recordId, { fields: ['fldig06GoIW20QBRc'] });
  const fone = contato ? contato.getCellValueAsString('fldig06GoIW20QBRc') : '';

  // Clique mais recente com esse número nos últimos 3 dias.
  const limite = Date.now() - 3 * 24 * 60 * 60 * 1000;
  const q = await tracking.selectRecordsAsync({
    fields: ['fldfY8elcz2EtSgac', 'fldWNAvghLPj6A7v2'],
    sorts: [{ field: 'fldWNAvghLPj6A7v2', direction: 'desc' }],
  });
  const clique = q.records.find(r =>
    r.getCellValueAsString('fldfY8elcz2EtSgac').trim() === numero &&
    new Date(r.getCellValue('fldWNAvghLPj6A7v2')).getTime() >= limite);

  if (!clique) {
    output.set('resultado', `nenhum clique com atendimento ${numero} nos últimos 3 dias`);
  } else {
    // O clique passa a apontar só para este contato (desfaz associação errada por horário, se houver)
    // e o contato passa a apontar só para este clique (o mais recente vale).
    await tracking.updateRecordAsync(clique.id, {
      fldoBN2OCS1H2ZbsP: [{ id: cfg.recordId }],
      fld7ds8p3LI2ywXtB: { name: 'associado' },
      fld2jqCuEhjyJeBvz: fone,
    });
    await contatos.updateRecordAsync(cfg.recordId, { fldl8L7EEosnvS4HO: [{ id: clique.id }] });
    output.set('resultado', `contato ligado ao clique do atendimento ${numero}`);
  }
}
