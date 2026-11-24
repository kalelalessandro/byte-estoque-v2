/**
 * Regra defensiva: tela exibida se a API sinalizar que o usuário logado não
 * possui empresa vinculada (`precisa_cadastrar_empresa: true`).
 *
 * No schema atual isso é impossível (`usuarios.id_empresa NOT NULL`), mas a
 * interface trata o caso sem quebrar o fluxo.
 */
import Marca from '../components/Marca'
import Tela from '../components/Tela'

export default function EmpresaPendente({ usuario, aoIrCadastro, aoSair }) {
  return (
    <Tela className="tela-empresa-pendente">
      <header className="topo">
        <Marca />
      </header>

      <main className="centro">
        <section className="cartao" aria-labelledby="titulo-empresa-pendente">
          <div className="cartao__cabecalho">
            <span className="hero__selo">ATENÇÃO</span>
            <h1 id="titulo-empresa-pendente">Cadastro de empresa necessário</h1>
            <p>
              A conta <strong>{usuario?.email}</strong> está autenticada, mas
              não possui empresa vinculada.
            </p>
          </div>

          <div className="alerta">
            Para continuar, é necessário cadastrar uma empresa. Como o schema
            exige o vínculo desde a criação da conta, refaça o cadastro
            informando os dados do usuário e da empresa.
          </div>

          <div className="acoes-formulario">
            <button
              className="botao botao--primario"
              type="button"
              onClick={aoIrCadastro}
            >
              Ir para o cadastro
            </button>
            <button
              className="botao botao--secundario"
              type="button"
              onClick={aoSair}
            >
              Sair
            </button>
          </div>
        </section>
      </main>
    </Tela>
  )
}
