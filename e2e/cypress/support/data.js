// Dados de teste. Os "montar..." devolvem um cadastro VÁLIDO (caminho feliz);
// nos testes negativos sobrescrevemos só o campo que está sendo testado:
//   montarEmpresa({ cnpj: '123' })
import { cnpj } from '../shared/documents';

export { cnpj, cnpjInvalido, mascararCnpj } from '../shared/documents';

// Todo e-mail de teste termina neste domínio: é o que permite a limpeza do banco
// apagar só o que o Cypress criou (ver tasks/db.js).
export const DOMINIO_E2E = 'e2e.exemplo.com.br';
export const email = (nome) => `${nome}@${DOMINIO_E2E}`;

export const repetir = (tamanho, caractere = 'A') => caractere.repeat(tamanho);

/** E-mail com exatamente `tamanho` caracteres (limite do banco: 254). */
export const emailComTamanho = (tamanho) =>
  repetir(tamanho - `@${DOMINIO_E2E}`.length, 'e') + `@${DOMINIO_E2E}`;

export const montarUsuario = (sobrescritas = {}) => ({
  nome: 'Marina Albuquerque',
  email: email('marina.albuquerque'),
  telefone: '81987654321',
  senha: 'Sen#Mar2026',
  ...sobrescritas,
});

export const montarEmpresa = (sobrescritas = {}) => ({
  razao_social: 'Distribuidora Recife Norte Ltda',
  cnpj: cnpj('CY0000000001'),
  cep: '',
  inscricao: '',
  telefone_empresa: '',
  ...sobrescritas,
});

export const montarProduto = (sobrescritas = {}) => ({
  sku: 'PRD-1001',
  nome: 'Parafuso Sextavado M8',
  descricao: 'Parafuso aço zincado 8mm',
  unidade_estoque: 150,
  preco: '12.50',
  ...sobrescritas,
});
