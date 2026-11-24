"""Rotas do módulo de Operações (compras, vendas e histórico).

Uma operação é registrada de forma atômica: os itens, o estoque e os títulos
financeiros (1x ou parcelados) são gravados na mesma transação. A empresa vem
sempre da sessão; produtos e parceiro precisam ser da mesma empresa.

Rotas:

    POST   /api/operacoes                 registra operação
    GET    /api/operacoes                 lista/filtra operações
    GET    /api/operacoes/<id>            detalhe da operação
    PATCH  /api/operacoes/<id>            altera operação concluída (desfaz/refaz efeitos)
    POST   /api/operacoes/<id>/cancelar   cancela e desfaz estoque/títulos
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, g
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError

from ..core.auth_utils import ler_json, login_obrigatorio, resposta_erro, resposta_ok
from ..db import get_db
from ..db.models import (
    BaixaFinanceira,
    Operacao,
    OperacaoItem,
    Parceiro,
    Produto,
    TituloFinanceiro,
    Usuario,
)
from .operations_rules import validar_criacao

bp = Blueprint("operations", __name__)

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200
STATUS_CONCLUIDA = "concluida"
STATUS_CANCELADA = "cancelada"
TIPOS_VALIDOS = {"venda", "compra"}
STATUS_VALIDOS = {STATUS_CONCLUIDA, STATUS_CANCELADA}
CENTAVO = Decimal("0.01")


# ---------------------------------------------------------------------------
# Auxiliares de serialização e leitura
# ---------------------------------------------------------------------------


def dinheiro(valor) -> str:
    return f"{Decimal(valor):.2f}"


def _resumo_parceiro(parceiro: Parceiro | None) -> dict | None:
    if parceiro is None:
        return None
    return {
        "id_parceiro": parceiro.id_parceiro,
        "nome": parceiro.nome,
        "e_cliente": bool(parceiro.e_cliente),
        "e_fornecedor": bool(parceiro.e_fornecedor),
    }


def _resumo_usuario(usuario: Usuario) -> dict:
    return {"id_usuario": usuario.id_usuario, "nome": usuario.nome}


def _serializar_item(item: OperacaoItem, produto: Produto) -> dict:
    subtotal = Decimal(item.quantidade) * Decimal(item.valor_unitario)
    return {
        "id_produto": produto.id_produto,
        "sku": produto.sku,
        "nome": produto.nome,
        "quantidade": item.quantidade,
        "valor_unitario": dinheiro(item.valor_unitario),
        "subtotal": dinheiro(subtotal),
    }


def _serializar_operacao(
    operacao: Operacao,
    parceiro: Parceiro | None,
    usuario: Usuario,
    itens: list[tuple[OperacaoItem, Produto]],
    titulos: list[TituloFinanceiro],
) -> dict:
    total = sum(
        (Decimal(item.quantidade) * Decimal(item.valor_unitario) for item, _ in itens),
        Decimal("0.00"),
    )
    return {
        "id_operacao": operacao.id_operacao,
        "tipo": operacao.tipo,
        "status": operacao.status,
        "ocorrencia": operacao.ocorrencia.isoformat(),
        "observacoes": operacao.observacoes,
        "id_parceiro": operacao.id_parceiro,
        "parceiro": _resumo_parceiro(parceiro),
        "usuario": _resumo_usuario(usuario),
        "itens": [_serializar_item(item, produto) for item, produto in itens],
        "total": dinheiro(total),
        "parcelas": len(titulos),
        "titulos": [
            {
                "id_titulo": titulo.id_titulo,
                "tipo": titulo.tipo,
                "valor": dinheiro(titulo.valor),
                "vencimento": titulo.vencimento.isoformat(),
                "descricao": titulo.descricao,
                "cancelado": bool(titulo.cancelado),
                "id_parceiro": titulo.id_parceiro,
            }
            for titulo in titulos
        ],
        "pode_editar": operacao.status == STATUS_CONCLUIDA,
        "pode_cancelar": operacao.status == STATUS_CONCLUIDA,
    }


def _carregar_operacao(
    id_operacao: int, id_empresa: int, *, travar: bool = False
):
    consulta = (
        select(Operacao, Parceiro, Usuario)
        .outerjoin(
            Parceiro,
            and_(
                Parceiro.id_parceiro == Operacao.id_parceiro,
                Parceiro.id_empresa == id_empresa,
            ),
        )
        .join(Usuario, Usuario.id_usuario == Operacao.id_usuario)
        .where(
            Operacao.id_operacao == id_operacao,
            Usuario.id_empresa == id_empresa,
        )
    )
    if travar:
        consulta = consulta.with_for_update()
    return get_db().execute(consulta).first()


def _carregar_itens(id_operacoes: list[int], id_empresa: int):
    if not id_operacoes:
        return []
    return get_db().execute(
        select(OperacaoItem, Produto)
        .join(Produto, Produto.id_produto == OperacaoItem.id_produto)
        .where(
            OperacaoItem.id_operacao.in_(id_operacoes),
            Produto.id_empresa == id_empresa,
        )
        .order_by(OperacaoItem.id_operacao, Produto.nome, Produto.id_produto)
    ).all()


def _carregar_titulos(id_operacoes: list[int], id_empresa: int):
    if not id_operacoes:
        return []
    return get_db().scalars(
        select(TituloFinanceiro)
        .where(
            TituloFinanceiro.id_operacao.in_(id_operacoes),
            TituloFinanceiro.id_empresa == id_empresa,
        )
        .order_by(TituloFinanceiro.vencimento, TituloFinanceiro.id_titulo)
    ).all()


def _detalhe(id_operacao: int, id_empresa: int) -> dict | None:
    linha = _carregar_operacao(id_operacao, id_empresa)
    if linha is None:
        return None
    operacao, parceiro, usuario = linha
    itens = _carregar_itens([id_operacao], id_empresa)
    titulos = _carregar_titulos([id_operacao], id_empresa)
    return _serializar_operacao(operacao, parceiro, usuario, itens, titulos)


def _produtos_da_empresa(db, ids: list[int], id_empresa: int, *, travar: bool):
    consulta = (
        select(Produto)
        .where(Produto.id_empresa == id_empresa, Produto.id_produto.in_(ids))
        .order_by(Produto.id_produto)
    )
    if travar:
        consulta = consulta.with_for_update()
    return db.scalars(consulta).all()


def _validar_parceiro(db, id_parceiro: int | None, id_empresa: int):
    if id_parceiro is None:
        return None, None
    parceiro = db.scalar(
        select(Parceiro).where(
            Parceiro.id_parceiro == id_parceiro,
            Parceiro.id_empresa == id_empresa,
        )
    )
    if parceiro is None:
        return None, resposta_erro(
            "Parceiro não encontrado nesta empresa.",
            422,
            campos={"id_parceiro": "Parceiro não encontrado."},
        )
    return parceiro, None


def _valores_parcelas(total: Decimal, parcelas: int) -> list[Decimal] | None:
    """Divide o total em centavos sem perder nem criar centavos."""
    total_centavos = int((total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if total_centavos < parcelas:
        return None
    base, resto = divmod(total_centavos, parcelas)
    valores = [base] * (parcelas - 1) + [base + resto]
    return [Decimal(centavos) / 100 for centavos in valores]


def _somar_meses(data_base: date, meses: int) -> date:
    indice = data_base.month - 1 + meses
    ano = data_base.year + indice // 12
    mes = indice % 12 + 1
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def _criar_titulos(
    db,
    *,
    id_empresa: int,
    id_operacao: int,
    id_parceiro: int | None,
    tipo_operacao: str,
    total: Decimal,
    parcelas: int,
    primeiro_vencimento: date,
) -> None:
    valores = _valores_parcelas(total, parcelas)
    if valores is None:
        raise ValueError("total insuficiente para o número de parcelas")
    tipo_titulo = "a receber" if tipo_operacao == "venda" else "a pagar"
    descricao_base = "Venda" if tipo_operacao == "venda" else "Compra"
    for indice, valor in enumerate(valores, start=1):
        descricao = f"{descricao_base} #{id_operacao}"
        if parcelas > 1:
            descricao += f" - Parcela {indice}/{parcelas}"
        db.add(
            TituloFinanceiro(
                id_empresa=id_empresa,
                id_operacao=id_operacao,
                id_parceiro=id_parceiro,
                tipo=tipo_titulo,
                valor=valor,
                descricao=descricao[:500],
                vencimento=_somar_meses(primeiro_vencimento, indice - 1),
                cancelado=False,
            )
        )


def _erro_itens(mensagem: str):
    return resposta_erro(mensagem, 422, campos={"itens": mensagem})


def _erro_estoque(mensagem: str):
    return resposta_erro(mensagem, 422, campos={"itens": mensagem})


# ---------------------------------------------------------------------------
# POST /api/operacoes -> registrar operação
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def registrar_operacao():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    id_empresa = g.usuario.id_empresa
    db = get_db()

    parceiro, erro_parceiro = _validar_parceiro(
        db, valores["id_parceiro"], id_empresa
    )
    if erro_parceiro is not None:
        return erro_parceiro

    ids_produtos = sorted(item["id_produto"] for item in valores["itens"])
    produtos = _produtos_da_empresa(db, ids_produtos, id_empresa, travar=True)
    if len(produtos) != len(ids_produtos):
        db.rollback()
        return _erro_itens("Um ou mais produtos não pertencem a esta empresa.")

    por_id = {produto.id_produto: produto for produto in produtos}
    estoque = {produto.id_produto: produto.unidade_estoque for produto in produtos}
    total = Decimal("0.00")
    for item in valores["itens"]:
        produto_id = item["id_produto"]
        total += Decimal(item["quantidade"]) * item["valor_unitario"]
        if valores["tipo"] == "venda":
            if estoque[produto_id] < item["quantidade"]:
                db.rollback()
                return _erro_estoque(
                    f"Estoque insuficiente para o produto {por_id[produto_id].sku}."
                )
            estoque[produto_id] -= item["quantidade"]
        else:
            estoque[produto_id] += item["quantidade"]

    total = total.quantize(CENTAVO)
    if total <= 0:
        db.rollback()
        return resposta_erro(
            "O total da operação deve ser maior que zero.",
            422,
            campos={"itens": "Total da operação deve ser maior que zero."},
        )

    parcelas = valores["parcelas"]
    valores_parcelas = _valores_parcelas(total, parcelas)
    if valores_parcelas is None:
        db.rollback()
        return resposta_erro(
            "O valor total é pequeno demais para esse número de parcelas.",
            422,
            campos={"parcelas": "Total insuficiente para o parcelamento."},
        )

    ocorrencia = valores["ocorrencia"] or datetime.now()
    primeiro_vencimento = valores["vencimento"] or (
        ocorrencia.date() + timedelta(days=30)
    )

    try:
        operacao = Operacao(
            id_parceiro=valores["id_parceiro"],
            id_usuario=g.usuario.id_usuario,
            tipo=valores["tipo"],
            status=STATUS_CONCLUIDA,
            ocorrencia=ocorrencia,
            observacoes=valores["observacoes"],
        )
        db.add(operacao)
        db.flush()  # gera id_operacao

        for item in valores["itens"]:
            db.add(
                OperacaoItem(
                    id_operacao=operacao.id_operacao,
                    id_produto=item["id_produto"],
                    quantidade=item["quantidade"],
                    valor_unitario=item["valor_unitario"],
                )
            )
        for produto_id, quantidade in estoque.items():
            por_id[produto_id].unidade_estoque = quantidade

        _criar_titulos(
            db,
            id_empresa=id_empresa,
            id_operacao=operacao.id_operacao,
            id_parceiro=valores["id_parceiro"],
            tipo_operacao=valores["tipo"],
            total=total,
            parcelas=parcelas,
            primeiro_vencimento=primeiro_vencimento,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não foi possível registrar a operação. Confira os dados.",
            409,
        )

    return resposta_ok(
        _detalhe(operacao.id_operacao, id_empresa),
        "Operação registrada com sucesso.",
        201,
    )


# ---------------------------------------------------------------------------
# GET /api/operacoes -> listar operações
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_operacoes():
    def inteiro(nome: str, padrao: int, minimo: int, maximo: int):
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

    from flask import request

    limit, msg = inteiro("limit", LIMITE_PADRAO, 1, LIMITE_MAXIMO)
    if msg:
        return resposta_erro(msg, 422)
    offset, msg = inteiro("offset", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)

    id_empresa = g.usuario.id_empresa
    filtros = [Usuario.id_empresa == id_empresa]

    tipo = (request.args.get("tipo") or "").strip().casefold()
    if tipo:
        if tipo not in TIPOS_VALIDOS:
            return resposta_erro("'tipo' deve ser: venda ou compra.", 422)
        filtros.append(Operacao.tipo == tipo)

    status = (request.args.get("status") or "").strip().casefold()
    if status:
        if status not in STATUS_VALIDOS:
            return resposta_erro("'status' deve ser: concluida ou cancelada.", 422)
        filtros.append(Operacao.status == status)

    busca = (request.args.get("busca") or "").strip()
    if busca:
        filtros.append(
            Parceiro.nome.contains(busca, autoescape=True)
            | Operacao.observacoes.contains(busca, autoescape=True)
        )

    base = (
        select(Operacao, Parceiro, Usuario)
        .join(Usuario, Usuario.id_usuario == Operacao.id_usuario)
        .outerjoin(
            Parceiro,
            and_(
                Parceiro.id_parceiro == Operacao.id_parceiro,
                Parceiro.id_empresa == id_empresa,
            ),
        )
        .where(*filtros)
    )

    db = get_db()
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    linhas = db.execute(
        base.order_by(Operacao.ocorrencia.desc(), Operacao.id_operacao.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    ids = [operacao.id_operacao for operacao, _, _ in linhas]
    itens_por_operacao: dict[int, list] = {id_: [] for id_ in ids}
    for item, produto in _carregar_itens(ids, id_empresa):
        itens_por_operacao[item.id_operacao].append((item, produto))
    titulos_por_operacao: dict[int, list] = {id_: [] for id_ in ids}
    for titulo in _carregar_titulos(ids, id_empresa):
        titulos_por_operacao[titulo.id_operacao].append(titulo)

    return resposta_ok(
        {
            "operacoes": [
                _serializar_operacao(
                    operacao,
                    parceiro,
                    usuario,
                    itens_por_operacao[operacao.id_operacao],
                    titulos_por_operacao[operacao.id_operacao],
                )
                for operacao, parceiro, usuario in linhas
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/operacoes/<id> -> detalhe
# ---------------------------------------------------------------------------


@bp.get("/<int:id_operacao>")
@login_obrigatorio
def obter_operacao(id_operacao: int):
    detalhe = _detalhe(id_operacao, g.usuario.id_empresa)
    if detalhe is None:
        return resposta_erro("Operação não encontrada.", 404)
    return resposta_ok(detalhe)


# ---------------------------------------------------------------------------
# PATCH /api/operacoes/<id> -> alterar operação concluída
# ---------------------------------------------------------------------------


@bp.patch("/<int:id_operacao>")
@login_obrigatorio
def alterar_operacao(id_operacao: int):
    """Altera a operação desfazendo e refazendo estoque/títulos na mesma transação.

    A edição completa exige ``tipo``, ``itens``, ``parcelas`` e ``vencimento``.
    Operações com títulos já baixados não podem ser alteradas.
    """
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    id_empresa = g.usuario.id_empresa
    db = get_db()
    linha = _carregar_operacao(id_operacao, id_empresa, travar=True)
    if linha is None:
        db.rollback()
        return resposta_erro("Operação não encontrada.", 404)
    operacao, _, _ = linha
    if operacao.status != STATUS_CONCLUIDA:
        db.rollback()
        return resposta_erro(
            "Somente operações concluídas podem ser alteradas.", 409
        )

    itens_antigos = _carregar_itens([id_operacao], id_empresa)
    titulos_antigos = _carregar_titulos([id_operacao], id_empresa)
    if titulos_antigos:
        baixas = db.scalar(
            select(func.count())
            .select_from(BaixaFinanceira)
            .where(
                BaixaFinanceira.id_titulo.in_(
                    [titulo.id_titulo for titulo in titulos_antigos]
                )
            )
        )
        if baixas:
            db.rollback()
            return resposta_erro(
                "Não é possível alterar a operação: um ou mais títulos já receberam baixa.",
                409,
            )

    parceiro, erro_parceiro = _validar_parceiro(
        db, valores["id_parceiro"], id_empresa
    )
    if erro_parceiro is not None:
        db.rollback()
        return erro_parceiro

    ids_antigos = {item.id_produto for item, _ in itens_antigos}
    ids_novos = {item["id_produto"] for item in valores["itens"]}
    produtos = _produtos_da_empresa(
        db, sorted(ids_antigos | ids_novos), id_empresa, travar=True
    )
    por_id = {produto.id_produto: produto for produto in produtos}
    if len(por_id) != len(ids_antigos | ids_novos):
        db.rollback()
        return _erro_itens("Um ou mais produtos não pertencem a esta empresa.")

    estoque = {produto.id_produto: produto.unidade_estoque for produto in produtos}

    # Desfaz o efeito dos itens antigos.
    for item, _ in itens_antigos:
        if operacao.tipo == "venda":
            estoque[item.id_produto] += item.quantidade
        else:
            estoque[item.id_produto] -= item.quantidade
            if estoque[item.id_produto] < 0:
                db.rollback()
                return _erro_estoque(
                    "Não é possível alterar: o estoque de uma compra já foi consumido."
                )

    # Aplica os itens novos e valida o estoque final.
    total = Decimal("0.00")
    for item in valores["itens"]:
        produto_id = item["id_produto"]
        total += Decimal(item["quantidade"]) * item["valor_unitario"]
        if valores["tipo"] == "venda":
            estoque[produto_id] -= item["quantidade"]
            if estoque[produto_id] < 0:
                db.rollback()
                return _erro_estoque(
                    f"Estoque insuficiente para o produto {por_id[produto_id].sku}."
                )
        else:
            estoque[produto_id] += item["quantidade"]

    total = total.quantize(CENTAVO)
    if total <= 0:
        db.rollback()
        return resposta_erro(
            "O total da operação deve ser maior que zero.",
            422,
            campos={"itens": "Total da operação deve ser maior que zero."},
        )
    if _valores_parcelas(total, valores["parcelas"]) is None:
        db.rollback()
        return resposta_erro(
            "O valor total é pequeno demais para esse número de parcelas.",
            422,
            campos={"parcelas": "Total insuficiente para o parcelamento."},
        )

    ocorrencia = valores["ocorrencia"] or operacao.ocorrencia
    primeiro_vencimento = valores["vencimento"] or (
        ocorrencia.date() + timedelta(days=30)
    )

    try:
        db.execute(
            delete(TituloFinanceiro).where(
                TituloFinanceiro.id_operacao == id_operacao,
                TituloFinanceiro.id_empresa == id_empresa,
            )
        )
        db.execute(
            delete(OperacaoItem).where(OperacaoItem.id_operacao == id_operacao)
        )

        operacao.tipo = valores["tipo"]
        operacao.id_parceiro = valores["id_parceiro"]
        operacao.ocorrencia = ocorrencia
        operacao.observacoes = valores["observacoes"]

        for item in valores["itens"]:
            db.add(
                OperacaoItem(
                    id_operacao=id_operacao,
                    id_produto=item["id_produto"],
                    quantidade=item["quantidade"],
                    valor_unitario=item["valor_unitario"],
                )
            )
        for produto_id, quantidade in estoque.items():
            por_id[produto_id].unidade_estoque = quantidade

        _criar_titulos(
            db,
            id_empresa=id_empresa,
            id_operacao=id_operacao,
            id_parceiro=valores["id_parceiro"],
            tipo_operacao=valores["tipo"],
            total=total,
            parcelas=valores["parcelas"],
            primeiro_vencimento=primeiro_vencimento,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível alterar a operação.", 409)

    return resposta_ok(
        _detalhe(id_operacao, id_empresa),
        "Operação alterada com sucesso.",
    )


# ---------------------------------------------------------------------------
# POST /api/operacoes/<id>/cancelar -> cancelar e desfazer efeitos
# ---------------------------------------------------------------------------


@bp.post("/<int:id_operacao>/cancelar")
@login_obrigatorio
def cancelar_operacao(id_operacao: int):
    id_empresa = g.usuario.id_empresa
    db = get_db()
    linha = _carregar_operacao(id_operacao, id_empresa, travar=True)
    if linha is None:
        db.rollback()
        return resposta_erro("Operação não encontrada.", 404)
    operacao, _, _ = linha
    if operacao.status == STATUS_CANCELADA:
        db.rollback()
        return resposta_erro("Operação já está cancelada.", 409)
    if operacao.status != STATUS_CONCLUIDA:
        db.rollback()
        return resposta_erro("Somente operações concluídas podem ser canceladas.", 409)

    itens = _carregar_itens([id_operacao], id_empresa)
    titulos = _carregar_titulos([id_operacao], id_empresa)
    if titulos:
        baixas = db.scalar(
            select(func.count())
            .select_from(BaixaFinanceira)
            .where(
                BaixaFinanceira.id_titulo.in_([t.id_titulo for t in titulos])
            )
        )
        if baixas:
            db.rollback()
            return resposta_erro(
                "Não é possível cancelar: um ou mais títulos já receberam baixa.",
                409,
            )

    ids_produtos = sorted(item.id_produto for item, _ in itens)
    produtos = _produtos_da_empresa(db, ids_produtos, id_empresa, travar=True)
    por_id = {produto.id_produto: produto for produto in produtos}
    if len(por_id) != len(ids_produtos):
        db.rollback()
        return resposta_erro(
            "Não foi possível cancelar: produto vinculado não encontrado.", 409
        )

    estoque = {produto.id_produto: produto.unidade_estoque for produto in produtos}
    for item, _ in itens:
        if operacao.tipo == "venda":
            estoque[item.id_produto] += item.quantidade
        else:
            estoque[item.id_produto] -= item.quantidade
            if estoque[item.id_produto] < 0:
                db.rollback()
                return _erro_estoque(
                    "Não é possível cancelar: o estoque da compra já foi consumido."
                )

    try:
        for produto_id, quantidade in estoque.items():
            por_id[produto_id].unidade_estoque = quantidade
        for titulo in titulos:
            titulo.cancelado = True
        operacao.status = STATUS_CANCELADA
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível cancelar a operação.", 409)

    return resposta_ok(
        _detalhe(id_operacao, id_empresa),
        "Operação cancelada com sucesso.",
    )
