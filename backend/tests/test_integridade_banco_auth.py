"""Testes de integridade do banco envolvendo as tabelas de autenticação.

Cobre os casos do plano V1.2 que tocam ``empresas``, ``cargos`` e ``usuarios``
(BDD, FKN e INTG). Diferente dos demais módulos, aqui o SQL é executado direto
no MySQL, como o plano prevê para os casos de banco.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from src.app.db import get_engine
from tests.helpers import cadastrar_ok, criar_conta, empresa_valida, usuario_valido

pytestmark = pytest.mark.banco


def executar_sql(app, sql: str, params: dict | None = None):
    """Executa SQL direto no MySQL, em uma transação própria (commit/rollback)."""
    with app.app_context():
        with get_engine().begin() as conexao:
            resultado = conexao.execute(text(sql), params or {})
            return resultado.fetchall() if resultado.returns_rows else None


def assert_erro_banco(
    app,
    sql: str,
    params: dict | None = None,
    *,
    codigos: tuple[str, ...],
):
    """Executa o SQL e exige um erro do MySQL contendo um dos códigos informados."""
    with pytest.raises((IntegrityError, OperationalError)) as excinfo:
        executar_sql(app, sql, params)
    mensagem = str(excinfo.value)
    assert any(codigo in mensagem for codigo in codigos), mensagem


# ---------------------------------------------------------------------------
# BDD - Integridade do Banco (parte de autenticação)
# ---------------------------------------------------------------------------


def test_bdd_p01_criado_em_preenchido_automaticamente(app):
    """BDD-P01: criado_em da empresa recebe a data/hora atual quando omitido."""
    executar_sql(
        app,
        "INSERT INTO empresas (razao_social, cnpj) "
        "VALUES ('BD Empresa Default', 'BD000000000141')",
    )

    linha = executar_sql(
        app,
        "SELECT criado_em FROM empresas WHERE cnpj = :cnpj",
        {"cnpj": "BD000000000141"},
    )

    assert linha is not None
    assert linha[0][0] is not None


def test_bdd_p02_admin_sistema_false_quando_omitido(app, client):
    """BDD-P02: admin_sistema assume FALSE quando omitido no INSERT."""
    dados = criar_conta(
        client,
        email="bd.dono.default@exemplo.com.br",
        senha="Bd#Default1",
        nome="BD Dono Default",
        cnpj="11222333000181",
    )
    empresa_id = dados["empresa"]["id_empresa"]
    cargo_id = dados["usuario"]["id_cargo"]

    executar_sql(
        app,
        "INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha) "
        "VALUES (:empresa, :cargo, 'BD Usuario Default', "
        "'bd.default@exemplo.com.br', 'hash-qualquer')",
        {"empresa": empresa_id, "cargo": cargo_id},
    )

    linha = executar_sql(
        app,
        "SELECT admin_sistema FROM usuarios WHERE email = :email",
        {"email": "bd.default@exemplo.com.br"},
    )

    assert linha is not None
    assert linha[0][0] in (0, False)


def test_bdd_p07_texto_com_acentos_e_emoji_sem_perda(client, app):
    """BDD-P07: texto com acentos/emoji é gravado e lido sem perda (utf8mb4)."""
    razao_social = "Água, Café e Pão 🍞"

    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social=razao_social, cnpj="44555666000181"
        ),
        usuario=usuario_valido(
            nome="BD Utf8", email="bd.utf8@exemplo.com.br", senha="Bd#Utf82026"
        ),
    )

    linha = executar_sql(
        app,
        "SELECT razao_social FROM empresas WHERE id_empresa = :id",
        {"id": dados["empresa"]["id_empresa"]},
    )

    assert linha is not None
    assert linha[0][0] == razao_social


def test_bdd_p08_hash_de_senha_nao_e_a_senha_em_texto(client, app):
    """BDD-P08: hash_senha armazenado difere da senha em texto puro."""
    senha = "Hash#Check2026"

    dados = criar_conta(
        client,
        email="bd.hash@exemplo.com.br",
        senha=senha,
        nome="BD Hash",
        cnpj="11222333000181",
    )

    linha = executar_sql(
        app,
        "SELECT hash_senha FROM usuarios WHERE id_usuario = :id",
        {"id": dados["usuario"]["id_usuario"]},
    )

    assert linha is not None
    hash_senha = linha[0][0]
    assert hash_senha != senha
    assert senha not in hash_senha


def test_bdd_n01_admin_sistema_com_valor_2_viola_check(app, client):
    """BDD-N01: admin_sistema = 2 viola o CHECK do schema."""
    dados = criar_conta(
        client,
        email="bd.n01@exemplo.com.br",
        senha="Bd#N01Pass1",
        nome="BD N01",
        cnpj="11222333000181",
    )

    assert_erro_banco(
        app,
        "INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha, "
        "admin_sistema) VALUES (:empresa, :cargo, 'BD Admin Invalido', "
        "'bd.admin2@exemplo.com.br', 'h', 2)",
        {
            "empresa": dados["empresa"]["id_empresa"],
            "cargo": dados["usuario"]["id_cargo"],
        },
        codigos=("3819", "chk_usuarios_admin_sistema"),
    )


def test_bdd_n05_cnpj_duplicado_viola_unique(app):
    """BDD-N05: CNPJ duplicado viola a UNIQUE uq_empresas_cnpj."""
    executar_sql(
        app,
        "INSERT INTO empresas (razao_social, cnpj) "
        "VALUES ('BD Empresa Unica', 'BD000000000222')",
    )

    assert_erro_banco(
        app,
        "INSERT INTO empresas (razao_social, cnpj) "
        "VALUES ('BD Empresa Duplicada', 'BD000000000222')",
        codigos=("1062", "uq_empresas_cnpj"),
    )


def test_bdd_n06_excluir_empresa_com_usuarios_e_bloqueado(app, client):
    """BDD-N06: DELETE de empresa com usuários é bloqueado (RESTRICT)."""
    dados = criar_conta(
        client,
        email="bd.n06@exemplo.com.br",
        senha="Bd#N06Pass1",
        nome="BD N06",
        cnpj="11222333000181",
    )

    assert_erro_banco(
        app,
        "DELETE FROM empresas WHERE id_empresa = :id",
        {"id": dados["empresa"]["id_empresa"]},
        codigos=("1451", "fk_usuarios_empresa"),
    )


# ---------------------------------------------------------------------------
# FKN - Chaves Estrangeiras e Campos Obrigatórios (usuários)
# ---------------------------------------------------------------------------


def test_fkn_n01_usuario_com_empresa_inexistente(app, client):
    """FKN-N01: INSERT de usuário com empresa inexistente viola a FK."""
    dados = criar_conta(
        client,
        email="fkn.n01@exemplo.com.br",
        senha="Fkn#N01Pass",
        nome="FKN N01",
        cnpj="11222333000181",
    )

    assert_erro_banco(
        app,
        "INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha) "
        "VALUES (999901, :cargo, 'FK Empresa Inexistente', "
        "'fk.empresa@exemplo.com.br', 'h')",
        {"cargo": dados["usuario"]["id_cargo"]},
        codigos=("1452", "fk_usuarios_empresa"),
    )


def test_fkn_n02_usuario_com_cargo_inexistente(app, client):
    """FKN-N02: INSERT de usuário com cargo inexistente viola a FK."""
    dados = criar_conta(
        client,
        email="fkn.n02@exemplo.com.br",
        senha="Fkn#N02Pass",
        nome="FKN N02",
        cnpj="11222333000181",
    )

    assert_erro_banco(
        app,
        "INSERT INTO usuarios (id_empresa, id_cargo, nome, email, hash_senha) "
        "VALUES (:empresa, 999902, 'FK Cargo Inexistente', "
        "'fk.cargo@exemplo.com.br', 'h')",
        {"empresa": dados["empresa"]["id_empresa"]},
        codigos=("1452", "fk_usuarios_cargo"),
    )


# ---------------------------------------------------------------------------
# INTG - Integridade Referencial (RESTRICT) das tabelas de autenticação
# ---------------------------------------------------------------------------


def test_intg_n01_excluir_cargo_com_usuarios_e_bloqueado(app, client):
    """INTG-N01: DELETE de cargo vinculado a usuários é bloqueado (RESTRICT)."""
    dados = criar_conta(
        client,
        email="intg.n01@exemplo.com.br",
        senha="Intg#N01Pass",
        nome="INTG N01",
        cnpj="11222333000181",
    )

    assert_erro_banco(
        app,
        "DELETE FROM cargos WHERE id_cargo = :id",
        {"id": dados["usuario"]["id_cargo"]},
        codigos=("1451", "fk_usuarios_cargo"),
    )


def test_intg_n11_alterar_pk_de_empresa_com_dependentes_e_bloqueado(app, client):
    """INTG-N11: UPDATE da PK de empresa com usuários é bloqueado (RESTRICT)."""
    dados = criar_conta(
        client,
        email="intg.n11@exemplo.com.br",
        senha="Intg#N11Pass",
        nome="INTG N11",
        cnpj="11222333000181",
    )

    assert_erro_banco(
        app,
        "UPDATE empresas SET id_empresa = 9399 WHERE id_empresa = :id",
        {"id": dados["empresa"]["id_empresa"]},
        codigos=("1451", "fk_usuarios_empresa"),
    )
