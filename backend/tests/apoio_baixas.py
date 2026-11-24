"""Apoio dos testes de baixas financeiras (BAI), segurança (SEG) e concorrência (CON).

Títulos e caixas ainda não têm módulo/API próprios; por isso são criados direto no
banco. A limpeza apaga primeiro baixas, títulos e caixas (FKs RESTRICT) e depois
reaproveita a limpeza de parceiros, antes de o ``banco_limpo`` remover usuários/empresas.
"""

from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.exc import OperationalError

from src.app.db import get_engine
from tests.apoio_parceiros import (
    EMPRESAS_COM_PARCEIROS,
    apagar_dados_de_parceiros,
)


def inserir_titulo(
    app,
    id_empresa: int,
    id_parceiro: int | None,
    *,
    tipo: str = "a receber",
    valor: str = "200.00",
    descricao: str = "Título de teste",
    cancelado: bool = False,
) -> int:
    """Cria um título financeiro e devolve o ``id_titulo``."""
    with app.app_context(), get_engine().begin() as conexao:
        return conexao.execute(
            text(
                "INSERT INTO titulos_financeiros "
                "(id_parceiro, id_empresa, tipo, valor, descricao, vencimento, cancelado) "
                "VALUES (:p, :e, :t, :v, :d, '2026-12-01', :c)"
            ),
            {"p": id_parceiro, "e": id_empresa, "t": tipo, "v": valor, "d": descricao, "c": cancelado},
        ).lastrowid


def abrir_caixa(app, id_usuario: int, *, fechado: bool = False) -> int:
    """Cria uma sessão de caixa (aberta, ou já fechada) e devolve o ``id_caixa``."""
    with app.app_context(), get_engine().begin() as conexao:
        return conexao.execute(
            text(
                "INSERT INTO caixas (aberto_por_usuario, aberto_em, valor_abertura, "
                "fechado_em, valor_contado) VALUES (:u, '2026-11-09 08:00:00', 100.00, :f, :c)"
            ),
            {
                "u": id_usuario,
                "f": "2026-11-09 08:30:00" if fechado else None,
                "c": 100.00 if fechado else None,
            },
        ).lastrowid


def criar_operacao(
    app, id_usuario: int, id_parceiro: int | None, *, tipo: str = "venda", status: str = "concluída"
) -> int:
    """Cria uma operação (módulo ainda sem API) e devolve o ``id_operacao``."""
    with app.app_context(), get_engine().begin() as conexao:
        return conexao.execute(
            text(
                "INSERT INTO operacoes (id_parceiro, id_usuario, tipo, status, ocorrencia) "
                "VALUES (:p, :u, :t, :s, '2026-11-07 16:45:00')"
            ),
            {"p": id_parceiro, "u": id_usuario, "t": tipo, "s": status},
        ).lastrowid


def inserir_baixa(
    app, id_titulo: int, id_caixa: int, valor: str, *, forma: str = "dinheiro",
    realizado_em: str = "2026-11-09 09:00:00",
) -> int:
    """Cria uma baixa direto no banco (para montar saldos nos testes de títulos)."""
    with app.app_context(), get_engine().begin() as conexao:
        return conexao.execute(
            text(
                "INSERT INTO baixas_financeiras (id_titulo, id_caixa, valor, realizado_em, "
                "forma_pagamento) VALUES (:t, :c, :v, :r, :f)"
            ),
            {"t": id_titulo, "c": id_caixa, "v": valor, "r": realizado_em, "f": forma},
        ).lastrowid


def fechar_caixa(app, id_caixa: int) -> None:
    with app.app_context(), get_engine().begin() as conexao:
        conexao.execute(
            text(
                "UPDATE caixas SET fechado_em = '2026-11-09 18:00:00', valor_contado = 100.00 "
                "WHERE id_caixa = :c"
            ),
            {"c": id_caixa},
        )


def contar_baixas(app, id_titulo: int) -> int:
    with app.app_context(), get_engine().connect() as conexao:
        return conexao.execute(
            text("SELECT COUNT(*) FROM baixas_financeiras WHERE id_titulo = :t"),
            {"t": id_titulo},
        ).scalar()


def _zerar_contador_dos_caixas(app) -> None:
    """Devolve o AUTO_INCREMENT de ``caixas`` e ``operacoes_caixa`` ao menor valor possível.

    Apagar as linhas não volta o contador: depois de uma suíte com 89 caixas, o primeiro caixa
    real abriria como \"#90\". ``AUTO_INCREMENT = 1`` faz o MySQL usar MAX(id) + 1 (ou 1 com a
    tabela vazia), então caixas e movimentos que já existiam no banco nunca são afetados.
    É ajuste de contador, não mudança de schema. Se outra conexão segurar a tabela, desiste
    depois de alguns segundos em vez de travar a suíte.
    """
    with app.app_context(), get_engine().connect() as conexao:
        conexao.execute(text("SET SESSION lock_wait_timeout = 5"))
        for tabela in ("operacoes_caixa", "caixas"):
            try:
                conexao.execute(text(f"ALTER TABLE {tabela} AUTO_INCREMENT = 1"))
            except OperationalError:
                pass  # limpeza de contador é só cosmética: não derruba o teste


def apagar_dados_de_baixas(app) -> None:
    """Apaga baixas, títulos e caixas das empresas de teste e depois os parceiros.

    Depois de apagar, zera o contador de ids dos caixas (veja ``_zerar_contador_dos_caixas``).
    """
    if not EMPRESAS_COM_PARCEIROS:
        return

    ids = list(EMPRESAS_COM_PARCEIROS)
    with app.app_context(), get_engine().begin() as conexao:
        for consulta in (
            "DELETE FROM baixas_financeiras WHERE id_titulo IN "
            "(SELECT id_titulo FROM titulos_financeiros WHERE id_empresa IN :ids)",
            "DELETE FROM titulos_financeiros WHERE id_empresa IN :ids",
            "DELETE FROM operacoes_caixa WHERE id_caixa IN (SELECT id_caixa FROM caixas "
            "WHERE aberto_por_usuario IN (SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids))",
            "DELETE FROM caixas WHERE aberto_por_usuario IN "
            "(SELECT id_usuario FROM usuarios WHERE id_empresa IN :ids)",
        ):
            conexao.execute(
                text(consulta).bindparams(bindparam("ids", expanding=True)), {"ids": ids}
            )
    _zerar_contador_dos_caixas(app)
    apagar_dados_de_parceiros(app)
