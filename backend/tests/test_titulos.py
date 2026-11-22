"""Testes do módulo TIT - Títulos Financeiros (plano de testes V1.3), pela API.

Cada teste referencia o ID do caso do plano (TIT-Pxx / TIT-Nxx) ou de segurança
(SEG-N06/N09). Além do plano: vínculo com operação (parceiro herdado/divergente),
filtros, flags da tela (``pode_baixar``/``pode_cancelar``) e a corrida entre cancelar
e dar baixa. Operações, caixas e baixas são criadas por SQL (ainda sem API própria).
"""

from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import text

from src.app.db import get_engine
from tests.apoio_baixas import (
    abrir_caixa,
    apagar_dados_de_baixas,
    contar_baixas,
    criar_operacao,
    inserir_baixa,
    inserir_titulo,
)
from tests.apoio_parceiros import EMAIL_B, campos, criar_parceiro, logar
from tests.helpers import CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar_titulos(app, banco_limpo):
    yield
    apagar_dados_de_baixas(app)


def _titulo(**sobrescritas):
    dados = {
        "tipo": "a pagar",
        "valor": "10.00",
        "descricao": "Título de teste",
        "vencimento": "2026-12-01",
    }
    dados.update(sobrescritas)
    return dados


def _criar(client, **sobrescritas) -> dict:
    resposta = client.post("/api/titulos", json=_titulo(**sobrescritas))
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


def _obter(client, id_titulo: int) -> dict:
    resposta = client.get(f"/api/titulos/{id_titulo}")
    assert resposta.status_code == 200, resposta.get_json()
    return resposta.get_json()["dados"]


def _outra_empresa(app):
    outro = app.test_client()
    conta = logar(outro, EMAIL_B, CNPJ_VALIDO_2)
    return outro, conta


# ---------------------------------------------------------------------------
# TIT - casos positivos
# ---------------------------------------------------------------------------


def test_tit_p01_listar_titulos_da_empresa(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Cliente Lista")
    inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], valor="150.00",
                   descricao="Título Lista 01")

    dados = client.get("/api/titulos").get_json()["dados"]

    assert dados["total"] == 1
    item = dados["titulos"][0]
    assert item["tipo"] == "a receber"
    assert item["valor"] == "150.00"
    assert item["vencimento"] == "2026-12-01"
    assert item["parceiro"]["nome"] == "Cliente Lista"
    assert item["situacao"] == "aberto"


def test_tit_p02_consultar_titulo_exibe_valor_vencimento_e_saldo(app, client):
    conta = logar(client)
    id_titulo = inserir_titulo(app, conta["id_empresa"], None, valor="400.00",
                               descricao="Título Consulta 02")

    dados = _obter(client, id_titulo)

    assert (dados["valor"], dados["vencimento"], dados["saldo_pendente"]) == (
        "400.00", "2026-12-01", "400.00",
    )
    assert dados["baixas"] == []


def test_tit_p03_registrar_conta_a_pagar_com_fornecedor(client):
    logar(client)
    fornecedor = criar_parceiro(client, nome="Fornecedor Titulo 03", e_cliente=False,
                                e_fornecedor=True)

    dados = _criar(client, tipo="a pagar", id_parceiro=fornecedor["id_parceiro"],
                   valor="1250.00", descricao="Aluguel do galpão novembro",
                   vencimento="2026-11-30")

    assert dados["parceiro"]["id_parceiro"] == fornecedor["id_parceiro"]
    assert dados["total_baixado"] == "0.00"
    assert dados["saldo_pendente"] == "1250.00"
    assert dados["situacao"] == "aberto"
    assert dados["id_operacao"] is None


def test_tit_p04_registrar_conta_a_receber_sem_parceiro(client):
    logar(client)

    dados = _criar(client, tipo="a receber", valor="300.00",
                   descricao="Venda avulsa de balcão sem cadastro", vencimento="2026-11-20")

    assert dados["parceiro"] is None
    assert dados["id_operacao"] is None
    # O título sem parceiro pode ser baixado normalmente.
    assert dados["pode_baixar"] is True
    assert dados["motivo_sem_baixa"] is None


def test_tit_p05_titulo_vinculado_a_operacao_e_ao_parceiro(app, client):
    conta = logar(client)
    cliente = criar_parceiro(client, nome="Cliente Titulo 06")
    id_operacao = criar_operacao(app, conta["id_usuario"], cliente["id_parceiro"])

    dados = _criar(client, tipo="a receber", id_parceiro=cliente["id_parceiro"],
                   id_operacao=id_operacao, valor="90.00",
                   descricao="Parcela extra da venda", vencimento="2026-12-18")

    assert dados["id_operacao"] == id_operacao
    assert dados["parceiro"]["id_parceiro"] == cliente["id_parceiro"]


