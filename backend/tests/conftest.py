"""Fixtures compartilhadas da suíte de testes de autenticação.

Os testes rodam contra o **MySQL real** do Docker (``database/docker-compose.yml``),
igual ao plano de testes V1.2. O fixture autouse ``banco_limpo`` apaga somente os
dados criados pela própria suíte (registrados em ``tests.helpers`` ou com os
padrões de teste ``@exemplo.com.br`` e CNPJ ``BD...``), sem tocar em dados de
demonstração/produção.
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app import create_app
from src.app.db import get_engine
from tests.helpers import CNPJS_CRIADOS, EMAILS_CRIADOS

PADRAO_EMAIL_TESTE = "%@exemplo.com.br"
PADRAO_CNPJ_BD = "BD%"


@pytest.fixture(scope="session")
def app():
    """Aplicação Flask em modo de teste, com o banco validado na inicialização."""
    aplicacao = create_app({"TESTING": True, "DEBUG": False})
    with aplicacao.app_context():
        with get_engine().connect() as conexao:
            conexao.execute(text("SELECT 1"))
    return aplicacao


@pytest.fixture()
def client(app):
    """Cliente HTTP do Flask (sem abrir porta de rede)."""
    return app.test_client()


def _consulta_por_emails(rotulo_sql: str, emails: set[str]):
    """Monta um ``text()`` que filtra por padrão de e-mail ou lista registrada."""
    if not emails:
        return (
            text(f"{rotulo_sql} WHERE email LIKE :padrao"),
            {"padrao": PADRAO_EMAIL_TESTE},
        )
    return (
        text(
            f"{rotulo_sql} WHERE email LIKE :padrao OR email IN :emails"
        ).bindparams(bindparam("emails", expanding=True)),
        {"padrao": PADRAO_EMAIL_TESTE, "emails": list(emails)},
    )


def limpar_dados_de_teste(app) -> None:
    """Apaga somente os dados criados pelos testes."""
    emails = set(EMAILS_CRIADOS)
    cnpjs = set(CNPJS_CRIADOS)

    with app.app_context():
        with get_engine().begin() as conexao:
            consulta_ids, params_ids = _consulta_por_emails(
                "SELECT DISTINCT id_empresa FROM usuarios", emails
            )
            ids_empresas = [linha[0] for linha in conexao.execute(consulta_ids, params_ids)]

            consulta_delete, params_delete = _consulta_por_emails(
                "DELETE FROM usuarios", emails
            )
            conexao.execute(consulta_delete, params_delete)

            # Empresas cujos usuários de teste foram removidos.
            if ids_empresas:
                conexao.execute(
                    text(
                        "DELETE FROM empresas WHERE id_empresa IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"ids": ids_empresas},
                )

            # Empresas criadas pelos testes (registro da API ou SQL direto "BD...").
            condicoes = ["cnpj LIKE :padrao_cnpj"]
            params_empresas: dict = {"padrao_cnpj": PADRAO_CNPJ_BD}
            if cnpjs:
                condicoes.append("cnpj IN :cnpjs")
                params_empresas["cnpjs"] = list(cnpjs)
            consulta_empresas = text(
                "DELETE FROM empresas WHERE " + " OR ".join(condicoes)
            )
            if cnpjs:
                consulta_empresas = consulta_empresas.bindparams(
                    bindparam("cnpjs", expanding=True)
                )
            conexao.execute(consulta_empresas, params_empresas)

            # Cargo padrão criado pelo cadastro e que ficou sem usuários.
            conexao.execute(
                text(
                    "DELETE FROM cargos WHERE cargo = 'Administrador' "
                    "AND NOT EXISTS (SELECT 1 FROM usuarios "
                    "WHERE usuarios.id_cargo = cargos.id_cargo)"
                )
            )

    EMAILS_CRIADOS.clear()
    CNPJS_CRIADOS.clear()


@pytest.fixture(autouse=True)
def banco_limpo(app):
    """Garante que cada teste comece e termine com o banco sem dados de teste."""
    limpar_dados_de_teste(app)
    yield
    limpar_dados_de_teste(app)
