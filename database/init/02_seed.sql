-- =============================================================================
-- Byte Estoque - Dados de exemplo (SEED)
-- =============================================================================
-- Executado automaticamente DEPOIS do 01_schema.sql, na primeira subida do
-- container. Serve para ja existir dados para testar consultas e o backend.
--
-- IMPORTANTE: sao dados FICTICIOS de demonstracao.
--   - Se voce nao quiser dados de exemplo: remova ou renomeie este arquivo
--     antes do primeiro "docker compose up -d" (o MySQL so executa os scripts
--     de init quando o volume de dados esta vazio).
--   - O script pode ser reexecutado sem duplicar nada: os INSERTs usam
--     "ON DUPLICATE KEY UPDATE" e ids fixos.
--
-- Este arquivo NAO contem testes de rejeicao de dados invalidos. Eles ficam em
-- verificacao/03_verificacao.sql, porque uma rejeicao esperada aqui faria o
-- MySQL interromper a inicializacao e nada seria gravado.
--
-- Cenario criado:
--   Empresa 1 - "Padaria Aurora LTDA"   -> dados completos: usuarios, catalogo,
--                                          parceiros, operacoes, caixa aberto,
--                                          titulos e baixas.
--   Empresa 2 - "Mercado Bom Preco LTDA" -> demonstra que o mesmo SKU pode
--                                          existir em empresas diferentes.
--   Empresa 3 - "Distribuidora Exemplo ME" -> criada sem informar criado_em,
--                                          comprovando o DEFAULT CURRENT_TIMESTAMP.
-- =============================================================================

USE crm_estoque;

SET NAMES utf8mb4;

SELECT '--- Aplicando dados de exemplo (seed) ---' AS etapa;

START TRANSACTION;

-- -----------------------------------------------------------------------------
-- 1) Empresas
-- -----------------------------------------------------------------------------
INSERT INTO empresas (id_empresa, razao_social, cnpj, criado_em, cep, inscricao, telefone_empresa) VALUES
    (1, 'Padaria Aurora LTDA', '11222333000181', '2026-01-15 08:00:00', '01310100', '114567890111', '1130001000'),
    (2, 'Mercado Bom Preco LTDA', '44555666000172', '2026-02-02 09:30:00', '04538133', '223456780222', '1130002000')
ON DUPLICATE KEY UPDATE razao_social = VALUES(razao_social);

-- criado_em omitido de proposito: o banco preenche com CURRENT_TIMESTAMP.
INSERT INTO empresas (id_empresa, razao_social, cnpj, cep) VALUES
    (3, 'Distribuidora Exemplo ME', '77888999000163', '13010100')
ON DUPLICATE KEY UPDATE razao_social = VALUES(razao_social);

-- -----------------------------------------------------------------------------
-- 2) Cargos (globais: nao possuem id_empresa)
-- -----------------------------------------------------------------------------
INSERT INTO cargos (id_cargo, cargo) VALUES
    (1, 'Dono'),
    (2, 'Funcionario'),
    (3, 'Financeiro')
ON DUPLICATE KEY UPDATE cargo = VALUES(cargo);

-- -----------------------------------------------------------------------------
-- 3) Usuarios
--    hash_senha guarda um valor FICTICIO. Nunca use este valor em producao:
--    o backend deve gerar o hash real (bcrypt/argon2) no cadastro.
-- -----------------------------------------------------------------------------
INSERT INTO usuarios (id_usuario, id_empresa, id_cargo, nome, email, telefone, hash_senha, admin_sistema) VALUES
    (1, 1, 1, 'Ana Souza',    'ana.souza@padariaaurora.com.br',    '11990000001', '$2b$12$exemploDeHashFicticioNaoUseEmProducao000000000000000', 1),
    (2, 1, 2, 'Bruno Lima',   'bruno.lima@padariaaurora.com.br',   '11990000002', '$2b$12$exemploDeHashFicticioNaoUseEmProducao000000000000000', 0),
    (3, 1, 3, 'Carla Mendes', 'carla.mendes@padariaaurora.com.br', '11990000003', '$2b$12$exemploDeHashFicticioNaoUseEmProducao000000000000000', 0),
    (4, 2, 1, 'Diego Rocha',  'diego.rocha@bompreco.com.br',       '11990000004', '$2b$12$exemploDeHashFicticioNaoUseEmProducao000000000000000', 1)
ON DUPLICATE KEY UPDATE nome = VALUES(nome);

