"""Testes do módulo CXA - Caixa (plano de testes V1.3), pela API.

Cada teste referencia o ID do caso do plano (CXA-Pxx / CXA-Nxx), de segurança (SEG) ou de
concorrência (CON-N04). Além do plano: um caixa aberto por empresa, extrato, histórico e a
corrida entre abrir/fechar/lançar. Títulos e baixas são criados por SQL (as baixas têm
API própria, mas aqui só importa o efeito delas no caixa).
"""

from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import text

from src.app.db import get_engine
from tests.apoio_baixas import (
    abrir_caixa as abrir_caixa_sql,
    apagar_dados_de_baixas,
    inserir_baixa,
    inserir_titulo,
)
from tests.apoio_parceiros import EMAIL_B, campos, criar_parceiro, logar
from tests.helpers import CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar_caixas(app, banco_limpo):
    yield
    apagar_dados_de_baixas(app)


def _abrir(client, valor="100.00") -> dict:
    resposta = client.post("/api/caixas", json={"valor_abertura": valor})
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


def _mover(client, id_caixa, tipo, valor, descricao=None):
    corpo = {"tipo": tipo, "valor": valor}
    if descricao is not None:
        corpo["descricao"] = descricao
    return client.post(f"/api/caixas/{id_caixa}/movimentos", json=corpo)


def _obter(client, id_caixa) -> dict:
    resposta = client.get(f"/api/caixas/{id_caixa}")
    assert resposta.status_code == 200, resposta.get_json()
    return resposta.get_json()["dados"]


def _linha(dados: dict, forma: str) -> dict:
    return next(item for item in dados["por_forma"] if item["forma"] == forma)


def _com_baixa(app, client, conta, id_caixa, *, tipo, valor, forma, parceiro="Parceiro Caixa"):
    """Cria um título (com parceiro) e uma baixa nele, direto no banco."""
    parceiros = client.get("/api/parceiros").get_json()["dados"]["parceiros"]
    existente = next((p for p in parceiros if p["nome"] == parceiro), None)
    id_parceiro = (existente or criar_parceiro(client, nome=parceiro))["id_parceiro"]
    id_titulo = inserir_titulo(app, conta["id_empresa"], id_parceiro, tipo=tipo, valor=valor,
                               descricao=f"Título {tipo} {valor}")
    inserir_baixa(app, id_titulo, id_caixa, valor, forma=forma)
    return id_titulo


# ---------------------------------------------------------------------------
# CXA - casos positivos
# ---------------------------------------------------------------------------


def test_cxa_p01_abrir_caixa_com_valor_de_abertura(client):
    conta = logar(client)

    dados = _abrir(client, "100.00")

    assert dados["situacao"] == "aberto"
    assert dados["valor_abertura"] == "100.00"
    assert dados["aberto_por"] == conta["nome"]
    assert dados["aberto_em"] and dados["fechado_em"] is None


def test_cxa_p02_abrir_caixa_com_abertura_zero(client):
    logar(client)

    dados = _abrir(client, "0.00")

    assert dados["valor_abertura"] == "0.00"
    assert dados["saldo_esperado_dinheiro"] == "0.00"


def test_cxa_p03_consultar_valores_logo_apos_abrir(client):
    logar(client)
    caixa = _abrir(client, "150.00")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["valor_abertura"] == "150.00"
    assert dados["saldo_esperado_dinheiro"] == "150.00"
    assert dados["extrato"] == []


def test_cxa_p04_registrar_suprimento_com_descricao(client):
    logar(client)
    caixa = _abrir(client)

    resposta = _mover(client, caixa["id_caixa"], "suprimento", "50.00", "Reforço de troco")

    assert resposta.status_code == 201
    entrada = _obter(client, caixa["id_caixa"])["extrato"][0]
    assert (entrada["tipo"], entrada["sentido"], entrada["valor"], entrada["descricao"]) == (
        "suprimento", "entrada", "50.00", "Reforço de troco",
    )


def test_cxa_p05_registrar_sangria_com_descricao(client):
    logar(client)
    caixa = _abrir(client, "300.00")

    resposta = _mover(client, caixa["id_caixa"], "sangria", "30.00", "Retirada para depósito bancário")

    assert resposta.status_code == 201
    saida = _obter(client, caixa["id_caixa"])["extrato"][0]
    assert (saida["tipo"], saida["sentido"], saida["valor"]) == ("sangria", "saida", "30.00")


