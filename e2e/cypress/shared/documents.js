// Geradores de CNPJ (numérico ou alfanumérico) com dígitos verificadores corretos.
// Mesma regra do backend (signup.py): módulo 11, valor do caractere = ASCII - 48.

const valor = (caractere) => caractere.charCodeAt(0) - 48;

function digitoVerificador(valores, pesos) {
  const soma = valores.reduce((total, v, i) => total + v * pesos[i], 0);
  const resto = soma % 11;
  return resto < 2 ? 0 : 11 - resto;
}

/** Recebe os 12 primeiros caracteres e devolve o CNPJ completo (14 caracteres). */
function cnpj(base12) {
  const base = base12.toUpperCase();
  const valores = [...base].map(valor);
  valores.push(digitoVerificador(valores, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]));
  valores.push(digitoVerificador(valores, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]));
  return base + valores[12] + valores[13];
}

/** CNPJ com o último dígito verificador propositalmente errado. */
function cnpjInvalido(base12) {
  const completo = cnpj(base12);
  return completo.slice(0, 13) + ((Number(completo[13]) + 1) % 10);
}

/** 11.222.333/0001-81 (máscara de 18 caracteres, cabe no campo da tela). */
function mascararCnpj(completo) {
  const c = completo;
  return `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}`;
}

module.exports = { cnpj, cnpjInvalido, mascararCnpj };
