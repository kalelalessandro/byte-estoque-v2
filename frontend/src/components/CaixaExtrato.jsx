/**
 * Extrato do caixa: todas as baixas (com o parceiro) e os suprimentos/sangrias da sessão,
 * mais recentes primeiro. Pix e cartão alteram o saldo geral, mas ficam fora da contagem do dinheiro.
 */
import { formatarDataHora, formatarMoeda } from '../formatos'

const ROTULO_TIPO = {
  recebimento: 'Recebimento',
  pagamento: 'Pagamento',
  suprimento: 'Suprimento',
  sangria: 'Sangria',
}

export default function CaixaExtrato({ extrato }) {
  if (extrato.length === 0) {
    return (
      <p className="interacoes__vazio">
        Nenhuma movimentação neste caixa além da abertura.
      </p>
    )
  }

  return (
    <div className="tabela-wrap">
      <table className="tabela">
        <thead>
          <tr>
            <th>Data/hora</th>
            <th>Lançamento</th>
            <th>Forma</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {extrato.map((item) => (
            <tr key={`${item.origem}-${item.id}`}>
              <td>{formatarDataHora(item.ocorrencia)}</td>
              <td>
                <strong>{ROTULO_TIPO[item.tipo] || item.tipo}</strong>
                {item.parceiro ? ` · ${item.parceiro}` : ''}
                {item.descricao ? (
                  <span className="tabela__secundario"> {item.descricao}</span>
                ) : null}
              </td>
              <td>
                {item.forma_pagamento}{' '}
                {!item.afeta_dinheiro ? (
                  <span className="badge">fora da contagem do dinheiro</span>
                ) : null}
              </td>
              <td
                className={`valor ${item.sentido === 'entrada' ? 'valor--recebimento' : 'valor--pagamento'}`}
              >
                {item.sentido === 'saida' ? '− ' : '+ '}
                {formatarMoeda(item.valor)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
