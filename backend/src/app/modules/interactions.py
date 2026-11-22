"""Rotas de interações com parceiros: contratos e compras.

Interação é um fato comercial com o parceiro: um cliente comprou, um cliente pediu
reembolso, um fornecedor assinou contrato, um fornecedor foi pago pelo fornecimento.
O tipo do fato fica na coluna ``canal`` (ver ``interactions_rules.py``).

Fazem parte da tela de parceiros ("Acessar Parceiro" → "Registrar Interação" /
"Consultar Interação" / "Alterar Interação" no fluxograma). Todas exigem login:

    POST   /api/parceiros/<id>/interacoes                 registra uma interação
    PATCH  /api/parceiros/<id>/interacoes/<interacao_id>  altera uma interação

A CONSULTA do histórico vem junto com ``GET /api/parceiros/<id>`` (campo ``interacoes``).

Regras (Documentação do Banco v1.2, tabela ``interacoes``):

- O responsável pelo registro é SEMPRE o usuário logado (``id_usuario``), nunca vem do
  JSON, e não muda ao alterar a interação.
- O banco só confere se parceiro e usuário EXISTEM; a aplicação garante que o parceiro
  é da mesma empresa do usuário (parceiro de outra empresa responde 404).
- Duas interações no mesmo dia com o mesmo parceiro são permitidas (ex.: compra e pagamento).
- Não há exclusão de interação no fluxo: o histórico é preservado.
"""

from __future__ import annotations

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
from ..db.models import Interacao, Parceiro, Usuario
from .interactions_rules import validar_criacao, validar_edicao
from .partners import (
    buscar_parceiro_da_empresa,
    parceiro_nao_encontrado,
    serializar_interacao,
    tipo_do_parceiro,
)

bp = Blueprint("interactions", __name__)
# Listagem geral (GUIA da tela de baixas financeiras): /api/interacoes.
bp_guia = Blueprint("interactions_guide", __name__)

LIMITE_GUIA_PADRAO = 20
LIMITE_GUIA_MAXIMO = 100


@bp_guia.get("")
@login_obrigatorio
def listar_interacoes():
    """Interações de TODOS os parceiros da empresa, mais recentes primeiro.

    Alimenta o "guia" da tela de baixas financeiras: o que foi combinado, comprado,
    reembolsado ou pago com cada parceiro. Parâmetros opcionais: ``id_parceiro``
    (só desse parceiro), ``limit`` (padrão 20, máximo 100) e ``offset``.
    """
    def numero(nome, padrao, minimo, maximo):
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

    limit, msg = numero("limit", LIMITE_GUIA_PADRAO, 1, LIMITE_GUIA_MAXIMO)
    if msg:
        return resposta_erro(msg, 422)
    offset, msg = numero("offset", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)
    id_parceiro, msg = numero("id_parceiro", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)

    # A empresa vem do PARCEIRO da interação (a tabela não tem id_empresa).
    filtros = [Parceiro.id_empresa == g.usuario.id_empresa]
    if id_parceiro:
        filtros.append(Interacao.id_parceiro == id_parceiro)

    base = (
        select(Interacao, Parceiro, Usuario.nome)
        .join(Parceiro, Parceiro.id_parceiro == Interacao.id_parceiro)
        .join(Usuario, Usuario.id_usuario == Interacao.id_usuario)
        .where(*filtros)
    )
    db = get_db()
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    linhas = db.execute(
        base.order_by(Interacao.ocorrencia.desc(), Interacao.interacao_id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    itens = []
    for interacao, parceiro, usuario_nome in linhas:
        item = serializar_interacao(interacao, usuario_nome)
        item["parceiro_nome"] = parceiro.nome
        item["parceiro_tipo"] = tipo_do_parceiro(parceiro)
        itens.append(item)

    return resposta_ok(
        {"interacoes": itens, "total": total, "limit": limit, "offset": offset}
    )


@bp.post("/<int:id_parceiro>/interacoes")
@login_obrigatorio
def registrar_interacao(id_parceiro: int):
    dados, erro = ler_json()
    if erro is not None:
        return erro

    # Parceiro de outra empresa (ou inexistente) -> 404, antes de validar o corpo.
    parceiro = buscar_parceiro_da_empresa(id_parceiro)
    if parceiro is None:
        return parceiro_nao_encontrado()

    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    try:
        interacao = Interacao(
            id_parceiro=parceiro.id_parceiro,
            id_usuario=g.usuario.id_usuario,  # responsável = usuário logado
            **valores,
        )
        db.add(interacao)
        db.flush()  # gera o interacao_id
        db.commit()
    except IntegrityError:
        # Ex.: o parceiro foi apagado por outra requisição neste meio tempo.
        db.rollback()
        return resposta_erro("Não foi possível registrar a interação.", 409)

    return resposta_ok(
        serializar_interacao(interacao, g.usuario.nome),
        "Interação registrada com sucesso.",
        201,
    )


@bp.patch("/<int:id_parceiro>/interacoes/<int:interacao_id>")
@login_obrigatorio
def alterar_interacao(id_parceiro: int, interacao_id: int):
    """Edição PARCIAL de data, canal e/ou descrição. O responsável não muda."""
    dados, erro = ler_json()
    if erro is not None:
        return erro

    db = get_db()

    parceiro = buscar_parceiro_da_empresa(id_parceiro)
    if parceiro is None:
        return parceiro_nao_encontrado()

    # A interação precisa ser DESTE parceiro (que já é da empresa do usuário).
    interacao = db.scalar(
        select(Interacao)
        .where(
            Interacao.interacao_id == interacao_id,
            Interacao.id_parceiro == parceiro.id_parceiro,
        )
        .with_for_update()
    )
    if interacao is None:
        db.rollback()  # libera a transação aberta pelo SELECT
        return resposta_erro("Interação não encontrada.", 404)

    valores, erros = validar_edicao(dados)
    if erros:
        db.rollback()
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    for campo, valor in valores.items():
        setattr(interacao, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível salvar as alterações da interação.", 409)

    # O nome exibido é o do RESPONSÁVEL original, que pode não ser quem está editando.
    usuario_nome = db.scalar(
        select(Usuario.nome).where(Usuario.id_usuario == interacao.id_usuario)
    )
    return resposta_ok(
        serializar_interacao(interacao, usuario_nome),
        "Interação atualizada com sucesso.",
    )
