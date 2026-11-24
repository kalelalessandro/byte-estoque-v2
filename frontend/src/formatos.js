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

/** "1200.5" -> "R$ 1.200,50" (o backend envia valores em texto com 2 casas). */
export function formatarMoeda(valor) {
  const numero = Number(valor)
  if (Number.isNaN(numero)) return ''
  return numero.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** "2026-11-09T09:15:00" -> "09/11/2026 09:15" (sem Date, para não sofrer com fuso). */
export function formatarDataHora(iso) {
  const [data, hora = ''] = (iso || '').split('T')
  return `${formatarData(data)} ${hora.slice(0, 5)}`.trim()
}

/** Agora, no fuso local, no formato do <input type="datetime-local"> (AAAA-MM-DDTHH:MM). */
export function agoraIso() {
  const agora = new Date()
  const doisDigitos = (n) => String(n).padStart(2, '0')
  return (
    `${agora.getFullYear()}-${doisDigitos(agora.getMonth() + 1)}-${doisDigitos(agora.getDate())}` +
    `T${doisDigitos(agora.getHours())}:${doisDigitos(agora.getMinutes())}`
  )
}

/**
 * Procura valores em reais no texto de uma interação ("R$ 1.200,00", "R$ 90", "R$ 45,5")
 * e devolve `[{ rotulo: 'R$ 1.200,00', valor: '1200.00' }]` (sem repetir). É só uma
 * SUGESTÃO para preencher o valor do título: quem confirma é o usuário.
 */
export function extrairValores(texto) {
  const encontrados = new Map()
  const regex = /R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?/g
  for (const [, inteiro, centavos = ''] of (texto || '').matchAll(regex)) {
    const valor = `${inteiro.replace(/\./g, '')}.${centavos.padEnd(2, '0')}`
    if (!encontrados.has(valor)) {
      encontrados.set(valor, { rotulo: formatarMoeda(valor), valor })
    }
  }
  return [...encontrados.values()]
}
