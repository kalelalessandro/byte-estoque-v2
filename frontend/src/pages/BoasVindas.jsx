/** Tela inicial: apresentação + acesso ao login/cadastro. */
import Marca from '../components/Marca'
import Tela from '../components/Tela'

export default function BoasVindas({ aoIrLogin, aoIrCadastro }) {
  return (
    <Tela className="tela-inicial">
      <header className="topo">
        <Marca />
        <button className="botao botao--texto" type="button" onClick={aoIrLogin}>
          Já tenho conta
        </button>
      </header>

      <main className="hero">
        <span className="hero__selo">CRM · ESTOQUE · FINANCEIRO</span>
        <h1>
          Controle seu negócio <em>em um só lugar.</em>
        </h1>
        <p>
          Cadastre sua empresa, acesse o sistema e acompanhe o estoque do seu
          jeito — simples, rápido e seguro.
        </p>
        <div className="hero__acoes">
          <button
            className="botao botao--primario"
            type="button"
            onClick={aoIrCadastro}
          >
            Criar conta
          </button>
          <button
            className="botao botao--secundario"
            type="button"
            onClick={aoIrLogin}
          >
            Entrar
          </button>
        </div>
      </main>

      <footer className="rodape">
        Byte Estoque © {new Date().getFullYear()}
      </footer>
    </Tela>
  )
}
