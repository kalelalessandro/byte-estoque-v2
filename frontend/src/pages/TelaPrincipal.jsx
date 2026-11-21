/** Casca do sistema autenticado: sidebar + páginas internas. */
import { useEffect, useState } from 'react'
import { api } from '../api'
import Icone from '../components/Icone'
import Sidebar from '../components/Sidebar'
import Tela from '../components/Tela'
import Categorias from './Categorias'
import Inicio from './Inicio'
import Parceiros from './Parceiros'
import Produtos from './Produtos'

const TITULOS = {
  inicio: 'Início',
  produtos: 'Produtos',
  categorias: 'Categorias',
  parceiros: 'Parceiros',
}

function iniciais(nome = '') {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  return (partes[0]?.[0] || 'U') + (partes[1]?.[0] || '')
}

export default function TelaPrincipal({ usuario, aoSair }) {
  const [pagina, setPagina] = useState('inicio')
  const [menuAberto, setMenuAberto] = useState(false)

  useEffect(() => {
    // Pré-aquece o cache das abas assim que o shell monta. Assim, quando o
    // usuário clicar em Produtos/Categorias/Parceiros, os dados normalmente já chegaram.
    const temporizador = setTimeout(() => {
      Promise.allSettled([
        api.produtos.listar({ limit: 200 }),
        api.categorias.listar(),
        api.parceiros.listar({ limit: 200 }),
      ])
    }, 150)

    return () => clearTimeout(temporizador)
  }, [])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [pagina])

  function navegar(destino) {
    setPagina(destino)
    setMenuAberto(false)
  }

  return (
    <Tela className="tela-app">
      <div className="app-layout">
        <Sidebar
          ativo={pagina}
          aoNavegar={navegar}
          aoSair={aoSair}
          usuario={usuario}
          aberto={menuAberto}
          aoFechar={() => setMenuAberto(false)}
        />

        {menuAberto ? (
          <button
            className="sidebar-overlay"
            type="button"
            aria-label="Fechar menu"
            onClick={() => setMenuAberto(false)}
          />
        ) : null}

        <div className="app-conteudo">
          <header className="app-topo">
            <div className="app-topo__esquerda">
              <button
                className="app-menu-botao"
                type="button"
                onClick={() => setMenuAberto(true)}
                aria-label="Abrir menu"
              >
                <Icone nome="menu" />
              </button>
              <div>
                <span className="app-topo__rotulo">
                  Byte Estoque / {TITULOS[pagina]}
                </span>
                <h1>{TITULOS[pagina]}</h1>
              </div>
            </div>

            <div className="app-topo__usuario">
              <span className="app-topo__avatar" aria-hidden="true">
                {iniciais(usuario?.nome).toUpperCase()}
              </span>
              <span className="app-topo__dados">
                <strong>{usuario?.nome || 'Usuário'}</strong>
                <small>{usuario?.empresa?.razao_social}</small>
              </span>
            </div>
          </header>

          <main className="app-pagina" id="conteudo-principal">
            {pagina === 'inicio' ? (
              <Inicio usuario={usuario} aoNavegar={navegar} />
            ) : null}
            {pagina === 'produtos' ? (
              <Produtos aoNavegar={navegar} />
            ) : null}
            {pagina === 'categorias' ? (
              <Categorias aoNavegar={navegar} />
            ) : null}
            {pagina === 'parceiros' ? <Parceiros /> : null}
          </main>
        </div>
      </div>
    </Tela>
  )
}
