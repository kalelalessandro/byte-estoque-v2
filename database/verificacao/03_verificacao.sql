-- Byte Estoque - Verificacao automatizada do banco (26 casos de teste).
-- Documentacao completa de cada caso: Teste_SQL-001.md, nesta mesma pasta.
--
-- Rodar (de dentro da pasta database/):
--   PowerShell: Get-Content .\verificacao\03_verificacao.sql -Raw | docker compose exec -T mysql mysql -u root -p crm_estoque
--   Bash:       docker compose exec -T mysql mysql -u root -p crm_estoque < verificacao/03_verificacao.sql
--
-- Nao altera dados: os testes gravam dentro de uma transacao que termina em ROLLBACK.
-- Resultado esperado: testes_com_falha = 0 no resumo do Bloco 2.

USE crm_estoque;

SET NAMES utf8mb4;

SELECT '=============================================================' AS x;
SELECT ' BYTE ESTOQUE - VERIFICACAO DO BANCO'                          AS x;
SELECT '=============================================================' AS x;

SELECT VERSION()                AS versao_mysql,
       DATABASE()               AS banco,
       @@character_set_database AS charset_padrao,
       @@collation_database     AS collation_padrao;

SELECT '' AS x;
SELECT '--- 1.1 Tabelas criadas (esperado: 13, todas InnoDB / utf8mb4) ---' AS x;

SELECT COUNT(*) AS total_tabelas
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE';

SELECT table_name AS tabela, engine AS motor, table_collation AS collation
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT '' AS x;
SELECT '--- 1.2 Tabela esperada ausente (resultado VAZIO = OK) ---' AS x;

WITH esperadas (tabela) AS (
             SELECT 'empresas'
    UNION ALL SELECT 'cargos'
    UNION ALL SELECT 'usuarios'
    UNION ALL SELECT 'parceiros'
    UNION ALL SELECT 'interacoes'
    UNION ALL SELECT 'categorias'
    UNION ALL SELECT 'produtos'
    UNION ALL SELECT 'operacoes'
    UNION ALL SELECT 'operacao_itens'
    UNION ALL SELECT 'caixas'
    UNION ALL SELECT 'operacoes_caixa'
    UNION ALL SELECT 'titulos_financeiros'
    UNION ALL SELECT 'baixas_financeiras'
)
SELECT e.tabela AS tabela_faltando
FROM esperadas e
LEFT JOIN information_schema.tables t
       ON t.table_schema = DATABASE() AND t.table_name = e.tabela
WHERE t.table_name IS NULL;

SELECT '' AS x;
SELECT '--- 1.3 Chaves primarias (esperado: 13) ---' AS x;

SELECT COUNT(*) AS total_primary_keys
FROM information_schema.table_constraints
WHERE table_schema = DATABASE() AND constraint_type = 'PRIMARY KEY';

SELECT table_name AS tabela, GROUP_CONCAT(column_name ORDER BY ordinal_position) AS colunas_pk
FROM information_schema.key_column_usage
WHERE table_schema = DATABASE() AND constraint_name = 'PRIMARY'
GROUP BY table_name
ORDER BY table_name;

SELECT '' AS x;
SELECT '--- 1.4 Chaves estrangeiras (esperado: 19, todas RESTRICT) ---' AS x;

SELECT COUNT(*) AS total_fks,
       SUM(delete_rule = 'RESTRICT') AS fks_delete_restrict,
       SUM(update_rule = 'RESTRICT') AS fks_update_restrict
FROM information_schema.referential_constraints
WHERE constraint_schema = DATABASE();

SELECT constraint_name AS fk, table_name AS tabela_dependente,
       referenced_table_name AS tabela_principal, delete_rule, update_rule
FROM information_schema.referential_constraints
WHERE constraint_schema = DATABASE()
ORDER BY table_name, constraint_name;

SELECT '' AS x;
SELECT '--- 1.5 Restricoes CHECK (esperado: 17) ---' AS x;

SELECT COUNT(*) AS total_checks
FROM information_schema.table_constraints
WHERE table_schema = DATABASE() AND constraint_type = 'CHECK';

SELECT tc.table_name AS tabela, tc.constraint_name AS check_nome, cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc
  ON cc.constraint_schema = tc.table_schema AND cc.constraint_name = tc.constraint_name
WHERE tc.table_schema = DATABASE() AND tc.constraint_type = 'CHECK'
ORDER BY tc.table_name, tc.constraint_name;

