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

  parceiros: {
    // tipo: 'todos' | 'cliente' | 'fornecedor' | 'ambos'
    listar: ({ busca = '', tipo = 'todos', limit = 50, offset = 0 } = {}) => {
      const parametros = new URLSearchParams()
      if (busca) parametros.set('busca', busca)
      if (tipo !== 'todos') parametros.set('tipo', tipo)
      parametros.set('limit', String(limit))
      parametros.set('offset', String(offset))
      return requisitar(`/api/parceiros?${parametros.toString()}`)
    },
    // Dados completos do parceiro + histórico de interações.
    obter: (idParceiro) => requisitar(`/api/parceiros/${idParceiro}`),
    criar: (dados) =>
      requisitar('/api/parceiros', { method: 'POST', corpo: dados }),
    editar: (idParceiro, dados) =>
      requisitar(`/api/parceiros/${idParceiro}`, {
        method: 'PATCH',
        corpo: dados,
      }),
    excluir: (idParceiro) =>
      requisitar(`/api/parceiros/${idParceiro}`, { method: 'DELETE' }),
  },

  interacoes: {
    // Guia: interações (contratos e compras) de todos os parceiros, ou só de um.
    listar: ({ id_parceiro = 0, limit = 20, offset = 0 } = {}) => {
      const parametros = new URLSearchParams()
      if (id_parceiro) parametros.set('id_parceiro', String(id_parceiro))
      parametros.set('limit', String(limit))
      parametros.set('offset', String(offset))
      return requisitar(`/api/interacoes?${parametros.toString()}`)
    },
    registrar: (idParceiro, dados) =>
      requisitar(`/api/parceiros/${idParceiro}/interacoes`, {
        method: 'POST',
        corpo: dados,
      }),
    editar: (idParceiro, idInteracao, dados) =>
      requisitar(`/api/parceiros/${idParceiro}/interacoes/${idInteracao}`, {
        method: 'PATCH',
        corpo: dados,
      }),
  },

  caixas: {
    // situacao: 'aberto' | 'fechado'
    listar: ({ situacao = '', limit = 50, offset = 0 } = {}) => {
      const parametros = new URLSearchParams()
      if (situacao) parametros.set('situacao', situacao)
      parametros.set('limit', String(limit))
      parametros.set('offset', String(offset))
      return requisitar(`/api/caixas?${parametros.toString()}`)
    },
    // O caixa aberto agora, com valores e extrato: { dados: { caixa: {...} | null } }.
    atual: () => requisitar('/api/caixas/atual'),
    obter: (idCaixa) => requisitar(`/api/caixas/${idCaixa}`),
    abrir: (dados) => requisitar('/api/caixas', { method: 'POST', corpo: dados }),
    // Suprimento ou sangria: { tipo, valor, descricao }.
    movimentar: (idCaixa, dados) =>
      requisitar(`/api/caixas/${idCaixa}/movimentos`, { method: 'POST', corpo: dados }),
    fechar: (idCaixa, dados) =>
      requisitar(`/api/caixas/${idCaixa}/fechar`, { method: 'POST', corpo: dados }),
  },

  titulos: {
    // tipo: 'pagar' | 'receber'; situacao: 'aberto' | 'parcial' | 'quitado' | 'cancelado'
    listar: ({ busca = '', tipo = '', situacao = '', id_parceiro = 0, limit = 50, offset = 0 } = {}) => {
      const parametros = new URLSearchParams()
      if (busca) parametros.set('busca', busca)
      if (tipo) parametros.set('tipo', tipo)
      if (situacao) parametros.set('situacao', situacao)
      if (id_parceiro) parametros.set('id_parceiro', String(id_parceiro))
      parametros.set('limit', String(limit))
      parametros.set('offset', String(offset))
      return requisitar(`/api/titulos?${parametros.toString()}`)
    },
    // Dados do título + saldo + histórico de baixas.
    obter: (idTitulo) => requisitar(`/api/titulos/${idTitulo}`),
    criar: (dados) =>
      requisitar('/api/titulos', { method: 'POST', corpo: dados }),
    cancelar: (idTitulo) =>
      requisitar(`/api/titulos/${idTitulo}/cancelar`, { method: 'POST' }),
  },

  baixas: {
    // tipo: 'recebimento' | 'pagamento'; forma: 'dinheiro' | 'pix' | 'cartao'
    listar: ({ busca = '', tipo = '', forma = '', limit = 50, offset = 0 } = {}) => {
      const parametros = new URLSearchParams()
      if (busca) parametros.set('busca', busca)
      if (tipo) parametros.set('tipo', tipo)
      if (forma) parametros.set('forma', forma)
      parametros.set('limit', String(limit))
      parametros.set('offset', String(offset))
      return requisitar(`/api/baixas?${parametros.toString()}`)
    },
    obter: (idBaixa) => requisitar(`/api/baixas/${idBaixa}`),
    // Títulos com saldo e parceiro, caixas abertos e formas de pagamento.
    opcoes: () => requisitar('/api/baixas/opcoes'),
    registrar: (dados) =>
      requisitar('/api/baixas', { method: 'POST', corpo: dados }),
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
