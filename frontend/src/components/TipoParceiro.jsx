/** Selo(s) de relacionamento do parceiro: Cliente, Fornecedor ou os dois. */
export default function TipoParceiro({ parceiro }) {
  return (
    <span className="tipos-parceiro">
      {parceiro.e_cliente ? (
        <span className="badge badge--cliente">Cliente</span>
      ) : null}
      {parceiro.e_fornecedor ? (
        <span className="badge badge--fornecedor">Fornecedor</span>
      ) : null}
    </span>
  )
}
