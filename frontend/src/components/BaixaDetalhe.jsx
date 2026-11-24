/**
 * "Consultar Baixa": dados da baixa, do título (com saldo) e do PARCEIRO ligado a ela,
 * mais o Guia com as interações desse parceiro.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import { formatarData, formatarDataHora, formatarMoeda } from '../formatos'
import Aviso from './Aviso'
import GuiaInteracoes from './GuiaInteracoes'
import Modal from './Modal'

const ROTULO_NATUREZA = { recebimento: 'Recebimento', pagamento: 'Pagamento' }
const ROTULO_PARCEIRO = { cliente: 'Cliente', fornecedor: 'Fornecedor', ambos: 'Cliente e fornecedor' }

export default function BaixaDetalhe({ idBaixa, aoFechar }) {
  const [baixa, setBaixa] = useState(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    api.baixas
      .obter(idBaixa)
      .then((resposta) => {
        if (ativo) setBaixa(resposta.dados)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
    return () => {
      ativo = false
    }
  }, [idBaixa])

  return (
    <Modal titulo={`Baixa #${idBaixa}`} aoFechar={aoFechar} largo>
      {erro ? <Aviso>{erro}</Aviso> : null}
      {!baixa && !erro ? <div className="estado-carregando">Carregando baixa…</div> : null}

      {baixa ? (
        <div className="detalhe">
          <dl className="detalhe__grade">
            <div>
              <dt>Parceiro</dt>
              <dd>
                {baixa.parceiro ? (
                  <>
                    {baixa.parceiro.nome}{' '}
                    <span className="badge">{ROTULO_PARCEIRO[baixa.parceiro.tipo]}</span>
                  </>
                ) : (
                  'Sem parceiro (título antigo)'
                )}
              </dd>
            </div>
            <div>
              <dt>Natureza</dt>
              <dd>
                <span className={`badge badge--${baixa.natureza}`}>
                  {ROTULO_NATUREZA[baixa.natureza] || baixa.titulo.tipo}
                </span>
              </dd>
            </div>
            <div>
              <dt>Valor da baixa</dt>
              <dd>{formatarMoeda(baixa.valor)}</dd>
            </div>
            <div>
              <dt>Forma de pagamento</dt>
              <dd>{baixa.forma_pagamento}</dd>
            </div>
            <div>
              <dt>Realizado em</dt>
              <dd>{formatarDataHora(baixa.realizado_em)}</dd>
            </div>
            <div>
              <dt>Caixa</dt>
              <dd>#{baixa.id_caixa}</dd>
            </div>
            <div className="detalhe__largo">
              <dt>Título</dt>
              <dd>
                #{baixa.titulo.id_titulo} · {baixa.titulo.descricao} · vence em{' '}
                {formatarData(baixa.titulo.vencimento)}
              </dd>
            </div>
            <div>
              <dt>Valor do título</dt>
              <dd>{formatarMoeda(baixa.titulo.valor)}</dd>
            </div>
            <div>
              <dt>Total baixado</dt>
              <dd>{formatarMoeda(baixa.titulo.total_baixado)}</dd>
            </div>
            <div>
              <dt>Saldo pendente</dt>
              <dd>{formatarMoeda(baixa.titulo.saldo_pendente)}</dd>
            </div>
          </dl>

          {baixa.parceiro ? (
            <GuiaInteracoes
              idParceiro={baixa.parceiro.id_parceiro}
              nomeParceiro={baixa.parceiro.nome}
              limite={8}
            />
          ) : null}
        </div>
      ) : null}
    </Modal>
  )
}
