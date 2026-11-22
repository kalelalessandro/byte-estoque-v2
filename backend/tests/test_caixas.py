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


def test_cxa_n09b_tipo_de_movimento_fora_da_lista(client):
    logar(client)
    caixa = _abrir(client)

    assert "tipo" in campos(_mover(client, caixa["id_caixa"], "emprestimo", "5.00"))


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


def test_nao_abre_segundo_caixa_com_um_ja_aberto(client):
    logar(client)
    primeiro = _abrir(client)

    resposta = client.post("/api/caixas", json={"valor_abertura": "10.00"})

    assert resposta.status_code == 409
    assert resposta.get_json()["id_caixa"] == primeiro["id_caixa"]
    # Fechado o primeiro, um novo pode ser aberto.
    client.post(f"/api/caixas/{primeiro['id_caixa']}/fechar", json={"valor_contado": "100.00"})
    assert client.post("/api/caixas", json={"valor_abertura": "10.00"}).status_code == 201


def test_extrato_junta_baixas_e_movimentos_com_parceiro(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _mover(client, caixa["id_caixa"], "suprimento", "50.00", "Troco")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="90.00",
               forma="Pix", parceiro="Cliente do Extrato")

    extrato = _obter(client, caixa["id_caixa"])["extrato"]

    assert {item["origem"] for item in extrato} == {"baixa", "movimento"}
    baixa = next(item for item in extrato if item["origem"] == "baixa")
    assert (baixa["parceiro"], baixa["sentido"], baixa["afeta_dinheiro"]) == (
        "Cliente do Extrato", "entrada", False,
    )
    movimento = next(item for item in extrato if item["origem"] == "movimento")
    assert movimento["usuario"] == conta["nome"] and movimento["afeta_dinheiro"] is True


def test_resumo_combina_todas_as_fontes(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    _mover(client, caixa["id_caixa"], "suprimento", "50.00")
    _mover(client, caixa["id_caixa"], "sangria", "20.00")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="80.00", forma="dinheiro")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a pagar", valor="30.00", forma="dinheiro",
               parceiro="Fornecedor X")
    _com_baixa(app, client, conta, caixa["id_caixa"], tipo="a receber", valor="500.00", forma="Pix")

    dados = _obter(client, caixa["id_caixa"])

    assert dados["saldo_esperado_dinheiro"] == "180.00"  # 100 + 50 - 20 + 80 - 30
    assert _linha(dados, "Pix")["recebimentos"] == "500.00"


def test_lista_historico_com_valores_e_filtro(client):
    logar(client)
    antigo = _abrir(client, "100.00")
    client.post(f"/api/caixas/{antigo['id_caixa']}/fechar", json={"valor_contado": "90.00"})
    atual = _abrir(client, "20.00")

    todos = client.get("/api/caixas").get_json()["dados"]
    fechados = client.get("/api/caixas?situacao=fechado").get_json()["dados"]
    abertos = client.get("/api/caixas?situacao=aberto").get_json()["dados"]

    assert [c["id_caixa"] for c in todos["caixas"]] == [atual["id_caixa"], antigo["id_caixa"]]
    assert fechados["caixas"][0]["diferenca"] == "-10.00"
    assert [c["id_caixa"] for c in abertos["caixas"]] == [atual["id_caixa"]]
    assert client.get("/api/caixas?situacao=x").status_code == 422
    assert client.get("/api/caixas?limit=0").status_code == 422


def test_caixa_atual_traz_valores_e_extrato(client):
    logar(client)
    caixa = _abrir(client, "100.00")
    _mover(client, caixa["id_caixa"], "suprimento", "10.00")

    dados = client.get("/api/caixas/atual").get_json()["dados"]["caixa"]

    assert dados["id_caixa"] == caixa["id_caixa"]
    assert dados["saldo_esperado_dinheiro"] == "110.00"
    assert len(dados["extrato"]) == 1


def test_campos_nao_permitidos_sao_recusados(client):
    logar(client)

    resposta = client.post("/api/caixas", json={"valor_abertura": "10.00", "aberto_em": "2020-01-01 00:00"})

    assert resposta.status_code == 422
    assert "aberto_em" in campos(resposta)


