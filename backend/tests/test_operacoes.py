"""Testes do módulo de Operações (OPE) e da baixa sem parceiro.

Cobre criação de venda/compra com atualização de estoque, títulos em 1x e
parcelados, parceiro opcional, listagem/detalhe, edição transacional,
cancelamento e a integração com baixas de títulos sem parceiro.
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.apoio_baixas import abrir_caixa
from tests.apoio_parceiros import (
    EMPRESAS_COM_PARCEIROS,
    criar_parceiro,
    logar,
)

EMPRESAS = set()


@pytest.fixture(autouse=True)
def limpar_operacoes(app, banco_limpo):
    """Remove baixas, títulos, itens, operações, produtos, categorias e parceiros."""
    yield

    if not EMPRESAS:
        EMPRESAS_COM_PARCEIROS.clear()
        return

    ids = list(EMPRESAS)
    with app.app_context(), get_engine().begin() as conexao:
        consultas = [
            "DELETE FROM baixas_financeiras WHERE id_titulo IN "
            "(SELECT id_titulo FROM titulos_financeiros WHERE id_empresa IN :ids)",
            "DELETE FROM titulos_financeiros WHERE id_empresa IN :ids",
            "DELETE FROM operacao_itens WHERE id_operacao IN "
            "(SELECT o.id_operacao FROM operacoes o JOIN usuarios u "
            " ON u.id_usuario = o.id_usuario WHERE u.id_empresa IN :ids)",
            "DELETE FROM operacoes WHERE id_usuario IN "
            "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)",
            "DELETE FROM produtos WHERE id_empresa IN :ids",
            "DELETE FROM categorias WHERE id_empresa IN :ids",
            "DELETE FROM operacoes_caixa WHERE id_caixa IN "
            "(SELECT id_caixa FROM caixas WHERE aberto_por_usuario IN "
            "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids))",
            "DELETE FROM caixas WHERE aberto_por_usuario IN "
            "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)",
            "DELETE FROM interacoes WHERE id_parceiro IN "
            "(SELECT id_parceiro FROM parceiros WHERE id_empresa IN :ids)",
            "DELETE FROM parceiros WHERE id_empresa IN :ids",
        ]
        for consulta in consultas:
            conexao.execute(
                text(consulta).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            )
    EMPRESAS.clear()
    EMPRESAS_COM_PARCEIROS.clear()


def _logar(client, email="ope.a@exemplo.com.br", cnpj="11222333000181") -> dict:
    conta = logar(client, email=email, cnpj=cnpj)
    EMPRESAS.add(conta["id_empresa"])
    return conta


def _categoria(client, nome="Geral") -> int:
    resposta = client.post("/api/categorias", json={"nome": nome})
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]["id_categoria"]


def _produto(client, id_categoria: int, sku: str, *, preco="10.00", estoque=10) -> dict:
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
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


def _payload(id_produto: int, *, tipo="venda", quantidade=3, preco="10.00", **extra):
    dados = {
        "tipo": tipo,
        "id_parceiro": None,
        "ocorrencia": "2026-11-16T10:00",
        "observacoes": "Operação de teste",
        "itens": [
            {
                "id_produto": id_produto,
                "quantidade": quantidade,
                "valor_unitario": preco,
            }
        ],
        "parcelas": 1,
        "vencimento": "2026-12-16",
    }
    dados.update(extra)
    return dados


def _estoque(client, id_produto: int) -> int:
    resposta = client.get(f"/api/produtos/{id_produto}")
    return resposta.get_json()["dados"]["unidade_estoque"]


def _criar(client, payload):
    return client.post("/api/operacoes", json=payload)


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------


def test_ope_p01_venda_sem_parceiro_atualiza_estoque_e_gera_titulo(client):
    conta = _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-001", estoque=10)

    resposta = _criar(client, _payload(produto["id_produto"]))

    assert resposta.status_code == 201, resposta.get_json()
    dados = resposta.get_json()["dados"]
    assert dados["tipo"] == "venda"
    assert dados["parceiro"] is None
    assert dados["total"] == "30.00"
    assert dados["itens"][0]["quantidade"] == 3
    assert _estoque(client, produto["id_produto"]) == 7
    assert len(dados["titulos"]) == 1
    assert dados["titulos"][0]["tipo"] == "a receber"
    assert dados["titulos"][0]["valor"] == "30.00"
    assert dados["titulos"][0]["id_parceiro"] is None
    assert dados["id_operacao"] > 0

    # A operação também aparece na listagem.
    listagem = client.get("/api/operacoes").get_json()["dados"]
    assert listagem["total"] == 1
    assert listagem["operacoes"][0]["id_operacao"] == dados["id_operacao"]


def test_ope_p02_compra_com_parceiro_em_3x(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-002", estoque=2)
    parceiro = criar_parceiro(
        client, nome="Fornecedor OPE", e_cliente=False, e_fornecedor=True
    )

    resposta = _criar(
        client,
        _payload(
            produto["id_produto"],
            tipo="compra",
            quantidade=4,
            preco="2.50",
            id_parceiro=parceiro["id_parceiro"],
            parcelas=3,
            vencimento="2026-12-10",
        ),
    )

    assert resposta.status_code == 201, resposta.get_json()
    dados = resposta.get_json()["dados"]
    assert dados["total"] == "10.00"
    assert dados["parceiro"]["id_parceiro"] == parceiro["id_parceiro"]
    assert _estoque(client, produto["id_produto"]) == 6
    assert len(dados["titulos"]) == 3
    assert [titulo["valor"] for titulo in dados["titulos"]] == [
        "3.33",
        "3.33",
        "3.34",
    ]
    assert [titulo["vencimento"] for titulo in dados["titulos"]] == [
        "2026-12-10",
        "2027-01-10",
        "2027-02-10",
    ]
    assert all(
        titulo["tipo"] == "a pagar" and titulo["id_parceiro"] == parceiro["id_parceiro"]
        for titulo in dados["titulos"]
    )

    titulos = client.get("/api/titulos").get_json()["dados"]["titulos"]
    assert {titulo["id_operacao"] for titulo in titulos} == {dados["id_operacao"]}


def test_ope_n01_venda_sem_estoque_e_recusada(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-003", estoque=1)

    resposta = _criar(client, _payload(produto["id_produto"], quantidade=2))

    assert resposta.status_code == 422
    assert "itens" in resposta.get_json()["campos"]
    assert _estoque(client, produto["id_produto"]) == 1
    assert client.get("/api/operacoes").get_json()["dados"]["total"] == 0
    assert client.get("/api/titulos").get_json()["dados"]["total"] == 0


def test_ope_n02_produto_inexistente_na_empresa(client):
    _logar(client)
    id_categoria = _categoria(client)
    _produto(client, id_categoria, "OPE-004")

    resposta = _criar(client, _payload(999999))

    assert resposta.status_code == 422
    assert "itens" in resposta.get_json()["campos"]


def test_ope_n03_sem_login(client):
    assert client.get("/api/operacoes").status_code == 401
    assert _criar(client, _payload(1)).status_code == 401


# ---------------------------------------------------------------------------
# Alteração
# ---------------------------------------------------------------------------


def test_ope_p03_alterar_itens_e_parcelas_refaz_estoque_e_titulos(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-005", estoque=10)
    criada = _criar(client, _payload(produto["id_produto"], quantidade=1)).get_json()[
        "dados"
    ]

    resposta = client.patch(
        f"/api/operacoes/{criada['id_operacao']}",
        json=_payload(
            produto["id_produto"],
            quantidade=4,
            preco="5.00",
            parcelas=2,
            vencimento="2027-01-15",
        ),
    )

    assert resposta.status_code == 200, resposta.get_json()
    dados = resposta.get_json()["dados"]
    assert dados["total"] == "20.00"
    assert _estoque(client, produto["id_produto"]) == 6  # 10 - 4 (não 10 - 1)
    assert len(dados["titulos"]) == 2
    assert [titulo["valor"] for titulo in dados["titulos"]] == ["10.00", "10.00"]
    assert [titulo["vencimento"] for titulo in dados["titulos"]] == [
        "2027-01-15",
        "2027-02-15",
    ]


def test_ope_n04_alterar_operacao_cancelada_e_recusado(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-006")
    criada = _criar(client, _payload(produto["id_produto"])).get_json()["dados"]
    assert (
        client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar").status_code
        == 200
    )

    resposta = client.patch(
        f"/api/operacoes/{criada['id_operacao']}",
        json=_payload(produto["id_produto"], quantidade=2),
    )

    assert resposta.status_code == 409


# ---------------------------------------------------------------------------
# Cancelamento
# ---------------------------------------------------------------------------


def test_ope_p04_cancelar_venda_estorna_estoque_e_titulos(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-007", estoque=8)
    criada = _criar(client, _payload(produto["id_produto"], quantidade=3)).get_json()[
        "dados"
    ]

    resposta = client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar")

    assert resposta.status_code == 200, resposta.get_json()
    dados = resposta.get_json()["dados"]
    assert dados["status"] == "cancelada"
    assert _estoque(client, produto["id_produto"]) == 8
    assert all(titulo["cancelado"] is True for titulo in dados["titulos"])
    assert dados["pode_cancelar"] is False


def test_ope_n05_cancelar_compra_com_estoque_consumido_e_recusado(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-008", estoque=0)
    compra = _criar(
        client, _payload(produto["id_produto"], tipo="compra", quantidade=2)
    ).get_json()["dados"]
    # Outra venda consome todo o estoque que a compra adicionou.
    _criar(client, _payload(produto["id_produto"], tipo="venda", quantidade=2))

    resposta = client.post(
        f"/api/operacoes/{compra['id_operacao']}/cancelar"
    )

    assert resposta.status_code == 422
    assert _estoque(client, produto["id_produto"]) == 0
    assert (
        client.get(f"/api/operacoes/{compra['id_operacao']}").get_json()["dados"][
            "status"
        ]
        == "concluida"
    )


# ---------------------------------------------------------------------------
# Listagem/filtros e integração com baixa sem parceiro
# ---------------------------------------------------------------------------


def test_ope_p05_listar_filtra_por_tipo_status_e_busca(client):
    _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-009")
    venda = _criar(client, _payload(produto["id_produto"])).get_json()["dados"]
    cliente = criar_parceiro(client, nome="Cliente Busca OPE")
    compra = _criar(
        client,
        _payload(
            produto["id_produto"],
            tipo="compra",
            id_parceiro=cliente["id_parceiro"],
            ocorrencia="2026-11-17T10:00",
        ),
    ).get_json()["dados"]

    vendas = client.get("/api/operacoes?tipo=venda").get_json()["dados"]
    assert [op["id_operacao"] for op in vendas["operacoes"]] == [venda["id_operacao"]]

    busca = client.get("/api/operacoes?busca=Busca OPE").get_json()["dados"]
    assert [op["id_operacao"] for op in busca["operacoes"]] == [compra["id_operacao"]]

    detalhe = client.get(f"/api/operacoes/{compra['id_operacao']}").get_json()["dados"]
    assert detalhe["parceiro"]["nome"] == "Cliente Busca OPE"


def test_ope_p06_titulo_gerado_sem_parceiro_pode_receber_baixa(app, client):
    conta = _logar(client)
    id_categoria = _categoria(client)
    produto = _produto(client, id_categoria, "OPE-010")
    operacao = _criar(client, _payload(produto["id_produto"])).get_json()["dados"]
    id_caixa = abrir_caixa(app, conta["id_usuario"])

    resposta = client.post(
        "/api/baixas",
        json={
            "id_titulo": operacao["titulos"][0]["id_titulo"],
            "id_caixa": id_caixa,
            "valor": operacao["titulos"][0]["valor"],
            "forma_pagamento": "dinheiro",
            "realizado_em": "2026-11-16 12:00",
        },
    )

    assert resposta.status_code == 201, resposta.get_json()
    assert resposta.get_json()["dados"]["parceiro"] is None
