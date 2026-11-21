"""Apoio compartilhado pelos testes de parceiros (PAR) e interações (INT).

Concentra o login de teste, os payloads e a limpeza dos dados criados. Como
``interacoes``, ``operacoes`` e ``titulos_financeiros`` referenciam ``parceiros`` /
``usuarios`` com ON DELETE RESTRICT, a limpeza apaga primeiro os dependentes; só
depois o ``banco_limpo`` (conftest) consegue apagar usuários e empresas de teste.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.helpers import CNPJ_VALIDO, criar_conta, entrar

SENHA = "Senha#Teste1"
EMAIL_A = "parc.a@exemplo.com.br"
EMAIL_B = "parc.b@exemplo.com.br"

# Empresas de teste que receberam parceiros (para a limpeza no final de cada teste).
EMPRESAS_COM_PARCEIROS: set[int] = set()


def logar(client, email: str = EMAIL_A, cnpj: str = CNPJ_VALIDO) -> dict:
    """Cria empresa + usuário, faz login e devolve ``{id_empresa, id_usuario, nome}``."""
    conta = criar_conta(client, email=email, senha=SENHA, cnpj=cnpj)
    assert entrar(client, email, SENHA).status_code == 200
    id_empresa = conta["empresa"]["id_empresa"]
    EMPRESAS_COM_PARCEIROS.add(id_empresa)
    return {
        "id_empresa": id_empresa,
        "id_usuario": conta["usuario"]["id_usuario"],
        "nome": conta["usuario"]["nome"],
    }


def parceiro_valido(**sobrescritas: Any) -> dict:
    """Payload mínimo válido (cliente); sobrescreva os campos que o caso precisa."""
    dados = {"nome": "Parceiro Teste", "e_cliente": True}
    dados.update(sobrescritas)
    return dados


def criar_parceiro(client, **sobrescritas: Any) -> dict:
    """Cria um parceiro exigindo 201 e devolve a chave ``dados`` da resposta."""
    resposta = client.post("/api/parceiros", json=parceiro_valido(**sobrescritas))
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()["dados"]


def obter_parceiro(client, id_parceiro: int) -> dict:
    resposta = client.get(f"/api/parceiros/{id_parceiro}")
    assert resposta.status_code == 200, resposta.get_json()
    return resposta.get_json()["dados"]


def campos(resposta) -> dict:
    """Atalho: o dicionário ``campos`` de uma resposta de erro."""
    return resposta.get_json()["campos"]


def inserir_operacao(app, id_parceiro: int, id_usuario: int) -> None:
    """Cria uma operação vinculada ao parceiro direto no banco (módulo ainda não existe)."""
    with app.app_context(), get_engine().begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO operacoes (id_parceiro, id_usuario, tipo, status, ocorrencia) "
                "VALUES (:p, :u, 'venda', 'pendente', NOW())"
            ),
            {"p": id_parceiro, "u": id_usuario},
        )


def inserir_titulo(app, id_parceiro: int, id_empresa: int) -> None:
    """Cria um título financeiro vinculado ao parceiro direto no banco."""
    with app.app_context(), get_engine().begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO titulos_financeiros "
                "(id_parceiro, id_empresa, tipo, valor, descricao, vencimento) "
                "VALUES (:p, :e, 'a receber', 10.00, 'Título de teste', CURDATE())"
            ),
            {"p": id_parceiro, "e": id_empresa},
        )


def apagar_dados_de_parceiros(app) -> None:
    """Apaga títulos, operações, interações e parceiros das empresas de teste."""
    if not EMPRESAS_COM_PARCEIROS:
        return

    ids = list(EMPRESAS_COM_PARCEIROS)
    ids_parceiros = "SELECT id_parceiro FROM parceiros WHERE id_empresa IN :ids"
    with app.app_context(), get_engine().begin() as conexao:
        for consulta in (
            "DELETE FROM titulos_financeiros WHERE id_empresa IN :ids",
            f"DELETE FROM operacoes WHERE id_parceiro IN ({ids_parceiros})",
            f"DELETE FROM interacoes WHERE id_parceiro IN ({ids_parceiros})",
            "DELETE FROM parceiros WHERE id_empresa IN :ids",
        ):
            conexao.execute(
                text(consulta).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            )
    EMPRESAS_COM_PARCEIROS.clear()
