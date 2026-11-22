/**
 * "Abrir Caixa": informa o valor de abertura (zero é permitido). A data e a hora são do
 * servidor, e o caixa é aberto pelo usuário logado. A API valida o valor (obrigatório,
 * numérico, não negativo, até 9.999.999.999,99) e mostramos a mensagem junto do campo.
 */
import { useState } from 'react'
import { api, ApiError, mensagemDeErro } from '../api'
import Aviso from './Aviso'
import Modal from './Modal'

export default function CaixaAbrirFormulario({ aoFechar, aoAberto }) {
  const [valor, setValor] = useState('')
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  async function salvar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})
    setOcupado(true)
    try {
      const resposta = await api.caixas.abrir({ valor_abertura: valor })
      aoAberto(resposta.dados)
    } catch (falha) {
      if (falha instanceof ApiError && falha.corpo?.campos) setErros(falha.corpo.campos)
      setErroGeral(mensagemDeErro(falha))
      setOcupado(false)
    }
  }

  return (
    <Modal titulo="Abrir caixa" aoFechar={ocupado ? () => {} : aoFechar}>
      <form className="formulario" onSubmit={salvar} noValidate>
        <div className="campo">
          <label htmlFor="caixa-abertura">Valor de abertura *</label>
          <input
            id="caixa-abertura"
            type="text"
            inputMode="decimal"
            placeholder="0,00"
            value={valor}
            onChange={(evento) => setValor(evento.target.value)}
            autoFocus
          />
          <small className="contador-caracteres">
            Dinheiro disponível no caixa ao começar. Pode ser zero.
          </small>
          {erros.valor_abertura ? (
            <small className="campo__erro">{erros.valor_abertura}</small>
          ) : null}
        </div>

        {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

        <div className="acoes-formulario">
          <button className="botao botao--primario" type="submit" disabled={ocupado}>
            {ocupado ? 'Abrindo…' : 'Abrir caixa'}
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
