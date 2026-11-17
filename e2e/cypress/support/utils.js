/**
 * Preenche um campo pelo seletor. Regras:
 *   - `undefined` ignora o campo (mantém o valor atual da tela);
 *   - "" apenas limpa o campo;
 *   - qualquer outro valor é digitado (sem interpretar "{" como tecla especial).
 */
export function preencher(seletor, valor) {
  if (valor === undefined) return;
  const campo = cy.get(seletor).clear();
  if (valor !== '') campo.type(valor, { delay: 0, parseSpecialCharSequences: false });
}

/**
 * Gera um `it` para cada linha da tabela de casos. O título já leva o ID do
 * Plano de Testes (ex.: "EMP-N06 - CNPJ numérico com dígitos incorretos"),
 * o que facilita rastrear cada teste até o plano.
 */
export const paraCada = (casos, executar) =>
  casos.forEach((caso) => it(`${caso.id} - ${caso.titulo}`, () => executar(caso)));