def test_tit_p06_descricao_com_exatamente_500_caracteres(client):
    logar(client)

    dados = _criar(client, descricao="t" * 500, vencimento="2026-12-21")

    assert len(_obter(client, dados["id_titulo"])["descricao"]) == 500


def test_tit_p07_valor_maximo_permitido(client):
    logar(client)

    dados = _criar(client, tipo="a receber", valor="9999999999.99",
                   descricao="Titulo valor maximo", vencimento="2026-12-23")

    assert dados["valor"] == "9999999999.99"


def test_tit_p08_saldo_pendente_reflete_baixa_parcial(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Cliente Saldo")
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], valor="500.00")
    inserir_baixa(app, id_titulo, id_caixa, "200.00")

    dados = _obter(client, id_titulo)

    assert dados["saldo_pendente"] == "300.00"
    assert dados["situacao"] == "parcial"


def test_tit_p09_saldo_zero_apos_liquidacao_total(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Fornecedor Quitado", e_cliente=False,
                              e_fornecedor=True)
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"],
                               tipo="a pagar", valor="150.00")
    inserir_baixa(app, id_titulo, id_caixa, "100.00")
    inserir_baixa(app, id_titulo, id_caixa, "50.00", forma="Pix")

    dados = _obter(client, id_titulo)

    assert dados["saldo_pendente"] == "0.00"
    assert dados["situacao"] == "quitado"
    assert dados["pode_baixar"] is False


def test_tit_p10_historico_de_baixas_do_titulo(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Cliente Historico")
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], valor="600.00")
    inserir_baixa(app, id_titulo, id_caixa, "100.00", realizado_em="2026-11-09 09:00:00")
    inserir_baixa(app, id_titulo, id_caixa, "250.00", forma="Pix",
                  realizado_em="2026-11-09 10:00:00")

    baixas = _obter(client, id_titulo)["baixas"]

    assert [(b["valor"], b["forma_pagamento"], b["realizado_em"]) for b in baixas] == [
        ("250.00", "Pix", "2026-11-09T10:00:00"),  # mais recente primeiro
        ("100.00", "dinheiro", "2026-11-09T09:00:00"),
    ]


def test_tit_p11_cancelar_titulo_sem_baixas(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Fornecedor Cancelar", e_cliente=False,
                              e_fornecedor=True)
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"],
                               tipo="a pagar", valor="60.00", descricao="Titulo Cancelar 15")

    resposta = client.post(f"/api/titulos/{id_titulo}/cancelar")

    assert resposta.status_code == 200
    dados = resposta.get_json()["dados"]
    assert dados["cancelado"] is True and dados["situacao"] == "cancelado"
    assert dados["pode_baixar"] is False
    # E não aceita novas baixas.
    baixa = client.post(
        "/api/baixas",
        json={"id_titulo": id_titulo, "id_caixa": id_caixa, "valor": "10.00",
              "forma_pagamento": "dinheiro", "realizado_em": "2026-11-09 11:00"},
    )
    assert baixa.status_code == 409
    assert contar_baixas(app, id_titulo) == 0


# ---------------------------------------------------------------------------
# TIT - casos negativos
# ---------------------------------------------------------------------------


def _recusado(client, campo, status=422, **sobrescritas):
    resposta = client.post("/api/titulos", json=_titulo(**sobrescritas))
    assert resposta.status_code == status, resposta.get_json()
    assert campo in campos(resposta)
    assert client.get("/api/titulos").get_json()["dados"]["total"] == 0  # nada foi criado
    return resposta


@pytest.mark.parametrize(
    "valor, trecho",
    [
        ("0.00", "maior que zero"),  # TIT-N01
        ("-10.00", "maior que zero"),  # TIT-N02
        ("", "obrigatório"),  # TIT-N03
        ("cem", "numérico inválido"),  # TIT-N04
        ("10.555", "2 casas decimais"),  # TIT-N05
        ("10000000000.00", "maior que"),  # TIT-N06
    ],
)
def test_tit_n01_a_n06_valor_invalido(client, valor, trecho):
    logar(client)

    resposta = _recusado(client, "valor", valor=valor, tipo="a receber")

    assert trecho in campos(resposta)["valor"]


def test_tit_n07_descricao_vazia(client):
    logar(client)

    _recusado(client, "descricao", descricao="", valor="20.00", vencimento="2026-12-30")


def test_tit_n08_descricao_com_501_caracteres(client):
    logar(client)

    resposta = _recusado(client, "descricao", descricao="u" * 501, valor="20.00")

    assert "no máximo 500" in campos(resposta)["descricao"]


def test_tit_n09_vencimento_vazio(client):
    logar(client)

    _recusado(client, "vencimento", vencimento="", valor="21.00")


