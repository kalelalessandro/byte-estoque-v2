/** Consulta de uma sessão de caixa (aberta ou já fechada): valores e extrato. */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import { formatarDataHora } from '../formatos'
import Aviso from './Aviso'
import CaixaExtrato from './CaixaExtrato'
import CaixaValores from './CaixaValores'
import Modal from './Modal'

export default function CaixaDetalhe({ idCaixa, aoFechar }) {
  const [caixa, setCaixa] = useState(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    api.caixas
      .obter(idCaixa)
      .then((resposta) => {
        if (ativo) setCaixa(resposta.dados)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
    return () => {
      ativo = false
    }
  }, [idCaixa])

  return (
    <Modal titulo={`Caixa #${idCaixa}`} aoFechar={aoFechar} largo>
      {erro ? <Aviso>{erro}</Aviso> : null}
      {!caixa && !erro ? <div className="estado-carregando">Carregando caixa…</div> : null}
      {caixa ? (
        <div className="detalhe">
          <p className="guia__ajuda">
            Aberto por {caixa.aberto_por} em {formatarDataHora(caixa.aberto_em)}
            {caixa.fechado_em ? ` · fechado em ${formatarDataHora(caixa.fechado_em)}` : ''}
          </p>
          <CaixaValores caixa={caixa} />
          <section className="interacoes" aria-label="Extrato do caixa">
            <header className="interacoes__topo">
              <h3>Extrato</h3>
            </header>
            <CaixaExtrato extrato={caixa.extrato} />
          </section>
        </div>
      ) : null}
    </Modal>
  )
}
