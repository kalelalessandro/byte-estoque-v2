"""Testes do módulo INT - Interações com parceiros (plano de testes V1.3), pela API.

Interação = fato comercial com o parceiro (contratos e compras). O TIPO fica na coluna
``canal``; os casos do plano usam valores como "telefone"/"WhatsApp" só porque o campo é
texto livre: o que vale aqui é o limite (30), a obrigatoriedade e a regra de empresa.
Os testes ``test_tipos_de_negocio_*`` cobrem os exemplos reais (compra, reembolso, contrato,
pagamento).

Cada teste referencia o ID do caso do plano (INT-Pxx / INT-Nxx). "Consultar Interação"
é o campo ``interacoes`` do ``GET /api/parceiros/<id>``.
"""

from __future__ import annotations

import pytest

from tests.apoio_parceiros import (
    EMAIL_B,
    apagar_dados_de_parceiros,
    campos,
    criar_parceiro,
    logar,
    obter_parceiro,
)
from tests.helpers import CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar_parceiros(app, banco_limpo):
    """Apaga interações/parceiros ANTES de o banco_limpo remover usuários/empresas."""
    yield
    apagar_dados_de_parceiros(app)


def _rota(id_parceiro: int, interacao_id: int | None = None) -> str:
    base = f"/api/parceiros/{id_parceiro}/interacoes"
    return base if interacao_id is None else f"{base}/{interacao_id}"


def _interacao(data="2026-11-03", canal="telefone", descricao="Cliente pediu orçamento"):
    return {"ocorrencia": data, "canal": canal, "descricao": descricao}


def _registrar(client, id_parceiro: int, **sobrescritas) -> dict:
    resposta = client.post(_rota(id_parceiro), json={**_interacao(), **sobrescritas})
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


# ---------------------------------------------------------------------------
# INT - casos positivos
# ---------------------------------------------------------------------------


def test_int_p01_registrar_interacao_por_telefone(client):
    """INT-P01: o usuário logado é o responsável e ela aparece no histórico."""
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 01")

    resposta = client.post(
        _rota(parceiro["id_parceiro"]),
        json=_interacao("2026-11-03", "telefone", "Cliente solicitou orçamento de 200 parafusos"),
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 201
    assert dados["id_usuario"] == conta["id_usuario"]
    assert dados["usuario_nome"] == conta["nome"]
    assert dados["ocorrencia"] == "2026-11-03"
    historico = obter_parceiro(client, parceiro["id_parceiro"])["interacoes"]
    assert [i["interacao_id"] for i in historico] == [dados["interacao_id"]]


def test_int_p02_registrar_interacao_logo_apos_inserir_parceiro(client):
    """INT-P02."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro Novo")

    dados = _registrar(
        client,
        parceiro["id_parceiro"],
        ocorrencia="2026-11-05",
        canal="WhatsApp",
        descricao="Primeiro contato pós-cadastro",
    )

    assert dados["canal"] == "WhatsApp"
    assert len(obter_parceiro(client, parceiro["id_parceiro"])["interacoes"]) == 1


def test_int_p03_duas_interacoes_no_mesmo_dia(client):
    """INT-P03."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 05")
    _registrar(client, parceiro["id_parceiro"], ocorrencia="2026-11-02", descricao="Primeira ligação")

    resposta = client.post(
        _rota(parceiro["id_parceiro"]),
        json=_interacao("2026-11-02", "e-mail", "Confirmação por escrito da ligação"),
    )

    assert resposta.status_code == 201
    assert len(obter_parceiro(client, parceiro["id_parceiro"])["interacoes"]) == 2


def test_int_p04_consultar_interacoes_registradas(client):
    """INT-P04: data, canal, descrição e usuário responsável (mais recentes primeiro)."""
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 06")
    _registrar(client, parceiro["id_parceiro"], ocorrencia="2026-11-01", descricao="Antiga")
    _registrar(client, parceiro["id_parceiro"], ocorrencia="2026-11-04", descricao="Recente")

    historico = obter_parceiro(client, parceiro["id_parceiro"])["interacoes"]

    assert [i["descricao"] for i in historico] == ["Recente", "Antiga"]
    assert historico[0]["canal"] == "telefone"
    assert historico[0]["usuario_nome"] == conta["nome"]


def test_int_p05_consultar_parceiro_sem_interacoes(client):
    """INT-P05: nenhuma lista (a tela mostra a mensagem de vazio)."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 07")

    assert obter_parceiro(client, parceiro["id_parceiro"])["interacoes"] == []


def test_int_p06_alterar_a_descricao_de_uma_interacao(client):
    """INT-P06."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 08")
    interacao = _registrar(client, parceiro["id_parceiro"], descricao="Descrição original")

    resposta = client.patch(
        _rota(parceiro["id_parceiro"], interacao["interacao_id"]),
        json={"descricao": "Descrição corrigida após reunião"},
    )

    assert resposta.status_code == 200
    historico = obter_parceiro(client, parceiro["id_parceiro"])["interacoes"]
    assert historico[0]["descricao"] == "Descrição corrigida após reunião"
    assert historico[0]["canal"] == "telefone"  # o que não foi enviado não muda