def test_cxa_p06_saldo_esperado_considera_abertura_suprimentos_e_sangrias(client):
    logar(client)
    caixa = _abrir(client, "200.00")
    _mover(client, caixa["id_caixa"], "suprimento", "50.00")
    _mover(client, caixa["id_caixa"], "sangria", "30.00")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["saldo_esperado_dinheiro"] == "220.00"
    assert (dados["suprimentos"], dados["sangrias"]) == ("50.00", "30.00")


def test_cxa_p07_baixa_de_recebimento_em_dinheiro_aumenta_o_saldo(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="80.00",
               forma="dinheiro")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["saldo_esperado_dinheiro"] == "180.00"
    assert _linha(dados, "dinheiro")["recebimentos"] == "80.00"


def test_cxa_p08_baixa_de_pagamento_em_dinheiro_reduz_o_saldo(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a pagar", valor="40.00",
               forma="dinheiro", parceiro="Fornecedor Caixa")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["saldo_esperado_dinheiro"] == "60.00"
    assert _linha(dados, "dinheiro")["pagamentos"] == "40.00"


def test_cxa_p09_baixa_via_pix_nao_altera_o_dinheiro(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="90.00", forma="Pix")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["saldo_esperado_dinheiro"] == "100.00"
    assert _linha(dados, "Pix")["liquido"] == "90.00"
    assert _linha(dados, "Pix")["afeta_dinheiro"] is False


def test_cxa_p10_baixa_via_cartao_nao_altera_o_dinheiro(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="75.00",
               forma="cartão")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["saldo_esperado_dinheiro"] == "100.00"
    assert _linha(dados, "cartão")["liquido"] == "75.00"


def test_cxa_p11_fechar_caixa_com_valor_contado_igual_ao_esperado(client):
    logar(client)
    caixa = _abrir(client, "200.00")
    _mover(client, caixa["id_caixa"], "suprimento", "50.00")
    _mover(client, caixa["id_caixa"], "sangria", "30.00")

    resposta = client.post(f"/api/caixas/{caixa['id_caixa']}/fechar", json={"valor_contado": "220.00"})
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["situacao"] == "fechado" and dados["fechado_em"]
    assert (dados["valor_contado"], dados["diferenca"]) == ("220.00", "0.00")


def test_cxa_p12_fechar_caixa_com_valor_menor_que_o_esperado(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="80.00",
               forma="dinheiro")

    resposta = client.post(f"/api/caixas/{caixa['id_caixa']}/fechar", json={"valor_contado": "170.00"})
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["diferenca"] == "-10.00"  # esperado 180,00
    assert "-10.00" in resposta.get_json()["mensagem"]


def test_cxa_p13_caixa_fechado_deixa_de_ser_caixa_aberto(client):
    logar(client)
    caixa = _abrir(client, "130.00")
    client.post(f"/api/caixas/{caixa['id_caixa']}/fechar", json={"valor_contado": "130.00"})

    assert client.get("/api/caixas/atual").get_json()["dados"]["caixa"] is None
    # E não aparece na seleção de caixa das baixas financeiras.
    assert client.get("/api/baixas/opcoes").get_json()["dados"]["caixas"] == []


# ---------------------------------------------------------------------------
# CXA - casos negativos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor, trecho",
    [
        ("-10.00", "não pode ser negativo"),  # CXA-N01
        ("", "obrigatório"),  # CXA-N02
        ("cem", "numérico inválido"),  # CXA-N03
        ("10000000000.00", "não pode ser maior"),  # CXA-N04
    ],
)
def test_cxa_n01_a_n04_abertura_invalida(client, valor, trecho):
    logar(client)

    resposta = client.post("/api/caixas", json={"valor_abertura": valor})

    assert resposta.status_code == 422
    assert trecho in campos(resposta)["valor_abertura"]
    assert client.get("/api/caixas/atual").get_json()["dados"]["caixa"] is None  # não abriu


