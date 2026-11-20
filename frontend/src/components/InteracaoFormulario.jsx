/**
 * Formulário (em linha) de interação com o parceiro: data, canal e descrição.
 *
 * Serve para "Registrar Interação" e "Alterar Interação". Quem usa passa `salvar`
 * (função assíncrona que chama a API); se ela lançar erro, as mensagens da API
 * aparecem junto de cada campo.
 */
import { useState } from 'react'
import { ApiError, mensagemDeErro } from '../api'
import { hojeIso } from '../formatos'
import Aviso from './Aviso'

// Sugestões; o canal é texto livre de até 30 caracteres.
const CANAIS_SUGERIDOS = ['Telefone', 'E-mail', 'WhatsApp', 'Reunião', 'Visita']

export default function InteracaoFormulario({
  inicial = null, // interação existente (alterar) ou null (registrar)
  rotuloSalvar,
  salvar, // async ({ ocorrencia, canal, descricao }) => void
  aoCancelar,
}) {
  const [formulario, setFormulario] = useState({
    ocorrencia: inicial?.ocorrencia || hojeIso(),
    canal: inicial?.canal || '',
    descricao: inicial?.descricao || '',
  })
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  function alterar(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  async function enviar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})
    setOcupado(true)
    try {
      await salvar(formulario)
    } catch (falha) {
      if (falha instanceof ApiError && falha.corpo?.campos) {
        setErros(falha.corpo.campos)
        setErroGeral(falha.message)
      } else {
        setErroGeral(mensagemDeErro(falha))
      }
      setOcupado(false)
    }
  }

  const erroDe = (campo) =>
    erros[campo] ? <small className="campo__erro">{erros[campo]}</small> : null

  return (
    <form className="formulario interacao-form" onSubmit={enviar} noValidate>
      <div className="grade">
        <div className="campo">
          <label htmlFor="interacao-data">Data *</label>
          <input
            id="interacao-data"
            type="date"
            value={formulario.ocorrencia}
            onChange={(evento) => alterar('ocorrencia', evento.target.value)}
          />
          {erroDe('ocorrencia')}
        </div>

        <div className="campo">
          <label htmlFor="interacao-canal">Canal *</label>
          <input
            id="interacao-canal"
            type="text"
            list="canais-sugeridos"
            maxLength={30}
            placeholder="Telefone, e-mail, WhatsApp…"
            value={formulario.canal}
            onChange={(evento) => alterar('canal', evento.target.value)}
          />
          <datalist id="canais-sugeridos">
            {CANAIS_SUGERIDOS.map((canal) => (
              <option key={canal} value={canal} />
            ))}
          </datalist>
          {erroDe('canal')}
        </div>

        <div className="campo campo--largo">
          <label htmlFor="interacao-descricao">Descrição *</label>
          <textarea
            id="interacao-descricao"
            rows={3}
            placeholder="O que foi tratado ou combinado neste contato"
            value={formulario.descricao}
            onChange={(evento) => alterar('descricao', evento.target.value)}
          />
          {erroDe('descricao')}
        </div>
      </div>

      {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

      <div className="acoes-formulario">
        <button className="botao botao--primario" type="submit" disabled={ocupado}>
          {ocupado ? 'Salvando…' : rotuloSalvar}
        </button>
        <button
          className="botao botao--secundario"
          type="button"
          onClick={aoCancelar}
          disabled={ocupado}
        >
          Cancelar
        </button>
      </div>
    </form>
  )
}
