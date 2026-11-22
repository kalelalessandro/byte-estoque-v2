"""Testes do módulo de Gestão de Usuários/Funcionários.

Cobrem criação/lista/edição/exclusão, isolamento entre empresas, cargos
Dono x Funcionário, login do funcionário, bloqueio de exclusão do Dono,
exclusão da própria conta e o caso de usuário com histórico (FK RESTRICT).
"""

from __future__ import annotations

import pytest

from tests.apoio_baixas import abrir_caixa, apagar_dados_de_baixas
from tests.apoio_parceiros import EMPRESAS_COM_PARCEIROS, logar
from tests.helpers import CNPJ_VALIDO_2

EMAIL_OWNER = "usr.owner@exemplo.com.br"
EMAIL_OWNER_B = "usr.owner.b@exemplo.com.br"
CNPJ_B = CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar(app, banco_limpo):
    yield
    apagar_dados_de_baixas(app)


def _logar(client, email=EMAIL_OWNER, cnpj="11222333000181"):
    return logar(client, email=email, cnpj=cnpj)


def _criar_funcionario(client, **sobrescritas):
    dados = {
        "nome": "Funcionário Teste",
        "email": "func.usuario@exemplo.com.br",
        "senha": "Func#123",
        "telefone": "81999998888",
    }
    dados.update(sobrescritas)
    return client.post("/api/usuarios", json=dados)


def _funcionario_ok(client, **sobrescritas) -> dict:
    resposta = _criar_funcionario(client, **sobrescritas)
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


def _entrar(client, email, senha="Func#123"):
    return client.post("/api/auth/login", json={"email": email, "senha": senha})


# ---------------------------------------------------------------------------
# Criação e listagem
# ---------------------------------------------------------------------------


def test_usr_p01_criar_funcionario_na_mesma_empresa(client):
    owner = _logar(client)

    dados = _funcionario_ok(client)

    assert dados["id_empresa"] == owner["id_empresa"]
    assert dados["cargo"] == "Funcionario"
    assert dados["admin_sistema"] is False
    assert dados["dono"] is False


def test_usr_p02_listar_inclui_dono_e_funcionario(client):
    owner = _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.get("/api/usuarios")

    assert resposta.status_code == 200
    dados = resposta.get_json()["dados"]
    assert dados["total"] == 2
    por_id = {item["id_usuario"]: item for item in dados["usuarios"]}
    assert por_id[owner["id_usuario"]]["dono"] is True
    assert por_id[owner["id_usuario"]]["cargo"] == "Administrador"
    assert por_id[funcionario["id_usuario"]]["dono"] is False
    assert por_id[funcionario["id_usuario"]]["cargo"] == "Funcionario"


def test_usr_p03_funcionario_consegue_entrar_e_ver_mesma_empresa(app, client):
    owner = _logar(client)
    funcionario = _funcionario_ok(client)
    funcionario_client = app.test_client()

    login = _entrar(funcionario_client, funcionario["email"])
    assert login.status_code == 200
    assert login.get_json()["dados"]["id_empresa"] == owner["id_empresa"]

    me = funcionario_client.get("/api/auth/me").get_json()["dados"]
    assert me["dono"] is False
    assert me["empresa"]["id_empresa"] == owner["id_empresa"]


def test_usr_n01_email_duplicado(client):
    _logar(client)
    _funcionario_ok(client, email="duplicado@exemplo.com.br")

    resposta = _criar_funcionario(client, email="duplicado@exemplo.com.br")

    assert resposta.status_code == 409
    assert "email" in resposta.get_json()["campos"]


def test_usr_n02_validacao_de_campos_e_cargo_no_corpo(client):
    _logar(client)

    sem_nome = _criar_funcionario(client, nome="  ")
    assert sem_nome.status_code == 422
    assert "nome" in sem_nome.get_json()["campos"]

    cargo_tentado = _criar_funcionario(client, cargo="Administrador")
    assert cargo_tentado.status_code == 422
    assert "cargo" in cargo_tentado.get_json()["campos"]


# ---------------------------------------------------------------------------
# Alteração
# ---------------------------------------------------------------------------


