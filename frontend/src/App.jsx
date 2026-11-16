/**
 * Roteamento simples por estado (sem biblioteca de rotas).
 *
 * Fluxo: carregando → (sessão?) principal : início
 *   início → login | cadastro (usuário → empresa) → principal
 */
import { useEffect, useState } from 'react'
import { api } from './api'
import BoasVindas from './pages/BoasVindas'
import Cadastro from './pages/Cadastro'
import EmpresaPendente from './pages/EmpresaPendente'
import Login from './pages/Login'
import TelaPrincipal from './pages/TelaPrincipal'

export default function App() {
  const [tela, setTela] = useState('carregando')
  const [usuario, setUsuario] = useState(null)
  const [aviso, setAviso] = useState('')

  useEffect(() => {
    let ativo = true
    api
      .me()
      .then((resposta) => {
        if (!ativo) return
        const dados = resposta.dados
        setUsuario(dados)
        setTela(
          dados.precisa_cadastrar_empresa ? 'empresa-pendente' : 'principal',
        )
      })
      .catch(() => {
        if (ativo) setTela('inicio')
      })
    return () => {
      ativo = false
    }
  }, [])

  function aplicarSessao(dados) {
    setUsuario(dados)
    setAviso('')
    setTela(dados.precisa_cadastrar_empresa ? 'empresa-pendente' : 'principal')
  }

  async function sair() {
    try {
      await api.logout()
    } catch {
      // Seguimos limpando a sessão local mesmo se a API falhar.
    }
    setUsuario(null)
    setAviso('')
    setTela('inicio')
  }

  if (tela === 'carregando') {
    return <div className="tela-carregando">Carregando…</div>
  }

  if (tela === 'login') {
    return (
      <Login
        aviso={aviso}
        aoEntrar={aplicarSessao}
        aoIrCadastro={() => {
          setAviso('')
          setTela('cadastro')
        }}
        aoVoltar={() => setTela('inicio')}
      />
    )
  }

  if (tela === 'cadastro') {
    return (
      <Cadastro
        aoFinalizar={aplicarSessao}
        aoIrLogin={(mensagem) => {
          setAviso(mensagem || '')
          setTela('login')
        }}
        aoVoltar={() => setTela('inicio')}
      />
    )
  }

  if (tela === 'empresa-pendente') {
    return (
      <EmpresaPendente
        usuario={usuario}
        aoIrCadastro={() => setTela('cadastro')}
        aoSair={sair}
      />
    )
  }

  if (tela === 'principal' && usuario) {
    return <TelaPrincipal usuario={usuario} aoSair={sair} />
  }

  return (
    <BoasVindas
      aoIrLogin={() => setTela('login')}
      aoIrCadastro={() => setTela('cadastro')}
    />
  )
}
