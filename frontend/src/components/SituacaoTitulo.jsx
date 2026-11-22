/** Selo da situação do título: Em aberto, Parcial, Quitado ou Cancelado. */
const ROTULOS = {
  aberto: 'Em aberto',
  parcial: 'Parcial',
  quitado: 'Quitado',
  cancelado: 'Cancelado',
}

export default function SituacaoTitulo({ titulo }) {
  return (
    <span className={`badge badge--${titulo.situacao}`}>
      {ROTULOS[titulo.situacao] || titulo.situacao}
    </span>
  )
}
