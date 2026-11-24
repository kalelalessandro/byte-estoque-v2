"""Testes do módulo de Gestão de Usuários/Funcionários.

Cobrem criação/lista/edição/exclusão, isolamento entre empresas, cargos
Dono x Funcionário, login do funcionário, bloqueio de exclusão do Dono,
exclusão da própria conta e o caso de usuário com histórico (FK RESTRICT).
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.apoio_baixas import (
    abrir_caixa,
    apagar_dados_de_baixas,
    criar_operacao,
)
from tests.apoio_parceiros import (
    EMPRESAS_COM_PARCEIROS,
    criar_parceiro,
    logar,
)
from tests.helpers import CNPJ_VALIDO_2

EMAIL_OWNER = "usr.owner@exemplo.com.br"
EMAIL_OWNER_B = "usr.owner.b@exemplo.com.br"
CNPJ_B = CNPJ_VALIDO_2


def _apagar_operacoes_das_empresas(app, ids_empresas: list[int]) -> None:
    if not ids_empresas:
        return
    with app.app_context(), get_engine().begin() as conexao:
        conexao.execute(
            text(
                "DELETE FROM operacao_itens WHERE id_operacao IN "
                "(SELECT o.id_operacao FROM operacoes o JOIN usuarios u "
                " ON u.id_usuario = o.id_usuario WHERE u.id_empresa IN :ids)"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": ids_empresas},
        )
        conexao.execute(
            text(
                "DELETE FROM operacoes WHERE id_usuario IN "
                "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": ids_empresas},
        )


@pytest.fixture(autouse=True)
def limpar(app, banco_limpo):
    yield
    ids_empresas = list(EMPRESAS_COM_PARCEIROS)
    apagar_dados_de_baixas(app)
    _apagar_operacoes_das_empresas(app, ids_empresas)


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
    """USR-N11: alterar e-mail para um já usado por outro usuário."""
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
    """USR-P05/USR-P08: Dono apaga funcionário."""
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
    """USR-N16: apagar funcionário que abriu caixa é bloqueado."""
    _logar(client)
    funcionario = _funcionario_ok(client)
    abrir_caixa(app, funcionario["id_usuario"])

    resposta = client.delete(f"/api/usuarios/{funcionario['id_usuario']}")

    assert resposta.status_code == 409
    assert "vinculados" in resposta.get_json()["erro"]
    listagem = client.get("/api/usuarios").get_json()["dados"]
    assert any(item["id_usuario"] == funcionario["id_usuario"] for item in listagem["usuarios"])


def test_usr_n07_isolamento_entre_empresas(app, client):
    """SEG-P03: lista de usuários mostra somente os da própria empresa."""
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


# ---------------------------------------------------------------------------
# Casos do plano V1.4 ainda sem teste específico
# ---------------------------------------------------------------------------


def test_usr_p02_criar_funcionario_sem_telefone(client):
    _logar(client)
    resposta = _criar_funcionario(client, telefone=None)

    assert resposta.status_code == 201, resposta.get_json()
    assert resposta.get_json()["dados"]["telefone"] is None




def test_usr_p05_alterar_nome_do_funcionario(client):
    _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}",
        json={"nome": "Nome Alterado"},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["nome"] == "Nome Alterado"


def test_usr_p06_alterar_email_do_funcionario(client):
    _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}",
        json={"email": "func.novo.email@exemplo.com.br"},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["email"] == "func.novo.email@exemplo.com.br"


def test_usr_p07_salvar_mantendo_o_proprio_email(client):
    _logar(client)
    funcionario = _funcionario_ok(client)

    resposta = client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}",
        json={"email": funcionario["email"], "nome": "Mesmo Email"},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["email"] == funcionario["email"]


def test_usr_p09_funcionario_apagado_nao_consegue_entrar(app, client):
    _logar(client)
    funcionario = _funcionario_ok(client)
    assert client.delete(f"/api/usuarios/{funcionario['id_usuario']}").status_code == 200

    outro = app.test_client()
    assert _entrar(outro, funcionario["email"]).status_code == 401


def test_usr_p10_acessar_o_proprio_usuario(client):
    owner = _logar(client)

    resposta = client.get("/api/auth/me")

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["id_usuario"] == owner["id_usuario"]


def test_usr_p11_alterar_nome_do_proprio_usuario(client):
    owner = _logar(client)

    resposta = client.patch(
        f"/api/usuarios/{owner['id_usuario']}", json={"nome": "Dono Renomeado"}
    )

    assert resposta.status_code == 200
    assert client.get("/api/auth/me").get_json()["dados"]["nome"] == "Dono Renomeado"


def test_usr_p12_alterar_email_do_proprio_usuario_e_entrar_com_ele(client):
    owner = _logar(client)

    resposta = client.patch(
        f"/api/usuarios/{owner['id_usuario']}",
        json={"email": "dono.novo@exemplo.com.br"},
    )
    assert resposta.status_code == 200

    assert _entrar(client, "dono.novo@exemplo.com.br", "Senha#Teste1").status_code == 200


@pytest.mark.parametrize(
    "id_caso,campo,valor",
    [
        ("USR-N03", "senha", ""),
        ("USR-N07", "email", "email-invalido"),
        ("USR-N10", "email", "a" * 245 + "@exemplo.com.br"),
    ],
)
def test_usr_validacoes_de_criacao_do_plano(client, id_caso, campo, valor):
    _logar(client)
    resposta = _criar_funcionario(client, **{campo: valor})

    assert resposta.status_code == 422, (id_caso, resposta.get_json())
    assert campo in resposta.get_json()["campos"], (id_caso, resposta.get_json())




def test_usr_n06_email_duplicado_so_diferenciando_maiusculas(client):
    _logar(client)
    _funcionario_ok(client, email="case.func@exemplo.com.br")

    resposta = _criar_funcionario(client, email="CASE.FUNC@exemplo.com.br")

    assert resposta.status_code == 409


@pytest.mark.parametrize(
    "id_caso,campo",
    [("USR-N12", "nome"), ("USR-N13", "email")],
)
def test_usr_validacoes_de_edicao_do_plano(client, id_caso, campo):
    _logar(client)
    funcionario = _funcionario_ok(client)
    valor = "   " if campo == "nome" else ""

    resposta = client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}", json={campo: valor}
    )

    assert resposta.status_code == 422, (id_caso, resposta.get_json())
    assert campo in resposta.get_json()["campos"], (id_caso, resposta.get_json())


def test_usr_n14_apagar_funcionario_com_interacoes_e_bloqueado(app, client):
    _logar(client)
    funcionario = _funcionario_ok(client)
    parceiro = criar_parceiro(client, nome="Parceiro USR N14")
    funcionario_client = app.test_client()
    assert _entrar(funcionario_client, funcionario["email"]).status_code == 200
    interacao = funcionario_client.post(
        f"/api/parceiros/{parceiro['id_parceiro']}/interacoes",
        json={
            "ocorrencia": "2026-11-10",
            "canal": "telefone",
            "descricao": "Interação do funcionário",
        },
    )
    assert interacao.status_code == 201, interacao.get_json()

    resposta = client.delete(f"/api/usuarios/{funcionario['id_usuario']}")

    assert resposta.status_code == 409


def test_usr_n15_apagar_funcionario_responsavel_por_operacao_e_bloqueado(app, client):
    _logar(client)
    funcionario = _funcionario_ok(client)
    criar_operacao(app, funcionario["id_usuario"], None)

    resposta = client.delete(f"/api/usuarios/{funcionario['id_usuario']}")

    assert resposta.status_code == 409


def test_usr_n18_alterar_email_do_proprio_usuario_para_email_duplicado(client):
    owner = _logar(client)
    _funcionario_ok(client, email="email.usado@exemplo.com.br")

    resposta = client.patch(
        f"/api/usuarios/{owner['id_usuario']}",
        json={"email": "email.usado@exemplo.com.br"},
    )

    assert resposta.status_code == 409


def test_usr_n19_alterar_proprio_usuario_com_nome_vazio(client):
    owner = _logar(client)

    resposta = client.patch(
        f"/api/usuarios/{owner['id_usuario']}", json={"nome": "   "}
    )

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["campos"]


def test_usr_n20_funcionario_cria_outro_funcionario_na_mesma_empresa(app, client):
    """Caso revisado no plano V1.4: sem sistema de permissões, funcionário também cria."""
    owner = _logar(client)
    _funcionario_ok(client)
    funcionario_client = app.test_client()
    assert _entrar(funcionario_client, "func.usuario@exemplo.com.br").status_code == 200

    resposta = _criar_funcionario(
        funcionario_client,
        nome="Segundo Funcionário",
        email="segundo.func@exemplo.com.br",
    )

    assert resposta.status_code == 201, resposta.get_json()
    listagem = client.get("/api/usuarios").get_json()["dados"]
    assert listagem["total"] == 3
    assert owner["id_usuario"] in {u["id_usuario"] for u in listagem["usuarios"]}


def test_seg_n10_funcionario_nao_se_promove_a_admin_sistema(app, client):
    """SEG-N10: funcionário não consegue alterar admin_sistema pela própria edição."""
    _logar(client)
    funcionario = _funcionario_ok(client)
    funcionario_client = app.test_client()
    assert _entrar(funcionario_client, funcionario["email"]).status_code == 200

    resposta = funcionario_client.patch(
        f"/api/usuarios/{funcionario['id_usuario']}",
        json={"admin_sistema": True},
    )

    assert resposta.status_code == 422
    assert "admin_sistema" in resposta.get_json()["campos"]
    me = funcionario_client.get("/api/auth/me").get_json()["dados"]
    assert me["admin_sistema"] is False
    assert me["dono"] is False

