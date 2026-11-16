"""Testes do módulo de produtos (criar e alterar).

Rodam contra o MySQL real, como o restante da suíte. Como ``produtos`` e
``categorias`` referenciam ``empresas`` com ON DELETE RESTRICT, o fixture
``limpar_produtos`` apaga primeiro os produtos/categorias criados aqui; só
depois o ``banco_limpo`` (conftest) consegue apagar as empresas de teste.
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.helpers import CNPJ_VALIDO, CNPJ_VALIDO_2, criar_conta, entrar

SENHA = "Senha#Teste1"
EMPRESAS_COM_PRODUTOS: set[int] = set()


@pytest.fixture(autouse=True)
def limpar_produtos(app, banco_limpo):
    """Remove produtos e categorias das empresas criadas pelo teste (ao final)."""
    yield
    if not EMPRESAS_COM_PRODUTOS:
        return
    ids = list(EMPRESAS_COM_PRODUTOS)
    with app.app_context(), get_engine().begin() as conexao:
        for tabela in ("produtos", "categorias"):
            conexao.execute(
                text(f"DELETE FROM {tabela} WHERE id_empresa IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": ids},
            )
    EMPRESAS_COM_PRODUTOS.clear()


def _categoria(app, id_empresa: int, nome: str = "Geral") -> int:
    """Cria uma categoria direto no banco (ainda não há rota de categorias)."""
    EMPRESAS_COM_PRODUTOS.add(id_empresa)
    with app.app_context(), get_engine().begin() as conexao:
        resultado = conexao.execute(
            text("INSERT INTO categorias (id_empresa, nome) VALUES (:e, :n)"),
            {"e": id_empresa, "n": nome},
        )
        return resultado.lastrowid


def _logar(client, email="prod.a@exemplo.com.br", cnpj=CNPJ_VALIDO) -> int:
    """Cria empresa + usuário, faz login e devolve o id_empresa."""
    conta = criar_conta(client, email=email, senha=SENHA, cnpj=cnpj)
    assert entrar(client, email, SENHA).status_code == 200
    return conta["empresa"]["id_empresa"]


def _payload(id_categoria: int, **extra) -> dict:
    dados = {
        "sku": "CAN-001",
        "id_categoria": id_categoria,
        "nome": "Caneta azul",
        "descricao": "Caneta esferográfica",
        "unidade_estoque": 10,
        "preco": 3.5,
    }
    dados.update(extra)
    return dados


# ---------------------------------------------------------------------------
# Criar produto
# ---------------------------------------------------------------------------


def test_prd_p01_criar_produto_valido(app, client):
    id_empresa = _logar(client)
    id_cat = _categoria(app, id_empresa)

    resposta = client.post("/api/produtos", json=_payload(id_cat))
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 201
    assert dados["id_empresa"] == id_empresa  # veio da sessão
    assert dados["preco"] == "3.50"
    assert dados["unidade_estoque"] == 10


def test_prd_p02_estoque_omitido_comeca_em_zero(app, client):
    id_cat = _categoria(app, _logar(client))
    corpo = _payload(id_cat)
    del corpo["unidade_estoque"]

    resposta = client.post("/api/produtos", json=corpo)

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["unidade_estoque"] == 0


def test_prd_n01_criar_sem_login(client):
    resposta = client.post("/api/produtos", json=_payload(1))
    assert resposta.status_code == 401


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("sku", ""),
        ("sku", "S" * 65),
        ("nome", "  "),
        ("nome", "N" * 151),
        ("descricao", "D" * 501),
        ("unidade_estoque", -1),
        ("unidade_estoque", 1.5),
        ("preco", -0.01),
        ("preco", 1.005),
        ("preco", "abc"),
        ("preco", 10_000_000_000),
        ("id_empresa", 999),  # empresa nunca vem do corpo
    ],
)
def test_prd_n02_criar_com_campo_invalido(app, client, campo, valor):
    id_cat = _categoria(app, _logar(client))

    resposta = client.post("/api/produtos", json=_payload(id_cat, **{campo: valor}))

    assert resposta.status_code == 422
    assert campo in resposta.get_json()["campos"]


def test_prd_n03_sku_duplicado_na_mesma_empresa(app, client):
    id_cat = _categoria(app, _logar(client))
    assert client.post("/api/produtos", json=_payload(id_cat)).status_code == 201

    # O banco ignora maiúsculas/minúsculas no SKU.
    resposta = client.post("/api/produtos", json=_payload(id_cat, sku="can-001"))

    assert resposta.status_code == 409


def test_prd_p03_mesmo_sku_em_empresas_diferentes(app, client):
    id_cat_a = _categoria(app, _logar(client))
    assert client.post("/api/produtos", json=_payload(id_cat_a)).status_code == 201

    outro = app.test_client()
    id_cat_b = _categoria(
        app, _logar(outro, "prod.b@exemplo.com.br", CNPJ_VALIDO_2), "Outra"
    )

    assert outro.post("/api/produtos", json=_payload(id_cat_b)).status_code == 201


def test_prd_n04_categoria_de_outra_empresa(app, client):
    _logar(client)
    outro = app.test_client()
    id_empresa_b = _logar(outro, "prod.b@exemplo.com.br", CNPJ_VALIDO_2)
    id_cat_b = _categoria(app, id_empresa_b)

    resposta = client.post("/api/produtos", json=_payload(id_cat_b))

    assert resposta.status_code == 422
    assert "id_categoria" in resposta.get_json()["campos"]


# ---------------------------------------------------------------------------
# Alterar produto
# ---------------------------------------------------------------------------


def _criar(client, app) -> int:
    id_empresa = _logar(client)
    id_cat = _categoria(app, id_empresa)
    return client.post("/api/produtos", json=_payload(id_cat)).get_json()["dados"][
        "id_produto"
    ]


def test_prd_p04_alterar_preco_e_estoque(app, client):
    id_produto = _criar(client, app)

    resposta = client.patch(
        f"/api/produtos/{id_produto}", json={"preco": "12,90", "unidade_estoque": 0}
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["preco"] == "12.90"
    assert dados["unidade_estoque"] == 0
    assert dados["nome"] == "Caneta azul"  # o que não foi enviado não muda


def test_prd_p05_alterar_nome_e_limpar_descricao(app, client):
    id_produto = _criar(client, app)

    resposta = client.patch(
        f"/api/produtos/{id_produto}", json={"nome": " Caneta preta ", "descricao": None}
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["nome"] == "Caneta preta"
    assert dados["descricao"] is None


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"nome": ""},
        {"preco": -1},
        {"unidade_estoque": -5},
        {"sku": "NOVO"},  # SKU não é editável
        {"id_empresa": 2},
    ],
)
def test_prd_n05_alterar_com_dados_invalidos(app, client, corpo):
    id_produto = _criar(client, app)

    resposta = client.patch(f"/api/produtos/{id_produto}", json=corpo)

    assert resposta.status_code == 422


def test_prd_n06_alterar_produto_de_outra_empresa(app, client):
    id_produto = _criar(client, app)
    outro = app.test_client()
    _logar(outro, "prod.b@exemplo.com.br", CNPJ_VALIDO_2)

    resposta = outro.patch(f"/api/produtos/{id_produto}", json={"preco": 1})

    assert resposta.status_code == 404
    # e o produto original continua intacto
    original = client.get(f"/api/produtos/{id_produto}").get_json()["dados"]
    assert original["preco"] == "3.50"


def test_prd_n07_alterar_sem_login(client):
    assert client.patch("/api/produtos/1", json={"preco": 1}).status_code == 401


def test_prd_n08_alterar_produto_inexistente(app, client):
    _logar(client)
    assert client.patch("/api/produtos/999999", json={"preco": 1}).status_code == 404
