/** Janela modal reutilizável (produto, categoria, confirmações). */
import { useEffect } from 'react'
import Icone from './Icone'

export default function Modal({ titulo, aoFechar, children, largo = false }) {
  useEffect(() => {
    function aoApertar(evento) {
      if (evento.key === 'Escape') aoFechar()
    }
    document.addEventListener('keydown', aoApertar)
    return () => document.removeEventListener('keydown', aoApertar)
  }, [aoFechar])

  return (
    <div
      className="modal-fundo"
      role="presentation"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget) aoFechar()
      }}
    >
      <section
        className={`modal ${largo ? 'modal--largo' : ''}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-modal"
      >
        <header className="modal__topo">
          <h2 id="titulo-modal">{titulo}</h2>
          <button
            className="modal__fechar"
            type="button"
            onClick={aoFechar}
            aria-label="Fechar"
          >
            <Icone nome="fechar" />
          </button>
        </header>
        {children}
      </section>
    </div>
  )
}
