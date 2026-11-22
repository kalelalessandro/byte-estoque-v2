"""Testes do módulo de Operações (OPE) e da baixa sem parceiro.

Cobre criação de venda/compra com atualização de estoque, títulos em 1x e
parcelados, parceiro opcional, listagem/detalhe, edição transacional,
cancelamento e a integração com baixas de títulos sem parceiro.
"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.apoio_baixas import abrir_caixa
from tests.apoio_parceiros import (
    EMPRESAS_COM_PARCEIROS,
    criar_parceiro,
    logar,
)
from tests.helpers import CNPJ_VALIDO_2

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
    """OPE-P02/OPE-P11: compra parcelada gera títulos a pagar."""
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
    """OPE-N01/OPE-N07: venda acima do estoque é recusada sem alterar nada."""
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


# ---------------------------------------------------------------------------
# Casos do plano V1.4 ainda sem teste específico
# ---------------------------------------------------------------------------


def test_ope_p01_venda_com_parceiro_cliente(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P01-CLI")
    cliente = criar_parceiro(client, nome="Cliente OPE P01", e_cliente=True)

    resposta = _criar(
        client, _payload(produto["id_produto"], id_parceiro=cliente["id_parceiro"])
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["parceiro"]["nome"] == "Cliente OPE P01"


def test_ope_p03_venda_sem_informar_parceiro(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P03-SEM")

    resposta = _criar(client, _payload(produto["id_produto"], id_parceiro=None))

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["parceiro"] is None
    assert len(resposta.get_json()["dados"]["titulos"]) == 1


def test_ope_p04_venda_com_tres_itens(client):
    _logar(client)
    cat = _categoria(client)
    p1 = _produto(client, cat, "OPE-P04-A", estoque=5)
    p2 = _produto(client, cat, "OPE-P04-B", estoque=5)
    p3 = _produto(client, cat, "OPE-P04-C", estoque=5)
    payload = _payload(p1["id_produto"], quantidade=1, preco="2.00")
    payload["itens"] = [
        {"id_produto": p1["id_produto"], "quantidade": 1, "valor_unitario": "2.00"},
        {"id_produto": p2["id_produto"], "quantidade": 2, "valor_unitario": "3.00"},
        {"id_produto": p3["id_produto"], "quantidade": 3, "valor_unitario": "4.00"},
    ]

    resposta = _criar(client, payload)

    assert resposta.status_code == 201, resposta.get_json()
    dados = resposta.get_json()["dados"]
    assert dados["total"] == "20.00"
    assert _estoque(client, p1["id_produto"]) == 4
    assert _estoque(client, p2["id_produto"]) == 3
    assert _estoque(client, p3["id_produto"]) == 2


def test_ope_p07_preco_alterado_depois_nao_muda_item(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P07", preco="10.00", estoque=5)
    criada = _criar(client, _payload(produto["id_produto"], quantidade=1, preco="10.00"))
    assert criada.status_code == 201
    operacao = criada.get_json()["dados"]

    client.patch(f"/api/produtos/{produto['id_produto']}", json={"preco": 99.0})
    detalhe = client.get(f"/api/operacoes/{operacao['id_operacao']}").get_json()["dados"]

    assert detalhe["itens"][0]["valor_unitario"] == "10.00"
    assert detalhe["total"] == "10.00"


def test_ope_p08_venda_consome_todo_o_estoque(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P08", estoque=2)
    criada = _criar(client, _payload(produto["id_produto"], quantidade=2))

    assert criada.status_code == 201
    assert _estoque(client, produto["id_produto"]) == 0


def test_ope_p09_produto_duplicado_e_recusado(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P09")
    payload = _payload(produto["id_produto"], quantidade=1)
    payload["itens"].append(
        {"id_produto": produto["id_produto"], "quantidade": 2, "valor_unitario": "10.00"}
    )

    resposta = _criar(client, payload)

    assert resposta.status_code == 422
    assert "itens" in resposta.get_json()["campos"]


def test_ope_p10_venda_parcelada_gera_titulos_a_receber(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P10")
    criada = _criar(
        client,
        _payload(
            produto["id_produto"],
            quantidade=3,
            preco="10.00",
            parcelas=3,
            vencimento="2026-12-16",
        ),
    )

    assert criada.status_code == 201
    titulos = criada.get_json()["dados"]["titulos"]
    assert len(titulos) == 3
    assert all(titulo["tipo"] == "a receber" for titulo in titulos)
    assert [titulo["valor"] for titulo in titulos] == ["10.00", "10.00", "10.00"]


def test_ope_p11_compra_parcelada_gera_titulos_a_pagar(client):
    """OPE-P11: compra parcelada gera um título a pagar por parcela."""
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P11", estoque=0)

    resposta = _criar(
        client,
        _payload(
            produto["id_produto"],
            tipo="compra",
            quantidade=3,
            preco="10.00",
            parcelas=3,
            vencimento="2026-12-16",
        ),
    )

    assert resposta.status_code == 201, resposta.get_json()
    titulos = resposta.get_json()["dados"]["titulos"]
    assert len(titulos) == 3
    assert all(titulo["tipo"] == "a pagar" for titulo in titulos)
    assert [titulo["valor"] for titulo in titulos] == ["10.00", "10.00", "10.00"]


def test_ope_p12_sem_parcelas_gera_um_titulo(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P12")
    payload = _payload(produto["id_produto"])
    payload.pop("parcelas")

    resposta = _criar(client, payload)

    assert resposta.status_code == 201
    assert len(resposta.get_json()["dados"]["titulos"]) == 1


def test_ope_p14_cancelar_venda_concluida(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P14", estoque=4)
    criada = _criar(client, _payload(produto["id_produto"], quantidade=2)).get_json()[
        "dados"
    ]

    resposta = client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar")

    assert resposta.status_code == 200
    assert _estoque(client, produto["id_produto"]) == 4
    assert all(t["cancelado"] for t in resposta.get_json()["dados"]["titulos"])


def test_ope_p15_cancelar_compra_concluida(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P15", estoque=0)
    criada = _criar(
        client,
        _payload(produto["id_produto"], tipo="compra", quantidade=3),
    ).get_json()["dados"]

    resposta = client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar")

    assert resposta.status_code == 200
    assert _estoque(client, produto["id_produto"]) == 0


def test_ope_p16_ocorrencia_e_usuario_responsavel(client):
    conta = _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-P16")
    payload = _payload(produto["id_produto"], ocorrencia="2026-11-16T10:30")

    criada = _criar(client, payload)

    dados = criada.get_json()["dados"]
    assert dados["ocorrencia"].startswith("2026-11-16T10:30")
    assert dados["usuario"]["id_usuario"] == conta["id_usuario"]


def test_ope_n01_operacao_sem_nenhum_item(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N01")
    payload = _payload(produto["id_produto"])
    payload["itens"] = []

    resposta = _criar(client, payload)

    assert resposta.status_code == 422
    assert "itens" in resposta.get_json()["campos"]


def test_ope_n02_quantidade_zero(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N02")

    resposta = _criar(client, _payload(produto["id_produto"], quantidade=0))

    assert resposta.status_code == 422
    assert "itens" in resposta.get_json()["campos"]


def test_ope_n03_quantidade_negativa(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N03")

    resposta = _criar(client, _payload(produto["id_produto"], quantidade=-1))

    assert resposta.status_code == 422


def test_ope_n04_quantidade_decimal(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N04")

    resposta = _criar(client, _payload(produto["id_produto"], quantidade=1.5))

    assert resposta.status_code == 422


def test_ope_n05_valor_unitario_negativo(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N05")

    resposta = _criar(client, _payload(produto["id_produto"], preco="-1.00"))

    assert resposta.status_code == 422


def test_ope_n06_valor_unitario_vazio(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N06")

    resposta = _criar(client, _payload(produto["id_produto"], preco=""))

    assert resposta.status_code == 422


def test_ope_n08_operacao_sem_tipo(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N08")
    payload = _payload(produto["id_produto"])
    payload.pop("tipo")

    resposta = _criar(client, payload)

    assert resposta.status_code == 422
    assert "tipo" in resposta.get_json()["campos"]


def test_ope_n09_ocorrencia_omitida_usa_data_atual(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N09")
    payload = _payload(produto["id_produto"])
    payload.pop("ocorrencia")

    resposta = _criar(client, payload)

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["ocorrencia"]


def test_ope_n10_venda_com_parceiro_apenas_fornecedor(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N10")
    fornecedor = criar_parceiro(
        client,
        nome="Fornecedor OPE N10",
        e_cliente=False,
        e_fornecedor=True,
    )

    resposta = _criar(
        client, _payload(produto["id_produto"], id_parceiro=fornecedor["id_parceiro"])
    )

    assert resposta.status_code == 201


def test_ope_n11_compra_com_parceiro_apenas_cliente(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N11", estoque=0)
    cliente = criar_parceiro(client, nome="Cliente OPE N11", e_cliente=True)

    resposta = _criar(
        client,
        _payload(
            produto["id_produto"],
            tipo="compra",
            quantidade=1,
            id_parceiro=cliente["id_parceiro"],
        ),
    )

    assert resposta.status_code == 201


def test_ope_n13_cancelar_operacao_ja_cancelada(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N13")
    criada = _criar(client, _payload(produto["id_produto"])).get_json()["dados"]
    assert (
        client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar").status_code
        == 200
    )

    resposta = client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar")

    assert resposta.status_code == 409


def test_ope_n14_cancelar_venda_com_titulo_baixado(client):
    conta = _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N14")
    criada = _criar(client, _payload(produto["id_produto"])).get_json()["dados"]
    caixa = abrir_caixa(app=client.application, id_usuario=conta["id_usuario"])
    titulo = criada["titulos"][0]
    assert (
        client.post(
            "/api/baixas",
            json={
                "id_titulo": titulo["id_titulo"],
                "id_caixa": caixa,
                "valor": titulo["valor"],
                "forma_pagamento": "dinheiro",
                "realizado_em": "2026-11-16 12:00",
            },
        ).status_code
        == 201
    )

    resposta = client.post(f"/api/operacoes/{criada['id_operacao']}/cancelar")

    assert resposta.status_code == 409


def test_ope_n15_cancelar_compra_com_estoque_consumido(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N15", estoque=0)
    compra = _criar(
        client, _payload(produto["id_produto"], tipo="compra", quantidade=2)
    ).get_json()["dados"]
    _criar(client, _payload(produto["id_produto"], tipo="venda", quantidade=2))

    resposta = client.post(f"/api/operacoes/{compra['id_operacao']}/cancelar")

    assert resposta.status_code == 422


def test_ope_n19_valor_unitario_acima_do_maximo(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N19")

    resposta = _criar(client, _payload(produto["id_produto"], preco="10000000000.00"))

    assert resposta.status_code == 422


def test_ope_n20_quantidade_acima_do_inteiro(client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "OPE-N20")

    resposta = _criar(
        client, _payload(produto["id_produto"], quantidade=2147483648)
    )

    assert resposta.status_code == 422


def test_ope_n21_um_item_sem_estoque_nao_altera_nada(client):
    _logar(client)
    cat = _categoria(client)
    p1 = _produto(client, cat, "OPE-N21-A", estoque=5)
    p2 = _produto(client, cat, "OPE-N21-B", estoque=1)
    payload = _payload(p1["id_produto"], quantidade=2)
    payload["itens"] = [
        {"id_produto": p1["id_produto"], "quantidade": 2, "valor_unitario": "10.00"},
        {"id_produto": p2["id_produto"], "quantidade": 2, "valor_unitario": "10.00"},
    ]

    resposta = _criar(client, payload)

    assert resposta.status_code == 422
    assert _estoque(client, p1["id_produto"]) == 5
    assert _estoque(client, p2["id_produto"]) == 1
    assert client.get("/api/operacoes").get_json()["dados"]["total"] == 0
    assert client.get("/api/titulos").get_json()["dados"]["total"] == 0


def test_seg_n03_operacao_com_produto_de_outra_empresa(app, client):
    """SEG-N03: produto de outra empresa na operação é recusado."""
    _logar(client)
    outro = app.test_client()
    _logar(outro, email="seg.n03.b@exemplo.com.br", cnpj=CNPJ_VALIDO_2)
    cat_b = _categoria(outro)
    produto_b = _produto(outro, cat_b, "SEG-N03-B")

    resposta = _criar(client, _payload(produto_b["id_produto"]))

    assert resposta.status_code == 422
    assert "itens" in resposta.get_json()["campos"]


def test_seg_n04_operacao_com_parceiro_de_outra_empresa(app, client):
    """SEG-N04: parceiro de outra empresa na operação é recusado."""
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "SEG-N04-A")
    outro = app.test_client()
    _logar(outro, email="seg.n04.b@exemplo.com.br", cnpj=CNPJ_VALIDO_2)
    parceiro_b = criar_parceiro(outro, nome="Parceiro SEG N04 B")

    resposta = _criar(
        client, _payload(produto["id_produto"], id_parceiro=parceiro_b["id_parceiro"])
    )

    assert resposta.status_code == 422
    assert "id_parceiro" in resposta.get_json()["campos"]


# ---------------------------------------------------------------------------
# CON-N01/N05/N06 — concorrência do plano V1.4 (CON-N02 fica como E2E/futuro:
# a API atual não tem "concluir operação", então não há duplo clique a testar)
# ---------------------------------------------------------------------------


def _cliente_logado(app):
    cliente = app.test_client()
    resposta = cliente.post(
        "/api/auth/login",
        json={"email": "ope.a@exemplo.com.br", "senha": "Senha#Teste1"},
    )
    assert resposta.status_code == 200, resposta.get_json()
    return cliente


def _disparar_juntos(threads):
    barreira = threading.Barrier(len(threads))
    resultados = [None] * len(threads)

    def executar(indice, acao):
        barreira.wait()
        resultados[indice] = acao()

    filhas = [
        threading.Thread(target=executar, args=(indice, acao))
        for indice, acao in enumerate(threads)
    ]
    for filha in filhas:
        filha.start()
    for filha in filhas:
        filha.join(timeout=15)
    return resultados


def test_con_n01_vendas_simultaneas_nao_deixam_estoque_negativo(app, client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "CON-N01", estoque=1)
    payload = _payload(produto["id_produto"], quantidade=1)
    clientes = [_cliente_logado(app), _cliente_logado(app)]

    respostas = _disparar_juntos(
        [
            (lambda c=clientes[0]: c.post("/api/operacoes", json=payload)),
            (lambda c=clientes[1]: c.post("/api/operacoes", json=payload)),
        ]
    )

    assert sorted(r.status_code for r in respostas) == [201, 422]
    assert _estoque(client, produto["id_produto"]) == 0
    assert client.get("/api/operacoes").get_json()["dados"]["total"] == 1
    assert client.get("/api/titulos").get_json()["dados"]["total"] == 1


def test_con_n05_criacoes_simultaneas_com_mesmo_sku(app, client):
    _logar(client)
    cat = _categoria(client)
    payload = {
        "sku": "CON-SKU-77",
        "id_categoria": cat,
        "nome": "Produto Concorrente",
        "preco": 5.0,
    }
    clientes = [_cliente_logado(app), _cliente_logado(app)]

    respostas = _disparar_juntos(
        [
            (lambda c=clientes[0]: c.post("/api/produtos", json=payload)),
            (lambda c=clientes[1]: c.post("/api/produtos", json=payload)),
        ]
    )

    assert sorted(r.status_code for r in respostas) == [201, 409]
    produtos = client.get("/api/produtos").get_json()["dados"]["produtos"]
    assert [p["sku"] for p in produtos] == ["CON-SKU-77"]


def test_con_n06_cancelamentos_simultaneos_estornam_uma_vez(app, client):
    _logar(client)
    cat = _categoria(client)
    produto = _produto(client, cat, "CON-N06", estoque=10)
    operacao = _criar(client, _payload(produto["id_produto"], quantidade=5)).get_json()[
        "dados"
    ]
    assert _estoque(client, produto["id_produto"]) == 5
    clientes = [_cliente_logado(app), _cliente_logado(app)]
    rota = f"/api/operacoes/{operacao['id_operacao']}/cancelar"

    respostas = _disparar_juntos(
        [
            (lambda c=clientes[0]: c.post(rota)),
            (lambda c=clientes[1]: c.post(rota)),
        ]
    )

    assert sorted(r.status_code for r in respostas) == [200, 409]
    assert _estoque(client, produto["id_produto"]) == 10
    detalhe = client.get(f"/api/operacoes/{operacao['id_operacao']}").get_json()["dados"]
    assert detalhe["status"] == "cancelada"
