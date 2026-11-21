/** Dashboard inicial do sistema autenticado. */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'

const MOEDA = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

const RESUMO_VAZIO = {
  produtos: 0,
  categorias: 0,
  valor_estoque: '0.00',
}

export default function Inicio({ usuario, aoNavegar }) {
  const [estado, setEstado] = useState({
    carregando: true,
    erro: '',
    dados: RESUMO_VAZIO,
  })

  useEffect(() => {
    let ativo = true

    // Uma única chamada agregada: nada de baixar todos os produtos/categorias.
    api
      .dashboard()
      .then((resposta) => {
        if (!ativo) return
        setEstado({ carregando: false, erro: '', dados: resposta.dados })
      })
      .catch((falha) => {
        if (!ativo) return
        setEstado((anterior) => ({
          ...anterior,
          carregando: false,
          erro: mensagemDeErro(falha),
        }))
      })

    return () => {
      ativo = false
    }
  }, [])

  const cartoes = [
    {
      id: 'produtos',
      rotulo: 'Produtos',
      valor: estado.dados.produtos,
      detalhe: 'itens cadastrados',
      icone: 'produtos',
      acao: () => aoNavegar('produtos'),
    },
    {
      id: 'categorias',
      rotulo: 'Categorias',
      valor: estado.dados.categorias,
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
      valor: MOEDA.format(Number(estado.dados.valor_estoque || 0)),
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

      {estado.erro ? <Aviso>{estado.erro}</Aviso> : null}

      <section className="dashboard__grade" aria-label="Resumo do estoque">
        {cartoes.map((cartao) => {
          const conteudo = (
            <>
              <span className={`metrica__icone metrica__icone--${cartao.id}`}>
                <Icone nome={cartao.icone} />
              </span>
              <span className="metrica__rotulo">{cartao.rotulo}</span>
              <strong className="metrica__valor">
                {estado.carregando ? '…' : cartao.valor}
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
