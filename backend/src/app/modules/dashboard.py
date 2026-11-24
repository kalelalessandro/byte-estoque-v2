"""Rotas de resumo agregado para o dashboard (produtos, categorias, parceiros, estoque e dinheiro).

Em vez de o frontend baixar todos os produtos e categorias para calcular
contagens e valor em estoque, o MySQL faz a agregação em uma única consulta.

O card **Dinheiro** vem do módulo de Caixa: é o SALDO GERAL do último caixa fechado da empresa
(dinheiro contado + líquido de Pix e cartão, o mesmo ``saldo_geral`` da página Caixas). Ele
aparece no dashboard assim que o caixa fecha; caixa ainda aberto não conta (o dinheiro só é
confirmado na contagem do fechamento).
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, g
from sqlalchemy import func, select

from ..core.auth_utils import login_obrigatorio, resposta_ok
from ..db import get_db
from ..db.models import Caixa, Categoria, Parceiro, Produto, Usuario
from .caixas import _resumos, serializar_caixa

bp = Blueprint("dashboard", __name__)


@bp.get("/resumo")
@login_obrigatorio
def resumo_dashboard():
    """Resumo da empresa logada: produtos, categorias, parceiros, estoque e dinheiro em caixa."""
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

    # Dinheiro: saldo geral do último caixa FECHADO (a empresa do caixa é a de quem o abriu).
    # Desempate por id quando dois fechamentos caem no mesmo segundo.
    ultimo_fechado = db.execute(
        select(Caixa)
        .join(Usuario, Usuario.id_usuario == Caixa.aberto_por_usuario)
        .where(Usuario.id_empresa == id_empresa, Caixa.fechado_em.is_not(None))
        .order_by(Caixa.fechado_em.desc(), Caixa.id_caixa.desc())
        .limit(1)
    ).first()
    dinheiro = None
    if ultimo_fechado is not None:
        caixa = ultimo_fechado[0]
        saldo_geral = serializar_caixa(caixa, None, _resumos([caixa])[caixa.id_caixa])["saldo_geral"]
        dinheiro = {
            "valor": saldo_geral,
            "id_caixa": caixa.id_caixa,
            "fechado_em": caixa.fechado_em.isoformat(),
        }

    return resposta_ok(
        {
            "produtos": int(total_produtos or 0),
            "categorias": int(total_categorias or 0),
            "parceiros": int(total_parceiros or 0),
            "valor_estoque": f"{valor:.2f}",
            # None até o primeiro caixa ser fechado.
            "dinheiro": dinheiro,
        }
    )
