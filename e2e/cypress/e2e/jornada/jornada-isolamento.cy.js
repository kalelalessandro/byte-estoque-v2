// JORNADA DE ISOLAMENTO — duas empresas no mesmo sistema (multi-tenant).
//
//   Empresa A (criada pela API) tem categoria e produto  >  Empresa B se cadastra pela tela
//   > B não enxerga nada de A > B reutiliza os mesmos nomes/SKU > B tenta mexer em A > sem login
//
// Casos do Plano de Testes V1.6 exercitados: SEG-P01, SEG-N01, SEG-N02, SEG-N09, SEG-N11,
// SEG-N12, CAT-P03, PRD-P07. `testIsolation: false` pelo mesmo motivo da jornada completa
// (os passos são encadeados).
import { cnpj, email, montarUsuario, montarEmpresa } from '../../support/data';

const sufixo = Date.now().toString(36).toUpperCase().padStart(10, '0').slice(-10);

const contaA = {
  usuario: montarUsuario({ nome: 'Alice Empresa A', email: email(`iso.a.${sufixo.toLowerCase()}`) }),
  empresa: montarEmpresa({ razao_social: 'Alfa Comercial Ltda', cnpj: cnpj(`JA${sufixo}`) }),
};
const contaB = {
  usuario: montarUsuario({ nome: 'Beatriz Empresa B', email: email(`iso.b.${sufixo.toLowerCase()}`) }),
  empresa: montarEmpresa({ razao_social: 'Beta Distribuidora Ltda', cnpj: cnpj(`JB${sufixo}`) }),
};

const CATEGORIA = 'Catálogo Compartilhado';
const SKU = 'ISO-001';

// Ids da empresa A, guardados para B tentar usá-los.
let idCategoriaA;
let idProdutoA;

const semFalhar = (opcoes) => ({ failOnStatusCode: false, ...opcoes });