SELECT '' AS x;
SELECT '--- 1.6 Restricoes UNIQUE declaradas (esperado: 8) ---' AS x;

SELECT COUNT(DISTINCT constraint_name) AS total_unicas
FROM information_schema.table_constraints
WHERE table_schema = DATABASE() AND constraint_type = 'UNIQUE';

SELECT tc.table_name AS tabela, tc.constraint_name AS unique_nome,
       GROUP_CONCAT(kcu.column_name ORDER BY kcu.ordinal_position) AS colunas
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_schema = tc.table_schema
 AND kcu.constraint_name   = tc.constraint_name
 AND kcu.table_name        = tc.table_name
WHERE tc.table_schema = DATABASE() AND tc.constraint_type = 'UNIQUE'
GROUP BY tc.table_name, tc.constraint_name
ORDER BY tc.table_name, tc.constraint_name;

SELECT '' AS x;
SELECT '--- 1.7 Colunas com valor padrao (esperado: 6) ---' AS x;

SELECT table_name AS tabela, column_name AS coluna, column_default AS valor_padrao
FROM information_schema.columns
WHERE table_schema = DATABASE() AND column_default IS NOT NULL
ORDER BY table_name, column_name;

SELECT '' AS x;
SELECT '--- 2.1 Testes funcionais das restricoes ---' AS x;

DROP PROCEDURE IF EXISTS verifica_restricoes;

DELIMITER $$

