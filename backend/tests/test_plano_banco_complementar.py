"""Casos de banco e colação do plano V1.4 que ainda não tinham teste pytest.

Complementa ``test_integridade_banco_auth.py`` com os demais casos BDD, FKN,
INTG e CAR do PDF, além de COL-N02/N03. O SQL é executado direto no MySQL, como
o plano prevê para ``cy.task``. Os dados criados aqui são removidos pelo
fixture local antes do ``banco_limpo`` (por causa do ON DELETE RESTRICT).
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.app.db import get_engine
from tests.helpers import CNPJ_VALIDO, CNPJ_VALIDO_2, criar_conta, entrar

pytestmark = pytest.mark.banco

SENHA = "Plano#Banco1"
CARGOS_CRIADOS = {
    "Plano Cargo Unico",
    "Plano Supervisor",
    "Plano Coordenação",
    "Plano Coordenacao",
    "Plano Cargo Longo",
}


def executar(app, sql: str, params: dict | None = None):
    with app.app_context(), get_engine().begin() as conexao:
        resultado = conexao.execute(text(sql), params or {})
        return resultado.fetchall() if resultado.returns_rows else resultado.lastrowid


def assert_erro(app, sql: str, params: dict | None = None, *, codigos: tuple[str, ...]):
    with pytest.raises((DataError, IntegrityError, OperationalError)) as excinfo:
        executar(app, sql, params)
    mensagem = str(excinfo.value)
    assert any(codigo in mensagem for codigo in codigos), mensagem


def limpar_plano(app) -> None:
    with app.app_context(), get_engine().begin() as conexao:
        ids_empresas = [
            linha[0]
            for linha in conexao.execute(
                text(
                    "SELECT id_empresa FROM empresas WHERE cnpj LIKE 'BD%' "
                    "UNION SELECT id_empresa FROM usuarios "
                    "WHERE email LIKE '%@exemplo.com.br'"
                )
            )
        ]
        if ids_empresas:
            ids = list(ids_empresas)
            consultas = [
                "DELETE FROM baixas_financeiras WHERE id_titulo IN "
                "(SELECT id_titulo FROM titulos_financeiros WHERE id_empresa IN :ids)",
                "DELETE FROM titulos_financeiros WHERE id_empresa IN :ids",
                "DELETE FROM operacao_itens WHERE id_operacao IN "
                "(SELECT o.id_operacao FROM operacoes o JOIN usuarios u "
                " ON u.id_usuario = o.id_usuario WHERE u.id_empresa IN :ids)",
                "DELETE FROM operacoes WHERE id_usuario IN "
                "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)",
                "DELETE FROM operacoes_caixa WHERE id_caixa IN "
                "(SELECT c.id_caixa FROM caixas c JOIN usuarios u "
                " ON u.id_usuario = c.aberto_por_usuario WHERE u.id_empresa IN :ids)",
                "DELETE FROM caixas WHERE aberto_por_usuario IN "
                "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)",
                "DELETE FROM interacoes WHERE id_parceiro IN "
                "(SELECT id_parceiro FROM parceiros WHERE id_empresa IN :ids) "
                "OR id_usuario IN (SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)",
                "DELETE FROM parceiros WHERE id_empresa IN :ids",
                "DELETE FROM produtos WHERE id_empresa IN :ids",
                "DELETE FROM categorias WHERE id_empresa IN :ids",
                "DELETE FROM usuarios WHERE id_empresa IN :ids",
            ]
            for consulta in consultas:
                conexao.execute(
                    text(consulta).bindparams(bindparam("ids", expanding=True)),
                    {"ids": ids},
                )
            conexao.execute(
                text("DELETE FROM empresas WHERE id_empresa IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": ids},
            )
        for cargo in CARGOS_CRIADOS:
            conexao.execute(
                text(
                    "DELETE FROM cargos WHERE cargo = :cargo AND NOT EXISTS "
                    "(SELECT 1 FROM usuarios WHERE usuarios.id_cargo = cargos.id_cargo)"
                ),
                {"cargo": cargo},
            )


@pytest.fixture(autouse=True)
def limpar_apos_plano(app, banco_limpo):
    yield
    limpar_plano(app)


def conta(client, email: str, cnpj: str = CNPJ_VALIDO) -> dict:
    dados = criar_conta(
        client, email=email, senha=SENHA, nome="Conta Plano", cnpj=cnpj
    )
    entrar(client, email, SENHA)
    return {
        "id_empresa": dados["empresa"]["id_empresa"],
        "id_usuario": dados["usuario"]["id_usuario"],
        "id_cargo": dados["usuario"]["id_cargo"],
    }


# ---------------------------------------------------------------------------
# BDD - casos completos do plano (os cobertos já estão em test_integridade_banco_auth)
# ---------------------------------------------------------------------------


def test_bdd_p03_estoque_do_produto_assume_zero_quando_omitido(app, client):
    c = conta(client, "plano.bdd.p03@exemplo.com.br")
    id_categoria = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat Default')",
        {"e": c["id_empresa"]},
    )
    executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-DEF-01', :c, 'BD Produto Default', 1.00)",
        {"e": c["id_empresa"], "c": id_categoria},
    )
    linha = executar(
        app,
        "SELECT unidade_estoque FROM produtos WHERE sku = 'BD-DEF-01' "
        "AND id_empresa = :e",
        {"e": c["id_empresa"]},
    )
    assert linha[0][0] == 0


def test_bdd_p04_cancelado_do_titulo_assume_false_quando_omitido(app, client):
    c = conta(client, "plano.bdd.p04@exemplo.com.br")
    id_titulo = executar(
        app,
        "INSERT INTO titulos_financeiros "
        "(id_empresa, tipo, valor, descricao, vencimento) "
        "VALUES (:e, 'a pagar', 10.00, 'BD Titulo Default', '2027-03-01')",
        {"e": c["id_empresa"]},
    )
    linha = executar(
        app,
        "SELECT cancelado, id_parceiro, id_operacao FROM titulos_financeiros "
        "WHERE id_titulo = :id",
        {"id": id_titulo},
    )
    assert linha[0][0] in (0, False)
    assert linha[0][1] is None
    assert linha[0][2] is None


def test_bdd_p05_operacao_pode_ser_inserida_sem_parceiro(app, client):
    c = conta(client, "plano.bdd.p05@exemplo.com.br")
    executar(
        app,
        "INSERT INTO operacoes (id_parceiro, id_usuario, tipo, status, ocorrencia) "
        "VALUES (NULL, :u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    linha = executar(
        app,
        "SELECT id_parceiro FROM operacoes WHERE id_usuario = :u",
        {"u": c["id_usuario"]},
    )
    assert linha and linha[0][0] is None


def test_bdd_p06_mesmo_sku_em_empresas_diferentes_e_aceito(app, client):
    a = conta(client, "plano.bdd.p06.a@exemplo.com.br")
    b = conta(client, "plano.bdd.p06.b@exemplo.com.br", CNPJ_VALIDO_2)
    cat_a = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat A')",
        {"e": a["id_empresa"]},
    )
    cat_b = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat B')",
        {"e": b["id_empresa"]},
    )
    executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-SKU-IGUAL', :c, 'Prod A', 1.00)",
        {"e": a["id_empresa"], "c": cat_a},
    )
    executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-SKU-IGUAL', :c, 'Prod B', 1.00)",
        {"e": b["id_empresa"], "c": cat_b},
    )
    linhas = executar(
        app,
        "SELECT nome FROM produtos WHERE sku = 'BD-SKU-IGUAL' "
        "AND id_empresa IN (:a, :b)",
        {"a": a["id_empresa"], "b": b["id_empresa"]},
    )
    assert {linha[0] for linha in linhas} == {"Prod A", "Prod B"}


def test_bdd_n02_parceiro_sem_relacionamento_viola_check(app, client):
    c = conta(client, "plano.bdd.n02@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO parceiros (id_empresa, nome, e_cliente, e_fornecedor) "
        "VALUES (:e, 'BD Parceiro Sem Relacao', 0, 0)",
        {"e": c["id_empresa"]},
        codigos=("3819", "chk_parceiros_relacionamento"),
    )


def test_bdd_n03_parceiro_com_email_vazio_viola_check(app, client):
    c = conta(client, "plano.bdd.n03@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO parceiros (id_empresa, nome, email, e_cliente) "
        "VALUES (:e, 'BD Parceiro Email Vazio', ' ', 1)",
        {"e": c["id_empresa"]},
        codigos=("3819", "chk_parceiros_email"),
    )


def test_bdd_n04_produto_com_categoria_de_outra_empresa_viola_fk(app, client):
    a = conta(client, "plano.bdd.n04.a@exemplo.com.br")
    b = conta(client, "plano.bdd.n04.b@exemplo.com.br", CNPJ_VALIDO_2)
    cat_b = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat B2')",
        {"e": b["id_empresa"]},
    )
    assert_erro(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-FK-01', :c, 'BD Produto Cat Alheia', 1.00)",
        {"e": a["id_empresa"], "c": cat_b},
        codigos=("1452", "fk_produtos_categoria"),
    )


def test_bdd_n07_excluir_produto_em_operacao_e_bloqueado(app, client):
    c = conta(client, "plano.bdd.n07@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat N07')",
        {"e": c["id_empresa"]},
    )
    prod = executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-FK-N07', :c, 'BD Produto N07', 1.00)",
        {"e": c["id_empresa"], "c": cat},
    )
    op = executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    executar(
        app,
        "INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) "
        "VALUES (:o, :p, 1, 1.00)",
        {"o": op, "p": prod},
    )
    assert_erro(
        app,
        "DELETE FROM produtos WHERE id_produto = :p",
        {"p": prod},
        codigos=("1451", "fk_operacao_itens_produto"),
    )


def test_bdd_n08_repetir_produto_na_operacao_viola_pk(app, client):
    c = conta(client, "plano.bdd.n08@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat N08')",
        {"e": c["id_empresa"]},
    )
    prod = executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-FK-N08', :c, 'BD Produto N08', 1.00)",
        {"e": c["id_empresa"], "c": cat},
    )
    op = executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    executar(
        app,
        "INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) "
        "VALUES (:o, :p, 1, 1.00)",
        {"o": op, "p": prod},
    )
    assert_erro(
        app,
        "INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) "
        "VALUES (:o, :p, 1, 1.00)",
        {"o": op, "p": prod},
        codigos=("1062", "PRIMARY"),
    )


def test_bdd_n09_item_com_quantidade_zero_viola_check(app, client):
    c = conta(client, "plano.bdd.n09@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat N09')",
        {"e": c["id_empresa"]},
    )
    prod = executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-FK-N09', :c, 'BD Produto N09', 1.00)",
        {"e": c["id_empresa"], "c": cat},
    )
    op = executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) "
        "VALUES (:o, :p, 0, 1.00)",
        {"o": op, "p": prod},
        codigos=("3819", "chk_operacao_itens_quantidade"),
    )


def test_bdd_n10_produto_com_preco_negativo_viola_check(app, client):
    c = conta(client, "plano.bdd.n10@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'BD Cat N10')",
        {"e": c["id_empresa"]},
    )
    assert_erro(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'BD-PRECO-NEG', :c, 'BD Preco Negativo', -1.00)",
        {"e": c["id_empresa"], "c": cat},
        codigos=("3819", "chk_produtos_preco"),
    )


def test_bdd_n11_caixa_fechado_sem_valor_contado_viola_check(app, client):
    c = conta(client, "plano.bdd.n11@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura, "
        "fechado_em, valor_contado) VALUES (:u, '2026-11-09 08:00:00', 10.00, "
        "'2026-11-09 18:00:00', NULL)",
        {"u": c["id_usuario"]},
        codigos=("3819", "chk_caixas_fechamento"),
    )


def test_bdd_n12_caixa_fechado_antes_da_abertura_viola_check(app, client):
    c = conta(client, "plano.bdd.n12@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura, "
        "fechado_em, valor_contado) VALUES (:u, '2026-11-09 18:00:00', 10.00, "
        "'2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
        codigos=("3819", "chk_caixas_fechamento"),
    )


def test_bdd_n13_titulo_com_valor_zero_viola_check(app, client):
    c = conta(client, "plano.bdd.n13@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO titulos_financeiros (id_empresa, tipo, valor, descricao, "
        "vencimento) VALUES (:e, 'a receber', 0, 'BD Titulo Zero', '2027-03-02')",
        {"e": c["id_empresa"]},
        codigos=("3819", "chk_titulos_financeiros_valor"),
    )


def test_bdd_n14_baixa_com_valor_zero_viola_check(app, client):
    c = conta(client, "plano.bdd.n14@exemplo.com.br")
    caixa = executar(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (:u, '2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
    )
    titulo = executar(
        app,
        "INSERT INTO titulos_financeiros (id_empresa, tipo, valor, descricao, "
        "vencimento) VALUES (:e, 'a receber', 10.00, 'BD Titulo Baixa', '2027-03-02')",
        {"e": c["id_empresa"]},
    )
    assert_erro(
        app,
        "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
        "forma_pagamento) VALUES (:t, :c, 0, '2026-11-09 09:00:00', 'dinheiro')",
        {"t": titulo, "c": caixa},
        codigos=("3819", "chk_baixas_financeiras_valor"),
    )


def test_bdd_n15_movimento_de_caixa_com_valor_zero_viola_check(app, client):
    c = conta(client, "plano.bdd.n15@exemplo.com.br")
    caixa = executar(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (:u, '2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "INSERT INTO operacoes_caixa (id_caixa, id_usuario, tipo, valor, ocorrencia) "
        "VALUES (:c, :u, 'sangria', 0, '2026-11-09 09:30:00')",
        {"c": caixa, "u": c["id_usuario"]},
        codigos=("3819", "chk_operacoes_caixa_valor"),
    )


# ---------------------------------------------------------------------------
# FKN - demais chaves estrangeiras e campos obrigatórios
# ---------------------------------------------------------------------------


def test_fkn_n03_interacao_com_parceiro_inexistente(app, client):
    c = conta(client, "plano.fkn.n03@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO interacoes (id_parceiro, id_usuario, ocorrencia, canal, descricao) "
        "VALUES (999903, :u, '2026-11-09', 'telefone', 'FK parceiro inexistente')",
        {"u": c["id_usuario"]},
        codigos=("1452", "fk_interacoes_parceiro"),
    )


def test_fkn_n04_operacao_com_usuario_inexistente(app):
    assert_erro(
        app,
        "INSERT INTO operacoes (id_parceiro, id_usuario, tipo, status, ocorrencia) "
        "VALUES (NULL, 999904, 'venda', 'pendente', '2026-11-09 10:00:00')",
        codigos=("1452", "fk_operacoes_usuario"),
    )


def test_fkn_n05_item_com_produto_inexistente(app, client):
    c = conta(client, "plano.fkn.n05@exemplo.com.br")
    op = executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 10:00:00')",
        {"u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) "
        "VALUES (:o, 999905, 1, 1.00)",
        {"o": op},
        codigos=("1452", "fk_operacao_itens_produto"),
    )


def test_fkn_n06_baixa_com_titulo_inexistente(app, client):
    c = conta(client, "plano.fkn.n06@exemplo.com.br")
    caixa = executar(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (:u, '2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
        "forma_pagamento) VALUES (999906, :c, 10.00, '2026-11-09 11:00:00', 'Pix')",
        {"c": caixa},
        codigos=("1452", "fk_baixas_financeiras_titulo"),
    )


def test_fkn_n07_baixa_sem_caixa_viola_not_null(app, client):
    c = conta(client, "plano.fkn.n07@exemplo.com.br")
    titulo = executar(
        app,
        "INSERT INTO titulos_financeiros (id_empresa, tipo, valor, descricao, "
        "vencimento) VALUES (:e, 'a receber', 10.00, 'FK Caixa Nulo', '2027-03-03')",
        {"e": c["id_empresa"]},
    )
    assert_erro(
        app,
        "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
        "forma_pagamento) VALUES (:t, NULL, 10.00, '2026-11-09 11:10:00', 'dinheiro')",
        {"t": titulo},
        codigos=("1048", "id_caixa"),
    )


def test_fkn_n08_titulo_com_parceiro_inexistente(app, client):
    c = conta(client, "plano.fkn.n08@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO titulos_financeiros (id_empresa, id_parceiro, tipo, valor, "
        "descricao, vencimento) VALUES (:e, 999908, 'a pagar', 10.00, "
        "'FK parceiro inexistente', '2027-03-03')",
        {"e": c["id_empresa"]},
        codigos=("1452", "fk_titulos_financeiros_parceiro"),
    )


def test_fkn_n09_produto_sem_categoria_viola_not_null(app, client):
    c = conta(client, "plano.fkn.n09@exemplo.com.br")
    assert_erro(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'FKN-SEM-CAT', NULL, 'Produto Sem Categoria BD', 1.00)",
        {"e": c["id_empresa"]},
        codigos=("1048", "id_categoria"),
    )


def test_fkn_n10_caixa_sem_usuario_de_abertura_viola_not_null(app):
    assert_erro(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (NULL, '2026-11-09 08:00:00', 10.00)",
        codigos=("1048", "aberto_por_usuario"),
    )


# ---------------------------------------------------------------------------
# INTG - integridade referencial (RESTRICT)
# ---------------------------------------------------------------------------


def test_intg_n02_excluir_usuario_com_operacoes_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n02@exemplo.com.br")
    executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "DELETE FROM usuarios WHERE id_usuario = :u",
        {"u": c["id_usuario"]},
        codigos=("1451", "fk_operacoes_usuario"),
    )


def test_intg_n03_excluir_usuario_com_interacoes_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n03@exemplo.com.br")
    parceiro = executar(
        app,
        "INSERT INTO parceiros (id_empresa, nome, e_cliente) "
        "VALUES (:e, 'INTG Parceiro N03', 1)",
        {"e": c["id_empresa"]},
    )
    executar(
        app,
        "INSERT INTO interacoes (id_parceiro, id_usuario, ocorrencia, canal, descricao) "
        "VALUES (:p, :u, '2026-11-09', 'telefone', 'INTG N03')",
        {"p": parceiro, "u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "DELETE FROM usuarios WHERE id_usuario = :u",
        {"u": c["id_usuario"]},
        codigos=("1451", "fk_interacoes_usuario"),
    )


def test_intg_n04_excluir_usuario_que_abriu_caixa_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n04@exemplo.com.br")
    executar(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (:u, '2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "DELETE FROM usuarios WHERE id_usuario = :u",
        {"u": c["id_usuario"]},
        codigos=("1451", "fk_caixas_usuario_abertura"),
    )


def test_intg_n05_excluir_parceiro_com_interacoes_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n05@exemplo.com.br")
    parceiro = executar(
        app,
        "INSERT INTO parceiros (id_empresa, nome, e_cliente) "
        "VALUES (:e, 'INTG Parceiro N05', 1)",
        {"e": c["id_empresa"]},
    )
    executar(
        app,
        "INSERT INTO interacoes (id_parceiro, id_usuario, ocorrencia, canal, descricao) "
        "VALUES (:p, :u, '2026-11-09', 'telefone', 'INTG N05')",
        {"p": parceiro, "u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "DELETE FROM parceiros WHERE id_parceiro = :p",
        {"p": parceiro},
        codigos=("1451", "fk_interacoes_parceiro"),
    )


def test_intg_n06_excluir_categoria_com_produtos_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n06@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'INTG Cat N06')",
        {"e": c["id_empresa"]},
    )
    executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'INTG-N06', :c, 'Produto N06', 1.00)",
        {"e": c["id_empresa"], "c": cat},
    )
    assert_erro(
        app,
        "DELETE FROM categorias WHERE id_categoria = :c",
        {"c": cat},
        codigos=("1451", "fk_produtos_categoria"),
    )


def test_intg_n07_excluir_operacao_com_itens_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n07@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'INTG Cat N07')",
        {"e": c["id_empresa"]},
    )
    prod = executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'INTG-N07', :c, 'Produto N07', 1.00)",
        {"e": c["id_empresa"], "c": cat},
    )
    op = executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    executar(
        app,
        "INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario) "
        "VALUES (:o, :p, 1, 1.00)",
        {"o": op, "p": prod},
    )
    assert_erro(
        app,
        "DELETE FROM operacoes WHERE id_operacao = :o",
        {"o": op},
        codigos=("1451", "fk_operacao_itens_operacao"),
    )


def test_intg_n08_excluir_operacao_com_titulos_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n08@exemplo.com.br")
    op = executar(
        app,
        "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
        "VALUES (:u, 'venda', 'pendente', '2026-11-09 08:00:00')",
        {"u": c["id_usuario"]},
    )
    executar(
        app,
        "INSERT INTO titulos_financeiros (id_empresa, id_operacao, tipo, valor, "
        "descricao, vencimento) VALUES (:e, :o, 'a receber', 10.00, "
        "'Titulo INTG N08', '2027-03-03')",
        {"e": c["id_empresa"], "o": op},
    )
    assert_erro(
        app,
        "DELETE FROM operacoes WHERE id_operacao = :o",
        {"o": op},
        codigos=("1451", "fk_titulos_financeiros_operacao"),
    )


def test_intg_n09_excluir_titulo_com_baixas_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n09@exemplo.com.br")
    caixa = executar(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (:u, '2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
    )
    titulo = executar(
        app,
        "INSERT INTO titulos_financeiros (id_empresa, tipo, valor, descricao, "
        "vencimento) VALUES (:e, 'a receber', 10.00, 'Titulo INTG N09', '2027-03-03')",
        {"e": c["id_empresa"]},
    )
    executar(
        app,
        "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
        "forma_pagamento) VALUES (:t, :c, 10.00, '2026-11-09 09:00:00', 'dinheiro')",
        {"t": titulo, "c": caixa},
    )
    assert_erro(
        app,
        "DELETE FROM titulos_financeiros WHERE id_titulo = :t",
        {"t": titulo},
        codigos=("1451", "fk_baixas_financeiras_titulo"),
    )


def test_intg_n10_excluir_caixa_com_movimentos_e_bloqueado(app, client):
    c = conta(client, "plano.intg.n10@exemplo.com.br")
    caixa = executar(
        app,
        "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
        "VALUES (:u, '2026-11-09 08:00:00', 10.00)",
        {"u": c["id_usuario"]},
    )
    executar(
        app,
        "INSERT INTO operacoes_caixa (id_caixa, id_usuario, tipo, valor, ocorrencia) "
        "VALUES (:c, :u, 'sangria', 5.00, '2026-11-09 09:00:00')",
        {"c": caixa, "u": c["id_usuario"]},
    )
    assert_erro(
        app,
        "DELETE FROM caixas WHERE id_caixa = :c",
        {"c": caixa},
        codigos=("1451", "fk_operacoes_caixa_caixa"),
    )


def test_intg_n12_trocar_empresa_de_produto_com_categoria_de_outra(app, client):
    a = conta(client, "plano.intg.n12.a@exemplo.com.br")
    b = conta(client, "plano.intg.n12.b@exemplo.com.br", CNPJ_VALIDO_2)
    cat_a = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'INTG Cat N12 A')",
        {"e": a["id_empresa"]},
    )
    prod = executar(
        app,
        "INSERT INTO produtos (id_empresa, sku, id_categoria, nome, preco) "
        "VALUES (:e, 'INTG-N12', :c, 'Produto N12', 1.00)",
        {"e": a["id_empresa"], "c": cat_a},
    )
    assert_erro(
        app,
        "UPDATE produtos SET id_empresa = :b WHERE id_produto = :p",
        {"b": b["id_empresa"], "p": prod},
        codigos=("1452", "fk_produtos_categoria"),
    )


# ---------------------------------------------------------------------------
# CAR - cargos
# ---------------------------------------------------------------------------


def test_car_n01_cargo_duplicado_viola_unique(app):
    executar(app, "INSERT INTO cargos (cargo) VALUES ('Plano Cargo Unico')")
    assert_erro(
        app,
        "INSERT INTO cargos (cargo) VALUES ('Plano Cargo Unico')",
        codigos=("1062", "uq_cargos_cargo"),
    )


def test_car_n02_cargo_diferente_apenas_em_maiusculas_viola_unique(app):
    executar(app, "INSERT INTO cargos (cargo) VALUES ('Plano Supervisor')")
    assert_erro(
        app,
        "INSERT INTO cargos (cargo) VALUES ('PLANO SUPERVISOR')",
        codigos=("1062", "uq_cargos_cargo"),
    )


def test_car_n03_cargo_diferente_apenas_por_acento_viola_unique(app):
    executar(app, "INSERT INTO cargos (cargo) VALUES ('Plano Coordenação')")
    assert_erro(
        app,
        "INSERT INTO cargos (cargo) VALUES ('Plano Coordenacao')",
        codigos=("1062", "uq_cargos_cargo"),
    )


def test_car_n04_cargo_nulo_viola_not_null(app):
    assert_erro(
        app,
        "INSERT INTO cargos (cargo) VALUES (NULL)",
        codigos=("1048", "cargo"),
    )


def test_car_n05_cargo_com_51_caracteres_viola_tamanho(app):
    assert_erro(
        app,
        "INSERT INTO cargos (cargo) VALUES (:cargo)",
        {"cargo": "Z" * 51},
        codigos=("1406", "Data too long", "cargo"),
    )


# ---------------------------------------------------------------------------
# COL - texto/collation que faltavam
# ---------------------------------------------------------------------------


def test_col_n02_preco_ambiguo_nao_e_gravado_trocado(app, client):
    c = conta(client, "plano.col.n02@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'Geral Col')",
        {"e": c["id_empresa"]},
    )
    resposta = client.post(
        "/api/produtos",
        json={
            "sku": "COL-PRC-01",
            "id_categoria": cat,
            "nome": "Produto Preco Ambiguo",
            "preco": "1.234,56",
        },
    )
    if resposta.status_code == 201:
        assert resposta.get_json()["dados"]["preco"] == "1234.56"
    else:
        assert resposta.status_code == 422


def test_col_n03_produto_com_nome_apenas_espacos_e_recusado(app, client):
    c = conta(client, "plano.col.n03@exemplo.com.br")
    cat = executar(
        app,
        "INSERT INTO categorias (id_empresa, nome) VALUES (:e, 'Geral Col Dois')",
        {"e": c["id_empresa"]},
    )
    resposta = client.post(
        "/api/produtos",
        json={
            "sku": "COL-ESP-01",
            "id_categoria": cat,
            "nome": "      ",
            "preco": 2.0,
        },
    )
    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["campos"]