describe('Jornada de isolamento entre empresas', { testIsolation: false }, () => {
  it('ISO-01 | Empresa A é criada pela API, com 1 categoria e 1 produto', () => {
    cy.apiCadastrar(contaA).its('status').should('eq', 201);
    cy.apiEntrar(contaA.usuario.email, contaA.usuario.senha).its('status').should('eq', 200);

    cy.apiCriarCategoria(CATEGORIA).then((categoria) => {
      idCategoriaA = categoria.id_categoria;
      cy.apiCriarProduto({
        sku: SKU,
        nome: 'Produto da Empresa A',
        id_categoria: idCategoriaA,
        unidade_estoque: 5,
        preco: '10.00',
      }).then((produto) => {
        idProdutoA = produto.id_produto;
      });
    });
    cy.apiSair();
  });

  it('ISO-02 | Empresa B se cadastra pela tela e começa com tudo vazio (SEG-P01)', () => {
    cy.cadastrarPelaTela(contaB);
    cy.get('.app-topo__dados').should('contain', contaB.empresa.razao_social);
    cy.conferirResumo({ produtos: 0, categorias: 0, valor: 0 });

    cy.menu('Produtos');
    cy.contains('h3', 'Nenhum produto por aqui').should('be.visible');
    cy.contains(SKU).should('not.exist');

    cy.menu('Categorias');
    cy.contains('h3', 'Nenhuma categoria cadastrada').should('be.visible');
    cy.contains(CATEGORIA).should('not.exist');
  });

  it('ISO-03 | B pode usar o mesmo nome de categoria e o mesmo SKU que A (CAT-P03, PRD-P07)', () => {
    cy.get('.categoria-form input').type(CATEGORIA);
    cy.get('.categoria-form').contains('button', 'Criar categoria').click();
    cy.contains('.alerta--sucesso', 'Categoria criada com sucesso.');

    cy.menu('Produtos');
    cy.contains('button', 'Novo produto').click();
    cy.get('#produto-sku').type(SKU);
    cy.get('#produto-categoria').select(CATEGORIA);
    cy.get('#produto-nome').type('Produto da Empresa B');
    cy.get('#produto-estoque').clear().type('20');
    cy.get('#produto-preco').type('99.90');
    cy.contains('[role="dialog"] button', 'Criar produto').click();

    cy.contains('.alerta--sucesso', 'Produto criado com sucesso.');
    cy.contains('tbody tr', SKU).should('contain', 'Produto da Empresa B');
    cy.contains('Produto da Empresa A').should('not.exist');
    cy.conferirResumo({ produtos: 1, categorias: 1, valor: 1998 }); // 20 × 99,90
  });

  it('ISO-04 | B não consegue ler, alterar nem apagar o produto de A por id direto (SEG-N01)', () => {
    cy.request(semFalhar({ url: `/api/produtos/${idProdutoA}` })).its('status').should('eq', 404);

    cy.request(
      semFalhar({ method: 'PATCH', url: `/api/produtos/${idProdutoA}`, body: { preco: '1.00' } }),
    )
      .its('status')
      .should('eq', 404);

    cy.request(semFalhar({ method: 'DELETE', url: `/api/produtos/${idProdutoA}` }))
      .its('status')
      .should('eq', 404);

    // A listagem de B só traz o produto de B.
    cy.request('/api/produtos').its('body.dados').then((dados) => {
      expect(dados.total).to.eq(1);
      expect(dados.produtos[0].id_produto).to.not.eq(idProdutoA);
      expect(dados.produtos[0].nome).to.eq('Produto da Empresa B');
    });
  });

  it('ISO-05 | B não consegue usar categoria de A nem forjar o id_empresa (SEG-N02, SEG-N09)', () => {
    cy.request(
      semFalhar({
        method: 'POST',
        url: '/api/produtos',
        body: { sku: 'ISO-FORJADO', nome: 'X', id_categoria: idCategoriaA, preco: '1.00' },
      }),
    )
      .its('status')
      .should('eq', 422);

    cy.request(
      semFalhar({
        method: 'POST',
        url: '/api/produtos',
        body: {
          sku: 'ISO-EMPRESA',
          nome: 'X',
          id_empresa: 1,
          id_categoria: idCategoriaA,
          preco: '1.00',
        },
      }),
    ).then((resposta) => {
      expect(resposta.status).to.eq(422);
      expect(resposta.body.campos).to.have.property('id_empresa');
    });

    cy.request(semFalhar({ method: 'PATCH', url: `/api/categorias/${idCategoriaA}`, body: { nome: 'Invadida' } }))
      .its('status')
      .should('eq', 404);
    cy.request(semFalhar({ method: 'DELETE', url: `/api/categorias/${idCategoriaA}` }))
      .its('status')
      .should('eq', 404);
  });

  it('ISO-06 | As respostas da API nunca expõem o hash da senha (SEG-N12)', () => {
    cy.request('/api/auth/me').its('body').then((corpo) => {
      expect(JSON.stringify(corpo)).to.not.contain('hash_senha');
      expect(JSON.stringify(corpo)).to.not.contain(contaB.usuario.senha);
    });
  });

  it('ISO-07 | Sem sessão, as rotas protegidas respondem 401 e a tela volta para o início (SEG-N11)', () => {
    cy.sairPelaTela();

    ['/api/produtos', '/api/categorias', '/api/dashboard/resumo', '/api/auth/me'].forEach((rota) => {
      cy.request(semFalhar({ url: rota })).then((resposta) => {
        expect(resposta.status, rota).to.eq(401);
        expect(resposta.body).to.not.have.property('dados');
      });
    });

    cy.reload();
    cy.contains('h1', 'Controle seu negócio').should('be.visible');
  });

  it('ISO-08 | Os dados de A continuam intactos depois de tudo que B tentou', () => {
    cy.entrarPelaTela(contaA.usuario.email, contaA.usuario.senha);
    cy.contains('h2', 'Olá, Alice!').should('be.visible');
    cy.get('.app-topo__dados').should('contain', contaA.empresa.razao_social);

    cy.menu('Produtos');
    cy.contains('tbody tr', SKU).within(() => {
      cy.contains('Produto da Empresa A');
      cy.contains('5 un.');
      cy.contains(/R\$\s*10,00/);
    });
    cy.contains('Produto da Empresa B').should('not.exist');
    cy.conferirResumo({ produtos: 1, categorias: 1, valor: 50 }); // 5 × 10,00

    cy.menu('Categorias');
    cy.contains('tbody tr', CATEGORIA).should('contain', '1 produto'); // não foi renomeada nem apagada
  });

  let idParceiroA;
  let idTituloA;
  let idCaixaA;

  it('ISO-09 | Empresa A cria parceiro, título e caixa para testar os módulos novos', () => {
    // A continua logada desde o ISO-08 (sessão do teste encadeado).
    cy.apiCriarParceiro({
      nome: 'Parceiro da Empresa A',
      email: 'parceiro.iso.a@e2e.exemplo.com.br',
      e_cliente: true,
    }).then((parceiro) => {
      idParceiroA = parceiro.id_parceiro;
      cy.apiCriarTitulo({
        tipo: 'a receber',
        id_parceiro: idParceiroA,
        valor: '40.00',
        vencimento: '2026-12-20',
        descricao: 'Título da Empresa A',
      }).then((titulo) => {
        idTituloA = titulo.id_titulo;
      });
    });
    cy.apiAbrirCaixa('50.00').then((caixa) => {
      idCaixaA = caixa.id_caixa;
    });
  });

  it('ISO-10 | Empresa B não acessa parceiro, título nem caixa da Empresa A', () => {
    cy.apiSair();
    cy.apiEntrar(contaB.usuario.email, contaB.usuario.senha)
      .its('status')
      .should('eq', 200);

    cy.request(semFalhar({ url: `/api/parceiros/${idParceiroA}` }))
      .its('status')
      .should('eq', 404);
    cy.request(semFalhar({ url: `/api/titulos/${idTituloA}` }))
      .its('status')
      .should('eq', 404);
    cy.request(semFalhar({ url: `/api/caixas/${idCaixaA}` }))
      .its('status')
      .should('eq', 404);

    cy.request('/api/parceiros').its('body.dados.total').should('eq', 0);
    cy.request('/api/titulos').its('body.dados.total').should('eq', 0);
    cy.request('/api/caixas/atual')
      .its('body.dados.caixa')
      .should('eq', null);

    cy.request(
      semFalhar({
        method: 'POST',
        url: '/api/baixas',
        body: {
          id_titulo: idTituloA,
          id_caixa: idCaixaA,
          valor: '40.00',
          forma_pagamento: 'dinheiro',
          realizado_em: '2026-11-23 10:00',
        },
      }),
    ).then((resposta) => {
      expect([404, 422]).to.include(resposta.status);
    });

    cy.request('/api/produtos').then((resposta) => {
      const produtoB = resposta.body.dados.produtos[0];
      cy.request(
        semFalhar({
          method: 'POST',
          url: '/api/operacoes',
          body: {
            tipo: 'venda',
            id_parceiro: idParceiroA,
            itens: [
              {
                id_produto: produtoB.id_produto,
                quantidade: 1,
                valor_unitario: '1.00',
              },
            ],
            parcelas: 1,
            vencimento: '2026-12-20',
          },
        }),
      ).then((operacao) => {
        expect([404, 422]).to.include(operacao.status);
      });
    });
  });

  it('ISO-11 | Empresa A confirma os próprios dados intactos no final', () => {
    cy.apiEntrar(contaA.usuario.email, contaA.usuario.senha)
      .its('status')
      .should('eq', 200);

    cy.request(`/api/parceiros/${idParceiroA}`)
      .its('body.dados.nome')
      .should('eq', 'Parceiro da Empresa A');
    cy.request(`/api/titulos/${idTituloA}`)
      .its('body.dados.descricao')
      .should('eq', 'Título da Empresa A');
    cy.request(`/api/caixas/${idCaixaA}`)
      .its('body.dados.id_caixa')
      .should('eq', idCaixaA);
  });
});
