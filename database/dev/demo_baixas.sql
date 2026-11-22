-- Dados de DEMONSTRAÇÃO para experimentar o Financeiro.
--
-- Cria títulos de exemplo (um a receber e um a pagar, com parceiro, e um SEM parceiro) para
-- a SUA empresa. Você também pode cadastrar títulos pela aba "Títulos" do Financeiro, e o
-- caixa se abre pela aba "Caixas": este script não mexe em caixa. NÃO faz parte de
-- database/init (não roda sozinho) e não altera o schema.
--
-- Como usar (troque o e-mail pelo do usuário com que você entra no sistema):
--   docker compose exec -T mysql mysql -uapp_crm -p crm_estoque < dev/demo_baixas.sql
--   (ou execute o conteúdo no seu cliente MySQL, já conectado ao banco crm_estoque)
--
-- Pré-requisito: já existir ao menos um parceiro cliente e um fornecedor cadastrados
-- na tela de Parceiros (o script usa o primeiro de cada tipo).

SET @email = 'troque-pelo-seu-email@exemplo.com.br';

SET @empresa = (SELECT id_empresa FROM usuarios WHERE email = @email);
SET @cliente = (SELECT MIN(id_parceiro) FROM parceiros WHERE id_empresa = @empresa AND e_cliente = TRUE);
SET @fornecedor = (SELECT MIN(id_parceiro) FROM parceiros WHERE id_empresa = @empresa AND e_fornecedor = TRUE);

-- Um título a receber (cliente), um a pagar (fornecedor) e um SEM parceiro
-- (este último NÃO aparece na tela de baixas: toda baixa precisa de parceiro).
INSERT INTO titulos_financeiros (id_parceiro, id_empresa, tipo, valor, descricao, vencimento)
VALUES
  (@cliente,    @empresa, 'a receber', 200.00, 'Pedido 1021 (demonstração)',   CURDATE() + INTERVAL 15 DAY),
  (@fornecedor, @empresa, 'a pagar',   300.00, 'Fornecimento de agosto (demo)', CURDATE() + INTERVAL 20 DAY),
  (NULL,        @empresa, 'a pagar',    80.00, 'Conta de energia (sem parceiro)', CURDATE() + INTERVAL 25 DAY);
