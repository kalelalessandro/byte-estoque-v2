/** Mensagem de erro/sucesso usada nas telas internas. */
export default function Aviso({ tipo = 'erro', children }) {
  if (!children) return null
  return (
    <div
      className={`alerta ${tipo === 'sucesso' ? 'alerta--sucesso' : ''}`.trim()}
      role="status"
    >
      {children}
    </div>
  )
}
