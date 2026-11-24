/** Casca de todas as telas: conteúdo + folha canadense cinza ao fundo. */
import FolhaCanadense from './FolhaCanadense'

export default function Tela({ children, className = '' }) {
  return (
    <div className={`tela ${className}`.trim()}>
      <div className="tela__conteudo">{children}</div>
      <FolhaCanadense
        className="marca-dagua"
        titulo="Folha canadense — marca d'água do Byte Estoque"
      />
    </div>
  )
}