CREATE PROCEDURE verifica_restricoes()
BEGIN
    DECLARE v_ok     INT DEFAULT 0;
    DECLARE v_falhas INT DEFAULT 0;
    DECLARE v_erro   INT DEFAULT 0;
    DECLARE v_msg    TEXT DEFAULT '';

  -- IDs dos testes que devem ser aceitos: conferem se o INSERT gravou de fato.
    DECLARE id_prod_outra_empresa INT DEFAULT NULL;
    DECLARE id_prod_defaults      INT DEFAULT NULL;
    DECLARE id_user_defaults      INT DEFAULT NULL;
    DECLARE id_caixa_fechado      INT DEFAULT NULL;
    DECLARE id_titulo_default     INT DEFAULT NULL;
    DECLARE id_titulo_manual      INT DEFAULT NULL;

    CREATE TEMPORARY TABLE tmp_resultados (
        teste    VARCHAR(90),
        esperado VARCHAR(120),
        obtido   VARCHAR(160),
        situacao VARCHAR(10)
    );

    START TRANSACTION;

    -- (1) CNPJ duplicado -> UNIQUE uq_empresas_cnpj
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO empresas (razao_social, cnpj) VALUES ('Empresa Duplicada', '11222333000181');
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(1) CNPJ duplicado', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(1) CNPJ duplicado', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (2) E-mail de usuario duplicado -> UNIQUE uq_usuarios_email
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha)
        VALUES (2, 2, 'Usuario Duplicado', 'ana.souza@padariaaurora.com.br', 'hash');
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(2) e-mail de usuario duplicado', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(2) e-mail de usuario duplicado', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (3) SKU repetido na MESMA empresa -> UNIQUE uq_produtos_empresa_sku
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco)
        VALUES (1, 'PRES-001', 2, 'SKU Repetido', 9.00);
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(3) SKU repetido na mesma empresa', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(3) SKU repetido na mesma empresa', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (4) Mesmo SKU em OUTRA empresa -> deve ser ACEITO
  --     Cria o SKU 'ZZ-TESTE-SKU-REPETIDO' na empresa 2. O teste (3) mostrou
  --     que esse SKU seria rejeitado na empresa 1, mas em OUTRA empresa ele e
  --     aceito: e a prova de que a unicidade do SKU e por empresa, nao global.
  --     (Usa um SKU proprio do teste para nao depender dos dados do seed.)
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco)
        VALUES (2, 'ZZ-TESTE-SKU-REPETIDO', 3, 'Produto de teste (SKU repetido em outra empresa)', 17.50);
        SET id_prod_outra_empresa = LAST_INSERT_ID();
        IF v_erro = 0 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(4) mesmo SKU em outra empresa', 'aceito', CONCAT('aceito (id_produto ', id_prod_outra_empresa, ')'), 'OK');
        ELSE
            SET id_prod_outra_empresa = NULL;
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(4) mesmo SKU em outra empresa', 'aceito', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (5) Produto com categoria de OUTRA empresa -> FK composta, erro 1452
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco)
        VALUES (1, 'X-001', 3, 'Produto Cruzado', 10.00);
        IF v_erro = 1452 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(5) produto com categoria de outra empresa', 'erro 1452 (FK invalida)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(5) produto com categoria de outra empresa', 'erro 1452 (FK invalida)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (6) Parceiro sem ser cliente nem fornecedor -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO parceiros (id_empresa, nome, e_cliente, e_fornecedor)
        VALUES (1, 'Parceiro Invalido', FALSE, FALSE);
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(6) parceiro sem e_cliente/e_fornecedor', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(6) parceiro sem e_cliente/e_fornecedor', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (7) E-mail de parceiro apenas com espacos -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO parceiros (id_empresa, nome, email, e_cliente)
        VALUES (1, 'Cliente Email Vazio', '   ', TRUE);
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(7) e-mail de parceiro so com espacos', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(7) e-mail de parceiro so com espacos', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (8) Estoque negativo -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, unidade_estoque, preco)
        VALUES (1, 'X-002', 2, 'Estoque Negativo', -1, 9.00);
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(8) unidade_estoque negativa', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(8) unidade_estoque negativa', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (9) Preco negativo -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco)
        VALUES (1, 'X-003', 2, 'Preco Negativo', -5.00);
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(9) preco negativo', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(9) preco negativo', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (10) Item de operacao com quantidade zero -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario)
        VALUES (1, 3, 0, 2.50);
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(10) item de operacao com quantidade 0', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(10) item de operacao com quantidade 0', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (11) Produto repetido na MESMA operacao -> PK composta, erro 1062
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario)
        VALUES (1, 1, 5, 9.50);
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(11) produto repetido na mesma operacao', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(11) produto repetido na mesma operacao', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (12) Caixa com fechamento incompleto -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura, fechado_em)
        VALUES (3, '2026-03-01 08:00:00', 100.00, '2026-03-01 18:00:00');
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(12) caixa com fechamento incompleto', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(12) caixa com fechamento incompleto', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (13) Fechamento anterior a abertura -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura, fechado_em, valor_contado)
        VALUES (3, '2026-03-01 18:00:00', 100.00, '2026-03-01 08:00:00', 50.00);
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(13) fechamento anterior a abertura', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(13) fechamento anterior a abertura', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (14) Movimento de caixa com valor zero -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO operacoes_caixa (id_caixa, id_usuario, tipo, valor, ocorrencia)
        VALUES (1, 3, 'sangria', 0, NOW());
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(14) movimento de caixa com valor 0', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(14) movimento de caixa com valor 0', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (15) Titulo com valor zero -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO titulos_financeiros (id_parceiro, tipo, valor, descricao, vencimento)
        VALUES (1, 'a_pagar', 0, 'Titulo com valor zero', '2026-04-01');
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(15) titulo com valor 0', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(15) titulo com valor 0', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (16) Baixa com valor negativo -> CHECK, erro 3819
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, forma_pagamento)
        VALUES (2, 1, -10.00, NOW(), 'pix');
        IF v_erro = 3819 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(16) baixa com valor negativo', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(16) baixa com valor negativo', 'erro 3819 (CHECK)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (17) FK invalida: usuario em empresa inexistente -> erro 1452
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha)
        VALUES (99999, 1, 'Usuario Orfao', 'orfao@exemplo.com', 'hash');
        IF v_erro = 1452 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(17) usuario em empresa inexistente', 'erro 1452 (FK invalida)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(17) usuario em empresa inexistente', 'erro 1452 (FK invalida)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (18) Exclusao bloqueada por FK (ON DELETE RESTRICT) -> erro 1451
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        DELETE FROM empresas WHERE id_empresa = 1;
        IF v_erro = 1451 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(18) excluir empresa com dependentes', 'erro 1451 (RESTRICT)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(18) excluir empresa com dependentes', 'erro 1451 (RESTRICT)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (19) Defaults: unidade_estoque = 0 e admin_sistema = 0 quando omitidos
    BEGIN
      -- No MySQL, DECLARE de variavel precisa vir antes de DECLARE HANDLER.
        DECLARE v_estoque INT DEFAULT -99;
        DECLARE v_admin   INT DEFAULT -99;
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;

        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco)
        VALUES (1, 'ZZ-TESTE-DEFAULTS', 2, 'Produto com defaults', 1.00);
        SET id_prod_defaults = LAST_INSERT_ID();

        INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha)
        VALUES (1, 2, 'Usuario Default', 'zz.teste.defaults@exemplo.com', 'hash');
        SET id_user_defaults = LAST_INSERT_ID();

        SELECT unidade_estoque INTO v_estoque FROM produtos  WHERE id_produto = id_prod_defaults;
        SELECT admin_sistema   INTO v_admin   FROM usuarios  WHERE id_usuario = id_user_defaults;

        IF v_erro = 0 AND v_estoque = 0 AND v_admin = 0 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(19) defaults de estoque e admin_sistema', '0 e 0',
                CONCAT(v_estoque, ' e ', v_admin), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(19) defaults de estoque e admin_sistema', '0 e 0',
                CONCAT('unidade_estoque=', v_estoque, ' admin_sistema=', v_admin, ' erro=', v_erro, ' ', v_msg), 'FALHA');
        END IF;
    END;

    -- (20) Collation sem diferenciar maiusculas: 'pres-001' colide com 'PRES-001'
  --      na mesma empresa -> erro 1062
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco)
        VALUES (1, 'pres-001', 2, 'SKU em minusculas', 9.00);
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(20) collation ai_ci no SKU (pres-001 = PRES-001)', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(20) collation ai_ci no SKU (pres-001 = PRES-001)', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (21) Documento repetido na MESMA empresa -> UNIQUE composto, erro 1062
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO parceiros (id_empresa, nome, documento, e_cliente)
        VALUES (1, 'Cliente Duplicado', '88777666000155', TRUE);
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(21) documento repetido na mesma empresa', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(21) documento repetido na mesma empresa', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (22) Categoria repetida na MESMA empresa -> UNIQUE composto, erro 1062
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO categorias (id_empresa, nome) VALUES (1, 'Bebidas');
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(22) categoria repetida na mesma empresa', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(22) categoria repetida na mesma empresa', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (23) Cargo repetido -> UNIQUE uq_cargos_cargo, erro 1062
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO cargos (cargo) VALUES ('Dono');
        IF v_erro = 1062 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(23) cargo repetido', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(23) cargo repetido', 'erro 1062 (duplicado)', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (24) Caixa FECHADO de forma coerente -> deve ser ACEITO
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura, fechado_em, valor_contado)
        VALUES (3, '2026-03-01 08:00:00', 100.00, '2026-03-01 18:00:00', 480.00);
        SET id_caixa_fechado = LAST_INSERT_ID();
        IF v_erro = 0 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(24) caixa fechado de forma coerente', 'aceito', CONCAT('aceito (id_caixa ', id_caixa_fechado, ')'), 'OK');
        ELSE
            SET id_caixa_fechado = NULL;
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(24) caixa fechado de forma coerente', 'aceito', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

    -- (25) Titulo sem informar "cancelado" -> deve ser ACEITO com cancelado = 0
    BEGIN
        DECLARE v_cancelado INT DEFAULT -99;
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO titulos_financeiros (id_parceiro, tipo, valor, descricao, vencimento)
        VALUES (1, 'a_pagar', 10.00, 'ZZ-TESTE-TITULO-DEFAULT', '2026-05-01');
        SET id_titulo_default = LAST_INSERT_ID();
        SELECT cancelado INTO v_cancelado FROM titulos_financeiros WHERE id_titulo = id_titulo_default;
        IF v_erro = 0 AND v_cancelado = 0 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(25) default cancelado = 0 em titulos', 'aceito, cancelado = 0',
                CONCAT('aceito, cancelado = ', v_cancelado), 'OK');
        ELSE
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(25) default cancelado = 0 em titulos', 'aceito, cancelado = 0',
                CONCAT('erro ', v_erro, ' cancelado=', v_cancelado, ' ', v_msg), 'FALHA');
        END IF;
    END;

    -- (26) Titulo sem operacao de origem (id_operacao NULL) -> deve ser ACEITO
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION
            GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO, v_msg = MESSAGE_TEXT;
        SET v_erro = 0;
        INSERT INTO titulos_financeiros (id_parceiro, id_operacao, tipo, valor, descricao, vencimento)
        VALUES (1, NULL, 'a_pagar', 15.00, 'ZZ-TESTE-TITULO-MANUAL', '2026-05-02');
        SET id_titulo_manual = LAST_INSERT_ID();
        IF v_erro = 0 THEN
            SET v_ok = v_ok + 1;
            INSERT INTO tmp_resultados VALUES ('(26) titulo sem operacao de origem (NULL)', 'aceito', CONCAT('aceito (id_titulo ', id_titulo_manual, ')'), 'OK');
        ELSE
            SET id_titulo_manual = NULL;
            SET v_falhas = v_falhas + 1;
            INSERT INTO tmp_resultados VALUES ('(26) titulo sem operacao de origem (NULL)', 'aceito', CONCAT('erro ', v_erro, ' | ', v_msg), 'FALHA');
        END IF;
    END;

  -- Relatorio. Os SELECTs vem ANTES do ROLLBACK: a tabela tmp_resultados foi
  -- preenchida dentro da transacao de teste, entao o ROLLBACK a esvaziaria.
  -- Os contadores v_ok e v_falhas ficam em variaveis, que o ROLLBACK nao afeta.
    SELECT teste, esperado, obtido, situacao FROM tmp_resultados ORDER BY teste;

    SELECT v_ok AS testes_ok, v_falhas AS testes_com_falha,
           CASE WHEN v_falhas = 0
                THEN 'TODAS AS RESTRICOES FUNCIONAM'
                ELSE 'ATENCAO: EXISTEM FALHAS'
           END AS veredito;

  -- Nao apagar os registros de teste com DELETE antes daqui: o DELETE pode
  -- falhar por chave estrangeira. O ROLLBACK abaixo desfaz tudo e nao deixa
  -- residuo no banco.
    ROLLBACK;

    DROP TEMPORARY TABLE tmp_resultados;
