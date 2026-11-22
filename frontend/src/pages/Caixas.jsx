/**
 * Caixas: abrir o caixa, registrar suprimentos/sangrias, consultar movimentações e valores,
 * e fechar com o valor contado (aba da página Financeiro).
 *
 * Fluxo "Caixa" do fluxograma: Abrir Caixa -> Registrar Suprimento/Sangria -> Consultar
 * Movimentações e Valores -> Fechar Caixa -> Informar Valor Contado -> Confirmar. Só há um
 * caixa aberto por empresa; as baixas financeiras entram nele (e o extrato mostra cada uma).
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import CaixaAbrirFormulario from '../components/CaixaAbrirFormulario'
import CaixaDetalhe from '../components/CaixaDetalhe'
import CaixaExtrato from '../components/CaixaExtrato'
import CaixaFecharFormulario from '../components/CaixaFecharFormulario'
import CaixaMovimentoFormulario from '../components/CaixaMovimentoFormulario'
import CaixaValores, { classeDiferenca } from '../components/CaixaValores'
import Icone from '../components/Icone'
import { formatarDataHora, formatarMoeda } from '../formatos'

export default function Caixas() {
  // undefined = carregando; null = nenhum caixa aberto; objeto = caixa aberto
  const [atual, setAtual] = useState(undefined)
  const [historico, setHistorico] = useState([])
  const [totalHistorico, setTotalHistorico] = useState(0)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [versao, setVersao] = useState(0) // incrementa para recarregar tudo
  // null | 'abrir' | 'movimento' | 'fechar' | { nome: 'detalhe', id }
  const [modal, setModal] = useState(null)

  useEffect(() => {
    let ativo = true
    Promise.all([
      api.caixas.atual(),
      api.caixas.listar({ situacao: 'fechado', limit: 50 }),
    ])
      .then(([resposta, fechados]) => {
        if (!ativo) return
        setAtual(resposta.dados.caixa)
        setHistorico(fechados.dados.caixas)
        setTotalHistorico(fechados.dados.total)
        setErro('')
      })
      .catch((falha) => {
        if (!ativo) return
        setErro(mensagemDeErro(falha))
        setAtual((anterior) => (anterior === undefined ? null : anterior))
      })
    return () => {
      ativo = false
    }
  }, [versao])

  const recarregar = () => setVersao((atualVersao) => atualVersao + 1)

  function concluir(mensagem) {
    setModal(null)
    setAviso(mensagem)
    recarregar()
  }

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <h3>Caixas</h3>
          <p>
            Abertura, suprimentos, sangrias e fechamento do caixa, com o extrato de tudo o
            que entrou e saiu.
          </p>
        </div>
        <div className="pagina__acoes">
          {atual ? (
            <>
              <button
                className="botao botao--secundario"
                type="button"
                onClick={() => {
                  setAviso('')
                  setModal('movimento')
                }}
              >
                <Icone nome="mais" />
                Registrar suprimento/sangria
              </button>
              <button
                className="botao botao--primario"
                type="button"
                onClick={() => {
                  setAviso('')
                  setModal('fechar')
                }}
              >
                Fechar caixa
              </button>
            </>
          ) : atual === null ? (
            <button
              className="botao botao--primario"
              type="button"
              onClick={() => {
                setAviso('')
                setModal('abrir')
              }}
            >
              <Icone nome="mais" />
              Abrir caixa
            </button>
          ) : null}
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      {atual === undefined ? (
        <div className="estado-carregando">Carregando caixa…</div>
      ) : atual === null ? (
        <section className="painel">
          <div className="estado-vazio">
            <Icone nome="dinheiro" />
            <h3>Nenhum caixa aberto</h3>
            <p>
              Abra um caixa para registrar baixas financeiras, suprimentos e sangrias.
            </p>
          </div>
        </section>
      ) : (
        <section className="painel" aria-label="Caixa aberto">
          <div className="painel__topo">
            <div>
              <h3 className="painel__titulo">
                Caixa #{atual.id_caixa} <span className="badge badge--aberto">Aberto</span>
              </h3>
              <p className="guia__ajuda">
                Aberto por {atual.aberto_por} em {formatarDataHora(atual.aberto_em)}
              </p>
            </div>
          </div>
          <CaixaValores caixa={atual} />
          <section className="interacoes" aria-label="Movimentações">
            <header className="interacoes__topo">
              <h3>Movimentações</h3>
            </header>
            <CaixaExtrato extrato={atual.extrato} />
          </section>
        </section>
      )}

      <section className="painel" aria-label="Caixas fechados">
        <div className="painel__topo">
          <h3 className="painel__titulo">Histórico de caixas</h3>
          <span className="contador">
            {totalHistorico} {totalHistorico === 1 ? 'fechado' : 'fechados'}
          </span>
        </div>
        {historico.length === 0 ? (
          <p className="interacoes__vazio">Nenhum caixa fechado ainda.</p>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Caixa</th>
                  <th>Aberto em</th>
                  <th>Fechado em</th>
                  <th>Esperado</th>
                  <th>Contado</th>
                  <th>Diferença</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {historico.map((caixa) => (
                  <tr key={caixa.id_caixa}>
                    <td>
                      <button
                        className="tabela__link"
                        type="button"
                        onClick={() => setModal({ nome: 'detalhe', id: caixa.id_caixa })}
                      >
                        #{caixa.id_caixa}
                      </button>{' '}
                      <span className="tabela__secundario">{caixa.aberto_por}</span>
                    </td>
                    <td>{formatarDataHora(caixa.aberto_em)}</td>
                    <td>{formatarDataHora(caixa.fechado_em)}</td>
                    <td>{formatarMoeda(caixa.saldo_esperado_dinheiro)}</td>
                    <td>{formatarMoeda(caixa.valor_contado)}</td>
                    <td className={`valor ${classeDiferenca(caixa.diferenca)}`}>
                      {formatarMoeda(caixa.diferenca)}
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        <button
                          className="botao-icone"
                          type="button"
                          onClick={() => setModal({ nome: 'detalhe', id: caixa.id_caixa })}
                          aria-label={`Consultar caixa ${caixa.id_caixa}`}
                          title="Consultar caixa"
                        >
                          <Icone nome="olho" />
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

      {modal === 'abrir' ? (
        <CaixaAbrirFormulario
          aoFechar={() => setModal(null)}
          aoAberto={() => concluir('Caixa aberto com sucesso.')}
        />
      ) : null}
      {modal === 'movimento' && atual ? (
        <CaixaMovimentoFormulario
          idCaixa={atual.id_caixa}
          aoFechar={() => setModal(null)}
          aoRegistrado={(resposta) => concluir(resposta.mensagem)}
        />
      ) : null}
      {modal === 'fechar' && atual ? (
        <CaixaFecharFormulario
          caixa={atual}
          aoFechar={() => setModal(null)}
          aoFechado={(resposta) => concluir(resposta.mensagem)}
        />
      ) : null}
      {modal?.nome === 'detalhe' ? (
        <CaixaDetalhe idCaixa={modal.id} aoFechar={() => setModal(null)} />
      ) : null}
    </div>
  )
}
