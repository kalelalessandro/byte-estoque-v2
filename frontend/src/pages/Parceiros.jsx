/**
 * Parceiros (clientes e fornecedores): listar, acessar, inserir, alterar e apagar.
 *
 * Segue o fluxo do fluxograma: Listar Parceiros → Acessar Parceiro (dados +
 * interações) → Alterar Parceiro → Apagar Parceiro; e Inserir Parceiro Novo →
 * Registrar Interação (o parceiro recém-criado já abre no "Acessar Parceiro").
 * Interações são contratos e compras: venda/reembolso a cliente, contrato/pagamento
 * de fornecedor.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'
import ParceiroDetalhe from '../components/ParceiroDetalhe'
import ParceiroFormulario from '../components/ParceiroFormulario'
import TipoParceiro from '../components/TipoParceiro'
import { formatarDocumento } from '../formatos'

const FILTROS = [
  { id: 'todos', rotulo: 'Todos' },
  { id: 'cliente', rotulo: 'Clientes' },
  { id: 'fornecedor', rotulo: 'Fornecedores' },
  { id: 'ambos', rotulo: 'Cliente e fornecedor' },
]

export default function Parceiros() {
  const [parceiros, setParceiros] = useState([])
  const [total, setTotal] = useState(0)
  const [busca, setBusca] = useState('')
  const [tipo, setTipo] = useState('todos')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [versao, setVersao] = useState(0) // incrementa para recarregar a lista
  // null | { nome: 'detalhe', id } | { nome: 'formulario', parceiro, voltarPara }
  const [modal, setModal] = useState(null)

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    // Busca imediata ao abrir a tela; debounce só quando o usuário digita.
    const atraso = busca.trim() ? 250 : 0
    const temporizador = setTimeout(() => {
      api.parceiros
        .listar({ busca: busca.trim(), tipo, limit: 200 })
        .then((resposta) => {
          if (!ativo) return
          setParceiros(resposta.dados.parceiros)
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
  }, [busca, tipo, versao])

  function recarregar() {
    setVersao((atual) => atual + 1)
  }

  function abrirNovo() {
    setAviso('')
    setModal({ nome: 'formulario', parceiro: null, voltarPara: null })
  }

  function abrirDetalhe(parceiro) {
    setAviso('')
    setModal({ nome: 'detalhe', id: parceiro.id_parceiro })
  }

  function abrirEdicao(parceiro, voltarPara = null) {
    setAviso('')
    setModal({ nome: 'formulario', parceiro, voltarPara })
  }

  function aoSalvar(salvo, edicao, voltarPara) {
    recarregar()
    if (edicao) {
      setAviso('Parceiro atualizado com sucesso.')
      // Quem veio do "Acessar Parceiro" volta para ele.
      setModal(voltarPara ? { nome: 'detalhe', id: voltarPara } : null)
    } else {
      setAviso('Parceiro criado com sucesso.')
      // Fluxo: Inserir Parceiro → Registrar Interação.
      setModal({ nome: 'detalhe', id: salvo.id_parceiro })
    }
  }

  /** Apaga o parceiro. Lança erro (ex.: 409 com vínculos) para quem chamou tratar. */
  async function excluir(parceiro) {
    await api.parceiros.excluir(parceiro.id_parceiro)
    setModal(null)
    setAviso('Parceiro excluído com sucesso.')
    recarregar()
  }

  async function excluirDaLista(parceiro) {
    const confirmado = window.confirm(
      `Excluir o parceiro "${parceiro.nome}"? Essa ação não pode ser desfeita.`,
    )
    if (!confirmado) return

    setAviso('')
    setErro('')
    try {
      await excluir(parceiro)
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <span className="rotulo-secao">Relacionamento</span>
          <h2>Parceiros</h2>
          <p>
            Clientes e fornecedores da sua empresa, com o histórico de compras,
            contratos e pagamentos.
          </p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--primario"
            type="button"
            onClick={abrirNovo}
          >
            <Icone nome="mais" />
            Inserir parceiro novo
          </button>
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      <section className="painel">
        <div className="painel__topo">
          <label className="campo-busca">
            <Icone nome="busca" />
            <input
              type="search"
              placeholder="Buscar por nome, e-mail ou documento…"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
              aria-label="Buscar parceiros"
            />
          </label>
          <span className="contador">
            {total} {total === 1 ? 'parceiro' : 'parceiros'}
          </span>
        </div>

        <div className="filtros" role="group" aria-label="Filtrar por relacionamento">
          {FILTROS.map((filtro) => (
            <button
              key={filtro.id}
              type="button"
              className={`filtro ${tipo === filtro.id ? 'filtro--ativo' : ''}`.trim()}
              aria-pressed={tipo === filtro.id}
              onClick={() => setTipo(filtro.id)}
            >
              {filtro.rotulo}
            </button>
          ))}
        </div>

        {carregando ? (
          <div className="estado-carregando">Carregando parceiros…</div>
        ) : parceiros.length === 0 ? (
          <div className="estado-vazio">
            <Icone nome="usuarios" />
            <h3>Nenhum parceiro por aqui</h3>
            <p>
              {busca || tipo !== 'todos'
                ? 'Nenhum resultado para esse filtro.'
                : 'Cadastre o primeiro cliente ou fornecedor da sua empresa.'}
            </p>
            {!busca && tipo === 'todos' ? (
              <button
                className="botao botao--primario"
                type="button"
                onClick={abrirNovo}
              >
                <Icone nome="mais" />
                Inserir parceiro novo
              </button>
            ) : null}
          </div>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Parceiro</th>
                  <th>Documento</th>
                  <th>E-mail</th>
                  <th>Tipo</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {parceiros.map((parceiro) => (
                  <tr key={parceiro.id_parceiro}>
                    <td>
                      <button
                        className="tabela__link"
                        type="button"
                        onClick={() => abrirDetalhe(parceiro)}
                      >
                        {parceiro.nome}
                      </button>
                    </td>
                    <td>
                      {parceiro.documento ? (
                        <span className="sku">
                          {formatarDocumento(parceiro.documento)}
                        </span>
                      ) : (
                        <span className="tabela__secundario">—</span>
                      )}
                    </td>
                    <td>
                      {parceiro.email || (
                        <span className="tabela__secundario">—</span>
                      )}
                    </td>
                    <td>
                      <TipoParceiro parceiro={parceiro} />
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        <button
                          className="botao-icone"
                          type="button"
                          onClick={() => abrirDetalhe(parceiro)}
                          aria-label={`Acessar ${parceiro.nome}`}
                          title="Acessar parceiro"
                        >
                          <Icone nome="olho" />
                        </button>
                        <button
                          className="botao-icone"
                          type="button"
                          onClick={() => abrirEdicao(parceiro)}
                          aria-label={`Alterar ${parceiro.nome}`}
                          title="Alterar"
                        >
                          <Icone nome="lapis" />
                        </button>
                        <button
                          className="botao-icone botao-icone--perigo"
                          type="button"
                          onClick={() => excluirDaLista(parceiro)}
                          aria-label={`Excluir ${parceiro.nome}`}
                          title="Excluir"
                        >
                          <Icone nome="lixo" />
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

      {modal?.nome === 'detalhe' ? (
        <ParceiroDetalhe
          idParceiro={modal.id}
          aoFechar={() => setModal(null)}
          aoEditar={(parceiro) => abrirEdicao(parceiro, parceiro.id_parceiro)}
        />
      ) : null}

      {modal?.nome === 'formulario' ? (
        <ParceiroFormulario
          parceiro={modal.parceiro}
          aoFechar={() =>
            setModal(
              modal.voltarPara ? { nome: 'detalhe', id: modal.voltarPara } : null,
            )
          }
          aoSalvo={(salvo) => aoSalvar(salvo, Boolean(modal.parceiro), modal.voltarPara)}
          aoExcluir={modal.parceiro ? excluir : undefined}
        />
      ) : null}
    </div>
  )
}
