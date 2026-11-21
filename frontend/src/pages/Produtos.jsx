/** Catálogo de produtos: listar, criar, editar e excluir. */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'
import Modal from '../components/Modal'

const MOEDA = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

const FORMULARIO_VAZIO = {
  sku: '',
  id_categoria: '',
  nome: '',
  descricao: '',
  unidade_estoque: '0',
  preco: '',
}

export default function Produtos({ aoNavegar }) {
  const [produtos, setProdutos] = useState([])
  const [categorias, setCategorias] = useState([])
  const [carregandoCategorias, setCarregandoCategorias] = useState(false)
  const [total, setTotal] = useState(0)
  const [busca, setBusca] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [modalAberto, setModalAberto] = useState(false)
  const [editando, setEditando] = useState(null)
  const [formulario, setFormulario] = useState(FORMULARIO_VAZIO)
  const [erroFormulario, setErroFormulario] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    // Busca imediata ao abrir a tela; debounce só quando o usuário digita.
    const atraso = busca.trim() ? 250 : 0
    const temporizador = setTimeout(() => {
      api.produtos
        .listar({ busca: busca.trim(), limit: 200 })
        .then((resposta) => {
          if (!ativo) return
          setProdutos(resposta.dados.produtos)
          setTotal(resposta.dados.total)
          setErro('')
        })
        .catch((falha) => {
          if (ativo) setErro(mensagemDeErro(falha))
        })
        .finally(() => {
          if (ativo) setCarregando(false)
        })
    }, atraso)

    return () => {
      ativo = false
      clearTimeout(temporizador)
    }
  }, [busca])

  async function carregarCategorias() {
    if (categorias.length > 0) return categorias
    setCarregandoCategorias(true)
    try {
      const resposta = await api.categorias.listar()
      setCategorias(resposta.dados.categorias)
      return resposta.dados.categorias
    } catch (falha) {
      setErro(mensagemDeErro(falha))
      return []
    } finally {
      setCarregandoCategorias(false)
    }
  }

  function abrirNovo() {
    setEditando(null)
    setFormulario({
      ...FORMULARIO_VAZIO,
      id_categoria: categorias[0]?.id_categoria || '',
    })
    setErroFormulario('')
    setAviso('')
    setModalAberto(true)
    carregarCategorias()
  }

  function abrirEdicao(produto) {
    setEditando(produto)
    setFormulario({
      sku: produto.sku,
      id_categoria: produto.id_categoria,
      nome: produto.nome,
      descricao: produto.descricao || '',
      unidade_estoque: String(produto.unidade_estoque),
      preco: produto.preco,
    })
    setErroFormulario('')
    setAviso('')
    setModalAberto(true)
    carregarCategorias()
  }

  function fecharModal() {
    if (salvando) return
    setModalAberto(false)
    setEditando(null)
    setErroFormulario('')
  }

  function alterarCampo(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  function combinaComBusca(produto) {
    const termo = busca.trim().toLowerCase()
    if (!termo) return true
    return (
      produto.nome.toLowerCase().includes(termo) ||
      produto.sku.toLowerCase().includes(termo)
    )
  }

  async function salvar(evento) {
    evento.preventDefault()
    setErroFormulario('')

    if (!formulario.id_categoria) {
      setErroFormulario('Selecione uma categoria para o produto.')
      return
    }
    if (!formulario.sku.trim() || !formulario.nome.trim()) {
      setErroFormulario('SKU e nome do produto são obrigatórios.')
      return
    }

    const dados = {
      sku: formulario.sku.trim(),
      id_categoria: Number(formulario.id_categoria),
      nome: formulario.nome.trim(),
      descricao: formulario.descricao.trim() || null,
      unidade_estoque: Number(formulario.unidade_estoque || 0),
      preco: formulario.preco,
    }

    setSalvando(true)
    try {
      // Atualização local com a própria resposta: evita o GET de recarga logo
      // depois do POST/PATCH e deixa o salvamento perceptivelmente instantâneo.
      const resposta = editando
        ? await api.produtos.editar(editando.id_produto, dados)
        : await api.produtos.criar(dados)
      const salvo = resposta.dados
      const combina = combinaComBusca(salvo)
      const jaEstavaNaLista = produtos.some(
        (produto) => produto.id_produto === salvo.id_produto,
      )

      setProdutos((atuais) => {
        if (editando) {
          if (!combina) {
            return atuais.filter(
              (produto) => produto.id_produto !== salvo.id_produto,
            )
          }
          if (jaEstavaNaLista) {
            return atuais.map((produto) =>
              produto.id_produto === salvo.id_produto ? salvo : produto,
            )
          }
          return [salvo, ...atuais]
        }
        return combina ? [salvo, ...atuais] : atuais
      })

      if (editando) {
        if (jaEstavaNaLista && !combina) {
          setTotal((atual) => Math.max(0, atual - 1))
        }
        if (!jaEstavaNaLista && combina) {
          setTotal((atual) => atual + 1)
        }
      } else if (combina) {
        setTotal((atual) => atual + 1)
      }

      setAviso(
        editando
          ? 'Produto atualizado com sucesso.'
          : 'Produto criado com sucesso.',
      )
      setModalAberto(false)
      setEditando(null)
    } catch (falha) {
      setErroFormulario(mensagemDeErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function excluir(produto) {
    const confirmado = window.confirm(
      `Excluir o produto "${produto.nome}" (${produto.sku})?`,
    )
    if (!confirmado) return

    setAviso('')
    try {
      await api.produtos.excluir(produto.id_produto)
      setProdutos((atuais) =>
        atuais.filter((item) => item.id_produto !== produto.id_produto),
      )
      setTotal((atual) => Math.max(0, atual - 1))
      setAviso('Produto excluído com sucesso.')
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <span className="rotulo-secao">Catálogo</span>
          <h2>Produtos</h2>
          <p>Gerencie os itens e o saldo de estoque da sua empresa.</p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--secundario"
            type="button"
            onClick={() => aoNavegar('categorias')}
          >
            <Icone nome="categorias" />
            Gerenciar categorias
          </button>
          <button
            className="botao botao--primario"
            type="button"
            onClick={abrirNovo}
          >
            <Icone nome="mais" />
            Novo produto
          </button>
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      <section className="painel">
        <div className="painel__topo">
          <label className="campo-busca">
            <Icone nome="busca" />
            <input
              type="search"
              placeholder="Buscar por nome ou SKU…"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
              aria-label="Buscar produtos"
            />
          </label>
          <span className="contador">
            {total} {total === 1 ? 'produto' : 'produtos'}
          </span>
        </div>

        {carregando ? (
          <div className="estado-carregando">Carregando produtos…</div>
        ) : produtos.length === 0 ? (
          <div className="estado-vazio">
            <Icone nome="produtos" />
            <h3>Nenhum produto por aqui</h3>
            <p>
              {busca
                ? 'Nenhum resultado para essa busca.'
                : 'Cadastre o primeiro produto para começar a controlar seu estoque.'}
            </p>
            {!busca ? (
              <button
                className="botao botao--primario"
                type="button"
                onClick={abrirNovo}
              >
                <Icone nome="mais" />
                Cadastrar produto
              </button>
            ) : null}
          </div>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Produto</th>
                  <th>Categoria</th>
                  <th>Estoque</th>
                  <th>Preço</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {produtos.map((produto) => (
                  <tr key={produto.id_produto}>
                    <td>
                      <span className="sku">{produto.sku}</span>
                    </td>
                    <td>
                      <strong className="tabela__destaque">{produto.nome}</strong>
                      {produto.descricao ? (
                        <small className="tabela__secundario">
                          {produto.descricao}
                        </small>
                      ) : null}
                    </td>
                    <td>
                      <span className="badge badge--categoria">
                        {produto.categoria_nome || 'Sem categoria'}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          produto.unidade_estoque === 0 ? 'badge--alerta' : ''
                        }`.trim()}
                      >
                        {produto.unidade_estoque} un.
                      </span>
                    </td>
                    <td className="tabela__numero">
                      {MOEDA.format(Number(produto.preco))}
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        <button
                          className="botao-icone"
                          type="button"
                          onClick={() => abrirEdicao(produto)}
                          aria-label={`Editar ${produto.nome}`}
                          title="Editar"
                        >
                          <Icone nome="lapis" />
                        </button>
                        <button
                          className="botao-icone botao-icone--perigo"
                          type="button"
                          onClick={() => excluir(produto)}
                          aria-label={`Excluir ${produto.nome}`}
                          title="Excluir"
                        >
                          <Icone nome="lixo" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {modalAberto ? (
        <Modal
          titulo={editando ? 'Editar produto' : 'Novo produto'}
          aoFechar={fecharModal}
          largo
        >
          {carregandoCategorias ? (
            <div className="estado-carregando">Carregando categorias…</div>
          ) : categorias.length === 0 ? (
            <div className="alerta">
              Cadastre uma categoria antes de criar produtos.{' '}
              <button
                className="botao botao--texto"
                type="button"
                onClick={() => {
                  fecharModal()
                  aoNavegar('categorias')
                }}
              >
                Criar categoria
              </button>
            </div>
          ) : null}

          <form className="formulario" onSubmit={salvar}>
            <div className="grade">
              <div className="campo">
                <label htmlFor="produto-sku">SKU *</label>
                <input
                  id="produto-sku"
                  type="text"
                  maxLength={64}
                  placeholder="Ex.: CAN-001"
                  value={formulario.sku}
                  onChange={(evento) =>
                    alterarCampo('sku', evento.target.value)
                  }
                  required
                />
              </div>

              <div className="campo">
                <label htmlFor="produto-categoria">Categoria *</label>
                <select
                  id="produto-categoria"
                  value={formulario.id_categoria}
                  onChange={(evento) =>
                    alterarCampo('id_categoria', evento.target.value)
                  }
                  disabled={carregandoCategorias}
                  required
                >
                  <option value="">
                    {carregandoCategorias ? 'Carregando…' : 'Selecione…'}
                  </option>
                  {categorias.map((categoria) => (
                    <option
                      key={categoria.id_categoria}
                      value={categoria.id_categoria}
                    >
                      {categoria.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo campo--largo">
                <label htmlFor="produto-nome">Nome *</label>
                <input
                  id="produto-nome"
                  type="text"
                  maxLength={150}
                  placeholder="Ex.: Caneta azul"
                  value={formulario.nome}
                  onChange={(evento) =>
                    alterarCampo('nome', evento.target.value)
                  }
                  required
                />
              </div>

              <div className="campo campo--largo">
                <label htmlFor="produto-descricao">Descrição</label>
                <textarea
                  id="produto-descricao"
                  maxLength={500}
                  rows={3}
                  placeholder="Detalhes opcionais do produto"
                  value={formulario.descricao}
                  onChange={(evento) =>
                    alterarCampo('descricao', evento.target.value)
                  }
                />
              </div>

              <div className="campo">
                <label htmlFor="produto-estoque">Unidade de estoque</label>
                <input
                  id="produto-estoque"
                  type="number"
                  min="0"
                  step="1"
                  value={formulario.unidade_estoque}
                  onChange={(evento) =>
                    alterarCampo('unidade_estoque', evento.target.value)
                  }
                />
              </div>

              <div className="campo">
                <label htmlFor="produto-preco">Preço (R$) *</label>
                <input
                  id="produto-preco"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0,00"
                  value={formulario.preco}
                  onChange={(evento) =>
                    alterarCampo('preco', evento.target.value)
                  }
                  required
                />
              </div>
            </div>

            {erroFormulario ? <Aviso>{erroFormulario}</Aviso> : null}

            <div className="acoes-formulario">
              <button
                className="botao botao--primario"
                type="submit"
                disabled={
                  salvando ||
                  carregandoCategorias ||
                  categorias.length === 0
                }
              >
                {salvando
                  ? 'Salvando…'
                  : editando
                    ? 'Salvar alterações'
                    : 'Criar produto'}
              </button>
              <button
                className="botao botao--secundario"
                type="button"
                onClick={fecharModal}
                disabled={salvando}
              >
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      ) : null}
    </div>
  )
}
