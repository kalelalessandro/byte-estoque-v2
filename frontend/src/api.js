/**
 * Cliente HTTP da API do Byte Estoque.
 *
 * Em desenvolvimento usamos caminhos relativos (`/api/...`) e o proxy do Vite
 * repassa para o Flask em http://127.0.0.1:5000. Assim o cookie de sessão fica
 * no mesmo host do front-end, sem precisar de CORS.
 */

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(status, corpo) {
    super(corpo?.erro || 'Não foi possível concluir a operação.')
    this.name = 'ApiError'
    this.status = status
    this.corpo = corpo || {}
  }
}

async function requisitar(caminho, { method = 'GET', corpo } = {}) {
  let resposta
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      method,
      credentials: 'include',
      headers: corpo ? { 'Content-Type': 'application/json' } : undefined,
      body: corpo ? JSON.stringify(corpo) : undefined,
    })
  } catch {
    throw new ApiError(0, {
      erro: 'Não foi possível conectar à API. Verifique se o backend está rodando.',
    })
  }

  let dados = null
  try {
    dados = await resposta.json()
  } catch {
    dados = null
  }

  if (!resposta.ok) {
    throw new ApiError(resposta.status, dados)
  }
  return dados
}

export const api = {
  saúde: () => requisitar('/api/health'),
  login: (email, senha) =>
    requisitar('/api/auth/login', { method: 'POST', corpo: { email, senha } }),
  cadastro: (empresa, usuario) =>
    requisitar('/api/auth/cadastro', {
      method: 'POST',
      corpo: { empresa, usuario },
    }),
  me: () => requisitar('/api/auth/me'),
  logout: () => requisitar('/api/auth/logout', { method: 'POST' }),
}

/** Junta a mensagem geral com os erros por campo (quando existirem). */
export function mensagemDeErro(erro) {
  if (!(erro instanceof ApiError)) {
    return erro?.message || 'Erro inesperado.'
  }
  const mensagens = Object.values(erro.corpo?.campos || {})
  return [erro.message, ...mensagens].filter(Boolean).join(' ')
}
