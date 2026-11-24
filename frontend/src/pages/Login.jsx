/** Tela de login. */
import { useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Marca from '../components/Marca'
import Tela from '../components/Tela'

export default function Login({ aviso, aoEntrar, aoIrCadastro, aoVoltar }) {
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(false)

  async function enviar(evento) {
    evento.preventDefault()
    setErro('')
    setCarregando(true)
    try {
      const resposta = await api.login(email.trim(), senha)
      aoEntrar(resposta.dados)
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    } finally {
      setCarregando(false)
    }
  }

  return (
    <Tela className="tela-login">
      <header className="topo">
        <Marca />
      </header>

      <main className="centro">
        <section className="cartao" aria-labelledby="titulo-login">
          <div className="cartao__cabecalho">
            <span className="hero__selo">ACESSO</span>
            <h1 id="titulo-login">Entrar no Byte Estoque</h1>
            <p>Use o e-mail e a senha cadastrados.</p>
          </div>

          {aviso ? <div className="alerta alerta--sucesso">{aviso}</div> : null}
          {erro ? <div className="alerta">{erro}</div> : null}

          <form className="formulario" onSubmit={enviar} noValidate>
            <div className="campo">
              <label htmlFor="login-email">E-mail</label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                placeholder="voce@empresa.com"
                value={email}
                onChange={(evento) => setEmail(evento.target.value)}
                autoFocus
                required
              />
            </div>

            <div className="campo">
              <label htmlFor="login-senha">Senha</label>
              <input
                id="login-senha"
                type="password"
                autoComplete="current-password"
                placeholder="Sua senha"
                value={senha}
                onChange={(evento) => setSenha(evento.target.value)}
                required
              />
            </div>

            <div className="acoes-formulario">
              <button
                className="botao botao--primario"
                type="submit"
                disabled={carregando}
              >
                {carregando ? 'Entrando...' : 'Entrar'}
              </button>
              <button
                className="botao botao--texto"
                type="button"
                onClick={aoIrCadastro}
              >
                Criar conta
              </button>
            </div>
          </form>

          <div className="rodape-formulario">
            <button className="botao botao--texto" type="button" onClick={aoVoltar}>
              ← Voltar para o início
            </button>
          </div>
        </section>
      </main>
    </Tela>
  )
}
