/**
 * Formulário de parceiro em janela modal: "Inserir Parceiro Novo" e "Alterar Parceiro".
 *
 * As regras (formato de CPF/CNPJ, e-mail, CEP, unicidade por empresa, "ao menos um
 * relacionamento") são validadas pela API; aqui só mostramos cada mensagem junto do
 * campo certo. Campos opcionais vazios são enviados como `null`. Texto só com espaços
 * é enviado como está, para a API recusar (documento/e-mail em branco são inválidos).
 */
import { useState } from 'react'
import { api, ApiError, mensagemDeErro } from '../api'
import { formatarCep, formatarDocumento } from '../formatos'
import Aviso from './Aviso'
import Icone from './Icone'
import Modal from './Modal'

const FORMULARIO_VAZIO = {
  nome: '',
  documento: '',
  email: '',
  cep: '',
  e_cliente: true,
  e_fornecedor: false,
  observacao: '',
}

function doParceiro(parceiro) {
  if (!parceiro) return FORMULARIO_VAZIO
  return {
    nome: parceiro.nome,
    documento: formatarDocumento(parceiro.documento),
    email: parceiro.email || '',
    cep: formatarCep(parceiro.cep),
    e_cliente: parceiro.e_cliente,
    e_fornecedor: parceiro.e_fornecedor,
    observacao: parceiro.observacao || '',
  }
}

/** Campo opcional vazio vira null (a API grava NULL, nunca texto vazio). */
const textoOuNulo = (valor) => (valor === '' ? null : valor)

export default function ParceiroFormulario({
  parceiro = null, // null = inserir; objeto = alterar
  aoFechar,
  aoSalvo, // (parceiroSalvo) => void
  aoExcluir, // (parceiro) => Promise (só na edição)
}) {
  const [formulario, setFormulario] = useState(() => doParceiro(parceiro))
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  function alterar(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  function tratarFalha(falha) {
    if (falha instanceof ApiError && falha.corpo?.campos) {
      setErros(falha.corpo.campos)
      setErroGeral(falha.message)
    } else {
      setErroGeral(mensagemDeErro(falha))
    }
  }

  async function salvar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})

    const dados = {
      nome: formulario.nome,
      documento: textoOuNulo(formulario.documento),
      email: textoOuNulo(formulario.email),
      cep: textoOuNulo(formulario.cep),
      e_cliente: formulario.e_cliente,
      e_fornecedor: formulario.e_fornecedor,
      observacao: textoOuNulo(formulario.observacao),
    }

    setOcupado(true)
    try {
      const resposta = parceiro
        ? await api.parceiros.editar(parceiro.id_parceiro, dados)
        : await api.parceiros.criar(dados)
      aoSalvo(resposta.dados)
    } catch (falha) {
      tratarFalha(falha)
      setOcupado(false)
    }
  }

  async function apagar() {
    const confirmado = window.confirm(
      `Excluir o parceiro "${parceiro.nome}"? Essa ação não pode ser desfeita.`,
    )
    if (!confirmado) return

    setErroGeral('')
    setErros({})
    setOcupado(true)
    try {
      await aoExcluir(parceiro)
    } catch (falha) {
      // Ex.: 409 com interações, operações ou títulos vinculados.
      setErroGeral(mensagemDeErro(falha))
      setOcupado(false)
    }
  }

  const erroDe = (campo) =>
    erros[campo] ? <small className="campo__erro">{erros[campo]}</small> : null

  return (
    <Modal
      titulo={parceiro ? 'Alterar parceiro' : 'Inserir parceiro novo'}
      aoFechar={ocupado ? () => {} : aoFechar}
      largo
    >
      <form className="formulario" onSubmit={salvar} noValidate>
        <div className="grade">
          <div className="campo campo--largo">
            <label htmlFor="parceiro-nome">Nome *</label>
            <input
              id="parceiro-nome"
              type="text"
              maxLength={150}
              placeholder="Pessoa ou empresa"
              value={formulario.nome}
              onChange={(evento) => alterar('nome', evento.target.value)}
              autoFocus
            />
            {erroDe('nome')}
          </div>

          <div className="campo">
            <label htmlFor="parceiro-documento">CPF ou CNPJ</label>
            <input
              id="parceiro-documento"
              type="text"
              maxLength={18}
              placeholder="Somente números ou com pontuação"
              value={formulario.documento}
              onChange={(evento) => alterar('documento', evento.target.value)}
            />
            {erroDe('documento')}
          </div>

          <div className="campo">
            <label htmlFor="parceiro-email">E-mail</label>
            <input
              id="parceiro-email"
              type="text"
              inputMode="email"
              maxLength={254}
              placeholder="contato@empresa.com.br"
              value={formulario.email}
              onChange={(evento) => alterar('email', evento.target.value)}
            />
            {erroDe('email')}
          </div>

          <div className="campo">
            <label htmlFor="parceiro-cep">CEP</label>
            <input
              id="parceiro-cep"
              type="text"
              inputMode="numeric"
              maxLength={9}
              placeholder="00000-000"
              value={formulario.cep}
              onChange={(evento) => alterar('cep', evento.target.value)}
            />
            {erroDe('cep')}
          </div>

          <fieldset className="campo opcoes">
            <legend>Relacionamento *</legend>
            <label className="opcao">
              <input
                type="checkbox"
                checked={formulario.e_cliente}
                onChange={(evento) => alterar('e_cliente', evento.target.checked)}
              />
              <span>Cliente</span>
            </label>
            <label className="opcao">
              <input
                type="checkbox"
                checked={formulario.e_fornecedor}
                onChange={(evento) =>
                  alterar('e_fornecedor', evento.target.checked)
                }
              />
              <span>Fornecedor</span>
            </label>
            {erroDe('relacionamento')}
            {erroDe('e_cliente')}
            {erroDe('e_fornecedor')}
          </fieldset>

          <div className="campo campo--largo">
            <label htmlFor="parceiro-observacao">Observação</label>
            <textarea
              id="parceiro-observacao"
              rows={3}
              placeholder="Informações complementares (opcional)"
              value={formulario.observacao}
              onChange={(evento) => alterar('observacao', evento.target.value)}
            />
            {erroDe('observacao')}
          </div>
        </div>

        {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

        <div className="acoes-formulario">
          <button className="botao botao--primario" type="submit" disabled={ocupado}>
            {ocupado
              ? 'Salvando…'
              : parceiro
                ? 'Salvar alterações'
                : 'Salvar parceiro'}
          </button>
          <button
            className="botao botao--secundario"
            type="button"
            onClick={aoFechar}
            disabled={ocupado}
          >
            Cancelar
          </button>
          {parceiro && aoExcluir ? (
            <button
              className="botao botao--perigo"
              type="button"
              onClick={apagar}
              disabled={ocupado}
            >
              <Icone nome="lixo" />
              Apagar parceiro
            </button>
          ) : null}
        </div>
      </form>
    </Modal>
  )
}