def test_tit_n10_vencimento_inexistente(client):
    logar(client)

    _recusado(client, "vencimento", vencimento="30/02/2027", valor="22.00")


def test_tit_n11_sem_selecionar_o_tipo(client):
    logar(client)

    _recusado(client, "tipo", tipo="", valor="23.00", vencimento="2027-01-05")


def test_tit_n11b_tipo_fora_da_lista(client):
    logar(client)

    _recusado(client, "tipo", tipo="a vista")


def test_tit_n12_parceiro_diferente_do_parceiro_da_operacao(app, client):
    conta = logar(client)
    cliente_op = criar_parceiro(client, nome="Cliente Op X")
    cliente_titulo = criar_parceiro(client, nome="Cliente Titulo Y")
    id_operacao = criar_operacao(app, conta["id_usuario"], cliente_op["id_parceiro"])

    resposta = _recusado(client, "id_parceiro", tipo="a receber",
                         id_parceiro=cliente_titulo["id_parceiro"], id_operacao=id_operacao,
                         valor="24.00", descricao="Parceiros divergentes")

    assert "mesmo da operação" in resposta.get_json()["erro"]


def test_tit_n13_cancelar_titulo_que_possui_baixas(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Cliente Com Baixa")
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], valor="100.00",
                               descricao="Titulo Com Baixa 13")
    inserir_baixa(app, id_titulo, id_caixa, "30.00")

    resposta = client.post(f"/api/titulos/{id_titulo}/cancelar")

    assert resposta.status_code == 409
    assert "possui baixas" in resposta.get_json()["erro"]
    assert _obter(client, id_titulo)["cancelado"] is False  # permanece ativo


def test_tit_n14_cancelar_titulo_ja_cancelado(app, client):
    conta = logar(client)
    id_titulo = inserir_titulo(app, conta["id_empresa"], None, cancelado=True,
                               descricao="Titulo Ja Cancelado 14")

    resposta = client.post(f"/api/titulos/{id_titulo}/cancelar")

    assert resposta.status_code == 409
    assert _obter(client, id_titulo)["situacao"] == "cancelado"
    assert _obter(client, id_titulo)["pode_cancelar"] is False


# ---------------------------------------------------------------------------
# Segurança e isolamento (SEG)
# ---------------------------------------------------------------------------


def test_seg_n06_titulo_com_parceiro_de_outra_empresa(app, client):
    logar(client)
    parceiro_a = criar_parceiro(client, nome="Parceiro Titulo Seg A")
    outro, _ = _outra_empresa(app)

    resposta = outro.post(
        "/api/titulos",
        json=_titulo(tipo="a receber", id_parceiro=parceiro_a["id_parceiro"],
                     vencimento="2027-02-01", descricao="Tentativa indevida"),
    )

    assert resposta.status_code == 422
    assert "id_parceiro" in campos(resposta)
    assert outro.get("/api/titulos").get_json()["dados"]["total"] == 0
    assert client.get("/api/titulos").get_json()["dados"]["total"] == 0


def test_seg_n09_id_empresa_no_corpo_e_rejeitado(app, client):
    conta_a = logar(client)
    outro, _ = _outra_empresa(app)

    resposta = outro.post(
        "/api/titulos",
        json=_titulo(id_empresa=conta_a["id_empresa"], valor="11.00",
                     descricao="Empresa forjada", vencimento="2027-02-02"),
    )

    assert resposta.status_code == 422
    assert "id_empresa" in campos(resposta)
    assert client.get("/api/titulos").get_json()["dados"]["total"] == 0


def test_operacao_de_outra_empresa_e_recusada(app, client):
    logar(client)
    outro, conta_b = _outra_empresa(app)
    parceiro_b = criar_parceiro(outro, nome="Cliente B")
    id_operacao_b = criar_operacao(app, conta_b["id_usuario"], parceiro_b["id_parceiro"])

    resposta = client.post("/api/titulos", json=_titulo(id_operacao=id_operacao_b))

    assert resposta.status_code == 422
    assert "id_operacao" in campos(resposta)


def test_titulo_sem_parceiro_herda_o_parceiro_da_operacao(app, client):
    conta = logar(client)
    cliente = criar_parceiro(client, nome="Cliente da Operacao")
    id_operacao = criar_operacao(app, conta["id_usuario"], cliente["id_parceiro"])

    dados = _criar(client, tipo="a receber", id_operacao=id_operacao)

    assert dados["parceiro"]["id_parceiro"] == cliente["id_parceiro"]
    assert dados["pode_baixar"] is True


