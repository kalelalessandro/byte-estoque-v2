/**
 * Valores de uma sessão de caixa: abertura, suprimentos, sangrias, saldo esperado em
 * dinheiro e, com o caixa fechado, o valor contado e a diferença. Embaixo, as linhas de
 * dinheiro, Pix e cartão: só o dinheiro altera o saldo físico do caixa.
 */
import { formatarMoeda } from '../formatos'

/** Classe de cor da diferença: sobra, falta ou zero. */
export function classeDiferenca(diferenca) {
  const numero = Number(diferenca)
  if (numero > 0) return 'diferenca--positiva'
  if (numero < 0) return 'diferenca--negativa'
  return 'diferenca--zero'
}

const ROTULO_FORMA = { dinheiro: 'Dinheiro', Pix: 'Pix', cartão: 'Cartão' }

export default function CaixaValores({ caixa }) {
  const fechado = caixa.situacao === 'fechado'
  return (
    <>
      <div className="cartoes-valor">
        <div className="cartao-valor">
          <span>Abertura</span>
          <strong>{formatarMoeda(caixa.valor_abertura)}</strong>
        </div>
        <div className="cartao-valor">
          <span>Suprimentos</span>
          <strong>{formatarMoeda(caixa.suprimentos)}</strong>
        </div>
        <div className="cartao-valor">
          <span>Sangrias</span>
          <strong>{formatarMoeda(caixa.sangrias)}</strong>
        </div>
        <div className="cartao-valor cartao-valor--destaque">
          <span>Saldo esperado em dinheiro</span>
          <strong>{formatarMoeda(caixa.saldo_esperado_dinheiro)}</strong>
        </div>
        {fechado ? (
          <>
            <div className="cartao-valor">
              <span>Valor contado</span>
              <strong>{formatarMoeda(caixa.valor_contado)}</strong>
            </div>
            <div className={`cartao-valor ${classeDiferenca(caixa.diferenca)}`}>
              <span>Diferença</span>
              <strong>{formatarMoeda(caixa.diferenca)}</strong>
            </div>
          </>
        ) : null}
      </div>

      <div className="tabela-wrap">
        <table className="tabela">
          <thead>
            <tr>
              <th>Forma de pagamento</th>
              <th>Recebimentos</th>
              <th>Pagamentos</th>
              <th>Líquido</th>
            </tr>
          </thead>
          <tbody>
            {caixa.por_forma.map((linha) => (
              <tr key={linha.forma}>
                <td>
                  {ROTULO_FORMA[linha.forma] || linha.forma}{' '}
                  {!linha.afeta_dinheiro ? (
                    <span className="badge">não altera o dinheiro</span>
                  ) : null}
                </td>
                <td>{formatarMoeda(linha.recebimentos)}</td>
                <td>{formatarMoeda(linha.pagamentos)}</td>
                <td>{formatarMoeda(linha.liquido)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