def test_int_p07_canal_com_exatamente_30_caracteres(client):
    """INT-P07."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 10")

    dados = _registrar(client, parceiro["id_parceiro"], ocorrencia="2026-11-04", canal="c" * 30)

    assert len(dados["canal"]) == 30


# ---------------------------------------------------------------------------
# INT - casos negativos
# ---------------------------------------------------------------------------


def test_int_n01_registrar_com_descricao_vazia(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 11")

    resposta = client.post(_rota(parceiro["id_parceiro"]), json=_interacao(descricao=""))

    assert resposta.status_code == 422
    assert "descricao" in campos(resposta)


def test_int_n02_registrar_com_canal_vazio(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 12")

    resposta = client.post(_rota(parceiro["id_parceiro"]), json=_interacao(canal=""))

    assert resposta.status_code == 422
    assert "canal" in campos(resposta)


def test_int_n03_registrar_com_data_vazia(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 13")

    resposta = client.post(_rota(parceiro["id_parceiro"]), json=_interacao(data=""))

    assert resposta.status_code == 422
    assert "ocorrencia" in campos(resposta)


def test_int_n04_registrar_com_canal_de_31_caracteres(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 14")

    resposta = client.post(_rota(parceiro["id_parceiro"]), json=_interacao(canal="d" * 31))

    assert resposta.status_code == 422
    assert "no máximo 30" in campos(resposta)["canal"]


@pytest.mark.parametrize("data", ["ontem"])
def test_int_n05_registrar_com_data_inexistente_ou_invalida(client, data):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 15")

    resposta = client.post(_rota(parceiro["id_parceiro"]), json=_interacao(data=data))

    assert resposta.status_code == 422
    assert "ocorrencia" in campos(resposta)


def test_int_n06_alterar_deixando_a_descricao_vazia(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 16")
    interacao = _registrar(client, parceiro["id_parceiro"], descricao="Original")

    resposta = client.patch(
        _rota(parceiro["id_parceiro"], interacao["interacao_id"]), json={"descricao": ""}
    )

    assert resposta.status_code == 422
    assert "descricao" in campos(resposta)
    assert obter_parceiro(client, parceiro["id_parceiro"])["interacoes"][0]["descricao"] == "Original"


def test_int_n07_alterar_com_canal_de_31_caracteres(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Int Parceiro 17")
    interacao = _registrar(client, parceiro["id_parceiro"])

    resposta = client.patch(
        _rota(parceiro["id_parceiro"], interacao["interacao_id"]), json={"canal": "e" * 31}
    )

    assert resposta.status_code == 422
    assert "canal" in campos(resposta)


# ---------------------------------------------------------------------------
# Extras: isolamento entre empresas e regras de integridade
# ---------------------------------------------------------------------------












def test_interacao_de_parceiro_de_outra_empresa_responde_404(app, client):
    """SEG-N05: interação em parceiro de outra empresa responde 404."""
    logar(client)
    parceiro_a = criar_parceiro(client, nome="Parceiro da Empresa A")
    interacao_a = _registrar(client, parceiro_a["id_parceiro"])

    outro = app.test_client()
    logar(outro, EMAIL_B, CNPJ_VALIDO_2)
    parceiro_b = criar_parceiro(outro, nome="Parceiro da Empresa B")

    # Empresa B não registra nem altera nada no parceiro da empresa A.
    assert outro.post(_rota(parceiro_a["id_parceiro"]), json=_interacao()).status_code == 404
    assert (
        outro.patch(
            _rota(parceiro_a["id_parceiro"], interacao_a["interacao_id"]), json={"canal": "x"}
        ).status_code
        == 404
    )
    # Nem usando um parceiro DELA com a interação da empresa A.
    assert (
        outro.patch(
            _rota(parceiro_b["id_parceiro"], interacao_a["interacao_id"]), json={"canal": "x"}
        ).status_code
        == 404
    )
    assert obter_parceiro(client, parceiro_a["id_parceiro"])["interacoes"][0]["canal"] == "telefone"




# ---------------------------------------------------------------------------
# GET /api/interacoes: o "guia" da tela de baixas financeiras
# ---------------------------------------------------------------------------








def test_seg_n14_xss_na_descricao_da_interacao_fica_como_texto(client):
    """SEG-N14: payload de XSS na descrição é retornado como texto JSON."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Parceiro SEG N14")
    payload = "<script>alert('xss')</script>"

    criada = _registrar(client, parceiro["id_parceiro"], descricao=payload)

    assert criada["descricao"] == payload
    assert client.get(f"/api/parceiros/{parceiro['id_parceiro']}").is_json
