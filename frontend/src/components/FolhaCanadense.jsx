/** Folha canadense estilizada — logo/marca d'água do Byte Estoque. */
export default function FolhaCanadense({ className = '', titulo }) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      {titulo ? <title>{titulo}</title> : null}
      <path
        fill="currentColor"
        d="M50 3 L55 20 L68 15 L63 32 L82 28 L72 43 L90 46 L76 59 L88 74 L68 68 L70 88 L55 77 L54 97 L50 82 L46 97 L45 77 L30 88 L32 68 L12 74 L24 59 L10 46 L28 43 L18 28 L37 32 L32 15 L45 20 Z"
      />
    </svg>
  )
}
