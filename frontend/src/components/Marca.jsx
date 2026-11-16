/** Marca do Byte Estoque: folha canadense cinza + wordmark. */
import FolhaCanadense from './FolhaCanadense'

export default function Marca({ compacta = false }) {
  return (
    <div className={`marca ${compacta ? 'marca--compacta' : ''}`.trim()}>
      <FolhaCanadense
        className="marca__folha"
        titulo="Folha canadense — marca do Byte Estoque"
      />
      <div className="marca__texto" aria-label="Byte Estoque">
        <strong>BYTE</strong>
        <span>ESTOQUE</span>
      </div>
    </div>
  )
}
