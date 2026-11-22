/**
 * "Fechar Caixa": mostra o saldo esperado em dinheiro, pede o valor contado e confirma
 * ("Dar baixa" do fluxograma). A prévia da diferença (contado − esperado) é só uma ajuda;
 * a diferença oficial vem da API, calculada com a sessão travada.
 */
import { useState } from 'react'
import { api, ApiError, mensagemDeErro } from '../api'
import { formatarMoeda } from '../formatos'
import Aviso from './Aviso'
import { classeDiferenca } from './CaixaValores'
import Modal from './Modal'

export default function CaixaFecharFormulario({ caixa, aoFechar, aoFechado }) {
  const [valor, setValor] = useState('')
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  // Prévia: só quando o texto é um número válido (aceita "170,50").
  const contado = Number(valor.replace(',', '.'))
  const previa =
    valor.trim() !== '' && !Number.isNaN(contado)
      ? contado - Number(caixa.saldo_esperado_dinheiro)
      : null

  async function salvar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})
    setOcupado(true)
    try {
      const resposta = await api.caixas.fechar(caixa.id_caixa, { valor_contado: valor })
      aoFechado(resposta)
    } catch (falha) {
      if (falha instanceof ApiError && falha.corpo?.campos) setErros(falha.corpo.campos)
      setErroGeral(mensagemDeErro(falha))
      setOcupado(false)
    }
  }

  return (
    <Modal titulo="Fechar caixa" aoFechar={ocupado ? () => {} : aoFechar}>
      <form className="formulario" onSubmit={salvar} noValidate>
        <p className="guia__ajuda">
          Saldo esperado em dinheiro:{' '}
          <strong>{formatarMoeda(caixa.saldo_esperado_dinheiro)}</strong>. Conte o dinheiro
          do caixa e informe o valor abaixo. Pix e cartão não entram na contagem, mas somam no
          saldo geral do caixa ({formatarMoeda(caixa.saldo_geral)} com o dinheiro esperado).
        </p>

        <div className="campo">
          <label htmlFor="caixa-contado">Valor contado *</label>
          <input
            id="caixa-contado"
            type="text"
            inputMode="decimal"
            placeholder="0,00"
            value={valor}
            onChange={(evento) => setValor(evento.target.value)}
            autoFocus
          />
          {erros.valor_contado ? (
            <small className="campo__erro">{erros.valor_contado}</small>
          ) : null}
        </div>

        {previa !== null ? (
          <p className={`guia__ajuda ${classeDiferenca(previa)}`}>
            Diferença prevista: <strong>{formatarMoeda(previa.toFixed(2))}</strong>
          </p>
        ) : null}

        {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

        <div className="acoes-formulario">
          <button className="botao botao--primario" type="submit" disabled={ocupado}>
            {ocupado ? 'Fechando…' : 'Confirmar fechamento'}
          </button>
          <button
            className="botao botao--secundario"
            type="button"
            onClick={aoFechar}
            disabled={ocupado}
          >
            Cancelar
          </button>
        </div>
      </form>
    </Modal>
  )
}
