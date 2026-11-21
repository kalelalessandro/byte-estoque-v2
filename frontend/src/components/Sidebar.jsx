/** Navegação lateral fixa do sistema autenticado. */
import Icone from './Icone'
import Marca from './Marca'

const ITENS = [
  { id: 'inicio', rotulo: 'Início', icone: 'inicio' },
  { id: 'produtos', rotulo: 'Produtos', icone: 'produtos' },
  { id: 'categorias', rotulo: 'Categorias', icone: 'categorias' },
]

const FUTUROS = [
  { rotulo: 'Parceiros', icone: 'usuarios' },
  { rotulo: 'Financeiro', icone: 'dinheiro' },
  { rotulo: 'Relatórios', icone: 'grafico' },
]

function iniciais(nome = '') {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  return (partes[0]?.[0] || 'U') + (partes[1]?.[0] || '')
}

export default function Sidebar({
  ativo,
  aoNavegar,
  aoSair,
  usuario,
  aberto,
  aoFechar,
}) {
  function navegar(id) {
    aoNavegar(id)
    aoFechar()
  }

  return (
    <aside className={`sidebar ${aberto ? 'sidebar--aberto' : ''}`.trim()}>
      <div className="sidebar__topo">
        <Marca compacta />
        <button
          className="sidebar__fechar"
          type="button"
          onClick={aoFechar}
          aria-label="Fechar menu"
        >
          <Icone nome="fechar" />
        </button>
      </div>

      <nav className="sidebar__nav" aria-label="Navegação principal">
        <span className="sidebar__secao">Menu</span>
        {ITENS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sidebar__item ${
              ativo === item.id ? 'sidebar__item--ativo' : ''
            }`.trim()}
            onClick={() => navegar(item.id)}
            aria-current={ativo === item.id ? 'page' : undefined}
          >
            <Icone nome={item.icone} />
            <span>{item.rotulo}</span>
          </button>
        ))}

        <span className="sidebar__secao sidebar__secao--futura">
          Em breve
        </span>
        {FUTUROS.map((item) => (
          <button
            key={item.rotulo}
            type="button"
            className="sidebar__item sidebar__item--futuro"
            disabled
            title="Módulo em construção"
          >
            <Icone nome={item.icone} />
            <span>{item.rotulo}</span>
            <small>em breve</small>
          </button>
        ))}
      </nav>

      <div className="sidebar__rodape">
        <div className="sidebar__usuario">
          <span className="sidebar__avatar" aria-hidden="true">
            {iniciais(usuario?.nome).toUpperCase()}
          </span>
          <span className="sidebar__dados">
            <strong>{usuario?.nome || 'Usuário'}</strong>
            <small>{usuario?.empresa?.razao_social || 'Byte Estoque'}</small>
          </span>
        </div>
        <button className="sidebar__sair" type="button" onClick={aoSair}>
          <Icone nome="sair" />
          Sair da conta
        </button>
      </div>
    </aside>
  )
}
