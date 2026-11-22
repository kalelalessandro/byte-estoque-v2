/**
 * Baixas financeiras: pagamentos e recebimentos efetivos de títulos (aba da página
 * Financeiro).
 *
 * Fluxo do fluxograma: Listar Baixas -> Consultar Baixas, e Registrar Baixas
 * Manualmente -> Selecionar Título/Caixa Aberto -> Informar Dados -> Salvar & Registrar.
 * Toda baixa está ligada a um parceiro (o do título). O Guia ao lado mostra as
 * interações (contratos e compras) cadastradas em Parceiros.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import BaixaDetalhe from '../components/BaixaDetalhe'
import BaixaFormulario from '../components/BaixaFormulario'
import GuiaInteracoes from '../components/GuiaInteracoes'
import Icone from '../components/Icone'
import { formatarDataHora, formatarMoeda } from '../formatos'

const FILTROS_TIPO = [
  { id: '', rotulo: 'Todas' },
  { id: 'recebimento', rotulo: 'Recebimentos' },
  { id: 'pagamento', rotulo: 'Pagamentos' },
]

const FILTROS_FORMA = [
  { id: '', rotulo: 'Qualquer forma' },
  { id: 'dinheiro', rotulo: 'Dinheiro' },
  { id: 'pix', rotulo: 'Pix' },
  { id: 'cartao', rotulo: 'Cartão' },
]

const ROTULO_NATUREZA = { recebimento: 'Recebimento', pagamento: 'Pagamento' }

export default function Baixas({ aoMudarAba = null }) {
  const [baixas, setBaixas] = useState([])
  const [total, setTotal] = useState(0)
  const [busca, setBusca] = useState('')
  const [tipo, setTipo] = useState('')
  const [forma, setForma] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [versao, setVersao] = useState(0) // incrementa para recarregar a lista
  // null | { nome: 'formulario' } | { nome: 'detalhe', id }
  const [modal, setModal] = useState(null)

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    const atraso = busca.trim() ? 250 : 0
    const temporizador = setTimeout(() => {
      api.baixas
        .listar({ busca: busca.trim(), tipo, forma, limit: 200 })
        .then((resposta) => {
          if (!ativo) return
          setBaixas(resposta.dados.baixas)
          setTotal(resposta.dados.total)
          setErro('')
        })
        .catch((falha) => {
          if (ativo) setErro(mensagemDeErro(falha))
        })
        .finally(() => {
          if (ativo) setCarregando(false)
        })
    }, atraso)

    return () => {
      ativo = false
      clearTimeout(temporizador)
    }
  }, [busca, tipo, forma, versao])

  function aoSalvar(baixa) {
    setVersao((atual) => atual + 1)
    setAviso(
      `Baixa registrada com sucesso${baixa.parceiro ? ` para ${baixa.parceiro.nome}` : ''}.`,
    )
    setModal(null)
  }

  const filtrando = Boolean(busca || tipo || forma)

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <h3>Baixas financeiras</h3>
          <p>
            Pagamentos e recebimentos efetivos de títulos, sempre ligados a um parceiro
            e a um caixa aberto.
          </p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--primario"
            type="button"
            onClick={() => {
              setAviso('')
              setModal({ nome: 'formulario' })
            }}
          >
            <Icone nome="mais" />
            Registrar baixa manualmente
          </button>
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      <div className="baixas-layout">
        <section className="painel">
          <div className="painel__topo">
            <label className="campo-busca">
              <Icone nome="busca" />
              <input
                type="search"
                placeholder="Buscar por parceiro ou título…"
                value={busca}
                onChange={(evento) => setBusca(evento.target.value)}
                aria-label="Buscar baixas"
              />
            </label>
            <span className="contador">
              {total} {total === 1 ? 'baixa' : 'baixas'}
            </span>
          </div>

          <div className="filtros" role="group" aria-label="Filtrar por natureza">
            {FILTROS_TIPO.map((filtro) => (
              <button
                key={filtro.id || 'todas'}
                type="button"
                className={`filtro ${tipo === filtro.id ? 'filtro--ativo' : ''}`.trim()}
                aria-pressed={tipo === filtro.id}
                onClick={() => setTipo(filtro.id)}
              >
                {filtro.rotulo}
              </button>
            ))}
          </div>
          <div className="filtros" role="group" aria-label="Filtrar por forma de pagamento">
            {FILTROS_FORMA.map((filtro) => (
              <button
                key={filtro.id || 'qualquer'}
                type="button"
                className={`filtro ${forma === filtro.id ? 'filtro--ativo' : ''}`.trim()}
                aria-pressed={forma === filtro.id}
                onClick={() => setForma(filtro.id)}
              >
                {filtro.rotulo}
              </button>
            ))}
          </div>

          {carregando ? (
            <div className="estado-carregando">Carregando baixas…</div>
          ) : baixas.length === 0 ? (
            <div className="estado-vazio">
              <Icone nome="dinheiro" />
              <h3>Nenhuma baixa por aqui</h3>
              <p>
                {filtrando
                  ? 'Nenhum resultado para esse filtro.'
                  : 'Registre o primeiro pagamento ou recebimento de um título.'}
              </p>
            </div>
          ) : (
            <div className="tabela-wrap">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Realizado em</th>
                    <th>Parceiro</th>
                    <th>Título</th>
                    <th>Caixa</th>
                    <th>Forma</th>
                    <th>Valor</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {baixas.map((baixa) => (
                    <tr key={baixa.id_baixa}>
                      <td>{formatarDataHora(baixa.realizado_em)}</td>
                      <td>
                        {baixa.parceiro ? (
                          baixa.parceiro.nome
                        ) : (
                          <span className="tabela__secundario">Sem parceiro</span>
                        )}
                      </td>
                      <td>
                        <button
                          className="tabela__link"
                          type="button"
                          onClick={() => setModal({ nome: 'detalhe', id: baixa.id_baixa })}
                        >
                          {baixa.titulo.descricao}
                        </button>{' '}
                        <span className={`badge badge--${baixa.natureza}`}>
                          {ROTULO_NATUREZA[baixa.natureza] || baixa.titulo.tipo}
                        </span>
                      </td>
                      <td>#{baixa.id_caixa}</td>
                      <td>{baixa.forma_pagamento}</td>
                      <td className={`valor valor--${baixa.natureza}`}>
                        {formatarMoeda(baixa.valor)}
                      </td>
                      <td>
                        <div className="tabela__acoes">
                          <button
                            className="botao-icone"
                            type="button"
                            onClick={() => setModal({ nome: 'detalhe', id: baixa.id_baixa })}
                            aria-label={`Consultar baixa ${baixa.id_baixa}`}
                            title="Consultar baixa"
                          >
                            <Icone nome="olho" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <GuiaInteracoes limite={10} />
      </div>

      {modal?.nome === 'formulario' ? (
        <BaixaFormulario
          aoFechar={() => setModal(null)}
          aoSalvo={aoSalvar}
          aoAbrirCaixa={
            aoMudarAba
              ? () => {
                  setModal(null)
                  aoMudarAba('caixas')
                }
              : null
          }
        />
      ) : null}
      {modal?.nome === 'detalhe' ? (
        <BaixaDetalhe idBaixa={modal.id} aoFechar={() => setModal(null)} />
      ) : null}
    </div>
  )
}
