/** Funções de formatação usadas na tela de parceiros (só exibição; o banco guarda sem pontuação). */

/** CPF (11) → 000.000.000-00; CNPJ (14, também alfanumérico) → 00.000.000/0000-00. */
export function formatarDocumento(documento) {
  if (!documento) return ''
  if (documento.length === 11) {
    return `${documento.slice(0, 3)}.${documento.slice(3, 6)}.${documento.slice(6, 9)}-${documento.slice(9)}`
  }
  if (documento.length === 14) {
    return `${documento.slice(0, 2)}.${documento.slice(2, 5)}.${documento.slice(5, 8)}/${documento.slice(8, 12)}-${documento.slice(12)}`
  }
  return documento
}

/** 50050010 → 50050-010. */
export function formatarCep(cep) {
  if (!cep) return ''
  return cep.length === 8 ? `${cep.slice(0, 5)}-${cep.slice(5)}` : cep
}

/** "2026-11-06" → "06/11/2026" (sem usar Date, para não sofrer com fuso horário). */
export function formatarData(iso) {
  const [ano, mes, dia] = (iso || '').split('-')
  return dia ? `${dia}/${mes}/${ano}` : iso || ''
}

/** Data de hoje no fuso local, no formato do <input type="date"> (AAAA-MM-DD). */
export function hojeIso() {
  return new Date().toLocaleDateString('sv-SE')
}
