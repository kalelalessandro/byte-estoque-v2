"""Rotas de baixas financeiras (pagamentos e recebimentos efetivos de títulos).

Rotas (todas exigem login):

    GET   /api/baixas          lista as baixas da empresa ("Listar Baixas")
    GET   /api/baixas/<id>     consulta uma baixa ("Consultar Baixas")
    GET   /api/baixas/opcoes   títulos com saldo, caixas abertos e formas de pagamento
                               (o que a tela oferece em "Selecionar Título/Caixa Aberto")
    POST  /api/baixas          registra uma baixa ("Salvar & Registrar Baixa")

Regras (Documentação do Banco v1.2 e plano de testes, módulos BAI/SEG/CON):

- **Toda baixa tem parceiro.** O schema liga a baixa ao parceiro pelo TÍTULO
  (``titulos_financeiros.id_parceiro``, que é opcional no banco). Por regra desta tela,
  só se dá baixa em título COM parceiro; título sem parceiro é recusado com uma
  mensagem explicando o que fazer.
- Saldo pendente = valor do título - soma das baixas. A baixa não pode exceder o
  saldo, nem ser feita em título cancelado ou já quitado.
- A baixa é lançada em um CAIXA ABERTO da mesma empresa (``fechado_em`` NULL). A
  empresa do caixa é a do usuário que o abriu (a tabela ``caixas`` não tem empresa).
- **Isolamento:** título, caixa e parceiro precisam ser da empresa do usuário logado;
  recursos de outra empresa são recusados.
- **Concorrência:** a baixa roda numa transação que trava o título e depois o caixa
  (``SELECT ... FOR UPDATE``, sempre nessa ordem) e soma as baixas com leitura travada,
  então duas baixas simultâneas não passam do saldo e uma baixa não entra num caixa
  que está sendo fechado.
- Não há exclusão nem edição de baixa (o schema não tem estorno).

A validação de formato dos campos fica em ``baixas_rules.py``.
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, g, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..core.auth_utils import (
    ler_json,
    login_obrigatorio,
    resposta_erro,
    resposta_ok,
)
from ..db import get_db
from ..db.models import BaixaFinanceira, Caixa, Parceiro, TituloFinanceiro, Usuario
from .baixas_rules import FORMAS_PAGAMENTO, validar_criacao
from .partners import tipo_do_parceiro

bp = Blueprint("baixas", __name__)

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200
LIMITE_OPCOES = 500  # títulos oferecidos no formulário

# Filtros da listagem. "tipo": recebimento = título a receber; pagamento = a pagar.
TIPO_DO_TITULO = {"recebimento": "a receber", "pagamento": "a pagar"}
FORMAS_FILTRO = {forma.casefold(): forma for forma in FORMAS_PAGAMENTO}


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def dinheiro(valor: Decimal) -> str:
    """Decimal -> texto com 2 casas (``"10.50"``), sem erro de ponto flutuante."""
    return f"{Decimal(valor):.2f}"


def natureza_do_titulo(titulo: TituloFinanceiro) -> str | None:
    """"recebimento" (título a receber) ou "pagamento" (título a pagar)."""
    tipo = (titulo.tipo or "").strip().casefold()
    for natureza, tipo_titulo in TIPO_DO_TITULO.items():
        if tipo == tipo_titulo:
            return natureza
    return None


def resumo_parceiro(parceiro: Parceiro | None) -> dict | None:
    if parceiro is None:
        return None
    return {
        "id_parceiro": parceiro.id_parceiro,
        "nome": parceiro.nome,
        "tipo": tipo_do_parceiro(parceiro),
    }


def _resumo_titulo(titulo: TituloFinanceiro, total_baixado: Decimal | None = None) -> dict:
    dados = {
        "id_titulo": titulo.id_titulo,
        "tipo": titulo.tipo,
        "natureza": natureza_do_titulo(titulo),
        "descricao": titulo.descricao,
        "valor": dinheiro(titulo.valor),
        "vencimento": titulo.vencimento.isoformat(),
        "cancelado": bool(titulo.cancelado),
    }
    if total_baixado is not None:
        dados["total_baixado"] = dinheiro(total_baixado)
        dados["saldo_pendente"] = dinheiro(titulo.valor - total_baixado)
    return dados


def serializar_baixa(
    baixa: BaixaFinanceira,
    titulo: TituloFinanceiro,
    parceiro: Parceiro | None,
    total_baixado: Decimal | None = None,
) -> dict:
    """Baixa + resumo do título e do PARCEIRO, quando o título tiver parceiro."""
    return {
        "id_baixa": baixa.id_baixa,
        "id_titulo": baixa.id_titulo,
        "id_caixa": baixa.id_caixa,
        "valor": dinheiro(baixa.valor),
        "realizado_em": baixa.realizado_em.isoformat(),
        "forma_pagamento": baixa.forma_pagamento,
        "natureza": natureza_do_titulo(titulo),
        "titulo": _resumo_titulo(titulo, total_baixado),
        "parceiro": resumo_parceiro(parceiro),
    }


def soma_das_baixas(id_titulo: int, *, travar: bool = False) -> Decimal:
    """Soma das baixas do título.

    Com ``travar=True`` é uma leitura travada (``FOR UPDATE``): lê o dado MAIS RECENTE
    mesmo que a transação já tenha um snapshot (o login lê o usuário antes) e impede
    baixas concorrentes no mesmo título até o commit.
    """
    consulta = select(func.coalesce(func.sum(BaixaFinanceira.valor), 0)).where(
        BaixaFinanceira.id_titulo == id_titulo
    )
    if travar:
        consulta = consulta.with_for_update()
    return Decimal(get_db().scalar(consulta))


def _caixas_abertos_da_empresa(id_empresa: int):
    """Consulta dos caixas abertos; a empresa vem do usuário que abriu o caixa."""
    return (
        select(Caixa, Usuario.nome)
        .join(Usuario, Usuario.id_usuario == Caixa.aberto_por_usuario)
        .where(Usuario.id_empresa == id_empresa, Caixa.fechado_em.is_(None))
        .order_by(Caixa.aberto_em.desc(), Caixa.id_caixa.desc())
    )


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


# ---------------------------------------------------------------------------
# GET /api/baixas/opcoes  -> o que o formulário oferece
# ---------------------------------------------------------------------------


@bp.get("/opcoes")
@login_obrigatorio
def opcoes_de_baixa():
    """Títulos que aceitam baixa, caixas abertos e formas de pagamento.

    Títulos oferecidos: da empresa, NÃO cancelados e com saldo pendente maior que
    zero. O parceiro é opcional: títulos sem parceiro também podem ser baixados.
    """
    db = get_db()
    id_empresa = g.usuario.id_empresa

    pago = (
        select(
            BaixaFinanceira.id_titulo.label("id_titulo"),
            func.sum(BaixaFinanceira.valor).label("pago"),
        )
        .group_by(BaixaFinanceira.id_titulo)
        .subquery()
    )
    saldo = TituloFinanceiro.valor - func.coalesce(pago.c.pago, 0)
    base = (
        select(TituloFinanceiro, Parceiro, saldo.label("saldo"))
        .outerjoin(
            Parceiro,
            (Parceiro.id_parceiro == TituloFinanceiro.id_parceiro)
            & (Parceiro.id_empresa == id_empresa),
        )
        .outerjoin(pago, pago.c.id_titulo == TituloFinanceiro.id_titulo)
        .where(
            TituloFinanceiro.id_empresa == id_empresa,
            TituloFinanceiro.cancelado.is_(False),
            saldo > 0,
        )
    )

    linhas = db.execute(
        base.order_by(TituloFinanceiro.vencimento, TituloFinanceiro.id_titulo)
        .limit(LIMITE_OPCOES)
    ).all()

    titulos = []
    for titulo, parceiro, saldo_pendente in linhas:
        resumo = _resumo_titulo(titulo)
        resumo["saldo_pendente"] = dinheiro(saldo_pendente)
        resumo["parceiro"] = resumo_parceiro(parceiro)
        titulos.append(resumo)

    caixas = [
        {
            "id_caixa": caixa.id_caixa,
            "aberto_em": caixa.aberto_em.isoformat(),
            "aberto_por": nome,
        }
        for caixa, nome in db.execute(_caixas_abertos_da_empresa(id_empresa)).all()
    ]

    return resposta_ok(
        {
            "titulos": titulos,
            "caixas": caixas,
            "formas_pagamento": list(FORMAS_PAGAMENTO),
        }
    )


# ---------------------------------------------------------------------------
# GET /api/baixas  -> listar baixas
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_baixas():
    """Lista as baixas da empresa, mais recentes primeiro.

    Parâmetros opcionais na URL:
      ``busca``       texto no nome do parceiro ou na descrição do título;
      ``tipo``        ``recebimento`` ou ``pagamento``;
      ``forma``       ``dinheiro``, ``pix`` ou ``cartao``;
      ``id_parceiro`` só as baixas desse parceiro;
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

    id_empresa = g.usuario.id_empresa
    filtros = [TituloFinanceiro.id_empresa == id_empresa]

    tipo = (request.args.get("tipo") or "").strip().casefold()
    if tipo:
        if tipo not in TIPO_DO_TITULO:
            return resposta_erro("'tipo' deve ser: recebimento ou pagamento.", 422)
        filtros.append(TituloFinanceiro.tipo == TIPO_DO_TITULO[tipo])

    forma = (request.args.get("forma") or "").strip().casefold().replace("ã", "a")
    if forma:
        if forma not in {"dinheiro", "pix", "cartao"}:
            return resposta_erro("'forma' deve ser: dinheiro, pix ou cartao.", 422)
        filtros.append(
            BaixaFinanceira.forma_pagamento
            == {"dinheiro": "dinheiro", "pix": "Pix", "cartao": "cartão"}[forma]
        )

    if id_parceiro:
        filtros.append(TituloFinanceiro.id_parceiro == id_parceiro)

    busca = (request.args.get("busca") or "").strip()
    if busca:
        filtros.append(
            Parceiro.nome.contains(busca, autoescape=True)
            | TituloFinanceiro.descricao.contains(busca, autoescape=True)
        )

    # Parceiro em JOIN externo: baixas antigas de título sem parceiro continuam listadas.
    base = (
        select(BaixaFinanceira, TituloFinanceiro, Parceiro)
        .join(TituloFinanceiro, TituloFinanceiro.id_titulo == BaixaFinanceira.id_titulo)
        .outerjoin(Parceiro, Parceiro.id_parceiro == TituloFinanceiro.id_parceiro)
        .where(*filtros)
    )

    db = get_db()
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    linhas = db.execute(
        base.order_by(BaixaFinanceira.realizado_em.desc(), BaixaFinanceira.id_baixa.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return resposta_ok(
        {
            "baixas": [serializar_baixa(b, t, p) for b, t, p in linhas],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/baixas/<id>  -> consultar baixa
# ---------------------------------------------------------------------------


@bp.get("/<int:id_baixa>")
@login_obrigatorio
def obter_baixa(id_baixa: int):
    db = get_db()
    linha = db.execute(
        select(BaixaFinanceira, TituloFinanceiro, Parceiro)
        .join(TituloFinanceiro, TituloFinanceiro.id_titulo == BaixaFinanceira.id_titulo)
        .outerjoin(Parceiro, Parceiro.id_parceiro == TituloFinanceiro.id_parceiro)
        .where(
            BaixaFinanceira.id_baixa == id_baixa,
            TituloFinanceiro.id_empresa == g.usuario.id_empresa,
        )
    ).first()
    if linha is None:
        return resposta_erro("Baixa não encontrada.", 404)

    baixa, titulo, parceiro = linha
    dados = serializar_baixa(baixa, titulo, parceiro, soma_das_baixas(titulo.id_titulo))
    return resposta_ok(dados)


# ---------------------------------------------------------------------------
# POST /api/baixas  -> registrar baixa
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def registrar_baixa():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    db = get_db()
    id_empresa = g.usuario.id_empresa

    # 1) Formato/limites dos campos (sem tocar no banco).
    valores, erros = validar_criacao(dados)
    if erros:
        # BAI-N13: sem caixa aberto na empresa o problema real é abrir um caixa.
        if "id_caixa" in erros and db.scalar(
            _caixas_abertos_da_empresa(id_empresa).with_only_columns(Caixa.id_caixa).limit(1)
        ) is None:
            return resposta_erro(
                "Não há caixa aberto na empresa. Abra um caixa antes de registrar baixas.",
                409,
                campos={"id_caixa": "Nenhum caixa aberto."},
            )
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    # 2) Trava o TÍTULO (da empresa do usuário). Ordem fixa de travas: título -> caixa.
    titulo = db.scalar(
        select(TituloFinanceiro)
        .where(
            TituloFinanceiro.id_titulo == valores["id_titulo"],
            TituloFinanceiro.id_empresa == id_empresa,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if titulo is None:
        db.rollback()
        return resposta_erro(
            "Título não encontrado nesta empresa.",
            422,
            campos={"id_titulo": "Título não encontrado."},
        )

    if titulo.cancelado:
        db.rollback()
        return resposta_erro(
            "O título está cancelado e não aceita baixas.",
            409,
            campos={"id_titulo": "Título cancelado."},
        )

    # 3) Parceiro é OPCIONAL: título sem parceiro também pode ser baixado.
    #    Porém, se o título aponta para um parceiro, ele precisa ser da empresa.
    parceiro = None
    if titulo.id_parceiro is not None:
        parceiro = db.scalar(
            select(Parceiro).where(
                Parceiro.id_parceiro == titulo.id_parceiro,
                Parceiro.id_empresa == id_empresa,
            )
        )
        if parceiro is None:
            db.rollback()
            return resposta_erro(
                "O parceiro vinculado ao título não pertence a esta empresa.",
                422,
                campos={"id_titulo": "Parceiro do título inválido."},
            )

    # 4) Trava o CAIXA (da empresa do usuário) e confere se continua aberto.
    caixa = db.scalar(
        select(Caixa)
        .join(Usuario, Usuario.id_usuario == Caixa.aberto_por_usuario)
        .where(Caixa.id_caixa == valores["id_caixa"], Usuario.id_empresa == id_empresa)
        .with_for_update(of=Caixa)
        .execution_options(populate_existing=True)
    )
    if caixa is None:
        db.rollback()
        return resposta_erro(
            "Caixa não encontrado nesta empresa.",
            422,
            campos={"id_caixa": "Caixa não encontrado."},
        )
    if caixa.fechado_em is not None:
        db.rollback()
        return resposta_erro(
            "O caixa selecionado está fechado e não aceita lançamentos.",
            409,
            campos={"id_caixa": "Caixa fechado."},
        )

    # 5) Saldo pendente (leitura travada: vê baixas já confirmadas por outras sessões).
    ja_baixado = soma_das_baixas(titulo.id_titulo, travar=True)
    saldo = titulo.valor - ja_baixado
    if saldo <= 0:
        db.rollback()
        return resposta_erro(
            "O título não possui saldo pendente.",
            409,
            campos={"id_titulo": "Título já quitado."},
        )
    if valores["valor"] > saldo:
        db.rollback()
        return resposta_erro(
            f"O valor excede o saldo pendente de R$ {dinheiro(saldo)}.",
            422,
            campos={"valor": f"Valor excede o saldo pendente de {dinheiro(saldo)}."},
        )

    # 6) Grava.
    try:
        baixa = BaixaFinanceira(**valores)
        db.add(baixa)
        db.flush()  # gera o id_baixa
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível registrar a baixa.", 409)

    return resposta_ok(
        serializar_baixa(baixa, titulo, parceiro, ja_baixado + valores["valor"]),
        "Baixa registrada com sucesso.",
        201,
    )