def test_usr_p04_atualizar_funcionario_e_senha(app, client):
    _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}",
        json={
            "nome": "Funcionário Atualizado",
            "email": "atualizado@exemplo.com.br",
            "telefone": "(81) 98888-7777",
            "senha": "Nova#Senha1",
        },
    )

    assert resposta.status_code == 200, resposta.get_json()
    dados = resposta.get_json()["dados"]
    assert dados["nome"] == "Funcionário Atualizado"
    assert dados["email"] == "atualizado@exemplo.com.br"
    assert dados["dono"] is False

    outro = app.test_client()
    assert _entrar(outro, funcionario["email"]).status_code == 401
    assert _entrar(outro, "atualizado@exemplo.com.br", "Nova#Senha1").status_code == 200


def test_usr_n03_atualizar_com_email_duplicado(client):
    owner = _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}",
        json={"email": owner["id_usuario"] and "usr.owner@exemplo.com.br"},
    )

    assert resposta.status_code == 409


# ---------------------------------------------------------------------------
# Exclusão e permissões
# ---------------------------------------------------------------------------


def test_usr_p05_dono_apaga_funcionario(client):
    _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.delete(f"/api/usuarios/{funcionario['id_usuario']}")

    assert resposta.status_code == 200
    listagem = client.get("/api/usuarios").get_json()["dados"]
    assert listagem["total"] == 1
    assert listagem["usuarios"][0]["dono"] is True


def test_usr_n04_funcionario_nao_pode_apagar_dono(app, client):
    owner = _logar(client)
    _funcionario_ok(client)
    funcionario_client = app.test_client()
    assert _entrar(funcionario_client, "func.usuario@exemplo.com.br").status_code == 200

    resposta = funcionario_client.delete(f"/api/usuarios/{owner['id_usuario']}")

    assert resposta.status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_usr_n09_funcionario_nao_pode_alterar_dono(app, client):
    owner = _logar(client)
    _funcionario_ok(client)
    funcionario_client = app.test_client()
    assert _entrar(funcionario_client, "func.usuario@exemplo.com.br").status_code == 200

    resposta = funcionario_client.patch(
        f"/api/usuarios/{owner['id_usuario']}",
        json={"nome": "Nome Alterado Pelo Funcionário"},
    )

    assert resposta.status_code == 403
    assert (
        client.get("/api/auth/me").get_json()["dados"]["nome"]
        == owner["nome"]
    )


def test_usr_n05_nao_pode_apagar_a_si_mesmo(client):
    owner = _logar(client)

    resposta = client.delete(f"/api/usuarios/{owner['id_usuario']}")

    assert resposta.status_code == 409
    assert client.get("/api/usuarios").get_json()["dados"]["total"] == 1


def test_usr_n06_apagar_funcionario_com_historico_e_bloqueado(app, client):
    _logar(client)
    funcionario = _funcionario_ok(client)
    abrir_caixa(app, funcionario["id_usuario"])

    resposta = client.delete(f"/api/usuarios/{funcionario['id_usuario']}")

    assert resposta.status_code == 409
    assert "vinculados" in resposta.get_json()["erro"]
    listagem = client.get("/api/usuarios").get_json()["dados"]
    assert any(item["id_usuario"] == funcionario["id_usuario"] for item in listagem["usuarios"])


def test_usr_n07_isolamento_entre_empresas(app, client):
    _logar(client)
    funcionario = _funcionario_ok(client)

    outro = app.test_client()
    _logar(outro, EMAIL_OWNER_B, CNPJ_B)

    assert outro.get("/api/usuarios").get_json()["dados"]["total"] == 1
    assert (
        outro.patch(
            f"/api/usuarios/{funcionario['id_usuario']}",
            json={"nome": "Invasão"},
        ).status_code
        == 404
    )
    assert outro.delete(f"/api/usuarios/{funcionario['id_usuario']}").status_code == 404


def test_usr_n08_rotas_exigem_login(client):
    assert client.get("/api/usuarios").status_code == 401
    assert client.post("/api/usuarios", json={}).status_code == 401
    assert client.delete("/api/usuarios/1").status_code == 401
