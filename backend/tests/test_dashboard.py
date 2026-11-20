"""Testes do resumo agregado do dashboard (performance do front)."""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.helpers import CNPJ_VALIDO, CNPJ_VALIDO_2, criar_conta, entrar

SENHA = "Senha#Teste1"
EMPRESAS_CRIADAS: set[int] = set()


@pytest.fixture(autouse=True)
def limpar_dados(app, banco_limpo):
    """Apaga produtos/categorias antes do banco_limpo remover usuários/empresas."""
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


def _logar(client, email="dash.a@exemplo.com.br", cnpj=CNPJ_VALIDO) -> int:
    conta = criar_conta(client, email=email, senha=SENHA, cnpj=cnpj)
    assert entrar(client, email, SENHA).status_code == 200
    id_empresa = conta["empresa"]["id_empresa"]
    EMPRESAS_CRIADAS.add(id_empresa)
    return id_empresa


def _categoria(client, nome: str = "Geral") -> int:
    resposta = client.post("/api/categorias", json={"nome": nome})
    assert resposta.status_code == 201
    return resposta.get_json()["dados"]["id_categoria"]


def _produto(client, id_categoria: int, sku: str, preco, estoque: int):
    resposta = client.post(
        "/api/produtos",
        json={
            "sku": sku,
            "id_categoria": id_categoria,
            "nome": f"Produto {sku}",
            "unidade_estoque": estoque,
            "preco": preco,
        },
    )
    assert resposta.status_code == 201
    return resposta.get_json()["dados"]


def test_dashboard_sem_login(client):
    assert client.get("/api/dashboard/resumo").status_code == 401


def test_dashboard_resumo_da_empresa(client):
    _logar(client)
    id_categoria = _categoria(client)
    _produto(client, id_categoria, "DASH-1", 3.5, 10)
    _produto(client, id_categoria, "DASH-2", 10, 2)

    resposta = client.get("/api/dashboard/resumo")

    assert resposta.status_code == 200
    dados = resposta.get_json()["dados"]
    assert dados["produtos"] == 2
    assert dados["categorias"] == 1
    assert dados["valor_estoque"] == "55.00"  # 3.5*10 + 10*2


def test_dashboard_nao_mistura_empresas(app, client):
    _logar(client)
    categoria_a = _categoria(client)
    _produto(client, categoria_a, "DASH-A", 5, 1)

    outro = app.test_client()
    _logar(outro, "dash.b@exemplo.com.br", CNPJ_VALIDO_2)
    categoria_b = _categoria(outro, "Outra")
    _produto(outro, categoria_b, "DASH-B1", 2, 4)
    _produto(outro, categoria_b, "DASH-B2", 3, 2)

    dados_a = client.get("/api/dashboard/resumo").get_json()["dados"]
    dados_b = outro.get("/api/dashboard/resumo").get_json()["dados"]

    assert dados_a == {
        "produtos": 1,
        "categorias": 1,
        "parceiros": 0,
        "valor_estoque": "5.00",
    }
    assert dados_b == {
        "produtos": 2,
        "categorias": 1,
        "parceiros": 0,
        "valor_estoque": "14.00",  # 2*4 + 3*2
    }
