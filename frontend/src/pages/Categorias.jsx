/** Gerenciamento de categorias usadas nos produtos. */
import { useCallback, useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'
import Modal from '../components/Modal'

export default function Categorias({ aoNavegar }) {
  const [categorias, setCategorias] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [nomeNovo, setNomeNovo] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [renomeando, setRenomeando] = useState(null)
  const [novoNome, setNovoNome] = useState('')
  const [erroModal, setErroModal] = useState('')

  const carregar = useCallback(() => {
    let ativo = true
    setCarregando(true)
    setErro('')

    // A API já devolve `produtos_count`; não é preciso baixar os produtos.
    api.categorias
      .listar()
      .then((resposta) => {
        if (ativo) setCategorias(resposta.dados.categorias)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })

    return () => {
      ativo = false
    }
  }, [])

  useEffect(() => carregar(), [carregar])

  async function criar(evento) {
    evento.preventDefault()
    const nome = nomeNovo.trim()
    if (!nome) {
      setErro('Informe o nome da categoria.')
      return
    }

    setSalvando(true)
    setErro('')
    setAviso('')
    try {
      const resposta = await api.categorias.criar(nome)
      const nova = resposta.dados
      setCategorias((atuais) =>
        [...atuais, nova].sort((a, b) =>
          a.nome.localeCompare(b.nome, 'pt-BR'),
        ),
      )
      setNomeNovo('')
      setAviso('Categoria criada com sucesso.')
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  function abrirRenomear(categoria) {
    setRenomeando(categoria)
    setNovoNome(categoria.nome)
    setErroModal('')
    setAviso('')
  }

  function fecharRenomear() {
    if (salvando) return
    setRenomeando(null)
    setNovoNome('')
    setErroModal('')
  }

  async function renomear(evento) {
    evento.preventDefault()
    const nome = novoNome.trim()
    if (!nome) {
      setErroModal('Informe o novo nome.')
      return
    }

    setSalvando(true)
    setErroModal('')
    try {
      const resposta = await api.categorias.renomear(
        renomeando.id_categoria,
        nome,
      )
      const atualizada = resposta.dados
      setCategorias((atuais) =>
        atuais
          .map((categoria) =>
            categoria.id_categoria === atualizada.id_categoria
              ? atualizada
              : categoria,
          )
          .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')),
      )
      setRenomeando(null)
      setNovoNome('')
      setErroModal('')
      setAviso('Categoria renomeada com sucesso.')
    } catch (falha) {
      setErroModal(mensagemDeErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function excluir(categoria) {
    if ((categoria.produtos_count || 0) > 0) {
      setErro(
        'Não é possível excluir uma categoria com produtos vinculados. Mova ou exclua os produtos antes.',
      )
      return
    }

    const confirmado = window.confirm(`Excluir a categoria "${categoria.nome}"?`)
    if (!confirmado) return

    setErro('')
    setAviso('')
    try {
      await api.categorias.excluir(categoria.id_categoria)
      setCategorias((atuais) =>
        atuais.filter((item) => item.id_categoria !== categoria.id_categoria),
      )
      setAviso('Categoria excluída com sucesso.')
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <span className="rotulo-secao">Catálogo</span>
          <h2>Categorias</h2>
          <p>Organize os produtos da sua empresa por categorias.</p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--secundario"
            type="button"
            onClick={() => aoNavegar('produtos')}
          >
            <Icone nome="produtos" />
            Ver produtos
          </button>
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      <section className="painel painel--formulario">
        <div className="painel__topo">
          <div>
            <h3>Nova categoria</h3>
            <p className="painel__ajuda">
              Crie categorias para classificar os produtos do catálogo.
            </p>
          </div>
        </div>
        <form className="categoria-form" onSubmit={criar}>
          <label className="campo">
            <span>Nome da categoria</span>
            <input
              type="text"
              maxLength={100}
              placeholder="Ex.: Ferramentas, Papelaria, Limpeza…"
              value={nomeNovo}
              onChange={(evento) => setNomeNovo(evento.target.value)}
            />
          </label>
          <button
            className="botao botao--primario"
            type="submit"
            disabled={salvando}
          >
            <Icone nome="mais" />
            {salvando ? 'Criando…' : 'Criar categoria'}
          </button>
        </form>
      </section>

      <section className="painel">
        <div className="painel__topo">
          <h3>Suas categorias</h3>
          <span className="contador">
            {categorias.length}{' '}
            {categorias.length === 1 ? 'categoria' : 'categorias'}
          </span>
        </div>

        <p className="painel__ajuda">
          A exclusão é permitida apenas para categorias <strong>sem produtos</strong>{' '}
          vinculados.
        </p>

        {carregando ? (
          <div className="estado-carregando">Carregando categorias…</div>
        ) : categorias.length === 0 ? (
          <div className="estado-vazio">
            <Icone nome="categorias" />
            <h3>Nenhuma categoria cadastrada</h3>
            <p>Crie a primeira categoria para poder cadastrar produtos.</p>
          </div>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Produtos vinculados</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {categorias.map((categoria) => {
                  const quantidade = categoria.produtos_count || 0
                  return (
                    <tr key={categoria.id_categoria}>
                      <td>
                        <strong className="tabela__destaque">
                          {categoria.nome}
                        </strong>
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            quantidade > 0 ? 'badge--categoria' : ''
                          }`.trim()}
                        >
                          {quantidade}{' '}
                          {quantidade === 1 ? 'produto' : 'produtos'}
                        </span>
                      </td>
                      <td>
                        <div className="tabela__acoes">
                          <button
                            className="botao-icone"
                            type="button"
                            onClick={() => abrirRenomear(categoria)}
                            aria-label={`Renomear ${categoria.nome}`}
                            title="Renomear"
                          >
                            <Icone nome="lapis" />
                          </button>
                          <button
                            className="botao-icone botao-icone--perigo"
                            type="button"
                            onClick={() => excluir(categoria)}
                            disabled={quantidade > 0}
                            title={
                              quantidade > 0
                                ? 'Mova ou exclua os produtos antes de apagar esta categoria.'
                                : 'Excluir categoria'
                            }
                            aria-label={`Excluir ${categoria.nome}`}
                          >
                            <Icone nome="lixo" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {renomeando ? (
        <Modal
          titulo="Renomear categoria"
          aoFechar={fecharRenomear}
        >
          <form className="formulario" onSubmit={renomear}>
            <div className="campo">
              <label htmlFor="categoria-nome">Novo nome</label>
              <input
                id="categoria-nome"
                type="text"
                maxLength={100}
                value={novoNome}
                onChange={(evento) => setNovoNome(evento.target.value)}
                autoFocus
                required
              />
            </div>
            {erroModal ? <Aviso>{erroModal}</Aviso> : null}
            <div className="acoes-formulario">
              <button
                className="botao botao--primario"
                type="submit"
                disabled={salvando}
              >
                {salvando ? 'Salvando…' : 'Salvar nome'}
              </button>
              <button
                className="botao botao--secundario"
                type="button"
                onClick={fecharRenomear}
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
