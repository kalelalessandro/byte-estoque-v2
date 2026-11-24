"""Testes do módulo CAT - Categorias (plano de testes V1.2).

Cobre os 5 casos positivos e os 9 negativos de categorias. Rodam contra o MySQL
real; o fixture ``limpar_categorias`` apaga produtos/categorias das empresas de
teste antes do ``banco_limpo`` (por causa das FKs com RESTRICT).
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.helpers import CNPJ_VALIDO, CNPJ_VALIDO_2, criar_conta, entrar

SENHA = "Senha#Teste1"
EMPRESAS_CRIADAS: set[int] = set()


@pytest.fixture(autouse=True)
def limpar_categorias(app, banco_limpo):
    """Remove produtos e categorias das empresas criadas por este arquivo."""
    yield

    if not EMPRESAS_CRIADAS:
        return

    ids = list(EMPRESAS_CRIADAS)
    with app.app_context(), get_engine().begin() as conexao:
        for tabela in ("produtos", "categorias"):
            conexao.execute(
                text(f"DELETE FROM {tabela} WHERE id_empresa IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": ids},
            )
    EMPRESAS_CRIADAS.clear()


def _logar(client, email="cat.a@exemplo.com.br", cnpj=CNPJ_VALIDO) -> int:
    """Cria conta + empresa, faz login e devolve o id_empresa."""
    conta = criar_conta(client, email=email, senha=SENHA, cnpj=cnpj)
    assert entrar(client, email, SENHA).status_code == 200
    EMPRESAS_CRIADAS.add(conta["empresa"]["id_empresa"])
    return conta["empresa"]["id_empresa"]


def _criar(client, nome: str):
    return client.post("/api/categorias", json={"nome": nome})


def _listar(client) -> list[dict]:
    return client.get("/api/categorias").get_json()["dados"]["categorias"]


# ---------------------------------------------------------------------------
# CAT - positivos
# ---------------------------------------------------------------------------


def test_cat_p01_criar_categoria_valida(client):
    _logar(client)

    resposta = _criar(client, "  Ferragens Leves  ")
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 201
    assert dados["nome"] == "Ferragens Leves"
    assert "Ferragens Leves" in [categoria["nome"] for categoria in _listar(client)]


def test_cat_p02_criar_categoria_100_caracteres(client):
    _logar(client)
    nome = "K" * 100

    resposta = _criar(client, nome)

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["nome"] == nome


def test_cat_p03_mesma_categoria_em_outra_empresa(app, client):
    _logar(client)
    outro = app.test_client()
    _logar(outro, "cat.b@exemplo.com.br", CNPJ_VALIDO_2)

    primeira = _criar(client, "Papelaria Compartilhada")
    segunda = _criar(outro, "Papelaria Compartilhada")

    assert primeira.status_code == 201
    assert segunda.status_code == 201
    assert (
        primeira.get_json()["dados"]["id_categoria"]
        != segunda.get_json()["dados"]["id_categoria"]
    )


def test_cat_p04_renomear_categoria(client):
    _logar(client)
    criada = _criar(client, "Limpeza Antiga").get_json()["dados"]

    resposta = client.patch(
        f"/api/categorias/{criada['id_categoria']}",
        json={"nome": "Limpeza e Higiene"},
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["nome"] == "Limpeza e Higiene"
    assert "Limpeza e Higiene" in [
        categoria["nome"] for categoria in _listar(client)
    ]


def test_cat_p05_produto_continua_vinculado_apos_renomear(client):
    _logar(client)
    categoria = _criar(client, "Bebidas Antiga").get_json()["dados"]

    produto = client.post(
        "/api/produtos",
        json={
            "sku": "CAT-VINC-01",
            "id_categoria": categoria["id_categoria"],
            "nome": "Produto da categoria",
            "preco": 1.5,
        },
    ).get_json()["dados"]

    resposta = client.patch(
        f"/api/categorias/{categoria['id_categoria']}",
        json={"nome": "Bebidas e Sucos"},
    )
    assert resposta.status_code == 200

    detalhe = client.get(f"/api/produtos/{produto['id_produto']}").get_json()["dados"]
    assert detalhe["id_categoria"] == categoria["id_categoria"]
    assert detalhe["categoria_nome"] == "Bebidas e Sucos"

    renomeada = next(
        item
        for item in _listar(client)
        if item["id_categoria"] == categoria["id_categoria"]
    )
    assert renomeada["produtos_count"] == 1


# ---------------------------------------------------------------------------
# CAT - negativos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "campo"),
    [
        ("", "nome"),
        ("    ", "nome"),
        ("L" * 101, "nome"),
    ],
    ids=["CAT-N01-nome-vazio", "CAT-N02-so-espacos", "CAT-N03-101-caracteres"],
)
def test_cat_negativos_criacao(client, nome, campo):
    _logar(client)

    resposta = _criar(client, nome)

    assert resposta.status_code == 422
    assert campo in resposta.get_json()["campos"]


def test_cat_n04_nome_duplicado_mesma_empresa(client):
    _logar(client)
    _criar(client, "Brinquedos Educativos")

    resposta = _criar(client, "Brinquedos Educativos")

    assert resposta.status_code == 409
    assert "nome" in resposta.get_json()["campos"]


def test_cat_n05_duplicado_por_acento_e_caixa(client):
    _logar(client)
    _criar(client, "Eletrodomésticos")

    resposta = _criar(client, "ELETRODOMESTICOS")

    assert resposta.status_code == 409
    assert "nome" in resposta.get_json()["campos"]


def test_cat_n06_renomear_para_nome_existente(client):
    _logar(client)
    primeira = _criar(client, "Móveis Escritório").get_json()["dados"]
    _criar(client, "Móveis Sala")

    resposta = client.patch(
        f"/api/categorias/{primeira['id_categoria']}",
        json={"nome": "Móveis Sala"},
    )

    assert resposta.status_code == 409
    assert "nome" in resposta.get_json()["campos"]


def test_cat_n07_renomear_com_nome_vazio(client):
    _logar(client)
    categoria = _criar(client, "Têxtil Base").get_json()["dados"]

    resposta = client.patch(
        f"/api/categorias/{categoria['id_categoria']}", json={"nome": ""}
    )

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["campos"]


def test_cat_n08_renomear_com_101_caracteres(client):
    _logar(client)
    categoria = _criar(client, "Vidros Base").get_json()["dados"]

    resposta = client.patch(
        f"/api/categorias/{categoria['id_categoria']}", json={"nome": "M" * 101}
    )

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["campos"]


def test_cat_n09_categorias_de_outra_empresa_nao_aparecem(app, client):
    _logar(client)
    _criar(client, "Categoria da Minha Empresa")
    outro = app.test_client()
    _logar(outro, "cat.b@exemplo.com.br", CNPJ_VALIDO_2)
    _criar(outro, "Exclusiva Empresa Rival")

    nomes = [categoria["nome"] for categoria in _listar(client)]

    assert "Categoria da Minha Empresa" in nomes
    assert "Exclusiva Empresa Rival" not in nomes


# ---------------------------------------------------------------------------
# Exclusão segura de categorias (casos CAT-P06, CAT-N10, CAT-N11 e CAT-N12)
# ---------------------------------------------------------------------------


def test_cat_p06_apagar_categoria_sem_produtos(client):
    """CAT-P06: categoria sem produtos pode ser apagada."""
    _logar(client)
    categoria = _criar(client, "Categoria Criada Sem Querer").get_json()["dados"]

    resposta = client.delete(f"/api/categorias/{categoria['id_categoria']}")

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["id_categoria"] == categoria["id_categoria"]
    assert "Categoria Criada Sem Querer" not in [
        c["nome"] for c in _listar(client)
    ]


def test_cat_n10_nao_apagar_categoria_com_produtos(client):
    """CAT-N10: categoria com produtos vinculados é bloqueada (409)."""
    _logar(client)
    categoria = _criar(client, "Categoria Com Produto").get_json()["dados"]
    produto = client.post(
        "/api/produtos",
        json={
            "sku": "CAT-DEL-01",
            "id_categoria": categoria["id_categoria"],
            "nome": "Produto da categoria",
            "preco": 1.5,
        },
    ).get_json()["dados"]

    resposta = client.delete(f"/api/categorias/{categoria['id_categoria']}")

    assert resposta.status_code == 409
    assert "produtos" in resposta.get_json()["erro"].lower()
    assert categoria["nome"] in [c["nome"] for c in _listar(client)]
    assert client.get(f"/api/produtos/{produto['id_produto']}").status_code == 200


def test_cat_n11_nao_apagar_categoria_de_outra_empresa(app, client):
    """CAT-N11: categoria de outra empresa não pode ser apagada (404)."""
    _logar(client)
    categoria = _criar(client, "Categoria da Empresa A").get_json()["dados"]

    outro = app.test_client()
    _logar(outro, "cat.b@exemplo.com.br", CNPJ_VALIDO_2)

    resposta = outro.delete(f"/api/categorias/{categoria['id_categoria']}")

    assert resposta.status_code == 404
    assert "Categoria da Empresa A" in [c["nome"] for c in _listar(client)]


def test_cat_n12_apagar_sem_login(client):
    """CAT-N12: exclusão exige sessão."""
    assert client.delete("/api/categorias/1").status_code == 401
