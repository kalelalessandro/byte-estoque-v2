"""Testes do card "Dinheiro" do dashboard, ligado ao módulo de Caixa.

O dinheiro mostrado é o SALDO GERAL do último caixa fechado da empresa (valor contado +
líquido de Pix e cartão): aparece assim que o caixa fecha; caixa aberto não conta; cada
empresa vê só o seu.
"""

from __future__ import annotations

import pytest

from tests.apoio_baixas import apagar_dados_de_baixas
from tests.apoio_parceiros import EMAIL_B, logar
from tests.helpers import CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar_caixas(app, banco_limpo):
    yield
    apagar_dados_de_baixas(app)


def _dinheiro(client):
    resposta = client.get("/api/dashboard/resumo")
    assert resposta.status_code == 200
    return resposta.get_json()["dados"]["dinheiro"]


def _abrir(client, valor="100.00") -> int:
    resposta = client.post("/api/caixas", json={"valor_abertura": valor})
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]["id_caixa"]


def _fechar(client, id_caixa: int, contado: str):
    resposta = client.post(f"/api/caixas/{id_caixa}/fechar", json={"valor_contado": contado})
    assert resposta.status_code == 200, resposta.get_json()
    return resposta.get_json()["dados"]


def test_sem_caixa_fechado_o_dinheiro_e_nulo(client):
    logar(client)

    assert _dinheiro(client) is None


def test_caixa_aberto_ainda_nao_conta_no_dashboard(client):
    logar(client)
    _abrir(client, "100.00")

    assert _dinheiro(client) is None


def test_fechar_o_caixa_coloca_o_valor_contado_no_dashboard(client):
    logar(client)
    id_caixa = _abrir(client, "200.00")
    fechado = _fechar(client, id_caixa, "170.50")  # falta dinheiro: o que vale é o contado

    dinheiro = _dinheiro(client)

    assert dinheiro == {
        "valor": "170.50",
        "id_caixa": id_caixa,
        "fechado_em": fechado["fechado_em"],
    }


def test_valor_contado_zero_aparece_como_zero_e_nao_como_ausente(client):
    logar(client)
    _fechar(client, _abrir(client, "50.00"), "0.00")

    assert _dinheiro(client)["valor"] == "0.00"


def test_o_dashboard_mostra_o_ultimo_caixa_fechado(client):
    logar(client)
    _fechar(client, _abrir(client, "100.00"), "100.00")
    segundo = _abrir(client, "30.00")
    assert _dinheiro(client)["valor"] == "100.00"  # o segundo ainda está aberto

    _fechar(client, segundo, "260.00")

    dinheiro = _dinheiro(client)
    assert (dinheiro["valor"], dinheiro["id_caixa"]) == ("260.00", segundo)


def test_cada_empresa_ve_apenas_o_seu_dinheiro(app, client):
    logar(client)
    _fechar(client, _abrir(client, "10.00"), "10.00")
    outro = app.test_client()
    logar(outro, EMAIL_B, CNPJ_VALIDO_2)

    assert _dinheiro(outro) is None
    _fechar(outro, _abrir(outro, "99.00"), "99.00")
    assert _dinheiro(outro)["valor"] == "99.00"
    assert _dinheiro(client)["valor"] == "10.00"


def test_pix_e_cartao_do_caixa_fechado_somam_no_dinheiro_do_dashboard(app, client):
    from tests.apoio_baixas import inserir_baixa, inserir_titulo
    from tests.apoio_parceiros import criar_parceiro

    conta = logar(client)
    id_parceiro = criar_parceiro(client)["id_parceiro"]
    id_caixa = _abrir(client, "100.00")
    receber = inserir_titulo(app, conta["id_empresa"], id_parceiro, tipo="a receber", valor="500.00")
    pagar = inserir_titulo(app, conta["id_empresa"], id_parceiro, tipo="a pagar", valor="80.00")
    inserir_baixa(app, receber, id_caixa, "200.00", forma="Pix")
    inserir_baixa(app, receber, id_caixa, "50.00", forma="cartão")
    inserir_baixa(app, pagar, id_caixa, "30.00", forma="Pix")

    assert _dinheiro(client) is None  # caixa ainda aberto não conta

    fechado = _fechar(client, id_caixa, "100.00")

    # Saldo geral = contado (100) + Pix (200 - 30) + cartão (50).
    assert fechado["saldo_geral"] == "320.00"
    assert _dinheiro(client)["valor"] == "320.00"