END$$

DELIMITER ;

CALL verifica_restricoes();

DROP PROCEDURE verifica_restricoes;

SELECT '' AS x;
SELECT '--- 3.1 Saldo pendente dos titulos (valor do titulo - baixas) ---' AS x;

SELECT t.id_titulo, p.nome AS parceiro, t.tipo, t.valor,
       COALESCE(SUM(b.valor), 0) AS total_baixado,
       t.valor - COALESCE(SUM(b.valor), 0) AS saldo_pendente
FROM titulos_financeiros t
JOIN parceiros p ON p.id_parceiro = t.id_parceiro
LEFT JOIN baixas_financeiras b ON b.id_titulo = t.id_titulo
GROUP BY t.id_titulo, p.nome, t.tipo, t.valor
ORDER BY t.id_titulo;

SELECT '' AS x;
SELECT '--- 3.2 Baixas que ultrapassam o titulo (esperado: 0) ---' AS x;

SELECT COUNT(*) AS baixas_acima_do_titulo
FROM (
    SELECT t.id_titulo, t.valor, COALESCE(SUM(b.valor), 0) AS total
    FROM titulos_financeiros t
    LEFT JOIN baixas_financeiras b ON b.id_titulo = t.id_titulo
    GROUP BY t.id_titulo, t.valor
) x
WHERE x.total > x.valor;

