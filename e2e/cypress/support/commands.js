// Comandos reutilizáveis das jornadas. Tudo que o usuário faz pela tela fica aqui
// (cadastro, login, menu); o que é só massa de dados usa a API (cy.request).
import { preencher } from './utils';

const MOEDA = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

// ---------------------------------------------------------------- navegação ---

/** Clica num item da sidebar (Início, Produtos, Categorias, Operações, Equipe, Parceiros ou Financeiro). */
Cypress.Commands.add('menu', (rotulo) => {
  cy.get('nav[aria-label="Navegação principal"]').contains('button', rotulo).click();
});

// ------------------------------------------------------------- pela interface ---

/** Cadastro, etapa 1 (usuário): preenche e clica em "Continuar para empresa". */
Cypress.Commands.add('cadastroEtapaUsuario', (usuario) => {
  preencher('#cad-nome', usuario.nome);
  preencher('#cad-email', usuario.email);
  preencher('#cad-telefone', usuario.telefone);
  preencher('#cad-senha', usuario.senha);
  preencher('#cad-confirmar', usuario.confirmar ?? usuario.senha);
  cy.contains('button', 'Continuar para empresa').click();
});

/** Cadastro, etapa 2 (empresa): preenche e clica em "Criar conta e empresa". */
Cypress.Commands.add('cadastroEtapaEmpresa', (empresa) => {
  preencher('#cad-razao', empresa.razao_social);
  preencher('#cad-cnpj', empresa.cnpj);
  preencher('#cad-cep', empresa.cep);
  preencher('#cad-inscricao', empresa.inscricao);
  preencher('#cad-telefone-empresa', empresa.telefone_empresa);
  cy.contains('button', 'Criar conta e empresa').click();
});

/** Fluxo completo: Início → Criar conta → usuário → empresa → já logado no Início. */
Cypress.Commands.add('cadastrarPelaTela', ({ usuario, empresa }) => {
  cy.visit('/');
  cy.contains('button', 'Criar conta').click();
  cy.cadastroEtapaUsuario(usuario);
  cy.cadastroEtapaEmpresa(empresa);
  cy.contains('h2', `Olá, ${usuario.nome.split(' ')[0]}!`).should('be.visible');
});

/** Login pela tela (precisa estar deslogado). */
Cypress.Commands.add('entrarPelaTela', (email, senha) => {
  cy.visit('/');
  cy.contains('button', 'Entrar').click();
  preencher('#login-email', email);
  preencher('#login-senha', senha);
  cy.get('form button[type="submit"]').click();
});

Cypress.Commands.add('sairPelaTela', () => {
  cy.intercept('POST', '/api/auth/logout').as('logout');
  cy.contains('button', 'Sair da conta').click();
  cy.wait('@logout').its('response.statusCode').should('eq', 200);
  cy.contains('h1', 'Controle seu negócio').should('be.visible');
  // Confirma no servidor que o cookie de sessão realmente foi invalidado antes
  // de recarregar a página; evita flakes de logout quando há requisições em voo.
  cy.request({ url: '/api/auth/me', failOnStatusCode: false })
    .its('status')
    .should('eq', 401);
});

/** Abre o Início e confere os 3 números do dashboard. `valor` é um número (ex.: 1725). */
Cypress.Commands.add('conferirResumo', ({ produtos, categorias, valor }) => {
  cy.menu('Início');
  const cartao = (rotulo) =>
    cy
      .contains('.metrica__rotulo', new RegExp(`^${rotulo}$`))
      .parent('.metrica')
      .find('.metrica__valor');
  cartao('Produtos').should('have.text', String(produtos));
  cartao('Categorias').should('have.text', String(categorias));
  cartao('Valor em estoque').should('have.text', MOEDA.format(valor));
});

// ------------------------------------------------------------------ pela API ---
// Usam o mesmo cookie de sessão do navegador (o Vite faz proxy de /api).

const corpoCadastro = ({ usuario, empresa }) => ({
  empresa: {
    razao_social: empresa.razao_social,
    cnpj: empresa.cnpj,
    cep: empresa.cep || null,
    inscricao: empresa.inscricao || null,
    telefone_empresa: empresa.telefone_empresa || null,
  },
  usuario: {
    nome: usuario.nome,
    email: usuario.email,
    senha: usuario.senha,
    telefone: usuario.telefone || null,
  },
});

Cypress.Commands.add('apiCadastrar', (conta) =>
  cy.request('POST', '/api/auth/cadastro', corpoCadastro(conta)),
);

Cypress.Commands.add('apiEntrar', (email, senha) =>
  cy.request('POST', '/api/auth/login', { email, senha }),
);

Cypress.Commands.add('apiSair', () => cy.request('POST', '/api/auth/logout'));

Cypress.Commands.add('apiCriarCategoria', (nome) =>
  cy.request('POST', '/api/categorias', { nome }).its('body.dados'),
);

Cypress.Commands.add('apiCriarProduto', (produto) =>
  cy.request('POST', '/api/produtos', produto).its('body.dados'),
);

Cypress.Commands.add('apiCriarParceiro', (parceiro) =>
  cy.request('POST', '/api/parceiros', parceiro).its('body.dados'),
);

Cypress.Commands.add('apiCriarTitulo', (titulo) =>
  cy.request('POST', '/api/titulos', titulo).its('body.dados'),
);

Cypress.Commands.add('apiAbrirCaixa', (valorAbertura = '0.00') =>
  cy.request('POST', '/api/caixas', { valor_abertura: valorAbertura }).its('body.dados'),
);

// ------------------------------------------------------------ apoio de tela ---

/** Fecha o modal aberto pelo X (não usa Escape para funcionar com modal aninhado). */
Cypress.Commands.add('fecharDialogo', () => {
  cy.get('[role="dialog"] button[aria-label="Fechar"]').click();
});

/** Seleciona uma opção de um `<select>` pelo texto visível (parcial). */
Cypress.Commands.add('selecionarOpcao', (seletor, texto) => {
  cy.get(seletor)
    .find('option')
    .then(($opcoes) => {
      const opcao = [...$opcoes].find((item) => item.textContent.includes(texto));
      if (!opcao) {
        throw new Error(`Opção "${texto}" não encontrada em ${seletor}`);
      }
      cy.get(seletor).select(opcao.value);
    });
});
