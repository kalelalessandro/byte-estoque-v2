"""Testes do vínculo obrigatório usuário ↔ empresa.

Cobrem a transação atômica do cadastro e o contexto de empresa devolvido pela
API no login/``me`` (incluindo a sinalização defensiva de redirecionamento).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.app.core.auth_utils import (
    ROTA_CADASTRO_EMPRESA,
    serializar_contexto_empresa,
)
from src.app.db import get_engine
from tests.helpers import cadastrar, criar_conta, entrar, me, usuario_valido

CNPJ_ATOMICO = "55443322000105"
EMAIL_ATOMICO = "fluxo.atomico@exemplo.com.br"


def test_login_retorna_contexto_da_empresa(client):
    """Login devolve a empresa do usuário e não pede novo cadastro de empresa."""
    conta = criar_conta(
        client,
        email="fluxo.login@exemplo.com.br",
        senha="Fluxo#Login1",
        nome="Fluxo Login",
    )

    resposta = entrar(client, "fluxo.login@exemplo.com.br", "Fluxo#Login1")
    corpo = resposta.get_json()

    assert resposta.status_code == 200
    assert corpo["dados"]["empresa"]["id_empresa"] == conta["empresa"]["id_empresa"]
    assert corpo["dados"]["empresa"]["cnpj"] == "11222333000181"
    assert corpo["dados"]["precisa_cadastrar_empresa"] is False
    assert corpo["dados"]["redirecionar_para"] is None


def test_me_retorna_contexto_da_empresa(client):
    """A rota protegida /me também devolve o contexto multi-tenant."""
    conta = criar_conta(
        client,
        email="fluxo.me@exemplo.com.br",
        senha="Fluxo#Me1234",
        nome="Fluxo Me",
    )
    login = entrar(client, "fluxo.me@exemplo.com.br", "Fluxo#Me1234")
    assert login.status_code == 200

    resposta = me(client)
    corpo = resposta.get_json()

    assert resposta.status_code == 200
    assert corpo["dados"]["empresa"]["id_empresa"] == conta["empresa"]["id_empresa"]
    assert corpo["dados"]["precisa_cadastrar_empresa"] is False
    assert corpo["dados"]["redirecionar_para"] is None


def test_contexto_defensivo_sem_empresa_sinaliza_redirecionamento():
    """Sem empresa, a API sinaliza que o front-end deve ir ao cadastro de empresa."""

    class UsuarioSemEmpresa:
        empresa = None

    contexto = serializar_contexto_empresa(UsuarioSemEmpresa())

    assert contexto["empresa"] is None
    assert contexto["precisa_cadastrar_empresa"] is True
    assert contexto["redirecionar_para"] == ROTA_CADASTRO_EMPRESA


def test_cadastro_atomico_desfaz_empresa_quando_usuario_falha(
    client, app, monkeypatch
):
    """Se o INSERT do usuário falhar, a empresa criada antes é desfeita (rollback)."""

    def falhar_ao_obter_cargo(*args, **kwargs):
        raise IntegrityError(
            "falha simulada no cargo",
            None,
            Exception("falha simulada no cargo"),
        )

    monkeypatch.setattr(
        "src.app.core.signup._obter_ou_criar_cargo", falhar_ao_obter_cargo
    )

    resposta = cadastrar(
        client,
        empresa={"razao_social": "Empresa Atômica Ltda", "cnpj": CNPJ_ATOMICO},
        usuario=usuario_valido(
            nome="Fluxo Atômico",
            email=EMAIL_ATOMICO,
            senha="Fluxo#Atom1",
        ),
    )

    assert resposta.status_code == 409

    with app.app_context():
        with get_engine().connect() as conexao:
            empresas = conexao.execute(
                text("SELECT COUNT(*) FROM empresas WHERE cnpj = :cnpj"),
                {"cnpj": CNPJ_ATOMICO},
            ).scalar()
            usuarios = conexao.execute(
                text("SELECT COUNT(*) FROM usuarios WHERE email = :email"),
                {"email": EMAIL_ATOMICO},
            ).scalar()

    assert empresas == 0, "a empresa não deveria existir após o rollback"
    assert usuarios == 0, "o usuário não deveria existir após o rollback"
