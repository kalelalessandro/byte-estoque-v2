/**
 * Operações: vendas/compras que atualizam o estoque e geram títulos financeiros.
 *
 * O formulário monta os itens, envia tudo para a API em uma transação única e a
 * lista é atualizada com a própria resposta (sem GET extra depois de salvar).
 * Parceiro é opcional; quando informado, os títulos gerados ficam ligados a ele.
 */
import { useEffect, useMemo, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import { agoraIso, formatarData, formatarDataHora, formatarMoeda } from '../formatos'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'
import Modal from '../components/Modal'

const TIPOS = {
  venda: { rotulo: 'Venda', classe: 'venda' },
  compra: { rotulo: 'Compra', classe: 'compra' },
}

const STATUS = {
  concluida: { rotulo: 'Concluída', classe: 'concluida' },
  cancelada: { rotulo: 'Cancelada', classe: 'cancelada' },
}

function dataDaquiA(dias = 30) {
  const data = new Date()
  data.setDate(data.getDate() + dias)
  return data.toLocaleDateString('sv-SE')
}

function itemVazio() {
  return { id_produto: '', quantidade: '1', valor_unitario: '' }
}

function formularioVazio() {
  return {
    tipo: 'venda',
    id_parceiro: '',
    ocorrencia: agoraIso(),
    observacoes: '',
    itens: [itemVazio()],
    parcelas: '1',
    vencimento: dataDaquiA(),
  }
}

function formularioDaOperacao(operacao) {
  return {
    tipo: operacao.tipo,
    id_parceiro: operacao.id_parceiro ? String(operacao.id_parceiro) : '',
    ocorrencia: (operacao.ocorrencia || agoraIso()).slice(0, 16),
    observacoes: operacao.observacoes || '',
    itens: operacao.itens.map((item) => ({
      id_produto: String(item.id_produto),
      quantidade: String(item.quantidade),
      valor_unitario: item.valor_unitario,
    })),
    parcelas: String(operacao.parcelas || 1),
    vencimento: operacao.titulos?.[0]?.vencimento || dataDaquiA(),
  }
}

export default function Operacoes() {
  const [operacoes, setOperacoes] = useState([])
  const [total, setTotal] = useState(0)
  const [filtros, setFiltros] = useState({ busca: '', tipo: '', status: '' })
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [modalAberto, setModalAberto] = useState(false)
  const [editando, setEditando] = useState(null)
  const [detalhe, setDetalhe] = useState(null)
  const [formulario, setFormulario] = useState(formularioVazio)
  const [produtos, setProdutos] = useState([])
  const [parceiros, setParceiros] = useState([])
  const [carregandoAuxiliares, setCarregandoAuxiliares] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroFormulario, setErroFormulario] = useState('')

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    const temporizador = setTimeout(() => {
      api.operacoes
        .listar({
          busca: filtros.busca.trim(),
          tipo: filtros.tipo,
          status: filtros.status,
          limit: 200,
        })
        .then((resposta) => {
          if (!ativo) return
          setOperacoes(resposta.dados.operacoes)
          setTotal(resposta.dados.total)
          setErro('')
        })
        .catch((falha) => {
          if (ativo) setErro(mensagemDeErro(falha))
        })
        .finally(() => {
          if (ativo) setCarregando(false)
        })
    }, 250)
    return () => {
      ativo = false
      clearTimeout(temporizador)
    }
  }, [filtros])

  const produtosPorId = useMemo(
    () => new Map(produtos.map((produto) => [produto.id_produto, produto])),
    [produtos],
  )

  const totalFormulario = formulario.itens.reduce(
    (soma, item) =>
      soma +
      Number(item.quantidade || 0) * Number(item.valor_unitario || 0),
    0,
  )

  async function carregarAuxiliares() {
    if (produtos.length > 0 && parceiros.length > 0) return
    setCarregandoAuxiliares(true)
    try {
      const [respostaProdutos, respostaParceiros] = await Promise.all([
        api.produtos.listar({ limit: 200 }),
        api.parceiros.listar({ limit: 200 }),
      ])
      setProdutos(respostaProdutos.dados.produtos)
      setParceiros(respostaParceiros.dados.parceiros)
    } catch (falha) {
      setErroFormulario(mensagemDeErro(falha))
    } finally {
      setCarregandoAuxiliares(false)
    }
  }

  function abrirNova() {
    setEditando(null)
    setFormulario(formularioVazio())
    setErroFormulario('')
    setAviso('')
    setModalAberto(true)
    carregarAuxiliares()
  }

  function abrirEdicao(operacao) {
    setEditando(operacao)
    setFormulario(formularioDaOperacao(operacao))
    setErroFormulario('')
    setAviso('')
    setModalAberto(true)
    carregarAuxiliares()
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

  function alterarItem(indice, campo, valor) {
    setFormulario((atual) => ({
      ...atual,
      itens: atual.itens.map((item, posicao) =>
        posicao === indice ? { ...item, [campo]: valor } : item,
      ),
    }))
  }

  function escolherProduto(indice, idProduto) {
    const produto = produtosPorId.get(Number(idProduto))
    setFormulario((atual) => ({
      ...atual,
      itens: atual.itens.map((item, posicao) =>
        posicao === indice
          ? {
              ...item,
              id_produto: idProduto,
              valor_unitario:
                item.valor_unitario || (produto ? produto.preco : ''),
            }
          : item,
      ),
    }))
  }

  function adicionarItem() {
    setFormulario((atual) => ({
      ...atual,
      itens: [...atual.itens, itemVazio()],
    }))
  }

  function removerItem(indice) {
    setFormulario((atual) =>
      atual.itens.length === 1
        ? atual
        : { ...atual, itens: atual.itens.filter((_, posicao) => posicao !== indice) },
    )
  }

  function combinaFiltros(operacao) {
    const busca = filtros.busca.trim().toLowerCase()
    if (filtros.tipo && operacao.tipo !== filtros.tipo) return false
    if (filtros.status && operacao.status !== filtros.status) return false
    if (!busca) return true
    return (
      (operacao.parceiro?.nome || '').toLowerCase().includes(busca) ||
      (operacao.observacoes || '').toLowerCase().includes(busca)
    )
  }

  function aplicarNaLista(operacao) {
    const existia = operacoes.some(
      (item) => item.id_operacao === operacao.id_operacao,
    )
    const combina = combinaFiltros(operacao)
    setOperacoes((atuais) => {
      if (!combina) {
        return atuais.filter(
          (item) => item.id_operacao !== operacao.id_operacao,
        )
      }
      if (existia) {
        return atuais.map((item) =>
          item.id_operacao === operacao.id_operacao ? operacao : item,
        )
      }
      return [operacao, ...atuais]
    })
    if (existia && !combina) setTotal((atual) => Math.max(0, atual - 1))
    if (!existia && combina) setTotal((atual) => atual + 1)
  }

  async function salvar(evento) {
    evento.preventDefault()
    setErroFormulario('')

    const itens = formulario.itens
      .filter((item) => item.id_produto && Number(item.quantidade) > 0)
      .map((item) => ({
        id_produto: Number(item.id_produto),
        quantidade: Number(item.quantidade),
        valor_unitario: item.valor_unitario,
      }))
    if (itens.length === 0) {
      setErroFormulario('Adicione pelo menos um item com produto e quantidade.')
      return
    }

    const dados = {
      tipo: formulario.tipo,
      id_parceiro: formulario.id_parceiro
        ? Number(formulario.id_parceiro)
        : null,
      ocorrencia: formulario.ocorrencia || null,
      observacoes: formulario.observacoes.trim() || null,
      itens,
      parcelas: Number(formulario.parcelas || 1),
      vencimento: formulario.vencimento || null,
    }

    setSalvando(true)
    try {
      const resposta = editando
        ? await api.operacoes.editar(editando.id_operacao, dados)
        : await api.operacoes.criar(dados)
      aplicarNaLista(resposta.dados)
      setAviso(
        editando
          ? 'Operação alterada com sucesso.'
          : 'Operação registrada e título financeiro gerado.',
      )
      setModalAberto(false)
      setEditando(null)
    } catch (falha) {
      setErroFormulario(mensagemDeErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function cancelar(operacao) {
    const confirmado = window.confirm(
      `Cancelar a operação #${operacao.id_operacao}? O estoque será estornado e os títulos cancelados.`,
    )
    if (!confirmado) return

    setErro('')
    setAviso('')
    try {
      const resposta = await api.operacoes.cancelar(operacao.id_operacao)
      aplicarNaLista(resposta.dados)
      setAviso('Operação cancelada, estoque estornado e títulos cancelados.')
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    }
  }

  const mostrarAjudaSemProdutos =
    !carregandoAuxiliares && produtos.length === 0

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <span className="rotulo-secao">Movimentações</span>
          <h2>Operações</h2>
          <p>
            Registre vendas e compras; o estoque e os títulos financeiros são
            atualizados automaticamente.
          </p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--primario"
            type="button"
            onClick={abrirNova}
          >
            <Icone nome="mais" />
            Nova operação
          </button>
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      <section className="painel">
        <div className="painel__topo painel__topo--filtros">
          <label className="campo-busca">
            <Icone nome="busca" />
            <input
              type="search"
              placeholder="Buscar por parceiro ou observação…"
              value={filtros.busca}
              onChange={(evento) =>
                setFiltros((atual) => ({ ...atual, busca: evento.target.value }))
              }
            />
          </label>
          <div className="filtros-operacoes">
            <select
              value={filtros.tipo}
              onChange={(evento) =>
                setFiltros((atual) => ({ ...atual, tipo: evento.target.value }))
              }
              aria-label="Filtrar por tipo"
            >
              <option value="">Todos os tipos</option>
              <option value="venda">Vendas</option>
              <option value="compra">Compras</option>
            </select>
            <select
              value={filtros.status}
              onChange={(evento) =>
                setFiltros((atual) => ({ ...atual, status: evento.target.value }))
              }
              aria-label="Filtrar por status"
            >
              <option value="">Todos os status</option>
              <option value="concluida">Concluídas</option>
              <option value="cancelada">Canceladas</option>
            </select>
            <span className="contador">
              {total} {total === 1 ? 'operação' : 'operações'}
            </span>
          </div>
        </div>

        {carregando ? (
          <div className="estado-carregando">Carregando operações…</div>
        ) : operacoes.length === 0 ? (
          <div className="estado-vazio">
            <Icone nome="operacoes" />
            <h3>Nenhuma operação registrada</h3>
            <p>
              Registre uma venda ou compra para atualizar o estoque e gerar os
              títulos financeiros.
            </p>
            <button
              className="botao botao--primario"
              type="button"
              onClick={abrirNova}
            >
              <Icone nome="mais" />
              Registrar primeira operação
            </button>
          </div>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela tabela--operacoes">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Tipo</th>
                  <th>Parceiro</th>
                  <th>Itens</th>
                  <th>Total</th>
                  <th>Títulos</th>
                  <th>Status</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {operacoes.map((operacao) => (
                  <tr key={operacao.id_operacao}>
                    <td className="tabela__numero">
                      {formatarDataHora(operacao.ocorrencia)}
                    </td>
                    <td>
                      <span
                        className={`badge-operacao badge-operacao--${
                          TIPOS[operacao.tipo]?.classe || 'venda'
                        }`}
                      >
                        {TIPOS[operacao.tipo]?.rotulo || operacao.tipo}
                      </span>
                    </td>
                    <td>
                      {operacao.parceiro?.nome || (
                        <span className="tabela__secundario">Sem parceiro</span>
                      )}
                    </td>
                    <td className="tabela__numero">
                      {operacao.itens.length}{' '}
                      {operacao.itens.length === 1 ? 'item' : 'itens'}
                    </td>
                    <td className="tabela__numero">
                      <strong>{formatarMoeda(operacao.total)}</strong>
                    </td>
                    <td className="tabela__numero">
                      {operacao.titulos.length}x
                      {operacao.parcelas > 1
                        ? ` (${operacao.parcelas}x)`
                        : ''}
                    </td>
                    <td>
                      <span
                        className={`badge-status badge-status--${
                          STATUS[operacao.status]?.classe || 'concluida'
                        }`}
                      >
                        {STATUS[operacao.status]?.rotulo || operacao.status}
                      </span>
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        <button
                          className="botao-icone"
                          type="button"
                          onClick={() => setDetalhe(operacao)}
                          aria-label={`Ver operação ${operacao.id_operacao}`}
                          title="Ver detalhes"
                        >
                          <Icone nome="olho" />
                        </button>
                        {operacao.pode_editar ? (
                          <button
                            className="botao-icone"
                            type="button"
                            onClick={() => abrirEdicao(operacao)}
                            aria-label={`Editar operação ${operacao.id_operacao}`}
                            title="Editar"
                          >
                            <Icone nome="lapis" />
                          </button>
                        ) : null}
                        {operacao.pode_cancelar ? (
                          <button
                            className="botao-icone botao-icone--perigo"
                            type="button"
                            onClick={() => cancelar(operacao)}
                            aria-label={`Cancelar operação ${operacao.id_operacao}`}
                            title="Cancelar operação"
                          >
                            <Icone nome="lixo" />
                          </button>
                        ) : null}
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
          titulo={editando ? `Editar operação #${editando.id_operacao}` : 'Nova operação'}
          aoFechar={fecharModal}
          largo
        >
          {carregandoAuxiliares ? (
            <div className="estado-carregando">
              Carregando produtos e parceiros…
            </div>
          ) : null}
          {mostrarAjudaSemProdutos ? (
            <Aviso>
              Cadastre pelo menos um produto antes de registrar uma operação.
            </Aviso>
          ) : null}

          <form className="formulario" onSubmit={salvar}>
            <div className="grade">
              <div className="campo">
                <label htmlFor="operacao-tipo">Tipo *</label>
                <select
                  id="operacao-tipo"
                  value={formulario.tipo}
                  onChange={(evento) =>
                    alterarCampo('tipo', evento.target.value)
                  }
                >
                  <option value="venda">Venda</option>
                  <option value="compra">Compra</option>
                </select>
              </div>

              <div className="campo">
                <label htmlFor="operacao-parceiro">Parceiro (opcional)</label>
                <select
                  id="operacao-parceiro"
                  value={formulario.id_parceiro}
                  onChange={(evento) =>
                    alterarCampo('id_parceiro', evento.target.value)
                  }
                >
                  <option value="">Sem parceiro</option>
                  {parceiros.map((parceiro) => (
                    <option
                      key={parceiro.id_parceiro}
                      value={parceiro.id_parceiro}
                    >
                      {parceiro.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo">
                <label htmlFor="operacao-ocorrencia">Ocorrência *</label>
                <input
                  id="operacao-ocorrencia"
                  type="datetime-local"
                  value={formulario.ocorrencia}
                  onChange={(evento) =>
                    alterarCampo('ocorrencia', evento.target.value)
                  }
                  required
                />
              </div>

              <div className="campo">
                <label htmlFor="operacao-parcelas">Parcelas *</label>
                <input
                  id="operacao-parcelas"
                  type="number"
                  min="1"
                  max="120"
                  step="1"
                  value={formulario.parcelas}
                  onChange={(evento) =>
                    alterarCampo('parcelas', evento.target.value)
                  }
                  required
                />
              </div>

              <div className="campo campo--largo">
                <label htmlFor="operacao-vencimento">
                  Primeiro vencimento *
                </label>
                <input
                  id="operacao-vencimento"
                  type="date"
                  value={formulario.vencimento}
                  onChange={(evento) =>
                    alterarCampo('vencimento', evento.target.value)
                  }
                  required
                />
              </div>
            </div>

            <section className="itens-operacao" aria-label="Itens da operação">
              <div className="itens-operacao__topo">
                <h3>Itens</h3>
                <button
                  className="botao botao--secundario botao--pequeno"
                  type="button"
                  onClick={adicionarItem}
                >
                  <Icone nome="mais" />
                  Adicionar item
                </button>
              </div>

              {formulario.itens.map((item, indice) => (
                <div className="item-operacao" key={indice}>
                  <div className="campo item-operacao__produto">
                    <label htmlFor={`item-produto-${indice}`}>Produto *</label>
                    <select
                      id={`item-produto-${indice}`}
                      value={item.id_produto}
                      onChange={(evento) =>
                        escolherProduto(indice, evento.target.value)
                      }
                      required
                    >
                      <option value="">Selecione…</option>
                      {produtos.map((produto) => (
                        <option
                          key={produto.id_produto}
                          value={produto.id_produto}
                        >
                          {produto.sku} · {produto.nome} · estoque{' '}
                          {produto.unidade_estoque}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="campo">
                    <label htmlFor={`item-quantidade-${indice}`}>
                      Quantidade *
                    </label>
                    <input
                      id={`item-quantidade-${indice}`}
                      type="number"
                      min="1"
                      step="1"
                      value={item.quantidade}
                      onChange={(evento) =>
                        alterarItem(indice, 'quantidade', evento.target.value)
                      }
                      required
                    />
                  </div>
                  <div className="campo">
                    <label htmlFor={`item-valor-${indice}`}>
                      Valor unitário *
                    </label>
                    <input
                      id={`item-valor-${indice}`}
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.valor_unitario}
                      onChange={(evento) =>
                        alterarItem(
                          indice,
                          'valor_unitario',
                          evento.target.value,
                        )
                      }
                      required
                    />
                  </div>
                  <button
                    className="botao-icone botao-icone--perigo item-operacao__remover"
                    type="button"
                    onClick={() => removerItem(indice)}
                    disabled={formulario.itens.length === 1}
                    aria-label="Remover item"
                    title="Remover item"
                  >
                    <Icone nome="lixo" />
                  </button>
                </div>
              ))}

              <div className="total-operacao">
                Total da operação: <strong>{formatarMoeda(totalFormulario)}</strong>
              </div>
            </section>

            <div className="campo">
              <label htmlFor="operacao-observacoes">Observações</label>
              <textarea
                id="operacao-observacoes"
                maxLength={2000}
                rows={2}
                placeholder="Informações opcionais sobre a operação"
                value={formulario.observacoes}
                onChange={(evento) =>
                  alterarCampo('observacoes', evento.target.value)
                }
              />
            </div>

            {erroFormulario ? <Aviso>{erroFormulario}</Aviso> : null}

            <div className="acoes-formulario">
              <button
                className="botao botao--primario"
                type="submit"
                disabled={
                  salvando ||
                  carregandoAuxiliares ||
                  produtos.length === 0
                }
              >
                {salvando
                  ? 'Salvando…'
                  : editando
                    ? 'Salvar alterações'
                    : 'Registrar operação'}
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

      {detalhe ? (
        <Modal
          titulo={`Operação #${detalhe.id_operacao}`}
          aoFechar={() => setDetalhe(null)}
          largo
        >
          <div className="detalhe">
            <dl className="detalhe__grade">
              <div>
                <dt>Tipo</dt>
                <dd>
                  <span
                    className={`badge-operacao badge-operacao--${
                      TIPOS[detalhe.tipo]?.classe || 'venda'
                    }`}
                  >
                    {TIPOS[detalhe.tipo]?.rotulo || detalhe.tipo}
                  </span>
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span
                    className={`badge-status badge-status--${
                      STATUS[detalhe.status]?.classe || 'concluida'
                    }`}
                  >
                    {STATUS[detalhe.status]?.rotulo || detalhe.status}
                  </span>
                </dd>
              </div>
              <div>
                <dt>Parceiro</dt>
                <dd>{detalhe.parceiro?.nome || 'Sem parceiro'}</dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>
                  <strong>{formatarMoeda(detalhe.total)}</strong>
                </dd>
              </div>
              <div>
                <dt>Ocorrência</dt>
                <dd>{formatarDataHora(detalhe.ocorrencia)}</dd>
              </div>
              <div>
                <dt>Títulos</dt>
                <dd>{detalhe.titulos.length}</dd>
              </div>
            </dl>

            <h3 className="detalhe__secao">Itens</h3>
            <div className="tabela-wrap">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th>Qtd.</th>
                    <th>Valor unit.</th>
                    <th>Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {detalhe.itens.map((item) => (
                    <tr key={item.id_produto}>
                      <td>
                        <strong>{item.nome}</strong>
                        <small className="tabela__secundario">{item.sku}</small>
                      </td>
                      <td>{item.quantidade}</td>
                      <td>{formatarMoeda(item.valor_unitario)}</td>
                      <td>{formatarMoeda(item.subtotal)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3 className="detalhe__secao">Títulos financeiros gerados</h3>
            <div className="tabela-wrap">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Vencimento</th>
                    <th>Tipo</th>
                    <th>Valor</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {detalhe.titulos.map((titulo) => (
                    <tr key={titulo.id_titulo}>
                      <td>{formatarData(titulo.vencimento)}</td>
                      <td>{titulo.tipo}</td>
                      <td>{formatarMoeda(titulo.valor)}</td>
                      <td>
                        {titulo.cancelado ? 'Cancelado' : 'Em aberto'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {detalhe.observacoes ? (
              <p className="guia__ajuda">Observações: {detalhe.observacoes}</p>
            ) : null}
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
