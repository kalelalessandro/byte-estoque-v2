/**
 * "Registrar Baixas Manualmente": selecionar título e caixa aberto, informar os dados
 * e salvar. Toda baixa é ligada a um PARCEIRO (o do título): só aparecem títulos com
 * parceiro e saldo pendente. As regras (saldo, título cancelado, caixa aberto, empresa)
 * são validadas pela API; aqui só mostramos cada mensagem junto do campo certo.
 *
 * Ao escolher o título, o Guia mostra as interações do parceiro (contratos, compras...).
 */
import { useEffect, useState } from 'react'
import { api, ApiError, mensagemDeErro } from '../api'
import { agoraIso, formatarData, formatarMoeda } from '../formatos'
import Aviso from './Aviso'
import GuiaInteracoes from './GuiaInteracoes'
import Modal from './Modal'

const ROTULO_NATUREZA = { recebimento: 'Receber', pagamento: 'Pagar' }

export default function BaixaFormulario({
  aoFechar,
  aoSalvo,
  idTituloInicial = null,
  aoAbrirCaixa = null, // leva o usuário para a aba Caixas quando não há caixa aberto
}) {
  const [opcoes, setOpcoes] = useState(null)
  const [formulario, setFormulario] = useState({
    id_titulo: '',
    id_caixa: '',
    valor: '',
    forma_pagamento: '',
    realizado_em: agoraIso(),
  })
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState({})
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    let ativo = true
    api.baixas
      .opcoes()
      .then((resposta) => {
        if (!ativo) return
        setOpcoes(resposta.dados)
        // Um único caixa aberto: já vem selecionado.
        if (resposta.dados.caixas.length === 1) {
          setFormulario((atual) => ({
            ...atual,
            id_caixa: String(resposta.dados.caixas[0].id_caixa),
          }))
        }
        // "Dar baixa" vindo da tela de títulos: o título já vem selecionado.
        if (idTituloInicial) {
          if (resposta.dados.titulos.some((item) => item.id_titulo === idTituloInicial)) {
            setFormulario((atual) => ({ ...atual, id_titulo: String(idTituloInicial) }))
          } else {
            setErroGeral(
              'Este título não pode receber baixa agora (cancelado, quitado ou sem parceiro).',
            )
          }
        }
      })
      .catch((falha) => {
        if (ativo) setErroGeral(mensagemDeErro(falha))
      })
    return () => {
      ativo = false
    }
  }, [idTituloInicial])

  function alterar(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  const titulo = opcoes?.titulos.find(
    (item) => String(item.id_titulo) === formulario.id_titulo,
  )
  const semCaixa = opcoes && opcoes.caixas.length === 0

  async function salvar(evento) {
    evento.preventDefault()
    setErroGeral('')
    setErros({})

    const numero = (texto) => (texto === '' ? null : Number(texto))
    const dados = {
      id_titulo: numero(formulario.id_titulo),
      id_caixa: numero(formulario.id_caixa),
      valor: formulario.valor,
      forma_pagamento: formulario.forma_pagamento,
      realizado_em: formulario.realizado_em,
    }

    setOcupado(true)
    try {
      const resposta = await api.baixas.registrar(dados)
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

  const titulosPorNatureza = (natureza) =>
    (opcoes?.titulos || []).filter((item) => item.natureza === natureza)

  return (
    <Modal titulo="Registrar baixa manualmente" aoFechar={ocupado ? () => {} : aoFechar} largo>
      {!opcoes && !erroGeral ? (
        <div className="estado-carregando">Carregando títulos e caixas…</div>
      ) : null}

      {opcoes ? (
        <form className="formulario" onSubmit={salvar} noValidate>
          {semCaixa ? (
            <Aviso>
              Não há caixa aberto na empresa. Abra um caixa antes de registrar baixas.
            </Aviso>
          ) : null}
          {semCaixa && aoAbrirCaixa ? (
            <button className="link-acao" type="button" onClick={aoAbrirCaixa}>
              Ir para Caixas e abrir um caixa
            </button>
          ) : null}
          {opcoes.titulos.length === 0 ? (
            <Aviso tipo="sucesso">
              Nenhum título com saldo pendente e parceiro vinculado.
              {opcoes.titulos_sem_parceiro > 0
                ? ` ${opcoes.titulos_sem_parceiro} título(s) sem parceiro não podem receber baixa: vincule um parceiro a eles.`
                : ''}
            </Aviso>
          ) : null}

          <div className="grade">
            <div className="campo campo--largo">
              <label htmlFor="baixa-titulo">Título *</label>
              <select
                id="baixa-titulo"
                value={formulario.id_titulo}
                onChange={(evento) => alterar('id_titulo', evento.target.value)}
              >
                <option value="">Selecione o título</option>
                {['recebimento', 'pagamento'].map((natureza) => {
                  const itens = titulosPorNatureza(natureza)
                  if (itens.length === 0) return null
                  return (
                    <optgroup
                      key={natureza}
                      label={natureza === 'recebimento' ? 'A receber' : 'A pagar'}
                    >
                      {itens.map((item) => (
                        <option key={item.id_titulo} value={item.id_titulo}>
                          {item.parceiro.nome} · {item.descricao} · saldo{' '}
                          {formatarMoeda(item.saldo_pendente)}
                        </option>
                      ))}
                    </optgroup>
                  )
                })}
              </select>
              {erroDe('id_titulo')}
            </div>

            {titulo ? (
              <div className="campo campo--largo resumo-titulo">
                <span className={`badge badge--${titulo.natureza}`}>
                  {ROTULO_NATUREZA[titulo.natureza] || titulo.tipo}
                </span>
                <span>
                  Parceiro: <strong>{titulo.parceiro.nome}</strong>
                </span>
                <span>Título: {formatarMoeda(titulo.valor)}</span>
                <span>
                  Saldo pendente: <strong>{formatarMoeda(titulo.saldo_pendente)}</strong>
                </span>
                <span>Vence em {formatarData(titulo.vencimento)}</span>
              </div>
            ) : null}

            <div className="campo">
              <label htmlFor="baixa-caixa">Caixa aberto *</label>
              <select
                id="baixa-caixa"
                value={formulario.id_caixa}
                onChange={(evento) => alterar('id_caixa', evento.target.value)}
                disabled={semCaixa}
              >
                <option value="">Selecione o caixa</option>
                {opcoes.caixas.map((caixa) => (
                  <option key={caixa.id_caixa} value={caixa.id_caixa}>
                    Caixa #{caixa.id_caixa} · aberto por {caixa.aberto_por}
                  </option>
                ))}
              </select>
              {erroDe('id_caixa')}
            </div>

            <div className="campo">
              <label htmlFor="baixa-forma">Forma de pagamento *</label>
              <select
                id="baixa-forma"
                value={formulario.forma_pagamento}
                onChange={(evento) => alterar('forma_pagamento', evento.target.value)}
              >
                <option value="">Selecione a forma</option>
                {opcoes.formas_pagamento.map((forma) => (
                  <option key={forma} value={forma}>
                    {forma.charAt(0).toUpperCase() + forma.slice(1)}
                  </option>
                ))}
              </select>
              {erroDe('forma_pagamento')}
            </div>

            <div className="campo">
              <label htmlFor="baixa-valor">Valor *</label>
              <input
                id="baixa-valor"
                type="text"
                inputMode="decimal"
                placeholder="0,00"
                value={formulario.valor}
                onChange={(evento) => alterar('valor', evento.target.value)}
              />
              {titulo ? (
                <button
                  className="link-acao"
                  type="button"
                  onClick={() => alterar('valor', titulo.saldo_pendente)}
                >
                  Usar o saldo total ({formatarMoeda(titulo.saldo_pendente)})
                </button>
              ) : null}
              {erroDe('valor')}
            </div>

            <div className="campo">
              <label htmlFor="baixa-realizado">Realizado em *</label>
              <input
                id="baixa-realizado"
                type="datetime-local"
                value={formulario.realizado_em}
                onChange={(evento) => alterar('realizado_em', evento.target.value)}
              />
              {erroDe('realizado_em')}
            </div>
          </div>

          {erroGeral ? <Aviso>{erroGeral}</Aviso> : null}

          {titulo ? (
            <GuiaInteracoes
              idParceiro={titulo.parceiro.id_parceiro}
              nomeParceiro={titulo.parceiro.nome}
              limite={5}
            />
          ) : (
            <p className="guia__ajuda">
              Selecione um título para ver, no guia, as interações já registradas com o
              parceiro dele.
            </p>
          )}

          <div className="acoes-formulario">
            <button
              className="botao botao--primario"
              type="submit"
              disabled={ocupado || semCaixa}
            >
              {ocupado ? 'Salvando…' : 'Salvar & registrar baixa'}
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
      ) : null}

      {!opcoes && erroGeral ? <Aviso>{erroGeral}</Aviso> : null}
    </Modal>
  )
}
