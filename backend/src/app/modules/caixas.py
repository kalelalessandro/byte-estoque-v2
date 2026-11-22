"""Rotas do caixa: sessões de caixa, suprimentos/sangrias e fechamento.

Rotas (todas exigem login), seguindo o fluxo "Caixa" do fluxograma:

    GET   /api/caixas                    histórico de sessões da empresa
    GET   /api/caixas/atual              caixa aberto agora (ou ``null``), com valores e extrato
    GET   /api/caixas/<id>               sessão com valores e extrato ("Consultar Movimentações
                                         e Valores")
    POST  /api/caixas                    abre um caixa ("Abrir Caixa")
    POST  /api/caixas/<id>/movimentos    registra suprimento ou sangria
    POST  /api/caixas/<id>/fechar        fecha o caixa com o valor contado ("Fechar Caixa")

Regras (Documentação do Banco v1.2 e plano de testes, módulos CXA/CON/SEG):

- **Empresa do caixa = empresa de quem o abriu** (``aberto_por_usuario``); a tabela não tem
  ``id_empresa``. Caixa de outra empresa responde 404.
- **Um caixa aberto por empresa** (o fluxo abre "o" caixa; as baixas usam o caixa aberto).
  Aberturas simultâneas são serializadas travando a linha da empresa.
- **Saldo esperado em dinheiro** = abertura + suprimentos − sangrias + recebimentos em
  dinheiro − pagamentos em dinheiro. Baixas via Pix e cartão NÃO mexem no dinheiro físico:
  aparecem em linhas separadas (``por_forma``). Pagamentos e recebimentos vêm de
  ``baixas_financeiras``; suprimentos e sangrias de ``operacoes_caixa`` (o mesmo evento
  nunca está nas duas, então nada é contado em dobro).
- Fechamento: informa o ``valor_contado``; ``diferenca`` = contado − esperado (negativa =
  faltou dinheiro). Caixa fechado não aceita lançamentos nem novo fechamento.
- **Concorrência:** movimentos e fechamento travam a sessão (``SELECT ... FOR UPDATE``). O
  fechamento soma baixas e movimentos com leitura travada, então uma baixa concorrente ou
  entra no valor esperado ou é recusada; nunca fica fora do extrato. Ordem de travas do
  sistema: empresa -> título -> caixa.
- Datas e horas de abertura, movimento e fechamento são do SERVIDOR (nunca do JSON).

A validação de formato dos campos fica em ``caixas_rules.py``.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
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
from ..db.models import (
    BaixaFinanceira,
    Caixa,
    Empresa,
    OperacaoCaixa,
    Parceiro,
    TituloFinanceiro,
    Usuario,
)
from .baixas import dinheiro
from .baixas_rules import FORMAS_PAGAMENTO
from .caixas_rules import validar_abertura, validar_fechamento, validar_movimento

bp = Blueprint("caixas", __name__)

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200
ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _chave(texto: str | None) -> str:
    """Texto sem acento e em minúsculas, para comparar "cartão" com "cartao"."""
    decomposto = unicodedata.normalize("NFD", (texto or "").strip())
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


_FORMA_POR_CHAVE = {_chave(forma): forma for forma in FORMAS_PAGAMENTO}


def _agora() -> datetime:
    """Horário do servidor, sem fração de segundo (colunas DATETIME)."""
    return datetime.now().replace(microsecond=0)


def _caixa_da_empresa(id_caixa: int, *, travar: bool = False):
    """``(caixa, nome de quem abriu)`` da empresa do usuário logado, ou ``None``.

    ``travar=True`` usa ``SELECT ... FOR UPDATE`` só na linha do caixa: lê o dado MAIS
    RECENTE (mesmo com snapshot antigo) e impede lançamentos/fechamento simultâneos.
    """
    consulta = (
        select(Caixa, Usuario.nome)
        .join(Usuario, Usuario.id_usuario == Caixa.aberto_por_usuario)
        .where(Caixa.id_caixa == id_caixa, Usuario.id_empresa == g.usuario.id_empresa)
    )
    if travar:
        consulta = consulta.with_for_update(of=Caixa).execution_options(
            populate_existing=True
        )
    return get_db().execute(consulta).first()


def _resumos(caixas: list[Caixa], *, travar: bool = False) -> dict[int, dict]:
    """Valores de cada caixa: suprimentos, sangrias, totais por forma e saldo esperado.

    Duas consultas agrupadas servem para vários caixas de uma vez (a listagem). Com
    ``travar=True`` (fechamento) as leituras são travadas: leem o dado mais recente e
    impedem lançamentos concorrentes. Só as linhas de ``baixas_financeiras`` e
    ``operacoes_caixa`` são travadas (não os títulos), para não cruzar com a ordem de
    travas da baixa (título -> caixa).
    """
    ids = [caixa.id_caixa for caixa in caixas]
    if not ids:
        return {}

    db = get_db()
    resumos = {
        caixa.id_caixa: {
            "valor_abertura": caixa.valor_abertura,
            "suprimentos": ZERO,
            "sangrias": ZERO,
            "formas": {
                forma: {"recebimentos": ZERO, "pagamentos": ZERO}
                for forma in FORMAS_PAGAMENTO
            },
        }
        for caixa in caixas
    }

    consulta_movimentos = (
        select(OperacaoCaixa.id_caixa, OperacaoCaixa.tipo, func.sum(OperacaoCaixa.valor))
        .where(OperacaoCaixa.id_caixa.in_(ids))
        .group_by(OperacaoCaixa.id_caixa, OperacaoCaixa.tipo)
    )
    if travar:
        consulta_movimentos = consulta_movimentos.with_for_update()
    for id_caixa, tipo, soma in db.execute(consulta_movimentos).all():
        chave = _chave(tipo)
        if chave == "suprimento":
            resumos[id_caixa]["suprimentos"] += Decimal(soma)
        elif chave == "sangria":
            resumos[id_caixa]["sangrias"] += Decimal(soma)

    consulta_baixas = (
        select(
            BaixaFinanceira.id_caixa,
            TituloFinanceiro.tipo,
            BaixaFinanceira.forma_pagamento,
            func.sum(BaixaFinanceira.valor),
        )
        .join(TituloFinanceiro, TituloFinanceiro.id_titulo == BaixaFinanceira.id_titulo)
        .where(BaixaFinanceira.id_caixa.in_(ids))
        .group_by(
            BaixaFinanceira.id_caixa, TituloFinanceiro.tipo, BaixaFinanceira.forma_pagamento
        )
    )
    if travar:
        consulta_baixas = consulta_baixas.with_for_update(of=BaixaFinanceira)
    for id_caixa, tipo_titulo, forma_pagamento, soma in db.execute(consulta_baixas).all():
        forma = _FORMA_POR_CHAVE.get(_chave(forma_pagamento))
        natureza = {"a receber": "recebimentos", "a pagar": "pagamentos"}.get(
            _chave(tipo_titulo)
        )
        if forma and natureza:
            resumos[id_caixa]["formas"][forma][natureza] += Decimal(soma)

    for resumo in resumos.values():
        em_dinheiro = resumo["formas"]["dinheiro"]
        resumo["saldo_esperado_dinheiro"] = (
            resumo["valor_abertura"]
            + resumo["suprimentos"]
            - resumo["sangrias"]
            + em_dinheiro["recebimentos"]
            - em_dinheiro["pagamentos"]
        )
    return resumos


def serializar_caixa(caixa: Caixa, aberto_por: str | None, resumo: dict) -> dict:
    """Caixa -> dict JSON, com os valores calculados.

    ``diferenca`` (só com o caixa fechado) = valor contado − saldo esperado em dinheiro.
    """
    esperado = resumo["saldo_esperado_dinheiro"]
    fechado = caixa.fechado_em is not None
    return {
        "id_caixa": caixa.id_caixa,
        "aberto_por": aberto_por,
        "aberto_em": caixa.aberto_em.isoformat(),
        "fechado_em": caixa.fechado_em.isoformat() if fechado else None,
        "situacao": "fechado" if fechado else "aberto",
        "valor_abertura": dinheiro(caixa.valor_abertura),
        "suprimentos": dinheiro(resumo["suprimentos"]),
        "sangrias": dinheiro(resumo["sangrias"]),
        "saldo_esperado_dinheiro": dinheiro(esperado),
        "valor_contado": dinheiro(caixa.valor_contado) if fechado else None,
        "diferenca": dinheiro(caixa.valor_contado - esperado) if fechado else None,
        # Linhas de dinheiro, Pix e cartão. Só o dinheiro altera o saldo físico.
        "por_forma": [
            {
                "forma": forma,
                "recebimentos": dinheiro(valores["recebimentos"]),
                "pagamentos": dinheiro(valores["pagamentos"]),
                "liquido": dinheiro(valores["recebimentos"] - valores["pagamentos"]),
                "afeta_dinheiro": forma == "dinheiro",
            }
            for forma, valores in resumo["formas"].items()
        ],
    }


def _extrato(id_caixa: int) -> list[dict]:
    """Todos os lançamentos do caixa (baixas + suprimentos/sangrias), mais recentes primeiro."""
    db = get_db()
    lancamentos: list[dict] = []

    linhas_baixas = db.execute(
        select(BaixaFinanceira, TituloFinanceiro, Parceiro.nome)
        .join(TituloFinanceiro, TituloFinanceiro.id_titulo == BaixaFinanceira.id_titulo)
        .outerjoin(Parceiro, Parceiro.id_parceiro == TituloFinanceiro.id_parceiro)
        .where(BaixaFinanceira.id_caixa == id_caixa)
    ).all()
    for baixa, titulo, parceiro_nome in linhas_baixas:
        natureza = {"a receber": "recebimento", "a pagar": "pagamento"}.get(_chave(titulo.tipo))
        lancamentos.append(
            {
                "origem": "baixa",
                "id": baixa.id_baixa,
                "ocorrencia": baixa.realizado_em.isoformat(),
                "descricao": titulo.descricao,
                "parceiro": parceiro_nome,
                "tipo": natureza,  # recebimento | pagamento
                "forma_pagamento": baixa.forma_pagamento,
                "valor": dinheiro(baixa.valor),
                "sentido": {"recebimento": "entrada", "pagamento": "saida"}.get(natureza),
                "afeta_dinheiro": _chave(baixa.forma_pagamento) == "dinheiro",
                "usuario": None,
            }
        )

    linhas_movimentos = db.execute(
        select(OperacaoCaixa, Usuario.nome)
        .join(Usuario, Usuario.id_usuario == OperacaoCaixa.id_usuario)
        .where(OperacaoCaixa.id_caixa == id_caixa)
    ).all()
    for movimento, usuario_nome in linhas_movimentos:
        lancamentos.append(
            {
                "origem": "movimento",
                "id": movimento.movimento_id,
                "ocorrencia": movimento.ocorrencia.isoformat(),
                "descricao": movimento.descricao,
                "parceiro": None,
                "tipo": _chave(movimento.tipo),  # suprimento | sangria
                "forma_pagamento": "dinheiro",
                "valor": dinheiro(movimento.valor),
                "sentido": "entrada" if _chave(movimento.tipo) == "suprimento" else "saida",
                "afeta_dinheiro": True,
                "usuario": usuario_nome,
            }
        )

    lancamentos.sort(key=lambda item: (item["ocorrencia"], item["origem"], item["id"]), reverse=True)
    return lancamentos


def _detalhe(caixa: Caixa, aberto_por: str | None) -> dict:
    """Caixa + valores + extrato (o que "Consultar Movimentações e Valores" mostra)."""
    resumo = _resumos([caixa])[caixa.id_caixa]
    dados = serializar_caixa(caixa, aberto_por, resumo)
    dados["extrato"] = _extrato(caixa.id_caixa)
    return dados


def _caixa_nao_encontrado():
    return resposta_erro("Caixa não encontrado.", 404)


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


def _consulta_caixas_da_empresa():
    return (
        select(Caixa, Usuario.nome)
        .join(Usuario, Usuario.id_usuario == Caixa.aberto_por_usuario)
        .where(Usuario.id_empresa == g.usuario.id_empresa)
    )


# ---------------------------------------------------------------------------
# GET /api/caixas  e  GET /api/caixas/atual  e  GET /api/caixas/<id>
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_caixas():
    """Histórico de sessões da empresa, mais recentes primeiro.

    Parâmetros opcionais: ``situacao`` (``aberto`` ou ``fechado``), ``limit`` (padrão 50,
    máximo 200) e ``offset``.
    """
    limit, msg = _ler_inteiro_query("limit", LIMITE_PADRAO, 1, LIMITE_MAXIMO)
    if msg:
        return resposta_erro(msg, 422)
    offset, msg = _ler_inteiro_query("offset", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)

    base = _consulta_caixas_da_empresa()
    situacao = (request.args.get("situacao") or "").strip().casefold()
    if situacao:
        if situacao not in ("aberto", "fechado"):
            return resposta_erro("'situacao' deve ser: aberto ou fechado.", 422)
        base = base.where(
            Caixa.fechado_em.is_(None) if situacao == "aberto" else Caixa.fechado_em.is_not(None)
        )

    db = get_db()
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    linhas = db.execute(
        base.order_by(Caixa.aberto_em.desc(), Caixa.id_caixa.desc()).limit(limit).offset(offset)
    ).all()
    resumos = _resumos([caixa for caixa, _ in linhas])

    return resposta_ok(
        {
            "caixas": [serializar_caixa(c, nome, resumos[c.id_caixa]) for c, nome in linhas],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@bp.get("/atual")
@login_obrigatorio
def caixa_atual():
    """O caixa aberto da empresa (o mais recente), ou ``{"caixa": null}``."""
    linha = get_db().execute(
        _consulta_caixas_da_empresa()
        .where(Caixa.fechado_em.is_(None))
        .order_by(Caixa.aberto_em.desc(), Caixa.id_caixa.desc())
        .limit(1)
    ).first()
    if linha is None:
        return resposta_ok({"caixa": None})
    return resposta_ok({"caixa": _detalhe(*linha)})


@bp.get("/<int:id_caixa>")
@login_obrigatorio
def obter_caixa(id_caixa: int):
    linha = _caixa_da_empresa(id_caixa)
    if linha is None:
        return _caixa_nao_encontrado()
    return resposta_ok(_detalhe(*linha))


# ---------------------------------------------------------------------------
# POST /api/caixas  -> abrir caixa
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def abrir_caixa():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_abertura(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    id_empresa = g.usuario.id_empresa

    # Aberturas simultâneas: trava a linha da EMPRESA e só então confere se já há caixa
    # aberto (leitura travada, para enxergar uma abertura confirmada há instantes).
    db.execute(select(Empresa.id_empresa).where(Empresa.id_empresa == id_empresa).with_for_update())
    ja_aberto = db.scalar(
        select(Caixa.id_caixa)
        .join(Usuario, Usuario.id_usuario == Caixa.aberto_por_usuario)
        .where(Usuario.id_empresa == id_empresa, Caixa.fechado_em.is_(None))
        .with_for_update(of=Caixa)
        .limit(1)
    )
    if ja_aberto is not None:
        db.rollback()
        return resposta_erro(
            "Já existe um caixa aberto nesta empresa. Feche-o antes de abrir outro.",
            409,
            id_caixa=ja_aberto,
        )

    try:
        caixa = Caixa(
            aberto_por_usuario=g.usuario.id_usuario,  # quem abre define a empresa da sessão
            aberto_em=_agora(),
            valor_abertura=valores["valor_abertura"],
        )
        db.add(caixa)
        db.flush()  # gera o id_caixa
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível abrir o caixa.", 409)

    return resposta_ok(_detalhe(caixa, g.usuario.nome), "Caixa aberto com sucesso.", 201)


# ---------------------------------------------------------------------------
# POST /api/caixas/<id>/movimentos  -> suprimento ou sangria
# ---------------------------------------------------------------------------


@bp.post("/<int:id_caixa>/movimentos")
@login_obrigatorio
def registrar_movimento(id_caixa: int):
    dados, erro = ler_json()
    if erro is not None:
        return erro

    db = get_db()

    # Trava a sessão: um fechamento em andamento termina antes (ou este lançamento é recusado).
    linha = _caixa_da_empresa(id_caixa, travar=True)
    if linha is None:
        db.rollback()
        return _caixa_nao_encontrado()
    caixa, aberto_por = linha

    if caixa.fechado_em is not None:
        db.rollback()
        return resposta_erro(
            "O caixa está fechado e não aceita lançamentos. Abra um novo caixa.", 409
        )

    valores, erros = validar_movimento(dados)
    if erros:
        db.rollback()
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    try:
        movimento = OperacaoCaixa(
            id_caixa=caixa.id_caixa,
            id_usuario=g.usuario.id_usuario,
            ocorrencia=max(_agora(), caixa.aberto_em),  # nunca antes da abertura
            **valores,
        )
        db.add(movimento)
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível registrar o movimento.", 409)

    rotulo = "Suprimento" if valores["tipo"] == "suprimento" else "Sangria"
    return resposta_ok(
        _detalhe(caixa, aberto_por), f"{rotulo} registrado com sucesso.", 201
    )


# ---------------------------------------------------------------------------
# POST /api/caixas/<id>/fechar  -> fechar caixa
# ---------------------------------------------------------------------------


@bp.post("/<int:id_caixa>/fechar")
@login_obrigatorio
def fechar_caixa(id_caixa: int):
    """Fecha o caixa com o valor contado e informa a diferença para o esperado."""
    dados, erro = ler_json()
    if erro is not None:
        return erro

    db = get_db()

    linha = _caixa_da_empresa(id_caixa, travar=True)
    if linha is None:
        db.rollback()
        return _caixa_nao_encontrado()
    caixa, aberto_por = linha

    if caixa.fechado_em is not None:
        db.rollback()
        return resposta_erro(
            "O caixa já foi fechado. Data/hora e valor contado originais foram mantidos.", 409
        )

    valores, erros = validar_fechamento(dados)
    if erros:
        db.rollback()
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    # Com a sessão travada, soma baixas e movimentos com leitura travada: o valor esperado
    # inclui tudo o que foi confirmado até aqui, e nada novo entra depois (CON-N04).
    resumo = _resumos([caixa], travar=True)[caixa.id_caixa]
    esperado = resumo["saldo_esperado_dinheiro"]

    caixa.fechado_em = max(_agora(), caixa.aberto_em)  # o CHECK exige fechado_em >= aberto_em
    caixa.valor_contado = valores["valor_contado"]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível fechar o caixa.", 409)

    diferenca = caixa.valor_contado - esperado
    # A resposta usa o MESMO resumo calculado sob trava (não recalcula depois do commit):
    # assim o esperado e a diferença informados são exatamente os do fechamento.
    dados_resposta = serializar_caixa(caixa, aberto_por, resumo)
    dados_resposta["extrato"] = _extrato(caixa.id_caixa)
    mensagem = "Caixa fechado com sucesso."
    if diferenca != 0:
        mensagem += f" Diferença de R$ {dinheiro(diferenca)} em relação ao esperado."
    return resposta_ok(dados_resposta, mensagem)