-- -----------------------------------------------------------------------------
-- 4) Parceiros (clientes e/ou fornecedores de cada empresa)
-- -----------------------------------------------------------------------------
INSERT INTO parceiros (id_parceiro, id_empresa, nome, documento, email, cep, e_cliente, e_fornecedor, observacao) VALUES
    (1, 1, 'Distribuidora Norte LTDA', '99888777000166', 'contato@distnorte.com.br',     '02012000', 0, 1, 'Fornecedor de farinha e fermento.'),
    (2, 1, 'Mercado Sul ME',           '88777666000155', 'compras@mercadosul.com.br',    '09040380', 1, 0, 'Cliente recorrente, compra semanal.'),
    (3, 2, 'Atacadao Central LTDA',    '77666555000144', 'vendas@atacadaocentral.com.br', NULL,       0, 1, 'Fornecedor do Mercado Bom Preco.'),
    (4, 1, 'Joana Ribeiro',            NULL,             NULL,                            NULL,       1, 1, 'Cliente e fornecedora ao mesmo tempo.')
ON DUPLICATE KEY UPDATE nome = VALUES(nome);

-- -----------------------------------------------------------------------------
-- 5) Categorias por empresa
--    A restricao UNIQUE (id_categoria, id_empresa) existe para servir de
--    referencia a FK composta declarada em produtos.
-- -----------------------------------------------------------------------------
INSERT INTO categorias (id_categoria, id_empresa, nome) VALUES
    (1, 1, 'Bebidas'),
    (2, 1, 'Padaria'),
    (3, 2, 'Mercearia')
ON DUPLICATE KEY UPDATE nome = VALUES(nome);

-- -----------------------------------------------------------------------------
-- 6) Produtos
--    Repare que "PRES-001" existe nas empresas 1 e 2: o SKU e unico DENTRO de
--    cada empresa, podendo ser reutilizado por empresas diferentes.
-- -----------------------------------------------------------------------------
INSERT INTO produtos (id_produto, id_empresa, sku, id_categoria, nome, descricao, unidade_estoque, preco) VALUES
    (1, 1, 'PRES-001', 2, 'Presunto fatiado',   'Presunto cozido fatiado, pacote de 200 g.', 30,  14.90),
    (2, 1, 'BEB-001',  1, 'Refrigerante lata',  'Refrigerante cola, lata 350 ml.',           48,   5.50),
    (3, 1, 'BEB-002',  1, 'Agua mineral 500ml', NULL,                                       120,   2.50),
    (4, 2, 'PRES-001', 3, 'Presunto fatiado',   'Produto equivalente no Mercado Bom Preco.', 15,  16.90),
    (5, 1, 'PAD-001',  2, 'Pao frances',        'Pao frances vendido por unidade.',         200,   0.75)
ON DUPLICATE KEY UPDATE nome = VALUES(nome), preco = VALUES(preco);

-- -----------------------------------------------------------------------------
-- 7) Operacoes comerciais e seus itens
--    1 = compra concluida do fornecedor 1
--    2 = venda pendente para o cliente 2
--    3 = venda cancelada para o cliente 2
-- -----------------------------------------------------------------------------
INSERT INTO operacoes (id_operacao, id_parceiro, id_usuario, tipo, status, ocorrencia, observacoes) VALUES
    (1, 1, 2, 'compra', 'concluida', '2026-02-10 09:15:00', 'Reposicao de estoque do mes.'),
    (2, 2, 3, 'venda',  'pendente',  '2026-02-12 14:40:00', 'Venda a prazo.'),
    (3, 2, 3, 'venda',  'cancelada', '2026-02-13 10:05:00', 'Cancelada pelo cliente antes da entrega.')
ON DUPLICATE KEY UPDATE status = VALUES(status);

INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) VALUES
    (1, 1, 20,  9.50),
    (1, 2, 24,  3.20),
    (2, 1,  8, 14.90),
    (2, 2, 12,  5.50),
    (3, 3,  6,  2.50)
ON DUPLICATE KEY UPDATE quantidade = VALUES(quantidade), valor_unitario = VALUES(valor_unitario);

-- -----------------------------------------------------------------------------
-- 8) Caixa: uma sessao aberta (fechado_em e valor_contado ficam NULOS)
-- -----------------------------------------------------------------------------
INSERT INTO caixas (id_caixa, aberto_por_usuario, aberto_em, valor_abertura, fechado_em, valor_contado) VALUES
    (1, 3, '2026-02-12 08:00:00', 800.00, NULL, NULL)
