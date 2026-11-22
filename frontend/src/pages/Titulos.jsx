/**
 * Títulos financeiros: contas a pagar e a receber (aba da página Financeiro).
 *
 * Fluxo "Financeiro" do fluxograma: Listar Títulos -> Consultar Título (saldo e histórico
 * de baixas) -> Cancelar título; Registrar Título Manualmente (com o guia de interações do
 * parceiro); Registrar Pagamento/Recebimento (abre o formulário de baixa já com o título).
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import BaixaFormulario from '../components/BaixaFormulario'
import Icone from '../components/Icone'
import SituacaoTitulo from '../components/SituacaoTitulo'
import TituloDetalhe from '../components/TituloDetalhe'
import TituloFormulario from '../components/TituloFormulario'
import { formatarData, formatarMoeda } from '../formatos'

const FILTROS_TIPO = [
  { id: '', rotulo: 'Todos' },
  { id: 'receber', rotulo: 'A receber' },
  { id: 'pagar', rotulo: 'A pagar' },
]

const FILTROS_SITUACAO = [
  { id: '', rotulo: 'Qualquer situação' },
  { id: 'aberto', rotulo: 'Em aberto' },
  { id: 'parcial', rotulo: 'Parcial' },
  { id: 'quitado', rotulo: 'Quitado' },
  { id: 'cancelado', rotulo: 'Cancelado' },
]

export default function Titulos({ aoMudarAba = null }) {
  const [titulos, setTitulos] = useState([])
  const [total, setTotal] = useState(0)
  const [busca, setBusca] = useState('')
  const [tipo, setTipo] = useState('')
  const [situacao, setSituacao] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [versao, setVersao] = useState(0) // incrementa para recarregar a lista
  // null | { nome: 'formulario' } | { nome: 'detalhe', id } | { nome: 'baixa', id, voltar }
  const [modal, setModal] = useState(null)

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    const atraso = busca.trim() ? 250 : 0
    const temporizador = setTimeout(() => {
      api.titulos
        .listar({ busca: busca.trim(), tipo, situacao, limit: 200 })
        .then((resposta) => {
          if (!ativo) return
          setTitulos(resposta.dados.titulos)
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
  }, [busca, tipo, situacao, versao])

  const recarregar = () => setVersao((atual) => atual + 1)
  const filtrando = Boolean(busca || tipo || situacao)

  function aoRegistrar(titulo) {
    recarregar()
    setAviso('Título registrado com sucesso.')
    setModal({ nome: 'detalhe', id: titulo.id_titulo })
  }

  function aoCancelar() {
    recarregar()
    setAviso('Título cancelado com sucesso.')
    setModal(null)
  }

  function aoBaixar(baixa) {
    recarregar()
    setAviso(
      `Baixa registrada com sucesso${baixa.parceiro ? ` para ${baixa.parceiro.nome}` : ''}.`,
    )
    setModal(null)
  }

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <h3>Títulos financeiros</h3>
          <p>
            Contas a pagar e a receber, com saldo, histórico de baixas e as interações do
            parceiro como guia.
          </p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--primario"
            type="button"
            onClick={() => {
              setAviso('')
              setModal({ nome: 'formulario' })
            }}
          >
            <Icone nome="mais" />
            Registrar título manualmente
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
              placeholder="Buscar por parceiro ou descrição…"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
              aria-label="Buscar títulos"
            />
          </label>
          <span className="contador">
            {total} {total === 1 ? 'título' : 'títulos'}
          </span>
        </div>

        <div className="filtros" role="group" aria-label="Filtrar por tipo">
          {FILTROS_TIPO.map((filtro) => (
            <button
              key={filtro.id || 'todos'}
              type="button"
              className={`filtro ${tipo === filtro.id ? 'filtro--ativo' : ''}`.trim()}
              aria-pressed={tipo === filtro.id}
              onClick={() => setTipo(filtro.id)}
            >
              {filtro.rotulo}
            </button>
          ))}
        </div>
        <div className="filtros" role="group" aria-label="Filtrar por situação">
          {FILTROS_SITUACAO.map((filtro) => (
            <button
              key={filtro.id || 'qualquer'}
              type="button"
              className={`filtro ${situacao === filtro.id ? 'filtro--ativo' : ''}`.trim()}
              aria-pressed={situacao === filtro.id}
              onClick={() => setSituacao(filtro.id)}
            >
              {filtro.rotulo}
            </button>
          ))}
        </div>

        {carregando ? (
          <div className="estado-carregando">Carregando títulos…</div>
        ) : titulos.length === 0 ? (
          <div className="estado-vazio">
            <Icone nome="dinheiro" />
            <h3>Nenhum título por aqui</h3>
            <p>
              {filtrando
                ? 'Nenhum resultado para esse filtro.'
                : 'Registre o primeiro título a pagar ou a receber.'}
            </p>
          </div>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Vencimento</th>
                  <th>Descrição</th>
                  <th>Parceiro</th>
                  <th>Tipo</th>
                  <th>Valor</th>
                  <th>Saldo</th>
                  <th>Situação</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {titulos.map((titulo) => (
                  <tr key={titulo.id_titulo}>
                    <td>{formatarData(titulo.vencimento)}</td>
                    <td>
                      <button
                        className="tabela__link"
                        type="button"
                        onClick={() => setModal({ nome: 'detalhe', id: titulo.id_titulo })}
                      >
                        {titulo.descricao.length > 60
                          ? `${titulo.descricao.slice(0, 60)}…`
                          : titulo.descricao}
                      </button>
                    </td>
                    <td>
                      {titulo.parceiro ? (
                        titulo.parceiro.nome
                      ) : (
                        <span className="tabela__secundario">Sem parceiro</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge badge--${titulo.natureza}`}>
                        {titulo.natureza === 'recebimento' ? 'A receber' : 'A pagar'}
                      </span>
                    </td>
                    <td>{formatarMoeda(titulo.valor)}</td>
                    <td className={`valor valor--${titulo.natureza}`}>
                      {formatarMoeda(titulo.saldo_pendente)}
                    </td>
                    <td>
                      <SituacaoTitulo titulo={titulo} />
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        <button
                          className="botao-icone"
                          type="button"
                          onClick={() => setModal({ nome: 'detalhe', id: titulo.id_titulo })}
                          aria-label={`Consultar título ${titulo.descricao}`}
                          title="Consultar título"
                        >
                          <Icone nome="olho" />
                        </button>
                        {titulo.pode_baixar ? (
                          <button
                            className="botao-icone"
                            type="button"
                            onClick={() =>
                              setModal({ nome: 'baixa', id: titulo.id_titulo, voltar: null })
                            }
                            aria-label={`Dar baixa em ${titulo.descricao}`}
                            title={
                              titulo.natureza === 'pagamento'
                                ? 'Registrar pagamento'
                                : 'Registrar recebimento'
                            }
                          >
                            <Icone nome="dinheiro" />
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

      {modal?.nome === 'formulario' ? (
        <TituloFormulario aoFechar={() => setModal(null)} aoSalvo={aoRegistrar} />
      ) : null}
      {modal?.nome === 'detalhe' ? (
        <TituloDetalhe
          idTitulo={modal.id}
          aoFechar={() => setModal(null)}
          aoCancelado={aoCancelar}
          aoDarBaixa={(titulo) => setModal({ nome: 'baixa', id: titulo.id_titulo })}
        />
      ) : null}
      {modal?.nome === 'baixa' ? (
        <BaixaFormulario
          idTituloInicial={modal.id}
          aoFechar={() => setModal(null)}
          aoSalvo={aoBaixar}
          aoAbrirCaixa={
            aoMudarAba
              ? () => {
                  setModal(null)
                  aoMudarAba('caixas')
                }
              : null
          }
        />
      ) : null}
    </div>
  )
}
