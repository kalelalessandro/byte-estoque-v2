/**
 * "Consultar Título": dados, saldo pendente, histórico de baixas e o Guia com as
 * interações do parceiro. Daqui o usuário pode dar baixa ou cancelar o título.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import { formatarData, formatarDataHora, formatarMoeda } from '../formatos'
import Aviso from './Aviso'
import GuiaInteracoes from './GuiaInteracoes'
import Icone from './Icone'
import Modal from './Modal'
import SituacaoTitulo from './SituacaoTitulo'

const ROTULO_PARCEIRO = { cliente: 'Cliente', fornecedor: 'Fornecedor', ambos: 'Cliente e fornecedor' }

export default function TituloDetalhe({ idTitulo, aoFechar, aoDarBaixa, aoCancelado }) {
  const [titulo, setTitulo] = useState(null)
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    let ativo = true
    api.titulos
      .obter(idTitulo)
      .then((resposta) => {
        if (ativo) setTitulo(resposta.dados)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
    return () => {
      ativo = false
    }
  }, [idTitulo])

  async function cancelar() {
    const confirmado = window.confirm(
      `Cancelar o título "${titulo.descricao}"? Ele deixará de aceitar baixas.`,
    )
    if (!confirmado) return

    setErro('')
    setOcupado(true)
    try {
      await api.titulos.cancelar(idTitulo)
      aoCancelado()
    } catch (falha) {
      // Ex.: 409 porque já existem baixas.
      setErro(mensagemDeErro(falha))
      setOcupado(false)
    }
  }

  return (
    <Modal titulo={titulo ? titulo.descricao : `Título #${idTitulo}`} aoFechar={aoFechar} largo>
      {erro ? <Aviso>{erro}</Aviso> : null}
      {!titulo && !erro ? <div className="estado-carregando">Carregando título…</div> : null}

      {titulo ? (
        <div className="detalhe">
          <dl className="detalhe__grade">
            <div>
              <dt>Situação</dt>
              <dd>
                <SituacaoTitulo titulo={titulo} />
              </dd>
            </div>
            <div>
              <dt>Tipo</dt>
              <dd>
                <span className={`badge badge--${titulo.natureza}`}>
                  {titulo.natureza === 'recebimento' ? 'A receber' : 'A pagar'}
                </span>
              </dd>
            </div>
            <div>
              <dt>Valor</dt>
              <dd>{formatarMoeda(titulo.valor)}</dd>
            </div>
            <div>
              <dt>Saldo pendente</dt>
              <dd>
                <strong>{formatarMoeda(titulo.saldo_pendente)}</strong>
              </dd>
            </div>
            <div>
              <dt>Vencimento</dt>
              <dd>{formatarData(titulo.vencimento)}</dd>
            </div>
            <div>
              <dt>Parceiro</dt>
              <dd>
                {titulo.parceiro ? (
                  <>
                    {titulo.parceiro.nome}{' '}
                    <span className="badge">{ROTULO_PARCEIRO[titulo.parceiro.tipo]}</span>
                  </>
                ) : (
                  'Sem parceiro'
                )}
              </dd>
            </div>
            <div className="detalhe__largo">
              <dt>Descrição</dt>
              <dd className="detalhe__texto">{titulo.descricao}</dd>
            </div>
          </dl>

          {!titulo.pode_baixar && titulo.motivo_sem_baixa ? (
            <p className="guia__ajuda">Não é possível dar baixa: {titulo.motivo_sem_baixa}</p>
          ) : null}

          <div className="acoes-formulario">
            {titulo.pode_baixar ? (
              <button
                className="botao botao--primario"
                type="button"
                onClick={() => aoDarBaixa(titulo)}
              >
                <Icone nome="dinheiro" />
                {titulo.natureza === 'pagamento' ? 'Registrar pagamento' : 'Registrar recebimento'}
              </button>
            ) : null}
            {titulo.pode_cancelar ? (
              <button
                className="botao botao--perigo"
                type="button"
                onClick={cancelar}
                disabled={ocupado}
              >
                Cancelar título
              </button>
            ) : null}
          </div>

          <section className="interacoes" aria-label="Histórico de baixas">
            <header className="interacoes__topo">
              <h3>Histórico de baixas</h3>
            </header>
            {titulo.baixas.length === 0 ? (
              <p className="interacoes__vazio">Nenhuma baixa registrada para este título.</p>
            ) : (
              <div className="tabela-wrap">
                <table className="tabela">
                  <thead>
                    <tr>
                      <th>Realizado em</th>
                      <th>Forma</th>
                      <th>Caixa</th>
                      <th>Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {titulo.baixas.map((baixa) => (
                      <tr key={baixa.id_baixa}>
                        <td>{formatarDataHora(baixa.realizado_em)}</td>
                        <td>{baixa.forma_pagamento}</td>
                        <td>#{baixa.id_caixa}</td>
                        <td>{formatarMoeda(baixa.valor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {titulo.parceiro ? (
            <GuiaInteracoes
              idParceiro={titulo.parceiro.id_parceiro}
              nomeParceiro={titulo.parceiro.nome}
              limite={8}
            />
          ) : null}
        </div>
      ) : null}
    </Modal>
  )
}
