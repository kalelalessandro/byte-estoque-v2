"""Rotas de títulos financeiros (contas a pagar e a receber).

Rotas (todas exigem login), seguindo o fluxo "Financeiro" do fluxograma:

    GET   /api/titulos                 lista os títulos da empresa ("Listar Títulos")
    GET   /api/titulos/<id>            consulta um título, com saldo e histórico de baixas
                                       ("Consultar Título" / "Consultar Histórico de Baixas")
    POST  /api/titulos                 registra um título em aberto ("Registrar Título
                                       Manualmente")
    POST  /api/titulos/<id>/cancelar   cancela um título ("Cancelar título")

Dar baixa (pagamento/recebimento) é feito em ``baixas.py``.

Regras (Documentação do Banco v1.2 e plano de testes, módulos TIT/SEG):

- A empresa do título vem SEMPRE do usuário logado, nunca do JSON (``id_empresa`` é
  recusado). Título de outra empresa responde 404.
- O parceiro é OPCIONAL no cadastro (o schema permite lançamentos sem parceiro, ex.:
  venda avulsa de balcão), mas precisa ser da mesma empresa. Atenção: título sem
  parceiro NÃO aceita baixa na tela de baixas financeiras (toda baixa tem parceiro).
- A operação de origem também é opcional e da mesma empresa. Se a operação tem parceiro,
  o título precisa ter o MESMO parceiro (se o título não informar parceiro, herda o da
  operação).
- Saldo pendente = valor - soma das baixas. Situação: ``aberto`` (sem baixas),
  ``parcial``, ``quitado`` ou ``cancelado``.
- Título com baixas não pode ser cancelado, e título cancelado não aceita baixas.
- Não há exclusão de título (FK RESTRICT) nem edição dos dados (W.I.P. no fluxograma).

A validação de formato dos campos fica em ``titulos_rules.py``.
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, g, request
from sqlalchemy import and_, func, select, text
from sqlalchemy.exc import IntegrityError

from ..core.auth_utils import (
    ler_json,
    login_obrigatorio,
    resposta_erro,
    resposta_ok,
)
from ..db import get_db
from ..db.models import BaixaFinanceira, Parceiro, TituloFinanceiro
from .baixas import dinheiro, natureza_do_titulo, resumo_parceiro, soma_das_baixas
from .titulos_rules import validar_criacao

bp = Blueprint("titulos", __name__)

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200

TIPO_FILTRO = {"pagar": "a pagar", "receber": "a receber"}
SITUACOES = ("aberto", "parcial", "quitado", "cancelado")

# Operações ainda não têm módulo próprio; a empresa da operação é a do usuário
# responsável (a tabela não tem id_empresa).
_SQL_OPERACAO = text(
    "SELECT o.id_parceiro FROM operacoes o "
    "JOIN usuarios u ON u.id_usuario = o.id_usuario "
    "WHERE o.id_operacao = :op AND u.id_empresa = :emp"
)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def situacao_do_titulo(titulo: TituloFinanceiro, pago: Decimal) -> str:
    if titulo.cancelado:
        return "cancelado"
    if pago <= 0:
        return "aberto"
    return "parcial" if pago < titulo.valor else "quitado"


def serializar_titulo(
    titulo: TituloFinanceiro, parceiro: Parceiro | None, pago: Decimal
) -> dict:
    """Título -> dict JSON, com situação, saldo e o que a tela pode fazer com ele."""
    pago = Decimal(pago)
    situacao = situacao_do_titulo(titulo, pago)
    saldo = Decimal("0.00") if titulo.cancelado else titulo.valor - pago

    motivo_sem_baixa = None
    if titulo.cancelado:
        motivo_sem_baixa = "Título cancelado."
    elif saldo <= 0:
        motivo_sem_baixa = "Título já quitado."

    return {
        "id_titulo": titulo.id_titulo,
        "id_empresa": titulo.id_empresa,
        "id_operacao": titulo.id_operacao,
        "tipo": titulo.tipo,
        "natureza": natureza_do_titulo(titulo),
        "descricao": titulo.descricao,
        "valor": dinheiro(titulo.valor),
        "vencimento": titulo.vencimento.isoformat(),
        "cancelado": bool(titulo.cancelado),
        "situacao": situacao,
        "total_baixado": dinheiro(pago),
        "saldo_pendente": dinheiro(saldo),
        "parceiro": resumo_parceiro(parceiro),
        "pode_baixar": motivo_sem_baixa is None,
        "motivo_sem_baixa": motivo_sem_baixa,
        "pode_cancelar": (not titulo.cancelado) and pago <= 0,
    }


def _pago_por_titulo():
    """Subconsulta: total já baixado por título."""
    return (
        select(
            BaixaFinanceira.id_titulo.label("id_titulo"),
            func.sum(BaixaFinanceira.valor).label("pago"),
        )
        .group_by(BaixaFinanceira.id_titulo)
        .subquery()
    )


def _titulo_da_empresa(id_titulo: int):
    """``(título, parceiro, pago)`` do título da empresa do usuário, ou ``None``."""
    pago = _pago_por_titulo()
    return get_db().execute(
        select(
            TituloFinanceiro,
            Parceiro,
            func.coalesce(pago.c.pago, 0).label("pago"),
        )
        .outerjoin(Parceiro, Parceiro.id_parceiro == TituloFinanceiro.id_parceiro)
        .outerjoin(pago, pago.c.id_titulo == TituloFinanceiro.id_titulo)
        .where(
            TituloFinanceiro.id_titulo == id_titulo,
            TituloFinanceiro.id_empresa == g.usuario.id_empresa,
        )
    ).first()


def _ler_inteiro_query(nome: str, padrao: int, minimo: int, maximo: int):
    bruto = request.args.get(nome)
    if bruto is None or bruto == "":
        return padrao, None
    try:
        valor = int(bruto)
    except ValueError:
        return None, f"'{nome}' deve ser um número inteiro."
    if valor < minimo or valor > maximo:
        return None, f"'{nome}' deve estar entre {minimo} e {maximo}."
    return valor, None


def _titulo_nao_encontrado():
    return resposta_erro("Título não encontrado.", 404)


# ---------------------------------------------------------------------------
# GET /api/titulos  -> listar títulos
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_titulos():
    """Lista os títulos da empresa, por vencimento.

    Parâmetros opcionais na URL:
      ``busca``       texto no nome do parceiro ou na descrição do título;
      ``tipo``        ``pagar`` ou ``receber``;
      ``situacao``    ``aberto``, ``parcial``, ``quitado`` ou ``cancelado``;
      ``id_parceiro`` só os títulos desse parceiro;
      ``limit``/``offset`` paginação (padrão 50, máximo 200).
    """
    limit, msg = _ler_inteiro_query("limit", LIMITE_PADRAO, 1, LIMITE_MAXIMO)
    if msg:
        return resposta_erro(msg, 422)
    offset, msg = _ler_inteiro_query("offset", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)
    id_parceiro, msg = _ler_inteiro_query("id_parceiro", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)

    pago = _pago_por_titulo()
    pago_col = func.coalesce(pago.c.pago, 0)
    filtros = [TituloFinanceiro.id_empresa == g.usuario.id_empresa]

    tipo = (request.args.get("tipo") or "").strip().casefold()
    if tipo:
        if tipo not in TIPO_FILTRO:
            return resposta_erro("'tipo' deve ser: pagar ou receber.", 422)
        filtros.append(TituloFinanceiro.tipo == TIPO_FILTRO[tipo])

    situacao = (request.args.get("situacao") or "").strip().casefold()
    if situacao:
        if situacao not in SITUACOES:
            return resposta_erro(
                "'situacao' deve ser: aberto, parcial, quitado ou cancelado.", 422
            )
        ativo = TituloFinanceiro.cancelado.is_(False)
        filtros.append(
            {
                "cancelado": TituloFinanceiro.cancelado.is_(True),
                "aberto": and_(ativo, pago_col == 0),
                "parcial": and_(ativo, pago_col > 0, pago_col < TituloFinanceiro.valor),
                "quitado": and_(ativo, pago_col >= TituloFinanceiro.valor),
            }[situacao]
        )

    if id_parceiro:
        filtros.append(TituloFinanceiro.id_parceiro == id_parceiro)

    busca = (request.args.get("busca") or "").strip()
    if busca:
        filtros.append(
            Parceiro.nome.contains(busca, autoescape=True)
            | TituloFinanceiro.descricao.contains(busca, autoescape=True)
        )

    base = (
        select(TituloFinanceiro, Parceiro, pago_col.label("pago"))
        .outerjoin(Parceiro, Parceiro.id_parceiro == TituloFinanceiro.id_parceiro)
        .outerjoin(pago, pago.c.id_titulo == TituloFinanceiro.id_titulo)
        .where(*filtros)
    )

    db = get_db()
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    linhas = db.execute(
        base.order_by(TituloFinanceiro.vencimento, TituloFinanceiro.id_titulo)
        .limit(limit)
        .offset(offset)
    ).all()

    return resposta_ok(
        {
            "titulos": [serializar_titulo(t, p, valor_pago) for t, p, valor_pago in linhas],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/titulos/<id>  -> consultar título (+ histórico de baixas)
# ---------------------------------------------------------------------------


@bp.get("/<int:id_titulo>")
@login_obrigatorio
def obter_titulo(id_titulo: int):
    linha = _titulo_da_empresa(id_titulo)
    if linha is None:
        return _titulo_nao_encontrado()

    titulo, parceiro, pago = linha
    dados = serializar_titulo(titulo, parceiro, pago)
    baixas = get_db().scalars(
        select(BaixaFinanceira)
        .where(BaixaFinanceira.id_titulo == titulo.id_titulo)
        .order_by(BaixaFinanceira.realizado_em.desc(), BaixaFinanceira.id_baixa.desc())
    ).all()
    dados["baixas"] = [
        {
            "id_baixa": baixa.id_baixa,
            "id_caixa": baixa.id_caixa,
            "valor": dinheiro(baixa.valor),
            "realizado_em": baixa.realizado_em.isoformat(),
            "forma_pagamento": baixa.forma_pagamento,
        }
        for baixa in baixas
    ]
    return resposta_ok(dados)


# ---------------------------------------------------------------------------
# POST /api/titulos  -> registrar título manualmente
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def registrar_titulo():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    # 1) Formato/limites dos campos (sem tocar no banco).
    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    id_empresa = g.usuario.id_empresa  # empresa vem da sessão, nunca do corpo

    # 2) Parceiro (se informado) precisa ser da MESMA empresa.
    parceiro = None
    if valores["id_parceiro"] is not None:
        parceiro = db.scalar(
            select(Parceiro).where(
                Parceiro.id_parceiro == valores["id_parceiro"],
                Parceiro.id_empresa == id_empresa,
            )
        )
        if parceiro is None:
            return resposta_erro(
                "Parceiro não encontrado nesta empresa.",
                422,
                campos={"id_parceiro": "Parceiro não encontrado."},
            )

    # 3) Operação (se informada): da mesma empresa e com o MESMO parceiro do título.
    if valores["id_operacao"] is not None:
        operacao = db.execute(
            _SQL_OPERACAO, {"op": valores["id_operacao"], "emp": id_empresa}
        ).first()
        if operacao is None:
            return resposta_erro(
                "Operação não encontrada nesta empresa.",
                422,
                campos={"id_operacao": "Operação não encontrada."},
            )

        id_parceiro_operacao = operacao[0]
        if id_parceiro_operacao is not None:
            if parceiro is None:
                # Título sem parceiro informado herda o da operação.
                parceiro = db.scalar(
                    select(Parceiro).where(
                        Parceiro.id_parceiro == id_parceiro_operacao,
                        Parceiro.id_empresa == id_empresa,
                    )
                )
                valores["id_parceiro"] = id_parceiro_operacao
            elif parceiro.id_parceiro != id_parceiro_operacao:
                return resposta_erro(
                    "O parceiro do título deve ser o mesmo da operação vinculada.",
                    422,
                    campos={"id_parceiro": "Diferente do parceiro da operação."},
                )

    # 4) Grava (sempre em aberto, sem baixas).
    try:
        titulo = TituloFinanceiro(id_empresa=id_empresa, **valores)
        db.add(titulo)
        db.flush()  # gera o id_titulo
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível registrar o título.", 409)

    return resposta_ok(
        serializar_titulo(titulo, parceiro, Decimal("0")),
        "Título registrado com sucesso.",
        201,
    )


# ---------------------------------------------------------------------------
# POST /api/titulos/<id>/cancelar  -> cancelar título
# ---------------------------------------------------------------------------


@bp.post("/<int:id_titulo>/cancelar")
@login_obrigatorio
def cancelar_titulo(id_titulo: int):
    """Cancela um título em aberto. Bloqueado se já cancelado ou se tiver baixas.

    Trava o título (``FOR UPDATE``) antes de contar as baixas: uma baixa que esteja
    sendo registrada trava o mesmo título primeiro, então as duas operações não se
    atropelam.
    """
    db = get_db()

    titulo = db.scalar(
        select(TituloFinanceiro)
        .where(
            TituloFinanceiro.id_titulo == id_titulo,
            TituloFinanceiro.id_empresa == g.usuario.id_empresa,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if titulo is None:
        db.rollback()
        return _titulo_nao_encontrado()

    if titulo.cancelado:
        db.rollback()
        return resposta_erro("O título já está cancelado.", 409)

    total_baixas = db.scalar(
        select(func.count())
        .select_from(BaixaFinanceira)
        .where(BaixaFinanceira.id_titulo == titulo.id_titulo)
        .with_for_update()
    )
    if total_baixas:
        db.rollback()
        return resposta_erro(
            "Não é possível cancelar: o título possui baixas registradas.",
            409,
            baixas=total_baixas,
        )

    titulo.cancelado = True
    db.commit()

    parceiro = (
        db.scalar(select(Parceiro).where(Parceiro.id_parceiro == titulo.id_parceiro))
        if titulo.id_parceiro is not None
        else None
    )
    return resposta_ok(
        serializar_titulo(titulo, parceiro, Decimal("0")), "Título cancelado com sucesso."
    )
