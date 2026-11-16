/** Tela principal pós-login: status WIP. */
import Marca from '../components/Marca'
import Tela from '../components/Tela'

export default function TelaPrincipal({ usuario, aoSair }) {
  return (
    <Tela className="tela-principal">
      <header className="topo topo--principal">
        <Marca compacta />
        <div className="topo__usuario">
          <span>
            {usuario.nome}
            <small>{usuario.empresa?.razao_social}</small>
          </span>
          <button
            className="botao botao--secundario botao--pequeno"
            type="button"
            onClick={aoSair}
          >
            Sair
          </button>
        </div>
      </header>

      <main className="principal">
        <div className="wip">
          <span className="wip__etiqueta">STATUS DO SISTEMA</span>
          <h1>(WORK IN PROGRESS)</h1>
          <p>Estamos construindo os módulos de CRM, estoque e financeiro.</p>
        </div>
      </main>

      <footer className="rodape">
        Byte Estoque © {new Date().getFullYear()} · modo demonstração
      </footer>
    </Tela>
  )
}