@pytest.mark.parametrize(
    "tipo, valor, trecho",
    [
        ("suprimento", "0.00", "maior que zero"),  # CXA-N05
        ("suprimento", "-20.00", "maior que zero"),  # CXA-N06
        ("sangria", "0.00", "maior que zero"),  # CXA-N07
        ("sangria", "", "obrigatório"),  # CXA-N08
        ("sangria", "dez", "numérico inválido"),  # CXA-N10
    ],
)
def test_cxa_n05_a_n10_movimento_com_valor_invalido(client, tipo, valor, trecho):
    logar(client)
    caixa = _abrir(client)

    resposta = _mover(client, caixa["id_caixa"], tipo, valor)

    assert resposta.status_code == 422
    assert trecho in campos(resposta)["valor"]
    assert _obter(client, caixa["id_caixa"])["extrato"] == []


def test_cxa_n09_movimento_sem_tipo(client):
    logar(client)
    caixa = _abrir(client)

    resposta = _mover(client, caixa["id_caixa"], "", "15.00")

    assert resposta.status_code == 422
    assert "tipo" in campos(resposta)




def test_cxa_n11_sem_caixa_aberto_nao_ha_onde_lancar(client):
    logar(client)

    assert client.get("/api/caixas/atual").get_json()["dados"]["caixa"] is None
    assert _mover(client, 999999, "suprimento", "25.00").status_code == 404


def test_cxa_n12_movimento_em_caixa_ja_fechado(client):
    logar(client)
    caixa = _abrir(client)
    client.post(f"/api/caixas/{caixa['id_caixa']}/fechar", json={"valor_contado": "100.00"})

    resposta = _mover(client, caixa["id_caixa"], "sangria", "8.00")

    assert resposta.status_code == 409
    assert _obter(client, caixa["id_caixa"])["extrato"] == []


@pytest.mark.parametrize(
    "valor, trecho",
    [
        ("", "obrigatório"),  # CXA-N13
        ("-1.00", "não pode ser negativo"),  # CXA-N14
        ("abc", "numérico inválido"),  # CXA-N15
    ],
)
def test_cxa_n13_a_n15_fechamento_com_valor_invalido(client, valor, trecho):
    logar(client)
    caixa = _abrir(client)

    resposta = client.post(f"/api/caixas/{caixa['id_caixa']}/fechar", json={"valor_contado": valor})

    assert resposta.status_code == 422
    assert trecho in campos(resposta)["valor_contado"]
    assert _obter(client, caixa["id_caixa"])["situacao"] == "aberto"


def test_cxa_n16_fechar_caixa_que_ja_foi_fechado(client):
    logar(client)
    caixa = _abrir(client, "100.00")
    primeiro = client.post(f"/api/caixas/{caixa['id_caixa']}/fechar",
                           json={"valor_contado": "100.00"}).get_json()["dados"]

    resposta = client.post(f"/api/caixas/{caixa['id_caixa']}/fechar", json={"valor_contado": "50.00"})

    assert resposta.status_code == 409
    original = _obter(client, caixa["id_caixa"])
    assert (original["fechado_em"], original["valor_contado"]) == (
        primeiro["fechado_em"], "100.00",
    )


# ---------------------------------------------------------------------------
# Extras: um caixa aberto por empresa, extrato, histórico, isolamento
# ---------------------------------------------------------------------------














def _outra_empresa(app):
    outro = app.test_client()
    conta = logar(outro, EMAIL_B, CNPJ_VALIDO_2)
    return outro, conta






# ---------------------------------------------------------------------------
# Concorrência (CON). Cada teste força a corrida: uma SEGUNDA sessão do banco segura
# uma trava, a requisição espera, e só então a segunda sessão confirma a mudança.
# Sem as travas a requisição não esperaria e usaria dados velhos.
# ---------------------------------------------------------------------------


def _em_thread(funcao):
    """Executa a requisição numa thread; ``resultado`` recebe ``status`` e ``json``."""
    resultado: dict = {}

    def executar():
        resposta = funcao()
        resultado.update(status=resposta.status_code, json=resposta.get_json())

    thread = threading.Thread(target=executar)
    thread.start()
    return thread, resultado








# ---------------------------------------------------------------------------
# Saldo geral (dinheiro + Pix + cartão) e limpeza do contador de ids
# ---------------------------------------------------------------------------






