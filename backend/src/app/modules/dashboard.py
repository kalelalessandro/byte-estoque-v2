"""Rotas de resumo agregado para o dashboard (produtos, categorias, parceiros e estoque).

Em vez de o frontend baixar todos os produtos e categorias para calcular
contagens e valor em estoque, o MySQL faz a agregação em uma única consulta.
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, g
from sqlalchemy import func, select

from ..core.auth_utils import login_obrigatorio, resposta_ok
from ..db import get_db
from ..db.models import Categoria, Parceiro, Produto

bp = Blueprint("dashboard", __name__)


@bp.get("/resumo")
@login_obrigatorio
def resumo_dashboard():
    """Resumo da empresa logada: produtos, categorias, parceiros e valor em estoque."""
    db = get_db()
    id_empresa = g.usuario.id_empresa

    # Uma ida ao banco: três contagens correlacionadas + soma do estoque.
    consulta = select(
        select(func.count())
        .select_from(Produto)
        .where(Produto.id_empresa == id_empresa)
        .scalar_subquery(),
        select(func.count())
        .select_from(Categoria)
        .where(Categoria.id_empresa == id_empresa)
        .scalar_subquery(),
        select(func.count())
        .select_from(Parceiro)
        .where(Parceiro.id_empresa == id_empresa)
        .scalar_subquery(),
        select(
            func.coalesce(
                func.sum(Produto.preco * Produto.unidade_estoque), 0
            )
        )
        .where(Produto.id_empresa == id_empresa)
        .scalar_subquery(),
    )
    total_produtos, total_categorias, total_parceiros, valor_estoque = db.execute(
        consulta
    ).one()
    valor = Decimal(str(valor_estoque or 0))

    return resposta_ok(
        {
            "produtos": int(total_produtos or 0),
            "categorias": int(total_categorias or 0),
            "parceiros": int(total_parceiros or 0),
            "valor_estoque": f"{valor:.2f}",
        }
    )