def _outra_empresa(app):
    outro = app.test_client()
    conta = logar(outro, EMAIL_B, CNPJ_VALIDO_2)
    return outro, conta


def test_isolamento_entre_empresas(app, client):
    logar(client)
    caixa = _abrir(client)
    outro, _ = _outra_empresa(app)

    assert outro.get(f"/api/caixas/{caixa['id_caixa']}").status_code == 404
    assert _mover(outro, caixa["id_caixa"], "sangria", "5.00").status_code == 404
    assert outro.post(f"/api/caixas/{caixa['id_caixa']}/fechar",
                      json={"valor_contado": "1.00"}).status_code == 404
    assert outro.get("/api/caixas").get_json()["dados"]["total"] == 0
    assert outro.get("/api/caixas/atual").get_json()["dados"]["caixa"] is None
    # A outra empresa pode abrir o PRÓPRIO caixa (um aberto por empresa, não global).
    assert outro.post("/api/caixas", json={"valor_abertura": "5.00"}).status_code == 201
    assert _obter(client, caixa["id_caixa"])["situacao"] == "aberto"


def test_rotas_de_caixa_exigem_login(client):
    assert client.get("/api/caixas").status_code == 401
    assert client.get("/api/caixas/atual").status_code == 401
    assert client.get("/api/caixas/1").status_code == 401
    assert client.post("/api/caixas", json={}).status_code == 401
    assert client.post("/api/caixas/1/movimentos", json={}).status_code == 401
    assert client.post("/api/caixas/1/fechar", json={}).status_code == 401


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


def test_aberturas_simultaneas_geram_um_unico_caixa(app, client):
    conta = logar(client)

    with app.app_context(), get_engine().connect() as concorrente:
        concorrente.execute(
            text("SELECT id_empresa FROM empresas WHERE id_empresa = :e FOR UPDATE"),
            {"e": conta["id_empresa"]},
        )
        thread, resultado = _em_thread(
            lambda: client.post("/api/caixas", json={"valor_abertura": "10.00"})
        )
        time.sleep(0.6)
        assert thread.is_alive(), "a abertura deveria esperar a trava da empresa"

        concorrente.execute(
            text("INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura) "
                 "VALUES (:u, '2026-11-09 08:00:00', 50.00)"),
            {"u": conta["id_usuario"]},
        )
        concorrente.commit()

    thread.join(timeout=10)
    assert resultado["status"] == 409
    abertos = client.get("/api/caixas?situacao=aberto").get_json()["dados"]["total"]
    assert abertos == 1


def test_con_n04_fechamento_inclui_baixa_confirmada_durante_a_espera(app, client):
    """Baixa de 40,00 em dinheiro confirmada enquanto o fechamento espera: entra no esperado."""
    conta = logar(client)
    caixa = abrir_caixa_sql(app, conta["id_usuario"])
    parceiro = criar_parceiro(client, nome="Cliente Corrida Caixa")
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"],
                               valor="40.00", descricao="Venda corrida")

    with app.app_context(), get_engine().connect() as concorrente:
        # Simula uma baixa em andamento: trava o caixa e grava a baixa, sem confirmar.
        concorrente.execute(text("SELECT id_caixa FROM caixas WHERE id_caixa = :c FOR UPDATE"), {"c": caixa})
        concorrente.execute(
            text("INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
                 "forma_pagamento) VALUES (:t, :c, 40.00, '2026-11-09 09:00:00', 'dinheiro')"),
            {"t": id_titulo, "c": caixa},
        )
        thread, resultado = _em_thread(
            lambda: client.post(f"/api/caixas/{caixa}/fechar", json={"valor_contado": "140.00"})
        )
        time.sleep(0.6)
        assert thread.is_alive(), "o fechamento deveria esperar a trava do caixa"
        concorrente.commit()

    thread.join(timeout=10)
    assert resultado["status"] == 200
    # abertura 100 (SQL) + baixa 40 = 140 esperado NO MOMENTO DO FECHAMENTO: a baixa
    # confirmada durante a espera entrou na conta (a diferença devolvida pelo fechamento é 0).
    assert resultado["json"]["dados"]["diferenca"] == "0.00"
    assert resultado["json"]["dados"]["saldo_esperado_dinheiro"] == "140.00"
    assert len(_obter(client, caixa)["extrato"]) == 1