def test_isolamento_entre_empresas_em_consulta_lista_e_cancelamento(app, client):
    """SEG-P04: listagem de títulos mostra somente os da empresa logada."""
    conta = logar(client)
    id_titulo = inserir_titulo(app, conta["id_empresa"], None, descricao="Da empresa A")
    outro, _ = _outra_empresa(app)

    assert outro.get(f"/api/titulos/{id_titulo}").status_code == 404
    assert outro.post(f"/api/titulos/{id_titulo}/cancelar").status_code == 404
    assert outro.get("/api/titulos").get_json()["dados"]["total"] == 0
    assert _obter(client, id_titulo)["cancelado"] is False


def test_rotas_de_titulos_exigem_login(client):
    assert client.get("/api/titulos").status_code == 401
    assert client.get("/api/titulos/1").status_code == 401
    assert client.post("/api/titulos", json={}).status_code == 401
    assert client.post("/api/titulos/1/cancelar").status_code == 401


# ---------------------------------------------------------------------------
# Listagem e filtros
# ---------------------------------------------------------------------------


def test_listar_filtra_por_tipo_situacao_parceiro_e_busca(app, client):
    conta = logar(client)
    cliente = criar_parceiro(client, nome="Cliente Filtro")
    fornecedor = criar_parceiro(client, nome="Fornecedor Filtro", e_cliente=False,
                                e_fornecedor=True)
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    a_receber = inserir_titulo(app, conta["id_empresa"], cliente["id_parceiro"],
                               valor="100.00", descricao="Venda de parafusos")
    a_pagar = inserir_titulo(app, conta["id_empresa"], fornecedor["id_parceiro"],
                             tipo="a pagar", valor="50.00", descricao="Frete de agosto")
    cancelado = inserir_titulo(app, conta["id_empresa"], None, cancelado=True,
                               descricao="Cancelado")
    inserir_baixa(app, a_receber, id_caixa, "40.00")
    inserir_baixa(app, a_pagar, id_caixa, "50.00")

    def ids(**filtros):
        dados = client.get("/api/titulos", query_string=filtros).get_json()["dados"]
        return {t["id_titulo"] for t in dados["titulos"]}

    assert ids(tipo="receber") == {a_receber, cancelado}
    assert ids(tipo="pagar") == {a_pagar}
    assert ids(situacao="parcial") == {a_receber}
    assert ids(situacao="quitado") == {a_pagar}
    assert ids(situacao="cancelado") == {cancelado}
    assert ids(situacao="aberto") == set()
    assert ids(id_parceiro=fornecedor["id_parceiro"]) == {a_pagar}
    assert ids(busca="frete") == {a_pagar}
    assert ids(busca="cliente filtro") == {a_receber}
    assert client.get("/api/titulos?tipo=x").status_code == 422
    assert client.get("/api/titulos?situacao=x").status_code == 422
    assert client.get("/api/titulos?limit=0").status_code == 422


def test_listar_ordena_por_vencimento(app, client):
    conta = logar(client)
    tarde = inserir_titulo(app, conta["id_empresa"], None, descricao="Tarde")
    cedo = _criar(client, vencimento="2026-11-01", descricao="Cedo")["id_titulo"]

    ordem = [t["id_titulo"] for t in client.get("/api/titulos").get_json()["dados"]["titulos"]]

    assert ordem == [cedo, tarde]


def test_corpo_nao_json_e_recusado(client):
    logar(client)

    assert client.post("/api/titulos", data="tipo=x").status_code == 415


# ---------------------------------------------------------------------------
# Concorrência: cancelar x dar baixa
# ---------------------------------------------------------------------------


def test_cancelar_espera_a_baixa_em_andamento_e_e_recusado(app, client):
    """Uma baixa confirmada enquanto o cancelamento espera a trava do título bloqueia o cancelamento."""
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Cliente Corrida")
    id_caixa = abrir_caixa(app, conta["id_usuario"])
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], valor="100.00")
    resultado: dict = {}

    with app.app_context(), get_engine().connect() as concorrente:
        concorrente.execute(
            text("SELECT id_titulo FROM titulos_financeiros WHERE id_titulo = :t FOR UPDATE"),
            {"t": id_titulo},
        )
        thread = threading.Thread(
            target=lambda: resultado.update(
                status=client.post(f"/api/titulos/{id_titulo}/cancelar").status_code
            )
        )
        thread.start()
        time.sleep(0.6)
        assert thread.is_alive(), "o cancelamento deveria esperar a trava do título"

        concorrente.execute(
            text(
                "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
                "forma_pagamento) VALUES (:t, :c, 10.00, '2026-11-09 09:00:00', 'dinheiro')"
            ),
            {"t": id_titulo, "c": id_caixa},
        )
        concorrente.commit()

    thread.join(timeout=10)
    assert resultado["status"] == 409
    assert _obter(client, id_titulo)["cancelado"] is False
