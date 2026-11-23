
// JORNADA COMPLETA DO USUÁRIO — um único usuário, do primeiro acesso até limpar o catálogo:
//
//   Cadastrar conta + empresa > Criar categoria > Criar produtos > Buscar > Atualizar produto
//   > Apagar produto > Alterar categoria > Apagar categoria > Sair / Entrar de novo
//
// Os `it` são ENCADEADOS de propósito (o resultado de um é a pré-condição do próximo),
// por isso `testIsolation: false` mantém a sessão e a página entre eles. Se um passo
// falhar, os seguintes também falham — comece sempre pelo primeiro vermelho.
//
// Os códigos entre parênteses (EMP-N10, PRD-N15...) apontam o caso do Plano de Testes V1.6
// que cada passo exercita.
import {
  cnpj,
  cnpjInvalido,
  mascararCnpj,
  email,
  montarUsuario,
  montarEmpresa,
} from '../../support/data';
import { preencher } from '../../support/utils';

// Sufixo único por execução: evita colisão de e-mail/CNPJ se a limpeza do banco falhar.
const sufixo = Date.now().toString(36).toUpperCase().padStart(10, '0').slice(-10);

const usuario = montarUsuario({ email: email(`jornada.${sufixo.toLowerCase()}`) });
const empresa = montarEmpresa({
  cnpj: cnpj(`JC${sufixo}`),
  cep: '50030-230',
  inscricao: 'IE-0012345-67',
  telefone_empresa: '(81) 3221-4455',
});

const CAT_A = 'Ferragens Leves';
const CAT_A_RENOMEADA = 'Ferragens e Parafusos';
const CAT_B = 'Embalagens';

const PROD_1 = {
  sku: 'PRD-1001',
  nome: 'Parafuso Sextavado M8',
  descricao: 'Parafuso aço zincado 8mm',
  unidade_estoque: 150,
  preco: '12.50',
};
const PROD_2 = { sku: 'PRD-1002', nome: 'Porca M8', unidade_estoque: 50, preco: '3.00' };
const PROD_3 = { sku: 'PRD-1003', nome: 'Arruela M8', preco: '0.00' }; // estoque em branco => 0

// ---------------------------------------------------------------- auxiliares ---

function criarCategoria(nome) {
  cy.get('.categoria-form input').clear().type(nome);
  cy.get('.categoria-form').contains('button', 'Criar categoria').click();
}

function preencherProduto(p) {
  preencher('#produto-sku', p.sku);
  if (p.categoria) cy.get('#produto-categoria').select(p.categoria);
  preencher('#produto-nome', p.nome);
  preencher('#produto-descricao', p.descricao);
  preencher(
    '#produto-estoque',
    p.unidade_estoque === undefined ? undefined : String(p.unidade_estoque),
  );
  preencher('#produto-preco', p.preco);
}

function abrirNovoProduto() {
  cy.contains('button', 'Novo produto').click();
  cy.get('[role="dialog"]').should('be.visible');
}

function abrirEdicaoProduto(nome) {
  cy.get(`button[aria-label="Editar ${nome}"]`).click();
  cy.get('[role="dialog"]').should('be.visible');
}

/** Linha da tabela (produtos ou categorias) que contém o texto. */
function linha(texto) {
  return cy.contains('tbody tr', texto);
}

const contador = () => cy.get('.contador');

// ------------------------------------------------------------------- jornada ---

