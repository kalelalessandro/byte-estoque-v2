/**
 * Guia de interações: painel de ajuda com o que foi combinado, comprado, reembolsado
 * ou pago com os parceiros (as interações cadastradas em Parceiros).
 *
 * - Sem `idParceiro`: as interações mais recentes de TODOS os parceiros da empresa.
 * - Com `idParceiro`: só as desse parceiro (por exemplo, o do título que será baixado),
 *   para o usuário conferir contratos e compras antes de registrar o pagamento.
 *
 * É só leitura: interações são registradas e alteradas na tela de Parceiros.
 *
 * Quando usado no cadastro de um título, recebe `aoUsarInteracao` e `aoUsarValor`: cada
 * interação ganha o botão "Usar na descrição" e, se o texto citar valores em reais
 * ("R$ 1.200,00"), botões para usar o valor. Nada é preenchido sem o clique do usuário.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import { extrairValores, formatarData } from '../formatos'
import Aviso from './Aviso'

export default function GuiaInteracoes({
  idParceiro = 0,
  nomeParceiro = '',
  limite = 10,
  aoUsarInteracao = null, // (interacao) => void
  aoUsarValor = null, // (valorTexto) => void
}) {
  const [interacoes, setInteracoes] = useState([])
  const [total, setTotal] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    api.interacoes
      .listar({ id_parceiro: idParceiro, limit: limite })
      .then((resposta) => {
        if (!ativo) return
        setInteracoes(resposta.dados.interacoes)
        setTotal(resposta.dados.total)
        setErro('')
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [idParceiro, limite])

  return (
    <aside className="guia" aria-label="Guia de interações">
      <h3>Guia de interações</h3>
      <p className="guia__ajuda">
        {idParceiro
          ? `Contratos, compras, reembolsos e pagamentos registrados com ${nomeParceiro || 'este parceiro'}. Confira antes de dar baixa.`
          : 'Últimas interações com seus parceiros: compras, reembolsos, contratos e pagamentos.'}
      </p>

      {erro ? <Aviso>{erro}</Aviso> : null}
      {carregando ? <p className="guia__vazio">Carregando interações…</p> : null}

      {!carregando && !erro && interacoes.length === 0 ? (
        <p className="guia__vazio">
          Nenhuma interação registrada. Cadastre contratos e compras na tela de
          Parceiros para vê-los aqui.
        </p>
      ) : null}

      <ol className="guia__lista">
        {interacoes.map((interacao) => (
          <li key={interacao.interacao_id} className="guia__item">
            <div className="guia__topo">
              <strong>{formatarData(interacao.ocorrencia)}</strong>
              <span className="badge">{interacao.canal}</span>
              {!idParceiro ? <small>{interacao.parceiro_nome}</small> : null}
            </div>
            <p>{interacao.descricao}</p>
            {aoUsarInteracao ? (
              <div className="guia__acoes">
                <button
                  className="link-acao"
                  type="button"
                  onClick={() => aoUsarInteracao(interacao)}
                >
                  Usar na descrição
                </button>
                {aoUsarValor
                  ? extrairValores(interacao.descricao).map((item) => (
                      <button
                        key={item.valor}
                        className="chip-valor"
                        type="button"
                        onClick={() => aoUsarValor(item.valor)}
                      >
                        Usar {item.rotulo}
                      </button>
                    ))
                  : null}
              </div>
            ) : null}
          </li>
        ))}
      </ol>

      {total > interacoes.length ? (
        <p className="guia__vazio">
          Mostrando {interacoes.length} de {total} interações.
        </p>
      ) : null}
    </aside>
  )
}
