/**
 * "Registrar Título Manualmente": tipo, parceiro (opcional), valor, vencimento e descrição.
 *
 * Ao escolher um parceiro, o Guia lista as interações dele (contratos, compras, reembolsos,
 * pagamentos). A descrição de cada interação normalmente traz o valor e os detalhes do
 * combinado: o usuário pode copiá-la para a descrição do título e usar o valor sugerido,
 * e depois conferir tudo antes de salvar. O schema não guarda um vínculo título -> interação;
 * por isso a descrição do título leva a referência "Interação #id".
 *
 * As regras (valor, tipo, vencimento real, parceiro da empresa...) são validadas pela
 * API; aqui só mostramos cada mensagem junto do campo certo.
 */
import { useEffect, useState } from 'react'
import { api, ApiError, mensagemDeErro } from '../api'
import { formatarData } from '../formatos'
import Aviso from './Aviso'
import GuiaInteracoes from './GuiaInteracoes'
import Modal from './Modal'

const LIMITE_DESCRICAO = 500
const ROTULO_TIPO_PARCEIRO = { cliente: 'cliente', fornecedor: 'fornecedor', ambos: 'cliente e fornecedor' }

export default function TituloFormulario({ aoFechar, aoSalvo }) {
  const [parceiros, setParceiros] = useState([])
  const [formulario, setFormulario] = useState({
    tipo: '',
    id_parceiro: '',
    valor: '',
    vencimento: '',
    descricao: '',
  })
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    let ativo = true
    api.parceiros
      .listar({ limit: 200 })
      .then((resposta) => {
        if (ativo) setParceiros(resposta.dados.parceiros)
      })
      .catch((falha) => {
        if (ativo) setErroGeral(mensagemDeErro(falha))
      })
    return () => {
      ativo = false
    }
  }, [])

  function alterar(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  const parceiro = parceiros.find(
    (item) => String(item.id_parceiro) === formulario.id_parceiro,
  )

  /** Copia a interação para a descrição do título (com a referência), limitada a 500. */
  function usarInteracao(interacao) {
    const texto = `Interação #${interacao.interacao_id} (${interacao.canal}, ${formatarData(
      interacao.ocorrencia,
    )}): ${interacao.descricao}`
    alterar('descricao', texto.slice(0, LIMITE_DESCRICAO))
  }

  async function salvar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})

    const dados = {
      tipo: formulario.tipo,
      id_parceiro: formulario.id_parceiro === '' ? null : Number(formulario.id_parceiro),
      valor: formulario.valor,
      vencimento: formulario.vencimento,
      descricao: formulario.descricao,
    }

    setOcupado(true)
    try {
      const resposta = await api.titulos.criar(dados)
      aoSalvo(resposta.dados)
    } catch (falha) {
      if (falha instanceof ApiError && falha.corpo?.campos) {
        setErros(falha.corpo.campos)
      }
      setErroGeral(mensagemDeErro(falha))
      setOcupado(false)
    }
  }

  const erroDe = (campo) =>
    erros[campo] ? <small className="campo__erro">{erros[campo]}</small> : null

  return (
    <Modal titulo="Registrar título manualmente" aoFechar={ocupado ? () => {} : aoFechar} largo>
      <form className="formulario" onSubmit={salvar} noValidate>
        <div className="grade">
          <div className="campo">
            <label htmlFor="titulo-tipo">Tipo *</label>
            <select
              id="titulo-tipo"
              value={formulario.tipo}
              onChange={(evento) => alterar('tipo', evento.target.value)}
            >
              <option value="">Selecione o tipo</option>
              <option value="a receber">A receber</option>
              <option value="a pagar">A pagar</option>
            </select>
            {erroDe('tipo')}
          </div>

          <div className="campo">
            <label htmlFor="titulo-parceiro">Parceiro</label>
            <select
              id="titulo-parceiro"
              value={formulario.id_parceiro}
              onChange={(evento) => alterar('id_parceiro', evento.target.value)}
            >
              <option value="">Sem parceiro</option>
              {parceiros.map((item) => (
                <option key={item.id_parceiro} value={item.id_parceiro}>
                  {item.nome} ({ROTULO_TIPO_PARCEIRO[item.tipo]})
                </option>
              ))}
            </select>
            {erroDe('id_parceiro')}
          </div>

          <div className="campo">
            <label htmlFor="titulo-valor">Valor *</label>
            <input
              id="titulo-valor"
              type="text"
              inputMode="decimal"
              placeholder="0,00"
              value={formulario.valor}
              onChange={(evento) => alterar('valor', evento.target.value)}
            />
            {erroDe('valor')}
          </div>

          <div className="campo">
            <label htmlFor="titulo-vencimento">Vencimento *</label>
            <input
              id="titulo-vencimento"
              type="date"
              value={formulario.vencimento}
              onChange={(evento) => alterar('vencimento', evento.target.value)}
            />
            {erroDe('vencimento')}
          </div>

          <div className="campo campo--largo">
            <label htmlFor="titulo-descricao">Descrição *</label>
            <textarea
              id="titulo-descricao"
              rows={3}
              placeholder="Ex.: Aluguel do galpão, novembro"
              value={formulario.descricao}
              onChange={(evento) => alterar('descricao', evento.target.value)}
            />
            <small className="contador-caracteres">
              {formulario.descricao.length}/{LIMITE_DESCRICAO}
            </small>
            {erroDe('descricao')}
          </div>
        </div>

        {!parceiro ? (
          <p className="guia__ajuda">
            Escolha um parceiro para ver, no guia, as interações dele (contratos, compras,
            reembolsos e pagamentos) e preencher o título a partir delas. Sem parceiro, o
            título não poderá receber baixa.
          </p>
        ) : (
          <GuiaInteracoes
            idParceiro={parceiro.id_parceiro}
            nomeParceiro={parceiro.nome}
            limite={20}
            aoUsarInteracao={usarInteracao}
            aoUsarValor={(valor) => alterar('valor', valor)}
          />
        )}

        {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

        <div className="acoes-formulario">
          <button className="botao botao--primario" type="submit" disabled={ocupado}>
            {ocupado ? 'Salvando…' : 'Registrar título aberto'}
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
