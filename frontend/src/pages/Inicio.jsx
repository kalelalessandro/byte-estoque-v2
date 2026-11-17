/** Dashboard inicial do sistema autenticado. */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'

const MOEDA = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

export default function Inicio({ usuario, aoNavegar }) {
  const [resumo, setResumo] = useState({
    carregando: true,
    erro: '',
    produtos: [],
    totalProdutos: 0,
    categorias: [],
  })

  useEffect(() => {
    let ativo = true

    Promise.all([
      api.produtos.listar({ limit: 200 }),
      api.categorias.listar(),
    ])
      .then(([produtos, categorias]) => {
        if (!ativo) return
        setResumo({
          carregando: false,
          erro: '',
          produtos: produtos.dados.produtos,
          totalProdutos: produtos.dados.total,
          categorias: categorias.dados.categorias,
        })
      })
      .catch((falha) => {
        if (!ativo) return
        setResumo((anterior) => ({
          ...anterior,
          carregando: false,
          erro: mensagemDeErro(falha),
        }))
      })

    return () => {
      ativo = false
    }
  }, [])

  const valorEmEstoque = resumo.produtos.reduce(
    (soma, produto) =>
      soma + Number(produto.preco || 0) * Number(produto.unidade_estoque || 0),
    0,
  )

  const cartoes = [
    {
      id: 'produtos',
      rotulo: 'Produtos',
      valor: resumo.totalProdutos,
      detalhe: 'itens cadastrados',
      icone: 'produtos',
      acao: () => aoNavegar('produtos'),
    },
    {
      id: 'categorias',
      rotulo: 'Categorias',
      valor: resumo.categorias.length,
      detalhe: 'categorias ativas',
      icone: 'categorias',
      acao: () => aoNavegar('categorias'),
    },
    {
      id: 'dinheiro',
      rotulo: 'Dinheiro',
      valor: '—',
      detalhe: 'Em breve',
      icone: 'dinheiro',
      indisponivel: true,
    },
    {
      id: 'parceiros',
      rotulo: 'Parceiros',
      valor: '—',
      detalhe: 'Em breve',
      icone: 'usuarios',
      indisponivel: true,
    },
    {
      id: 'estoque',
      rotulo: 'Valor em estoque',
      valor: MOEDA.format(valorEmEstoque),
      detalhe: 'preço × quantidade',
      icone: 'grafico',
    },
  ]

  const primeiroNome = (usuario?.nome || 'Usuário').split(/\s+/)[0]

  return (
    <div className="dashboard">
      <section className="dashboard__saudacao">
        <div>
          <span className="rotulo-secao">Visão geral</span>
          <h2>Olá, {primeiroNome}!</h2>
          <p>Aqui está um resumo do seu estoque.</p>
        </div>
        <button
          className="botao botao--primario"
          type="button"
          onClick={() => aoNavegar('produtos')}
        >
          <Icone nome="mais" />
          Ver produtos
        </button>
      </section>

      {resumo.erro ? <Aviso>{resumo.erro}</Aviso> : null}

      <section className="dashboard__grade" aria-label="Resumo do estoque">
        {cartoes.map((cartao) => {
          const conteudo = (
            <>
              <span className={`metrica__icone metrica__icone--${cartao.id}`}>
                <Icone nome={cartao.icone} />
              </span>
              <span className="metrica__rotulo">{cartao.rotulo}</span>
              <strong className="metrica__valor">
                {resumo.carregando ? '…' : cartao.valor}
              </strong>
              <span className="metrica__detalhe">
                {cartao.detalhe}
                {cartao.indisponivel ? (
                  <span className="metrica__tag">em breve</span>
                ) : null}
              </span>
              {cartao.acao ? (
                <span className="metrica__seta" aria-hidden="true">
                  <Icone nome="seta" />
                </span>
              ) : null}
            </>
          )

          return cartao.acao ? (
            <button
              key={cartao.id}
              type="button"
              className="metrica metrica--clicavel"
              onClick={cartao.acao}
            >
              {conteudo}
            </button>
          ) : (
            <article
              key={cartao.id}
              className={`metrica ${cartao.indisponivel ? 'metrica--futura' : ''}`.trim()}
            >
              {conteudo}
            </article>
          )
        })}
      </section>

      <section className="wip-painel" aria-label="Status do sistema">
        <span className="wip__etiqueta">Status do sistema</span>
        <h2>(WORK IN PROGRESS)</h2>
        <p>
          O catálogo de produtos e categorias já está disponível. Os módulos de
          parceiros, financeiro e caixa estão em construção.
        </p>
      </section>
    </div>
  )
}
