"""Testes do vínculo obrigatório usuário ↔ empresa.

Cobrem a transação atômica do cadastro e o contexto de empresa devolvido pela
API no login/``me`` (incluindo a sinalização defensiva de redirecionamento).
"""

from __future__ import annotations

import secrets

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.app.core.auth_utils import (
    ROTA_CADASTRO_EMPRESA,
    serializar_contexto_empresa,
)
from src.app.db import get_engine
from tests.helpers import cadastrar, criar_conta, entrar, me, usuario_valido

EMAIL_ATOMICO = "fluxo.atomico@exemplo.com.br"

PESOS_CNPJ_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_CNPJ_DV2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _gerar_cnpj_valido() -> str:
    """Gera um CNPJ numérico válido aleatório.

    CNPJ fixo aqui já causou falso negativo: um script de demonstração criou
    uma empresa com o mesmo CNPJ e a limpeza dos testes (que preserva dados
    ``@demo...``) não a apagava. Um CNPJ aleatório isola o teste de qualquer
    dado pré-existente.
    """
    while True:
        base = "".join(secrets.choice("0123456789") for _ in range(12))
        if len(set(base)) == 1:  # CNPJ com todos os dígitos iguais é inválido
            continue

        valores = [ord(caractere) - 48 for caractere in base]
        dv1 = 11 - sum(v * p for v, p in zip(valores, PESOS_CNPJ_DV1)) % 11
        dv1 = 0 if dv1 >= 10 else dv1
        dv2 = 11 - sum(v * p for v, p in zip(valores + [dv1], PESOS_CNPJ_DV2)) % 11
        dv2 = 0 if dv2 >= 10 else dv2
        return f"{base}{dv1}{dv2}"


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

    cnpj = _gerar_cnpj_valido()

    resposta = cadastrar(
        client,
        empresa={"razao_social": "Empresa Atômica Ltda", "cnpj": cnpj},
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
                {"cnpj": cnpj},
            ).scalar()
            usuarios = conexao.execute(
                text("SELECT COUNT(*) FROM usuarios WHERE email = :email"),
                {"email": EMAIL_ATOMICO},
            ).scalar()

    assert empresas == 0, "a empresa não deveria existir após o rollback"
    assert usuarios == 0, "o usuário não deveria existir após o rollback"
