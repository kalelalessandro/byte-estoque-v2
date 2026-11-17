/**
 * Cliente HTTP da API do Byte Estoque.
 *
 * Em desenvolvimento usamos caminhos relativos (`/api/...`) e o proxy do Vite
 * repassa para o Flask em http://127.0.0.1:5000. Assim o cookie de sessão fica
 * no mesmo host do front-end, sem precisar de CORS.
 */

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

// O React em modo estrito monta componentes duas vezes em desenvolvimento.
// Este cache evita refazer a mesma busca ao trocar de tela; qualquer escrita
// (POST/PATCH/DELETE) invalida o cache para dados nunca ficarem desatualizados.
// O TTL é alto de propósito: o shell pré-carrega produtos/categorias após o
// login e as abas reaproveitam esses dados.
const CACHE_TTL_MS = 5 * 60 * 1000
const cacheGet = new Map()

export class ApiError extends Error {
  constructor(status, corpo) {
    super(corpo?.erro || 'Não foi possível concluir a operação.')
    this.name = 'ApiError'
    this.status = status
    this.corpo = corpo || {}
  }
}

async function executar(caminho, { method = 'GET', corpo } = {}) {
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

function requisitar(caminho, opcoes = {}) {
  const metodo = (opcoes.method || 'GET').toUpperCase()

  if (metodo !== 'GET') {
    cacheGet.clear()
    return executar(caminho, { ...opcoes, method: metodo })
  }

  const agora = Date.now()
  const emCache = cacheGet.get(caminho)
  if (emCache && emCache.expiraEm > agora) {
    return emCache.promessa
  }

  const promessa = executar(caminho, { ...opcoes, method: metodo }).catch(
    (erro) => {
      cacheGet.delete(caminho)
      throw erro
    },
  )
  cacheGet.set(caminho, { expiraEm: agora + CACHE_TTL_MS, promessa })
  return promessa
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
  dashboard: () => requisitar('/api/dashboard/resumo'),

  categorias: {
    listar: () => requisitar('/api/categorias'),
    criar: (nome) =>
      requisitar('/api/categorias', { method: 'POST', corpo: { nome } }),
    renomear: (idCategoria, nome) =>
      requisitar(`/api/categorias/${idCategoria}`, {
        method: 'PATCH',
        corpo: { nome },
      }),
    excluir: (idCategoria) =>
      requisitar(`/api/categorias/${idCategoria}`, { method: 'DELETE' }),
  },

  produtos: {
    listar: ({ busca = '', limit = 50, offset = 0 } = {}) => {
      const parametros = new URLSearchParams()
      if (busca) parametros.set('busca', busca)
      parametros.set('limit', String(limit))
      parametros.set('offset', String(offset))
      return requisitar(`/api/produtos?${parametros.toString()}`)
    },
    criar: (dados) =>
      requisitar('/api/produtos', { method: 'POST', corpo: dados }),
    editar: (idProduto, dados) =>
      requisitar(`/api/produtos/${idProduto}`, {
        method: 'PATCH',
        corpo: dados,
      }),
    excluir: (idProduto) =>
      requisitar(`/api/produtos/${idProduto}`, { method: 'DELETE' }),
  },
}

/** Junta a mensagem geral com os erros por campo (quando existirem). */
export function mensagemDeErro(erro) {
  if (!(erro instanceof ApiError)) {
    return erro?.message || 'Erro inesperado.'
  }
  const mensagens = Object.values(erro.corpo?.campos || {})
  return [erro.message, ...mensagens].filter(Boolean).join(' ')
}
