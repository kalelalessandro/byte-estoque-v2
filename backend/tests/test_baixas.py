"""Testes do módulo BAI - Baixas Financeiras (plano de testes V1.3), pela API.

Cada teste referencia o ID do caso do plano (BAI-Pxx / BAI-Nxx), de segurança
(SEG-N07/N08) ou de concorrência (CON-N03/N04). O parceiro do título é opcional:
títulos sem parceiro também aceitam baixa.
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
    fechar_caixa,
    inserir_titulo,
)
from tests.apoio_parceiros import (
    EMAIL_B,
    campos,
    criar_parceiro,
    logar,
)
from tests.helpers import CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar_baixas(app, banco_limpo):
    yield
    apagar_dados_de_baixas(app)


def _cenario(app, client, *, tipo="a receber", valor="200.00", relacionamento=None, caixa=True):
    """Empresa logada com parceiro, título (com parceiro) e, opcionalmente, caixa aberto."""
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Parceiro de Baixa", **(relacionamento or {}))
    id_titulo = inserir_titulo(
        app, conta["id_empresa"], parceiro["id_parceiro"], tipo=tipo, valor=valor,
        descricao="Pedido 1021",
    )
    id_caixa = abrir_caixa(app, conta["id_usuario"]) if caixa else None
    return conta, parceiro, id_titulo, id_caixa


def _baixa(id_titulo, id_caixa, valor="200.00", forma="dinheiro", realizado="2026-11-09 09:15"):
    return {
        "id_titulo": id_titulo,
        "id_caixa": id_caixa,
        "valor": valor,
        "forma_pagamento": forma,
        "realizado_em": realizado,
    }


def _registrar(client, id_titulo, id_caixa, **dados):
    resposta = client.post("/api/baixas", json=_baixa(id_titulo, id_caixa, **dados))
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


def _saldo(client, id_baixa) -> str:
    resposta = client.get(f"/api/baixas/{id_baixa}")
    return resposta.get_json()["dados"]["titulo"]["saldo_pendente"]


# ---------------------------------------------------------------------------
# BAI - casos positivos
# ---------------------------------------------------------------------------


def test_bai_p01_baixa_total_em_dinheiro_de_titulo_a_receber(app, client):
    _, parceiro, id_titulo, id_caixa = _cenario(app, client)

    baixa = _registrar(client, id_titulo, id_caixa)

    assert baixa["id_caixa"] == id_caixa
    assert baixa["forma_pagamento"] == "dinheiro"
    assert baixa["natureza"] == "recebimento"
    assert baixa["parceiro"]["id_parceiro"] == parceiro["id_parceiro"]  # vínculo com parceiro
    assert baixa["titulo"]["saldo_pendente"] == "0.00"


def test_bai_p02_baixa_parcial_via_pix(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="500.00")

    baixa = _registrar(client, id_titulo, id_caixa, valor="120.00", forma="Pix")

    assert baixa["forma_pagamento"] == "Pix"
    assert baixa["titulo"]["saldo_pendente"] == "380.00"


def test_bai_p03_duas_baixas_parciais_quitam_o_titulo(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, tipo="a pagar", valor="300.00")

    _registrar(client, id_titulo, id_caixa, valor="100.00", realizado="2026-11-09 09:40")
    segunda = _registrar(
        client, id_titulo, id_caixa, valor="200.00", forma="cartão", realizado="2026-11-09 09:50"
    )

    assert segunda["titulo"]["saldo_pendente"] == "0.00"
    assert contar_baixas(app, id_titulo) == 2


def test_bai_p04_baixa_com_cartao(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="90.00")

    baixa = _registrar(client, id_titulo, id_caixa, valor="90.00", forma="cartão")

    assert baixa["forma_pagamento"] == "cartão"


def test_bai_p05_baixa_de_titulo_a_pagar_em_dinheiro(app, client):
    _, _, id_titulo, id_caixa = _cenario(
        app, client, tipo="a pagar", valor="70.00",
        relacionamento={"e_cliente": False, "e_fornecedor": True},
    )

    baixa = _registrar(client, id_titulo, id_caixa, valor="70.00")

    assert baixa["natureza"] == "pagamento"
    assert baixa["titulo"]["saldo_pendente"] == "0.00"


def test_bai_p06_recebimento_pela_opcao_do_financeiro(app, client):
    """BAI-P06: mesma rota; a baixa fica no caixa aberto e quita o título."""
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="250.00")

    baixa = _registrar(
        client, id_titulo, id_caixa, valor="250.00", forma="Pix", realizado="2026-11-09 10:30"
    )

    assert baixa["id_caixa"] == id_caixa
    assert baixa["titulo"]["saldo_pendente"] == "0.00"


def test_bai_p07_listar_baixas_da_empresa(app, client):
    _, parceiro, id_titulo, id_caixa = _cenario(app, client, valor="45.00")
    _registrar(client, id_titulo, id_caixa, valor="45.00")

    dados = client.get("/api/baixas").get_json()["dados"]

    assert dados["total"] == 1
    item = dados["baixas"][0]
    assert item["titulo"]["descricao"] == "Pedido 1021"
    assert item["id_caixa"] == id_caixa
    assert item["valor"] == "45.00"
    assert item["realizado_em"] == "2026-11-09T09:15:00"
    assert item["forma_pagamento"] == "dinheiro"
    assert item["parceiro"]["nome"] == "Parceiro de Baixa"


def test_bai_p08_selecao_de_caixa_lista_apenas_caixas_abertos(app, client):
    conta, _, _, id_aberto = _cenario(app, client)
    abrir_caixa(app, conta["id_usuario"], fechado=True)

    opcoes = client.get("/api/baixas/opcoes").get_json()["dados"]

    assert [c["id_caixa"] for c in opcoes["caixas"]] == [id_aberto]
    assert opcoes["formas_pagamento"] == ["dinheiro", "Pix", "cartão"]


# ---------------------------------------------------------------------------
# BAI - casos negativos
# ---------------------------------------------------------------------------


def _recusada(client, id_titulo, id_caixa, status, campo, **dados):
    resposta = client.post("/api/baixas", json=_baixa(id_titulo, id_caixa, **dados))
    assert resposta.status_code == status, resposta.get_json()
    assert campo in campos(resposta)
    return resposta


@pytest.mark.parametrize(
    "valor, trecho",
    [
        ("0.00", "maior que zero"),  # BAI-N01
        ("-5.00", "maior que zero"),  # BAI-N02
        ("", "obrigatório"),  # BAI-N03
        ("vinte", "numérico inválido"),  # BAI-N04
    ],
)
def test_bai_n01_a_n04_valor_invalido(app, client, valor, trecho):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="60.00")

    resposta = _recusada(client, id_titulo, id_caixa, 422, "valor", valor=valor)

    assert trecho in campos(resposta)["valor"]
    assert contar_baixas(app, id_titulo) == 0


def test_bai_n05_valor_acima_do_saldo(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="100.00")

    resposta = _recusada(client, id_titulo, id_caixa, 422, "valor", valor="100.01")

    assert "excede o saldo pendente" in resposta.get_json()["erro"]
    assert contar_baixas(app, id_titulo) == 0


def test_bai_n06_soma_das_baixas_excede_o_titulo(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="100.00")
    _registrar(client, id_titulo, id_caixa, valor="80.00", realizado="2026-11-09 11:00")

    resposta = _recusada(
        client, id_titulo, id_caixa, 422, "valor", valor="30.00", forma="Pix"
    )

    assert "20.00" in resposta.get_json()["erro"]
    assert contar_baixas(app, id_titulo) == 1


def test_bai_n07_baixa_em_titulo_cancelado(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Parceiro Cancelado")
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"],
                               valor="64.00", cancelado=True)
    id_caixa = abrir_caixa(app, conta["id_usuario"])

    resposta = _recusada(client, id_titulo, id_caixa, 409, "id_titulo", valor="64.00")

    assert "cancelado" in resposta.get_json()["erro"]


def test_bai_n08_baixa_em_titulo_ja_quitado(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="65.00")
    _registrar(client, id_titulo, id_caixa, valor="65.00")

    resposta = _recusada(client, id_titulo, id_caixa, 409, "id_titulo", valor="1.00")

    assert "não possui saldo pendente" in resposta.get_json()["erro"]


def test_bai_n09_sem_forma_de_pagamento(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="66.00")

    _recusada(client, id_titulo, id_caixa, 422, "forma_pagamento", valor="66.00", forma="")


def test_bai_n09b_forma_de_pagamento_fora_da_lista(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="66.00")

    _recusada(client, id_titulo, id_caixa, 422, "forma_pagamento", valor="66.00", forma="boleto")


def test_bai_n10_sem_realizado_em(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="67.00")

    _recusada(client, id_titulo, id_caixa, 422, "realizado_em", valor="67.00", realizado="")


def test_bai_n11_data_hora_invalida(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="68.00")

    _recusada(client, id_titulo, id_caixa, 422, "realizado_em", valor="68.00",
              realizado="2026-13-45 25:61")


def test_bai_n12_sem_selecionar_titulo(app, client):
    _, _, _, id_caixa = _cenario(app, client)

    resposta = client.post(
        "/api/baixas",
        json={"id_caixa": id_caixa, "valor": "10.00", "forma_pagamento": "dinheiro",
              "realizado_em": "2026-11-09 11:50"},
    )

    assert resposta.status_code == 422
    assert "id_titulo" in campos(resposta)


def test_bai_n13_sem_caixa_aberto(app, client):
    _, _, id_titulo, _ = _cenario(app, client, valor="69.00", caixa=False)

    assert client.get("/api/baixas/opcoes").get_json()["dados"]["caixas"] == []
    resposta = client.post(
        "/api/baixas",
        json={"id_titulo": id_titulo, "valor": "69.00", "forma_pagamento": "dinheiro",
              "realizado_em": "2026-11-09 12:00"},
    )

    assert resposta.status_code == 409
    assert "Abra um caixa" in resposta.get_json()["erro"]
    assert contar_baixas(app, id_titulo) == 0


def test_baixa_em_caixa_fechado_e_recusada(app, client):
    conta, _, id_titulo, _ = _cenario(app, client, caixa=False)
    id_fechado = abrir_caixa(app, conta["id_usuario"], fechado=True)

    resposta = _recusada(client, id_titulo, id_fechado, 409, "id_caixa")

    assert "fechado" in resposta.get_json()["erro"]


# ---------------------------------------------------------------------------
# Baixa em título sem parceiro
# ---------------------------------------------------------------------------


def test_baixa_em_titulo_sem_parceiro_e_permitida(app, client):
    conta = logar(client)
    id_titulo = inserir_titulo(app, conta["id_empresa"], None, valor="80.00",
                               descricao="Conta de energia")
    id_caixa = abrir_caixa(app, conta["id_usuario"])

    baixa = _registrar(client, id_titulo, id_caixa, valor="80.00")

    assert baixa["parceiro"] is None
    assert baixa["titulo"]["saldo_pendente"] == "0.00"
    assert contar_baixas(app, id_titulo) == 1


def test_titulo_sem_parceiro_e_oferecido_nas_opcoes(app, client):
    conta, _, id_com, _ = _cenario(app, client)
    id_sem = inserir_titulo(app, conta["id_empresa"], None, valor="80.00")

    opcoes = client.get("/api/baixas/opcoes").get_json()["dados"]

    por_id = {item["id_titulo"]: item for item in opcoes["titulos"]}
    assert set(por_id) == {id_com, id_sem}
    assert por_id[id_sem]["parceiro"] is None
    assert por_id[id_com]["parceiro"]["nome"] == "Parceiro de Baixa"


def test_opcoes_oferece_so_titulos_com_saldo_e_nao_cancelados(app, client):
    conta, parceiro, id_aberto, id_caixa = _cenario(app, client, valor="100.00")
    id_quitado = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], valor="10.00")
    inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"], cancelado=True)
    _registrar(client, id_quitado, id_caixa, valor="10.00")
    _registrar(client, id_aberto, id_caixa, valor="40.00")

    titulos = client.get("/api/baixas/opcoes").get_json()["dados"]["titulos"]

    assert [(t["id_titulo"], t["saldo_pendente"]) for t in titulos] == [(id_aberto, "60.00")]


# ---------------------------------------------------------------------------
# Listagem, filtros, detalhe e segurança
# ---------------------------------------------------------------------------


def test_listar_filtra_por_tipo_forma_parceiro_e_busca(app, client):
    conta, parceiro, id_receber, id_caixa = _cenario(app, client, valor="100.00")
    id_pagar = inserir_titulo(app, conta["id_empresa"], parceiro["id_parceiro"],
                              tipo="a pagar", valor="50.00", descricao="Frete de agosto")
    _registrar(client, id_receber, id_caixa, valor="100.00", forma="Pix")
    _registrar(client, id_pagar, id_caixa, valor="50.00", forma="cartão")

    def ids(**filtros):
        dados = client.get("/api/baixas", query_string=filtros).get_json()["dados"]
        return [b["id_titulo"] for b in dados["baixas"]]

    assert ids(tipo="recebimento") == [id_receber]
    assert ids(tipo="pagamento") == [id_pagar]
    assert ids(forma="pix") == [id_receber]
    assert ids(forma="cartao") == [id_pagar]
    assert ids(busca="frete") == [id_pagar]
    assert ids(busca="parceiro de baixa") == [id_pagar, id_receber] or sorted(
        ids(busca="parceiro de baixa")
    ) == sorted([id_pagar, id_receber])
    assert ids(id_parceiro=parceiro["id_parceiro"]) != []
    assert ids(id_parceiro=999999) == []
    assert client.get("/api/baixas?tipo=xyz").status_code == 422
    assert client.get("/api/baixas?forma=boleto").status_code == 422
    assert client.get("/api/baixas?limit=0").status_code == 422


def test_consultar_baixa_mostra_titulo_parceiro_e_saldo(app, client):
    _, parceiro, id_titulo, id_caixa = _cenario(app, client, valor="300.00")
    baixa = _registrar(client, id_titulo, id_caixa, valor="100.00")

    dados = client.get(f"/api/baixas/{baixa['id_baixa']}").get_json()["dados"]

    assert dados["parceiro"]["id_parceiro"] == parceiro["id_parceiro"]
    assert dados["titulo"]["valor"] == "300.00"
    assert dados["titulo"]["total_baixado"] == "100.00"
    assert dados["titulo"]["saldo_pendente"] == "200.00"
    assert client.get("/api/baixas/999999").status_code == 404


def test_campo_nao_permitido_e_recusado(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client)

    resposta = client.post("/api/baixas", json={**_baixa(id_titulo, id_caixa), "id_empresa": 1})

    assert resposta.status_code == 422
    assert "id_empresa" in campos(resposta)


def test_rotas_de_baixas_exigem_login(client):
    assert client.get("/api/baixas").status_code == 401
    assert client.get("/api/baixas/opcoes").status_code == 401
    assert client.get("/api/baixas/1").status_code == 401
    assert client.post("/api/baixas", json={}).status_code == 401
    assert client.get("/api/interacoes").status_code == 401


def _outra_empresa(app):
    outro = app.test_client()
    conta = logar(outro, EMAIL_B, CNPJ_VALIDO_2)
    parceiro = criar_parceiro(outro, nome="Parceiro da Empresa B")
    return outro, conta, parceiro


def test_seg_n07_baixa_em_titulo_de_outra_empresa(app, client):
    _, _, id_titulo_a, _ = _cenario(app, client, valor="50.00")
    outro, conta_b, _ = _outra_empresa(app)
    caixa_b = abrir_caixa(app, conta_b["id_usuario"])

    resposta = outro.post("/api/baixas", json=_baixa(id_titulo_a, caixa_b, valor="5.00"))

    assert resposta.status_code == 422
    assert "id_titulo" in campos(resposta)
    assert contar_baixas(app, id_titulo_a) == 0  # saldo do título de A inalterado


def test_seg_n08_baixa_em_caixa_de_outra_empresa(app, client):
    _, conta_a, id_titulo_a, id_caixa_a = _cenario(app, client)
    outro, conta_b, parceiro_b = _outra_empresa(app)
    id_titulo_b = inserir_titulo(app, conta_b["id_empresa"], parceiro_b["id_parceiro"],
                                 valor="5.00")

    resposta = outro.post("/api/baixas", json=_baixa(id_titulo_b, id_caixa_a, valor="5.00",
                                                    forma="Pix"))

    assert resposta.status_code == 422
    assert "id_caixa" in campos(resposta)
    assert contar_baixas(app, id_titulo_b) == 0


def test_isolamento_de_listagem_detalhe_e_opcoes(app, client):
    _, _, id_titulo_a, id_caixa_a = _cenario(app, client, valor="50.00")
    baixa_a = _registrar(client, id_titulo_a, id_caixa_a, valor="50.00")
    outro, _, _ = _outra_empresa(app)

    assert outro.get("/api/baixas").get_json()["dados"]["total"] == 0
    assert outro.get(f"/api/baixas/{baixa_a['id_baixa']}").status_code == 404
    opcoes = outro.get("/api/baixas/opcoes").get_json()["dados"]
    assert opcoes["titulos"] == [] and opcoes["caixas"] == []


def test_titulo_com_parceiro_de_outra_empresa_e_recusado(app, client):
    """Dado inconsistente (parceiro de outra empresa no título): a baixa não é feita."""
    conta, _, _, id_caixa = _cenario(app, client)
    _, _, parceiro_b = _outra_empresa(app)
    id_titulo = inserir_titulo(app, conta["id_empresa"], parceiro_b["id_parceiro"], valor="9.00")

    resposta = _recusada(client, id_titulo, id_caixa, 422, "id_titulo", valor="9.00")

    assert "parceiro" in resposta.get_json()["erro"]


# ---------------------------------------------------------------------------
# Concorrência (CON)
#
# Os testes forçam a corrida de forma determinística: uma SEGUNDA sessão do banco
# segura a trava da linha, a requisição de baixa fica esperando, e só então a segunda
# sessão confirma uma mudança concorrente. Sem as travas (SELECT ... FOR UPDATE) a
# requisição não esperaria e registraria a baixa com dados velhos.
# ---------------------------------------------------------------------------


def _requisitar_em_thread(cliente, corpo):
    """Dispara ``POST /api/baixas`` numa thread; devolve ``(thread, resultado)``."""
    resultado: dict = {}

    def executar():
        resultado["status"] = cliente.post("/api/baixas", json=corpo).status_code

    thread = threading.Thread(target=executar)
    thread.start()
    return thread, resultado


def test_con_n03_baixas_simultaneas_nao_passam_do_saldo(app, client):
    """Baixa concorrente de 100,00 confirmada enquanto outra espera: a espera é recusada."""
    _, _, id_titulo, id_caixa = _cenario(app, client, valor="100.00")

    with app.app_context(), get_engine().connect() as concorrente:
        # A "outra sessão" trava o título (como faria uma baixa em andamento).
        concorrente.execute(
            text("SELECT id_titulo FROM titulos_financeiros WHERE id_titulo = :t FOR UPDATE"),
            {"t": id_titulo},
        )
        thread, resultado = _requisitar_em_thread(
            client, _baixa(id_titulo, id_caixa, valor="100.00")
        )
        time.sleep(0.6)
        assert thread.is_alive(), "a baixa deveria esperar a trava do título"

        concorrente.execute(
            text(
                "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
                "forma_pagamento) VALUES (:t, :c, 100.00, '2026-11-09 09:00:00', 'dinheiro')"
            ),
            {"t": id_titulo, "c": id_caixa},
        )
        concorrente.commit()  # libera a trava

    thread.join(timeout=10)
    assert resultado["status"] == 409  # saldo já zerado pela baixa concorrente
    assert contar_baixas(app, id_titulo) == 1


def test_con_n04_baixa_durante_o_fechamento_do_caixa_e_recusada(app, client):
    """Caixa fechado por outra sessão enquanto a baixa espera: a baixa é recusada."""
    _, _, id_titulo, id_caixa = _cenario(app, client)

    with app.app_context(), get_engine().connect() as concorrente:
        # O fechamento do caixa trava a sessão de caixa.
        concorrente.execute(
            text("SELECT id_caixa FROM caixas WHERE id_caixa = :c FOR UPDATE"), {"c": id_caixa}
        )
        thread, resultado = _requisitar_em_thread(
            client, _baixa(id_titulo, id_caixa, valor="40.00")
        )
        time.sleep(0.6)
        assert thread.is_alive(), "a baixa deveria esperar a trava do caixa"

        concorrente.execute(
            text(
                "UPDATE caixas SET fechado_em = '2026-11-09 18:00:00', valor_contado = 100.00 "
                "WHERE id_caixa = :c"
            ),
            {"c": id_caixa},
        )
        concorrente.commit()

    thread.join(timeout=10)
    assert resultado["status"] == 409
    assert contar_baixas(app, id_titulo) == 0


def test_baixa_depois_do_fechamento_do_caixa_e_recusada(app, client):
    _, _, id_titulo, id_caixa = _cenario(app, client)
    fechar_caixa(app, id_caixa)

    resposta = client.post("/api/baixas", json=_baixa(id_titulo, id_caixa, valor="40.00"))

    assert resposta.status_code == 409
    assert contar_baixas(app, id_titulo) == 0
