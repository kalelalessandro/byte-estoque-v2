/**
 * Financeiro: página única com três abas (Títulos, Baixas e Caixas).
 *
 * Cada aba é a página completa do módulo. As abas se conversam: sem caixa aberto, o
 * formulário de baixa leva o usuário direto para a aba Caixas (`aoMudarAba('caixas')`).
 * Segue o padrão de acessibilidade de abas (tablist/tab/tabpanel, setas do teclado).
 */
import { useRef, useState } from 'react'
import Baixas from './Baixas'
import Caixas from './Caixas'
import Titulos from './Titulos'

const ABAS = [
  { id: 'titulos', rotulo: 'Títulos' },
  { id: 'baixas', rotulo: 'Baixas' },
  { id: 'caixas', rotulo: 'Caixas' },
]

export default function Financeiro({ abaInicial = 'titulos' }) {
  const [aba, setAba] = useState(abaInicial)
  const botoes = useRef({})

  /** Setas esquerda/direita, Home e End trocam de aba e movem o foco (padrão WAI-ARIA). */
  function aoTeclar(evento) {
    const posicao = ABAS.findIndex((item) => item.id === aba)
    let destino = null
    if (evento.key === 'ArrowRight') destino = (posicao + 1) % ABAS.length
    if (evento.key === 'ArrowLeft') destino = (posicao - 1 + ABAS.length) % ABAS.length
    if (evento.key === 'Home') destino = 0
    if (evento.key === 'End') destino = ABAS.length - 1
    if (destino === null) return
    evento.preventDefault()
    setAba(ABAS[destino].id)
    botoes.current[ABAS[destino].id]?.focus()
  }

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <span className="rotulo-secao">Financeiro</span>
          <h2>Financeiro</h2>
          <p>Títulos a pagar e a receber, baixas financeiras e o controle do caixa.</p>
        </div>
      </header>

      <div className="abas" role="tablist" aria-label="Seções do financeiro" onKeyDown={aoTeclar}>
        {ABAS.map((item) => (
          <button
            key={item.id}
            ref={(elemento) => {
              botoes.current[item.id] = elemento
            }}
            id={`aba-${item.id}`}
            className={`aba ${aba === item.id ? 'aba--ativa' : ''}`.trim()}
            type="button"
            role="tab"
            aria-selected={aba === item.id}
            aria-controls={`painel-${item.id}`}
            tabIndex={aba === item.id ? 0 : -1}
            onClick={() => setAba(item.id)}
          >
            {item.rotulo}
          </button>
        ))}
      </div>

      <div
        id={`painel-${aba}`}
        role="tabpanel"
        aria-labelledby={`aba-${aba}`}
        className="aba-painel"
      >
        {aba === 'titulos' ? <Titulos aoMudarAba={setAba} /> : null}
        {aba === 'baixas' ? <Baixas aoMudarAba={setAba} /> : null}
        {aba === 'caixas' ? <Caixas /> : null}
      </div>
    </div>
  )
}
