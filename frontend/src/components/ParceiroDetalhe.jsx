/**
 * "Acessar Parceiro": dados completos do parceiro + histórico de interações.
 *
 * Interações são contratos e compras com o parceiro: cliente comprou, cliente pediu
 * reembolso, fornecedor assinou contrato, fornecedor foi pago pelo fornecimento.
 *
 * Daqui o usuário pode alterar o parceiro (o formulário é aberto pela página),
 * registrar uma interação nova e alterar uma interação existente.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import { formatarCep, formatarData, formatarDocumento } from '../formatos'
import Aviso from './Aviso'
import Icone from './Icone'
import InteracaoFormulario from './InteracaoFormulario'
import Modal from './Modal'
import TipoParceiro from './TipoParceiro'

export default function ParceiroDetalhe({ idParceiro, aoFechar, aoEditar }) {
  const [parceiro, setParceiro] = useState(null)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [versao, setVersao] = useState(0) // incrementa para recarregar o parceiro
  // null | 'nova' | interacao_id em edição
  const [formulario, setFormulario] = useState(null)

  useEffect(() => {
    let ativo = true
    api.parceiros
      .obter(idParceiro)
      .then((resposta) => {
        if (ativo) setParceiro(resposta.dados)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
    return () => {
      ativo = false
    }
  }, [idParceiro, versao])

  async function registrar(dados) {
    await api.interacoes.registrar(idParceiro, dados)
    setFormulario(null)
    setAviso('Interação registrada com sucesso.')
    setVersao((atual) => atual + 1)
  }

  async function alterar(interacao, dados) {
    await api.interacoes.editar(idParceiro, interacao.interacao_id, dados)
    setFormulario(null)
    setAviso('Interação atualizada com sucesso.')
    setVersao((atual) => atual + 1)
  }

  const interacoes = parceiro?.interacoes || []

  return (
    <Modal titulo={parceiro?.nome || 'Parceiro'} aoFechar={aoFechar} largo>
      {erro ? <Aviso>{erro}</Aviso> : null}
      {!parceiro && !erro ? (
        <div className="estado-carregando">Carregando parceiro…</div>
      ) : null}

      {parceiro ? (
        <div className="detalhe">
          <dl className="detalhe__grade">
            <div>
              <dt>Relacionamento</dt>
              <dd>
                <TipoParceiro parceiro={parceiro} />
              </dd>
            </div>
            <div>
              <dt>CPF / CNPJ</dt>
              <dd>{formatarDocumento(parceiro.documento) || '—'}</dd>
            </div>
            <div>
              <dt>E-mail</dt>
              <dd>{parceiro.email || '—'}</dd>
            </div>
            <div>
              <dt>CEP</dt>
              <dd>{formatarCep(parceiro.cep) || '—'}</dd>
            </div>
            <div className="detalhe__largo">
              <dt>Observação</dt>
              <dd className="detalhe__texto">{parceiro.observacao || '—'}</dd>
            </div>
          </dl>

          <div className="acoes-formulario">
            <button
              className="botao botao--secundario"
              type="button"
              onClick={() => aoEditar(parceiro)}
            >
              <Icone nome="lapis" />
              Alterar parceiro
            </button>
          </div>

          <section className="interacoes" aria-label="Interações">
            <header className="interacoes__topo">
              <h3>Interações</h3>
              {formulario !== 'nova' ? (
                <button
                  className="botao botao--primario botao--pequeno"
                  type="button"
                  onClick={() => {
                    setAviso('')
                    setFormulario('nova')
                  }}
                >
                  <Icone nome="mais" />
                  Registrar interação
                </button>
              ) : null}
            </header>

            <p className="interacoes__ajuda">
              Compras, reembolsos, contratos e pagamentos feitos com este parceiro.
            </p>

            {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}

            {formulario === 'nova' ? (
              <InteracaoFormulario
                parceiro={parceiro}
                rotuloSalvar="Salvar interação"
                salvar={registrar}
                aoCancelar={() => setFormulario(null)}
              />
            ) : null}

            {interacoes.length === 0 && formulario !== 'nova' ? (
              <p className="interacoes__vazio">
                Nenhuma interação registrada para este parceiro.
              </p>
            ) : null}

            <ol className="interacoes__lista">
              {interacoes.map((interacao) =>
                formulario === interacao.interacao_id ? (
                  <li key={interacao.interacao_id} className="interacao">
                    <InteracaoFormulario
                      parceiro={parceiro}
                      inicial={interacao}
                      rotuloSalvar="Salvar alterações"
                      salvar={(dados) => alterar(interacao, dados)}
                      aoCancelar={() => setFormulario(null)}
                    />
                  </li>
                ) : (
                  <li key={interacao.interacao_id} className="interacao">
                    <div className="interacao__topo">
                      <strong>{formatarData(interacao.ocorrencia)}</strong>
                      <span className="badge">{interacao.canal}</span>
                      <small>por {interacao.usuario_nome || 'usuário'}</small>
                      <button
                        className="botao-icone"
                        type="button"
                        onClick={() => {
                          setAviso('')
                          setFormulario(interacao.interacao_id)
                        }}
                        aria-label="Alterar interação"
                        title="Alterar interação"
                      >
                        <Icone nome="lapis" />
                      </button>
                    </div>
                    <p className="detalhe__texto">{interacao.descricao}</p>
                  </li>
                ),
              )}
            </ol>
          </section>
        </div>
      ) : null}
    </Modal>
  )
}