def test_movimento_espera_o_fechamento_e_e_recusado(app, client):
    logar(client)
    caixa = _abrir(client)["id_caixa"]

    with app.app_context(), get_engine().connect() as concorrente:
        concorrente.execute(text("SELECT id_caixa FROM caixas WHERE id_caixa = :c FOR UPDATE"), {"c": caixa})
        thread, resultado = _em_thread(lambda: _mover(client, caixa, "sangria", "10.00"))
        time.sleep(0.6)
        assert thread.is_alive(), "o lançamento deveria esperar a trava do caixa"
        concorrente.execute(
            text("UPDATE caixas SET fechado_em = '2099-01-01 00:00:00', valor_contado = 100.00 "
                 "WHERE id_caixa = :c"),  # depois da abertura (CHECK do schema)
            {"c": caixa},
        )
        concorrente.commit()

    thread.join(timeout=10)
    assert resultado["status"] == 409
    assert _obter(client, caixa)["extrato"] == []


# ---------------------------------------------------------------------------
# Saldo geral (dinheiro + Pix + cartão) e limpeza do contador de ids
# ---------------------------------------------------------------------------


def test_pix_e_cartao_alteram_o_saldo_geral_do_caixa(app, client):
    conta = logar(client)
    caixa = _abrir(client, "100.00")
    id_caixa = caixa["id_caixa"]
    _com_baixa(app, client, conta, id_caixa, tipo="a receber", valor="50.00", forma="dinheiro")
    _com_baixa(app, client, conta, id_caixa, tipo="a receber", valor="90.00", forma="Pix")
    _com_baixa(app, client, conta, id_caixa, tipo="a receber", valor="40.00", forma="cartão")
    _com_baixa(app, client, conta, id_caixa, tipo="a pagar", valor="30.00", forma="Pix")

    dados = _obter(client, id_caixa)

    assert dados["saldo_esperado_dinheiro"] == "150.00"  # gaveta: 100 + 50
    assert dados["saldo_geral"] == "250.00"  # 150 + (90 - 30) + 40


def test_saldo_geral_do_caixa_fechado_usa_o_valor_contado(app, client):
    conta = logar(client)
    id_caixa = _abrir(client, "100.00")["id_caixa"]
    _com_baixa(app, client, conta, id_caixa, tipo="a receber", valor="70.00", forma="Pix")

    fechado = client.post(f"/api/caixas/{id_caixa}/fechar", json={"valor_contado": "95.00"})

    dados = fechado.get_json()["dados"]
    assert dados["saldo_esperado_dinheiro"] == "100.00"
    assert dados["saldo_geral"] == "165.00"  # contado 95 + Pix 70
    assert _obter(client, id_caixa)["saldo_geral"] == "165.00"


def test_apos_a_limpeza_o_proximo_caixa_nao_herda_o_contador_dos_testes(app, client):
    logar(client)
    for _ in range(3):
        id_caixa = _abrir(client)["id_caixa"]
        client.post(f"/api/caixas/{id_caixa}/fechar", json={"valor_contado": "0"})

    apagar_dados_de_baixas(app)

    with app.app_context(), get_engine().connect() as conexao:
        # O MySQL 8 guarda estatísticas em cache; sem isso o contador lido pode estar velho.
        conexao.execute(text("SET SESSION information_schema_stats_expiry = 0"))
        proximo = conexao.execute(
            text(
                "SELECT AUTO_INCREMENT FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'caixas'"
            )
        ).scalar()
        maior = conexao.execute(text("SELECT COALESCE(MAX(id_caixa), 0) FROM caixas")).scalar()
    # Sem caixas de demonstração o contador volta a 1; com elas, fica em MAX(id) + 1.
    assert proximo == maior + 1