ON DUPLICATE KEY UPDATE valor_abertura = VALUES(valor_abertura);

-- Movimentos adicionais da sessao (suprimento e sangria)
INSERT INTO operacoes_caixa (movimento_id, id_caixa, id_usuario, tipo, valor, ocorrencia, descricao) VALUES
    (1, 1, 3, 'suprimento', 100.00, '2026-02-12 08:30:00', 'Troco adicional para o dia.'),
    (2, 1, 3, 'sangria',     50.00, '2026-02-12 12:10:00', 'Retirada parcial para deposito.')
ON DUPLICATE KEY UPDATE valor = VALUES(valor);

-- -----------------------------------------------------------------------------
-- 9) Titulos financeiros e baixas
--    Titulo 1: compra da operacao 1, quitado em uma baixa.
--    Titulo 2: venda da operacao 2, parcialmente baixado (sobram 400.00).
--    Titulo 3: lancamento manual a pagar, sem operacao de origem e sem baixa.
-- -----------------------------------------------------------------------------
INSERT INTO titulos_financeiros (id_titulo, id_parceiro, id_operacao, tipo, valor, descricao, vencimento, cancelado) VALUES
    (1, 1, 1,    'a_pagar',   1000.00, 'Compra de estoque - operacao 1',              '2026-03-12', 0),
    (2, 2, 2,    'a_receber',  900.00, 'Venda a prazo - operacao 2',                  '2026-03-14', 0),
    (3, 3, NULL, 'a_pagar',    320.00, 'Lancamento manual: energia eletrica',         '2026-03-05', 0)
ON DUPLICATE KEY UPDATE valor = VALUES(valor), cancelado = VALUES(cancelado);

INSERT INTO baixas_financeiras (id_baixa, id_titulo, id_caixa, valor, realizado_em, forma_pagamento) VALUES
    (1, 1, 1, 1000.00, '2026-02-12 15:00:00', 'pix'),
    (2, 2, 1,  400.00, '2026-02-13 09:20:00', 'dinheiro'),
    (3, 2, 1,  100.00, '2026-02-14 10:45:00', 'cartao')
ON DUPLICATE KEY UPDATE valor = VALUES(valor);

COMMIT;

-- -----------------------------------------------------------------------------
-- 10) Resumo do que foi gravado
-- -----------------------------------------------------------------------------
SELECT 'empresas' AS tabela, COUNT(*) AS registros FROM empresas
UNION ALL SELECT 'cargos',              COUNT(*) FROM cargos
UNION ALL SELECT 'usuarios',            COUNT(*) FROM usuarios
UNION ALL SELECT 'parceiros',           COUNT(*) FROM parceiros
UNION ALL SELECT 'interacoes',          COUNT(*) FROM interacoes
UNION ALL SELECT 'categorias',          COUNT(*) FROM categorias
UNION ALL SELECT 'produtos',            COUNT(*) FROM produtos
UNION ALL SELECT 'operacoes',           COUNT(*) FROM operacoes
UNION ALL SELECT 'operacao_itens',      COUNT(*) FROM operacao_itens
UNION ALL SELECT 'caixas',              COUNT(*) FROM caixas
UNION ALL SELECT 'operacoes_caixa',     COUNT(*) FROM operacoes_caixa
UNION ALL SELECT 'titulos_financeiros', COUNT(*) FROM titulos_financeiros
UNION ALL SELECT 'baixas_financeiras',  COUNT(*) FROM baixas_financeiras;

-- Saldo pendente de cada titulo: valor do titulo menos a soma das baixas.
SELECT t.id_titulo,
       e.razao_social                      AS empresa,
       p.nome                              AS parceiro,
       t.tipo,
       t.valor,
       COALESCE(SUM(b.valor), 0)           AS total_baixado,
       t.valor - COALESCE(SUM(b.valor), 0) AS saldo_pendente
FROM titulos_financeiros t
JOIN parceiros p ON p.id_parceiro = t.id_parceiro
JOIN empresas  e ON e.id_empresa  = p.id_empresa
LEFT JOIN baixas_financeiras b ON b.id_titulo = t.id_titulo
GROUP BY t.id_titulo, e.razao_social, p.nome, t.tipo, t.valor
ORDER BY t.id_titulo;

SELECT 'Seed aplicado com sucesso.' AS resultado;