describe('Jornada completa do usuário', { testIsolation: false }, () => {
  // ============================================================ 1. CONTA ===

  it('JOR-01 | A tela inicial mostra a marca e os caminhos de acesso (LOG-P01)', () => {
    cy.visit('/');
    cy.contains('h1', 'Controle seu negócio').should('be.visible');
    cy.contains('button', 'Criar conta').should('be.visible');
    cy.contains('button', 'Entrar').should('be.visible');
    cy.contains('button', 'Já tenho conta').should('be.visible');
    cy.get('.marca__folha').should('exist'); // folha canadense cinza
  });

  it('JOR-02 | Etapa 1 do cadastro valida os dados de acesso antes de avançar (LOG-N13/N14/N16)', () => {
    cy.contains('button', 'Criar conta').click();
    cy.contains('h1', 'Seus dados de acesso').should('be.visible');

    // Tudo vazio.
    cy.contains('button', 'Continuar para empresa').click();
    cy.contains('.campo__erro', 'Informe seu nome completo.');
    cy.contains('.campo__erro', 'Informe um e-mail válido.');
    cy.contains('.campo__erro', 'A senha precisa ter pelo menos 6 caracteres.');

    // E-mail sem @, senha curta e confirmação diferente.
    cy.cadastroEtapaUsuario({
      nome: usuario.nome,
      email: 'sem-arroba',
      telefone: usuario.telefone,
      senha: '123',
      confirmar: '456',
    });
    cy.contains('.campo__erro', 'Informe um e-mail válido.');
    cy.contains('.campo__erro', 'A senha precisa ter pelo menos 6 caracteres.');
    cy.contains('.campo__erro', 'As senhas não conferem.');
    cy.contains('h1', 'Seus dados de acesso').should('be.visible'); // não avançou

    // Dados corretos: avança para a empresa.
    cy.cadastroEtapaUsuario(usuario);
    cy.contains('h1', 'Dados da empresa').should('be.visible');
  });

  it('JOR-03 | Etapa 2 valida a empresa, recusa CNPJ inválido e "Voltar" preserva os dados (EMP-N02/N06/N16)', () => {
    // Campos obrigatórios vazios.
    cy.contains('button', 'Criar conta e empresa').click();
    cy.contains('.campo__erro', 'Informe a razão social da empresa.');
    cy.contains('.campo__erro', 'O CNPJ deve ter 14 caracteres.');

    // CNPJ curto e CEP incompleto.
    preencher('#cad-razao', empresa.razao_social);
    preencher('#cad-cnpj', 'abc');
    preencher('#cad-cep', '123');
    cy.contains('button', 'Criar conta e empresa').click();
    cy.contains('.campo__erro', 'O CNPJ deve ter 14 caracteres.');
    cy.contains('.campo__erro', 'O CEP deve ter 8 dígitos.');

    // CNPJ com 14 caracteres, mas dígito verificador errado: quem recusa é a API.
    cy.cadastroEtapaEmpresa({
      ...empresa,
      cnpj: mascararCnpj(cnpjInvalido(`JC${sufixo}`)),
    });
    cy.contains('.alerta', 'dígitos verificadores incorretos');
    cy.contains('h1', 'Dados da empresa').should('be.visible'); // continua na etapa 2

    // "Voltar" mantém o que foi digitado nas duas etapas.
    cy.contains('button', /^Voltar$/).click();
    cy.contains('h1', 'Seus dados de acesso').should('be.visible');
    cy.get('#cad-nome').should('have.value', usuario.nome);
    cy.get('#cad-email').should('have.value', usuario.email);
    cy.contains('button', 'Continuar para empresa').click();
    cy.get('#cad-razao').should('have.value', empresa.razao_social);
  });

  it('JOR-04 | Cadastro com CNPJ válido (com máscara) cria conta + empresa e já entra no sistema (EMP-P06/P09)', () => {
    cy.cadastroEtapaEmpresa({ ...empresa, cnpj: mascararCnpj(empresa.cnpj) });

    cy.contains('h2', 'Olá, Marina!').should('be.visible');
    cy.contains('h1', 'Início').should('be.visible');
    cy.get('.app-topo__dados').should('contain', empresa.razao_social);
    cy.get('.wip-painel').should('contain', '(WORK IN PROGRESS)');
    cy.get('svg.marca__folha').should('exist');

    // Módulos que ainda não existem aparecem desabilitados na sidebar.
    cy.get('button.sidebar__item--futuro')
      .should('have.length', 1)
      .each(($botao) => expect($botao).to.be.disabled);
  });

  it('JOR-05 | Dashboard de uma empresa nova está zerado', () => {
    cy.conferirResumo({ produtos: 0, categorias: 0, valor: 0 });
  });

  // ======================================================== 2. CATEGORIAS ===

  it('JOR-06 | Sem categorias, não dá para cadastrar produto e o sistema leva o usuário a criá-las', () => {
    cy.menu('Produtos');
    cy.contains('h3', 'Nenhum produto por aqui').should('be.visible');

    cy.contains('.estado-vazio button', 'Cadastrar produto').click();
    cy.get('[role="dialog"]').should('contain', 'Cadastre uma categoria antes de criar produtos.');
    cy.contains('[role="dialog"] button', 'Criar produto').should('be.disabled');

    cy.contains('[role="dialog"] button', 'Criar categoria').click();
    cy.get('[role="dialog"]').should('not.exist');
    cy.contains('h3', 'Nova categoria').should('be.visible');
  });

  it('JOR-07 | Criar categorias: valida vazio e duplicidade e mantém a lista em ordem alfabética (CAT-P01, CAT-N01, CAT-N05)', () => {
    // Nome vazio.
    cy.get('.categoria-form').contains('button', 'Criar categoria').click();
    cy.contains('.alerta', 'Informe o nome da categoria.');

    // Primeira categoria.
    criarCategoria(CAT_A);
    cy.contains('.alerta--sucesso', 'Categoria criada com sucesso.');
    linha(CAT_A).should('contain', '0 produtos');
    contador().should('contain', '1 categoria');

    // Mesmo nome, só muda a caixa: o banco ignora maiúsculas/acentos.
    criarCategoria(CAT_A.toUpperCase());
    cy.contains('.alerta', 'Já existe uma categoria com este nome nesta empresa.');
    contador().should('contain', '1 categoria');

    // Segunda categoria; "Embalagens" vem antes de "Ferragens Leves".
    criarCategoria(CAT_B);
    cy.contains('.alerta--sucesso', 'Categoria criada com sucesso.');
    contador().should('contain', '2 categorias');
    cy.get('tbody tr').first().should('contain', CAT_B);
  });

  // ========================================================== 3. PRODUTOS ===

  it('JOR-08 | Criar produtos: completo, sem estoque (assume 0) e SKU repetido (PRD-P01/P02/P03, PRD-N15/N16)', () => {
    cy.menu('Produtos');

    // Produto completo.
    abrirNovoProduto();
    preencherProduto({ ...PROD_1, categoria: CAT_A });
    cy.contains('[role="dialog"] button', 'Criar produto').click();
    cy.get('[role="dialog"]').should('not.exist');
    cy.contains('.alerta--sucesso', 'Produto criado com sucesso.');
    linha(PROD_1.sku).within(() => {
      cy.contains(PROD_1.nome);
      cy.contains(PROD_1.descricao);
      cy.contains('.badge--categoria', CAT_A);
      cy.contains('150 un.');
      cy.contains(/R\$\s*12,50/);
    });

    // SKU repetido (com outra caixa): o modal continua aberto com o erro.
    abrirNovoProduto();
    preencherProduto({ sku: 'prd-1001', nome: 'Duplicado', preco: '1.00', categoria: CAT_A });
    cy.contains('[role="dialog"] button', 'Criar produto').click();
    cy.get('[role="dialog"]').should('contain', 'Já existe um produto com este SKU nesta empresa.');
    cy.contains('[role="dialog"] button', 'Cancelar').click();
    cy.get('[role="dialog"]').should('not.exist');

    // Segundo produto.
    abrirNovoProduto();
    preencherProduto({ ...PROD_2, categoria: CAT_A });
    cy.contains('[role="dialog"] button', 'Criar produto').click();
    cy.get('[role="dialog"]').should('not.exist');
    linha(PROD_2.sku).should('contain', '50 un.');

    // Terceiro: estoque em branco vira 0 e preço 0,00 é aceito.
    abrirNovoProduto();
    preencherProduto({ ...PROD_3, categoria: CAT_A, unidade_estoque: '' });
    cy.contains('[role="dialog"] button', 'Criar produto').click();
    cy.get('[role="dialog"]').should('not.exist');
    linha(PROD_3.sku).within(() => {
      cy.contains('0 un.');
      cy.contains(/R\$\s*0,00/);
    });

    contador().should('contain', '3 produtos');
  });

  it('JOR-09 | Buscar produtos por nome e por SKU', () => {
    cy.get('input[aria-label="Buscar produtos"]').type('Porca');
    contador().should('contain', '1 produto');
    linha(PROD_2.sku).should('exist');
    cy.contains('tbody tr', PROD_1.sku).should('not.exist');

    cy.get('input[aria-label="Buscar produtos"]').clear().type(PROD_1.sku);
    contador().should('contain', '1 produto');
    linha(PROD_1.sku).should('exist');

    cy.get('input[aria-label="Buscar produtos"]').clear().type('nao-existe-xyz');
    cy.contains('Nenhum resultado para essa busca.').should('be.visible');

    cy.get('input[aria-label="Buscar produtos"]').clear();
    contador().should('contain', '3 produtos');
  });

  it('JOR-10 | Dashboard reflete os 3 produtos, as 2 categorias e o valor em estoque (150×12,50 + 50×3,00)', () => {
    cy.conferirResumo({ produtos: 3, categorias: 2, valor: 2025 });
  });

  // ================================================ 4. ATUALIZAR PRODUTO ===

  it('JOR-11 | Cancelar a edição não altera o produto', () => {
    cy.menu('Produtos');
    abrirEdicaoProduto(PROD_1.nome);
    preencher('#produto-nome', 'NÃO DEVE SER SALVO');
    cy.contains('[role="dialog"] button', 'Cancelar').click();
    cy.get('[role="dialog"]').should('not.exist');
    linha(PROD_1.sku).should('contain', PROD_1.nome);
    cy.contains('NÃO DEVE SER SALVO').should('not.exist');
  });

  it('JOR-12 | Atualizar produto: SKU de outro produto é recusado; depois nome, descrição, SKU, preço e estoque são salvos (PRD-P09/P10/P11, PRD-N17)', () => {
    abrirEdicaoProduto(PROD_1.nome);

    // 1) SKU que já pertence a outro produto da empresa.
    preencher('#produto-sku', PROD_2.sku);
    cy.contains('[role="dialog"] button', 'Salvar alterações').click();
    cy.get('[role="dialog"]').should('contain', 'Já existe um produto com este SKU nesta empresa.');

    // 2) Corrige e salva tudo de uma vez.
    preencherProduto({
      sku: 'PRD-1001-V2',
      nome: 'Parafuso Sextavado M8 Zincado',
      descricao: 'Parafuso aço zincado 8mm — lote novo',
      unidade_estoque: 100,
      preco: '15.75',
    });
    cy.contains('[role="dialog"] button', 'Salvar alterações').click();
    cy.get('[role="dialog"]').should('not.exist');
    cy.contains('.alerta--sucesso', 'Produto atualizado com sucesso.');

    linha('PRD-1001-V2').within(() => {
      cy.contains('Parafuso Sextavado M8 Zincado');
      cy.contains('lote novo');
      cy.contains('100 un.');
      cy.contains(/R\$\s*15,75/);
    });
    contador().should('contain', '3 produtos'); // editar não cria outro registro
  });

  it('JOR-13 | Mover produto para outra categoria (PRD-P12)', () => {
    abrirEdicaoProduto(PROD_2.nome);
    cy.get('#produto-categoria').select(CAT_B);
    cy.contains('[role="dialog"] button', 'Salvar alterações').click();
    cy.get('[role="dialog"]').should('not.exist');
    linha(PROD_2.sku).should('contain', CAT_B);
  });

  it('JOR-14 | Dashboard recalcula o valor em estoque após a edição (100×15,75 + 50×3,00)', () => {
    cy.conferirResumo({ produtos: 3, categorias: 2, valor: 1725 });
  });

  // ============================================== 5. CATEGORIAS × PRODUTOS ===

  it('JOR-15 | Categorias com produtos mostram o vínculo e não podem ser excluídas', () => {
    cy.menu('Categorias');
    cy.contains('tbody tr', CAT_A).should('contain', '2 produtos'); // PRD-1001-V2 e PRD-1003
    cy.contains('tbody tr', CAT_B).should('contain', '1 produto'); // PRD-1002

    cy.get(`button[aria-label="Excluir ${CAT_A}"]`).should('be.disabled');
    cy.get(`button[aria-label="Excluir ${CAT_B}"]`).should('be.disabled');
  });

  // ============================================================ 6. APAGAR ===

  it('JOR-16 | Apagar produto: cancelar a confirmação mantém; confirmar remove (PRD-N22, PRD-P13)', () => {
    cy.menu('Produtos');

    // Intercepta as três confirmações: cancela a primeira e aceita as duas seguintes.
    cy.window().then((win) => {
      cy.stub(win, 'confirm')
        .onCall(0).returns(false)
        .onCall(1).returns(true)
        .onCall(2).returns(true);
    });

    // Cancela a confirmação: nada acontece.
    cy.get(`button[aria-label="Excluir ${PROD_3.nome}"]`).click();
    linha(PROD_3.sku).should('exist');
    contador().should('contain', '3 produtos');

    // Confirma: o produto some e o contador diminui.
    cy.get(`button[aria-label="Excluir ${PROD_3.nome}"]`).click();
    cy.contains('.alerta--sucesso', 'Produto excluído com sucesso.');
    cy.contains('tbody tr', PROD_3.sku).should('not.exist');
    contador().should('contain', '2 produtos');

    // Apaga também a Porca M8 (a categoria "Embalagens" fica sem produtos).
    cy.get(`button[aria-label="Excluir ${PROD_2.nome}"]`).click();
    cy.contains('tbody tr', PROD_2.sku).should('not.exist');
    contador().should('contain', '1 produto');
  });

  it('JOR-17 | Dashboard após apagar produtos (só sobra 100×15,75)', () => {
    cy.conferirResumo({ produtos: 1, categorias: 2, valor: 1575 });
  });

  // ======================================================= 7. ALTERAR CATEGORIA ===

  it('JOR-18 | Renomear categoria: o produto continua vinculado (CAT-P04, CAT-P05)', () => {
    cy.menu('Categorias');
    cy.get(`button[aria-label="Renomear ${CAT_A}"]`).click();
    cy.get('#categoria-nome').should('have.value', CAT_A);
    preencher('#categoria-nome', CAT_A_RENOMEADA);
    cy.contains('[role="dialog"] button', 'Salvar nome').click();
    cy.get('[role="dialog"]').should('not.exist');
    cy.contains('.alerta--sucesso', 'Categoria renomeada com sucesso.');
    cy.contains('tbody tr', CAT_A_RENOMEADA).should('contain', '1 produto');

    cy.menu('Produtos');
    linha('PRD-1001-V2').find('.badge--categoria').should('have.text', CAT_A_RENOMEADA);
  });

  it('JOR-19 | Renomear para um nome já usado é recusado; vazio também (CAT-N06, CAT-N07)', () => {
    cy.menu('Categorias');
    cy.get(`button[aria-label="Renomear ${CAT_B}"]`).click();

    preencher('#categoria-nome', CAT_A_RENOMEADA.toUpperCase());
    cy.contains('[role="dialog"] button', 'Salvar nome').click();
    cy.get('[role="dialog"]').should('contain', 'Já existe uma categoria com este nome nesta empresa.');

    preencher('#categoria-nome', '   ');
    cy.contains('[role="dialog"] button', 'Salvar nome').click();
    cy.get('[role="dialog"]').should('contain', 'Informe o novo nome.');

    cy.contains('[role="dialog"] button', 'Cancelar').click();
    cy.get('[role="dialog"]').should('not.exist');
    cy.contains('tbody tr', CAT_B).should('exist'); // nome original intacto
  });

  // ======================================================= 8. APAGAR CATEGORIA ===

  it('JOR-20 | Apagar categoria sem produtos: cancelar mantém; confirmar remove', () => {
    // Intercepta as duas confirmações: cancela a primeira e aceita a segunda.
    cy.window().then((win) => {
      cy.stub(win, 'confirm')
        .onCall(0).returns(false)
        .onCall(1).returns(true);
    });

    cy.get(`button[aria-label="Excluir ${CAT_B}"]`).click();
    cy.contains('tbody tr', CAT_B).should('exist');
    contador().should('contain', '2 categorias');

    cy.get(`button[aria-label="Excluir ${CAT_B}"]`).click();
    cy.contains('.alerta--sucesso', 'Categoria excluída com sucesso.');
    cy.contains('tbody tr', CAT_B).should('not.exist');
    contador().should('contain', '1 categoria');
  });

  it('JOR-21 | A última categoria só é liberada depois de apagar o último produto; o catálogo termina vazio', () => {
    // Ainda tem o PRD-1001-V2: botão travado.
    cy.get(`button[aria-label="Excluir ${CAT_A_RENOMEADA}"]`).should('be.disabled');

    cy.menu('Produtos');

    // Intercepta as duas confirmações e aceita ambas.
    cy.window().then((win) => {
      cy.stub(win, 'confirm')
        .onCall(0).returns(true)
        .onCall(1).returns(true);
    });

    cy.get('button[aria-label="Excluir Parafuso Sextavado M8 Zincado"]').click();
    cy.contains('h3', 'Nenhum produto por aqui').should('be.visible');

    cy.menu('Categorias');
    cy.contains('tbody tr', CAT_A_RENOMEADA).should('contain', '0 produtos');
    cy.get(`button[aria-label="Excluir ${CAT_A_RENOMEADA}"]`).should('be.enabled');
    cy.get(`button[aria-label="Excluir ${CAT_A_RENOMEADA}"]`).click();
    cy.contains('h3', 'Nenhuma categoria cadastrada').should('be.visible');

    cy.conferirResumo({ produtos: 0, categorias: 0, valor: 0 });
  });

  it('JOR-22 | Produto que já participou de uma operação não pode ser apagado (PRD-N21)', () => {
    // Massa pela API; a operação é criada direto no banco (o módulo ainda não tem tela).
    cy.apiCriarCategoria('Categoria Bloqueada').then((categoria) => {
      cy.apiCriarProduto({
        sku: 'BLQ-001',
        nome: 'Produto Em Operação',
        id_categoria: categoria.id_categoria,
        unidade_estoque: 3,
        preco: '9.90',
      });
    });
    cy.task('db:vincularProdutoEmOperacao', { sku: 'BLQ-001', email: usuario.email });

    cy.reload(); // a API foi chamada fora da tela: limpa o cache em memória do front
    cy.menu('Produtos');
    cy.get('button[aria-label="Excluir Produto Em Operação"]').click(); // confirm: aceito
    cy.contains('.alerta', 'Não é possível apagar o produto: existem registros vinculados a ele.');
    linha('BLQ-001').should('exist');

    cy.menu('Categorias');
    cy.get('button[aria-label="Excluir Categoria Bloqueada"]').should('be.disabled');
  });

  // ============================================================ 9. SESSÃO ===

  it('JOR-23 | Recarregar a página mantém o usuário logado', () => {
    cy.reload();
    cy.contains('h2', 'Olá, Marina!').should('be.visible');
  });

  it('JOR-24 | Sair encerra a sessão e recarregar não traz o usuário de volta', () => {
    cy.sairPelaTela();
    cy.reload();
    cy.contains('h1', 'Controle seu negócio').should('be.visible');
  });

  it('JOR-25 | Login recusa campos vazios, senha errada e e-mail inexistente (LOG-N03/N04/N05)', () => {
    cy.contains('button', 'Entrar').click();

    cy.get('form button[type="submit"]').click();
    cy.contains('.alerta', 'Informe e-mail e senha.');

    preencher('#login-email', usuario.email);
    preencher('#login-senha', 'SenhaErrada#1');
    cy.get('form button[type="submit"]').click();
    cy.contains('.alerta', 'E-mail ou senha incorretos.');

    preencher('#login-email', email('nao.existe.xyz'));
    preencher('#login-senha', usuario.senha);
    cy.get('form button[type="submit"]').click();
    cy.contains('.alerta', 'E-mail ou senha incorretos.'); // mesma mensagem: não revela se o e-mail existe
    cy.contains('h1', 'Entrar no Byte Estoque').should('be.visible');
  });

  it('JOR-26 | Login com e-mail em MAIÚSCULAS funciona e os dados da empresa continuam lá (LOG-P10)', () => {
    preencher('#login-email', usuario.email.toUpperCase());
    preencher('#login-senha', usuario.senha);
    cy.get('form button[type="submit"]').click();

    cy.contains('h2', 'Olá, Marina!').should('be.visible');
    cy.get('.app-topo__dados').should('contain', empresa.razao_social);
    cy.menu('Produtos');
    linha('BLQ-001').should('exist'); // o que ficou do passo JOR-22
  });

  it('JOR-27 | A senha não fica em texto no banco e o cadastro cria um Administrador (BDD-P08)', () => {
    cy.task('db:usuario', { email: usuario.email }).then((linha) => {
      expect(linha, 'usuário gravado').to.not.equal(null);
      expect(linha.cargo).to.equal('Administrador');
      expect(linha.hash_senha).to.not.equal(usuario.senha);
      expect(linha.hash_senha).to.not.contain(usuario.senha);
      expect(linha.email).to.equal(usuario.email.toLowerCase());
    });
  });

  // ================================================ 10. CADASTROS REPETIDOS ===

  it('JOR-28 | Novo cadastro com e-mail já existente é recusado e volta para a etapa do usuário (LOG-N10/N11)', () => {
    cy.sairPelaTela();
    cy.contains('button', 'Criar conta').click();

    cy.cadastroEtapaUsuario({ ...usuario, email: usuario.email.toUpperCase() });
    cy.cadastroEtapaEmpresa({
      ...empresa,
      razao_social: 'Outra Empresa Ltda',
      cnpj: cnpj(`JD${sufixo}`),
    });

    cy.contains('.alerta', 'Já existe um usuário cadastrado com este e-mail.');
    cy.contains('h1', 'Seus dados de acesso').should('be.visible');
  });

  it('JOR-29 | Novo cadastro com CNPJ já existente (mesmo digitado com máscara) é recusado e volta para a etapa da empresa (EMP-N10/N12)', () => {
    cy.contains('button', 'Voltar para o início').click();
    cy.contains('button', 'Criar conta').click();

    cy.cadastroEtapaUsuario({ ...usuario, email: email(`outro.${sufixo.toLowerCase()}`) });
    cy.cadastroEtapaEmpresa({ ...empresa, cnpj: mascararCnpj(empresa.cnpj).toLowerCase() });

    cy.contains('.alerta', 'Já existe uma empresa cadastrada com este CNPJ.');
    cy.contains('h1', 'Dados da empresa').should('be.visible');

    // Nada foi criado pelos dois cadastros recusados.
    cy.task('db:usuario', { email: email(`outro.${sufixo.toLowerCase()}`) }).should('equal', null);
  });

  // ================================================== 11. MÓDULOS NOVOS ===
  // A partir daqui a jornada cobre Parceiros, Operações, Financeiro e Equipe,
  // integrando estoque, títulos, caixa, baixa e usuários na mesma conta.

  const FUNCIONARIO = {
    nome: 'Funcionário Jornada',
    email: email(`func.jornada.${sufixo.toLowerCase()}`),
    senha: 'Func#123',
  };
  const PARCEIRO = {
    nome: 'Cliente Jornada',
    email: email(`cliente.jornada.${sufixo.toLowerCase()}`),
  };
  const CATEGORIA_OPE = 'Operações E2E';
  const PRODUTO_OPE = {
    sku: 'E2E-OPE-001',
    nome: 'Produto da Operação',
    preco: '20.00',
  };

  it('JOR-30 | Volta ao início e entra com a conta dona', () => {
    cy.contains('button', 'Voltar para o início').click();
    cy.entrarPelaTela(usuario.email, usuario.senha);
    cy.contains('h2', 'Olá, Marina!').should('be.visible');
  });

  it('JOR-31 | Cria categoria e produto que serão movimentados pela operação', () => {
    cy.menu('Categorias');
    criarCategoria(CATEGORIA_OPE);
    cy.contains('.alerta--sucesso', 'Categoria criada com sucesso.');

    cy.menu('Produtos');
    abrirNovoProduto();
    cy.get('#produto-categoria option').contains(CATEGORIA_OPE).should('exist');
    preencherProduto({
      ...PRODUTO_OPE,
      categoria: CATEGORIA_OPE,
      descricao: 'Produto usado na jornada de operações',
      unidade_estoque: 5,
    });
    cy.get('#produto-categoria').select(CATEGORIA_OPE);
    cy.contains('[role="dialog"] button', 'Criar produto').click();
    cy.get('[role="dialog"]').should('not.exist');
    linha(PRODUTO_OPE.sku).within(() => {
      cy.contains(PRODUTO_OPE.nome);
      cy.contains('5 un.');
      cy.contains(/R\$\s*20,00/);
    });
  });

  it('JOR-32 | Cadastra parceiro e registra a interação de compra', () => {
    cy.menu('Parceiros');
    cy.contains('button', 'Inserir parceiro novo').click();
    preencher('#parceiro-nome', PARCEIRO.nome);
    preencher('#parceiro-email', PARCEIRO.email);
    cy.contains('[role="dialog"] button', 'Salvar parceiro').click();

    cy.get('[role="dialog"]').should('contain', PARCEIRO.nome);
    cy.contains('[role="dialog"] button', 'Registrar interação').click();
    preencher('#interacao-canal', 'Compra');
    preencher('#interacao-descricao', 'Compra combinada para a jornada completa');
    cy.contains('[role="dialog"] button', 'Salvar interação').click();
    cy.get('[role="dialog"]').should(
      'contain',
      'Compra combinada para a jornada completa',
    );
    cy.fecharDialogo();
  });

  it('JOR-33 | Registra venda de 2 unidades vinculada ao parceiro, em 2 parcelas', () => {
    cy.menu('Operações');
    cy.contains('button', 'Nova operação').click();
    cy.get('#operacao-parceiro option').contains(PARCEIRO.nome).should('exist');
    cy.get('#item-produto-0 option').contains(PRODUTO_OPE.sku).should('exist');

    cy.get('#operacao-tipo').select('venda');
    cy.selecionarOpcao('#operacao-parceiro', PARCEIRO.nome);
    cy.get('#operacao-parcelas').clear().type('2');
    cy.selecionarOpcao('#item-produto-0', PRODUTO_OPE.sku);
    cy.get('#item-quantidade-0').clear().type('2');
    cy.get('#item-valor-0').clear().type(PRODUTO_OPE.preco);
    cy.contains('[role="dialog"] button', 'Registrar operação').click();

    cy.contains('.alerta--sucesso', 'Operação registrada e título financeiro gerado.');
    cy.contains('tbody tr', PARCEIRO.nome).within(() => {
      cy.contains('Venda');
      cy.contains('2x (2x)');
    });
  });

  it('JOR-34 | Estoque do produto cai de 5 para 3 e o dashboard acompanha', () => {
    cy.menu('Produtos');
    linha(PRODUTO_OPE.sku).should('contain', '3 un.');
  });

  it('JOR-35 | Abre caixa, registra movimento, dá baixa em título e fecha o caixa', () => {
    cy.menu('Financeiro');
    cy.get('#aba-caixas').click();
    cy.contains('button', 'Abrir caixa').click();
    preencher('#caixa-abertura', '100,00');
    cy.get('[role="dialog"]').contains('button', 'Abrir caixa').click();
    cy.contains('.alerta--sucesso', 'Caixa aberto com sucesso.');
    cy.contains('h3', /Caixa #\d+/).should('be.visible');

    cy.contains('button', 'Registrar suprimento/sangria').click();
    cy.get('#mov-tipo').select('suprimento');
    preencher('#mov-valor', '10,00');
    preencher('#mov-descricao', 'Reforço de troco da jornada');
    cy.get('[role="dialog"]').contains('button', 'Salvar').click();
    cy.contains('.alerta--sucesso', 'Suprimento registrado').should('be.visible');

    cy.get('#aba-baixas').click();
    cy.contains('button', 'Registrar baixa manualmente').click();
    cy.get('#baixa-titulo option').should(($opcoes) => {
      expect($opcoes.length).to.be.greaterThan(1);
    });
    cy.selecionarOpcao('#baixa-titulo', 'Venda #');
    cy.get('#baixa-forma').select('dinheiro');
    cy.contains('button', 'Usar o saldo total').click();
    cy.contains('[role="dialog"] button', 'Salvar & registrar baixa').click();
    cy.contains('.alerta--sucesso', 'Baixa registrada').should('be.visible');

    cy.get('#aba-caixas').click();
    cy.contains('button', 'Fechar caixa').click();
    // Abertura 100 + suprimento 10 + recebimento 20 = 130.
    preencher('#caixa-contado', '130,00');
    cy.get('[role="dialog"]').contains('button', 'Confirmar fechamento').click();
    cy.contains('.alerta--sucesso', 'Caixa fechado com sucesso.').should('be.visible');

    cy.menu('Início');
    cy.contains('.metrica__rotulo', 'Dinheiro')
      .parent('.metrica')
      .find('.metrica__valor')
      .should('contain.text', '130,00');
  });

  it('JOR-36 | Cria funcionário e confirma que ele acessa a mesma empresa', () => {
    cy.menu('Equipe');
    cy.contains('button', 'Novo funcionário').click();
    preencher('#usuario-nome', FUNCIONARIO.nome);
    preencher('#usuario-email', FUNCIONARIO.email);
    preencher('#usuario-telefone', '81999990000');
    preencher('#usuario-senha', FUNCIONARIO.senha);
    cy.contains('[role="dialog"] button', 'Criar funcionário').click();
    cy.contains('tbody tr', FUNCIONARIO.nome).should('be.visible');
    cy.contains('tbody tr', usuario.nome).should('contain', 'Dono');

    cy.sairPelaTela();
    cy.entrarPelaTela(FUNCIONARIO.email, FUNCIONARIO.senha);
    cy.contains('h2', 'Olá, Funcionário!').should('be.visible');
    cy.menu('Equipe');
    cy.contains('tbody tr', usuario.nome).should('contain', 'Dono');
    cy.contains('tbody tr', usuario.nome)
      .find('button[aria-label^="Excluir"]')
      .should('not.exist');
  });

  it('JOR-37 | Dono volta, apaga o funcionário e encerra a jornada', () => {
    cy.sairPelaTela();
    cy.entrarPelaTela(usuario.email, usuario.senha);
    cy.menu('Equipe');
    cy.window().then((win) => cy.stub(win, 'confirm').returns(true));
    cy.get(`button[aria-label="Excluir ${FUNCIONARIO.nome}"]`).click();
    cy.contains('.alerta--sucesso', 'Funcionário excluído com sucesso.').should(
      'be.visible',
    );
    cy.contains('tbody tr', FUNCIONARIO.nome).should('not.exist');
    cy.sairPelaTela();
  });
});
