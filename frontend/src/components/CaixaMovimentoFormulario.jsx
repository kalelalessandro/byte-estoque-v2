/**
 * "Registrar Suprimento/Sangria" no caixa aberto: tipo, valor e descrição (motivo).
 * Suprimento = entrada de dinheiro; sangria = saída. Data e hora são do servidor.
 */
import { useState } from 'react'
import { api, ApiError, mensagemDeErro } from '../api'
import Aviso from './Aviso'
import Modal from './Modal'

export default function CaixaMovimentoFormulario({ idCaixa, aoFechar, aoRegistrado }) {
  const [formulario, setFormulario] = useState({ tipo: '', valor: '', descricao: '' })
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  function alterar(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  async function salvar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})
    setOcupado(true)
    try {
      const resposta = await api.caixas.movimentar(idCaixa, formulario)
      aoRegistrado(resposta)
    } catch (falha) {
      if (falha instanceof ApiError && falha.corpo?.campos) setErros(falha.corpo.campos)
      setErroGeral(mensagemDeErro(falha))
      setOcupado(false)
    }
  }

  const erroDe = (campo) =>
    erros[campo] ? <small className="campo__erro">{erros[campo]}</small> : null

  return (
    <Modal titulo="Registrar suprimento/sangria" aoFechar={ocupado ? () => {} : aoFechar}>
      <form className="formulario" onSubmit={salvar} noValidate>
        <div className="grade">
          <div className="campo">
            <label htmlFor="mov-tipo">Tipo *</label>
            <select
              id="mov-tipo"
              value={formulario.tipo}
              onChange={(evento) => alterar('tipo', evento.target.value)}
            >
              <option value="">Selecione o tipo</option>
              <option value="suprimento">Suprimento (entrada)</option>
              <option value="sangria">Sangria (saída)</option>
            </select>
            {erroDe('tipo')}
          </div>

          <div className="campo">
            <label htmlFor="mov-valor">Valor *</label>
            <input
              id="mov-valor"
              type="text"
              inputMode="decimal"
              placeholder="0,00"
              value={formulario.valor}
              onChange={(evento) => alterar('valor', evento.target.value)}
            />
            {erroDe('valor')}
          </div>

          <div className="campo campo--largo">
            <label htmlFor="mov-descricao">Descrição</label>
            <textarea
              id="mov-descricao"
              rows={2}
              placeholder="Ex.: Reforço de troco"
              value={formulario.descricao}
              onChange={(evento) => alterar('descricao', evento.target.value)}
            />
            {erroDe('descricao')}
          </div>
        </div>

        {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

        <div className="acoes-formulario">
          <button className="botao botao--primario" type="submit" disabled={ocupado}>
            {ocupado ? 'Salvando…' : 'Salvar'}
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