SELECT '' AS x;
SELECT '--- 3.3 Composicao do caixa aberto ---' AS x;

SELECT c.id_caixa,
       c.valor_abertura,
       COALESCE((SELECT SUM(CASE WHEN m.tipo = 'suprimento' THEN m.valor ELSE -m.valor END)
                 FROM operacoes_caixa m WHERE m.id_caixa = c.id_caixa), 0) AS movimentos_adicionais,
       COALESCE((SELECT SUM(b.valor) FROM baixas_financeiras b
                 JOIN titulos_financeiros t ON t.id_titulo = b.id_titulo
                 WHERE b.id_caixa = c.id_caixa AND t.tipo = 'a_receber'), 0) AS recebimentos,
       COALESCE((SELECT SUM(b.valor) FROM baixas_financeiras b
                 JOIN titulos_financeiros t ON t.id_titulo = b.id_titulo
                 WHERE b.id_caixa = c.id_caixa AND t.tipo = 'a_pagar'), 0) AS pagamentos
FROM caixas c
WHERE c.fechado_em IS NULL;

SELECT '' AS x;
SELECT '--- 3.4 Produto com categoria de outra empresa (esperado: 0) ---' AS x;

SELECT COUNT(*) AS produtos_com_categoria_de_outra_empresa
FROM produtos pr
JOIN categorias ca ON ca.id_categoria = pr.id_categoria
WHERE ca.id_empresa <> pr.id_empresa;

SELECT '' AS x;
SELECT '--- 3.5 Resumo geral de registros por tabela ---' AS x;

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

SELECT '' AS x;
SELECT '=============================================================' AS x;
SELECT ' VERIFICACAO CONCLUIDA'                                       AS x;
SELECT ' Procure por "testes_com_falha" nos resultados acima.'         AS x;
SELECT '=============================================================' AS x;
