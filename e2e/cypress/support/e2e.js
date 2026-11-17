// Arquivo carregado automaticamente antes de CADA spec (ver supportFile no cypress.config.js).
import './commands';

// Garante que cada spec começa e termina sem sobras dos testes anteriores.
// A limpeza só apaga usuários com e-mail "@e2e.exemplo.com.br" (e o que depende
// deles); dados de demonstração/produção nunca são tocados.
before(() => {
  cy.task('db:cleanup');
});

after(() => {
  cy.task('db:cleanup');
});
