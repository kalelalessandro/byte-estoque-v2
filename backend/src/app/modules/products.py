"""Rotas do módulo de produtos do Byte Estoque.

Rotas (todas exigem login, igual ``GET /api/auth/me``):

    POST   /api/produtos        cria um produto
    GET    /api/produtos        lista os produtos da empresa (busca + paginação)
    GET    /api/produtos/<id>   detalhe de um produto
    PATCH  /api/produtos/<id>   altera nome, descrição, preço e/ou estoque

Regras principais:

- **Multi-tenant:** a empresa do produto vem SEMPRE do usuário logado
  (``g.usuario.id_empresa``), nunca do JSON. Um usuário só enxerga/edita
  produtos da própria empresa; produto de outra empresa responde 404.
- **SKU** é único dentro da empresa (``UNIQUE (id_empresa, sku)``) e, por
  decisão deste módulo, não é alterado depois de criado.
- **Categoria** precisa existir e ser da mesma empresa (o banco também
  garante isso pela FK composta; aqui damos uma mensagem amigável antes).
- O formato das respostas é o mesmo do módulo de autenticação
  (``resposta_ok`` / ``resposta_erro``).

A validação/normalização dos campos fica em ``products_rules.py``.
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
from ..db.models import Categoria, Produto
from .products_rules import validar_criacao, validar_edicao

bp = Blueprint("products", __name__)

# Paginação da listagem.
LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def serializar_produto(produto: Produto) -> dict:
    """Produto -> dict JSON.

    O preço vai como TEXTO com 2 casas (``"10.50"``) para o JSON não introduzir
    erros de ponto flutuante; o frontend converte/formata como preferir.
    """
    return {
        "id_produto": produto.id_produto,
        "id_empresa": produto.id_empresa,
        "sku": produto.sku,
        "id_categoria": produto.id_categoria,
        "nome": produto.nome,
        "descricao": produto.descricao,
        "unidade_estoque": produto.unidade_estoque,
        "preco": f"{produto.preco:.2f}",
    }


def _buscar_produto_da_empresa(id_produto: int, *, travar: bool = False) -> Produto | None:
    """Busca o produto filtrando pela empresa do usuário logado.

    Se o produto existir mas for de OUTRA empresa, devolve ``None`` (a rota
    responde 404, sem revelar que o id existe).

    ``travar=True`` usa ``SELECT ... FOR UPDATE``: bloqueia a linha até o
    commit, evitando que duas edições simultâneas se atropelem.
    """
    consulta = select(Produto).where(
        Produto.id_produto == id_produto,
        Produto.id_empresa == g.usuario.id_empresa,
    )
    if travar:
        consulta = consulta.with_for_update()
    return get_db().scalar(consulta)


def _produto_nao_encontrado():
    return resposta_erro("Produto não encontrado.", 404)


def _ler_inteiro_query(nome: str, padrao: int, minimo: int, maximo: int):
    """Lê ``?nome=123`` da URL. Devolve ``(valor, None)`` ou ``(None, mensagem)``."""
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
# POST /api/produtos  -> criar produto
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def criar_produto():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    # 1) Valida formato/limites dos campos (sem tocar no banco).
    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    id_empresa = g.usuario.id_empresa  # empresa vem da sessão, nunca do corpo

    # 2) A categoria precisa existir e ser da MESMA empresa do usuário.
    categoria = db.scalar(
        select(Categoria).where(
            Categoria.id_categoria == valores["id_categoria"],
            Categoria.id_empresa == id_empresa,
        )
    )
    if categoria is None:
        return resposta_erro(
            "Categoria não encontrada para esta empresa.",
            422,
            campos={"id_categoria": "Categoria inválida."},
        )

    # 3) Checagem amigável de SKU duplicado (a UNIQUE do banco continua valendo).
    #    A collation do banco ignora maiúsculas/acentos: "ABC-1" == "abc-1".
    ja_existe = db.scalar(
        select(Produto.id_produto).where(
            Produto.id_empresa == id_empresa,
            Produto.sku == valores["sku"],
        )
    )
    if ja_existe is not None:
        return resposta_erro(
            "Já existe um produto com este SKU nesta empresa.",
            409,
            campos={"sku": "SKU já cadastrado."},
        )

    # 4) Grava.
    try:
        produto = Produto(id_empresa=id_empresa, **valores)
        db.add(produto)
        db.flush()  # gera o id_produto
        db.commit()
    except IntegrityError:
        # Corrida: outro request criou o mesmo SKU entre a checagem e o INSERT.
        db.rollback()
        return resposta_erro(
            "Não foi possível criar o produto: SKU já cadastrado nesta empresa.",
            409,
            campos={"sku": "SKU já cadastrado."},
        )

    return resposta_ok(serializar_produto(produto), "Produto criado com sucesso.", 201)


# ---------------------------------------------------------------------------
# GET /api/produtos  -> listar (apoio para a tela e para conferir os testes)
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_produtos():
    """Lista os produtos da empresa do usuário.

    Parâmetros opcionais na URL:
      ``busca``  texto procurado no nome ou no SKU;
      ``limit``  itens por página (padrão 50, máximo 200);
      ``offset`` quantos itens pular (padrão 0).
    """
    limit, msg = _ler_inteiro_query("limit", LIMITE_PADRAO, 1, LIMITE_MAXIMO)
    if msg:
        return resposta_erro(msg, 422)
    offset, msg = _ler_inteiro_query("offset", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)

    filtros = [Produto.id_empresa == g.usuario.id_empresa]

    busca = (request.args.get("busca") or "").strip()
    if busca:
        # autoescape: "%" e "_" digitados pelo usuário valem como texto comum.
        filtros.append(
            Produto.nome.contains(busca, autoescape=True)
            | Produto.sku.contains(busca, autoescape=True)
        )

    db = get_db()
    total = db.scalar(select(func.count()).select_from(Produto).where(*filtros))
    produtos = db.scalars(
        select(Produto)
        .where(*filtros)
        .order_by(Produto.nome, Produto.id_produto)
        .limit(limit)
        .offset(offset)
    ).all()

    return resposta_ok(
        {
            "produtos": [serializar_produto(p) for p in produtos],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/produtos/<id>  -> detalhe
# ---------------------------------------------------------------------------


@bp.get("/<int:id_produto>")
@login_obrigatorio
def obter_produto(id_produto: int):
    produto = _buscar_produto_da_empresa(id_produto)
    if produto is None:
        return _produto_nao_encontrado()
    return resposta_ok(serializar_produto(produto))


# ---------------------------------------------------------------------------
# PATCH /api/produtos/<id>  -> alterar nome, descrição, preço e/ou estoque
# ---------------------------------------------------------------------------


@bp.patch("/<int:id_produto>")
@login_obrigatorio
def alterar_produto(id_produto: int):
    """Edição PARCIAL: envie só o que mudou. Ex.: ``{"preco": 12.9}``.

    Campos editáveis: ``nome``, ``descricao``, ``unidade_estoque`` e ``preco``.
    ``unidade_estoque`` DEFINE o novo saldo (não soma/subtrai).
    """
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_edicao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()

    # Trava a linha (FOR UPDATE) e já filtra pela empresa do usuário.
    produto = _buscar_produto_da_empresa(id_produto, travar=True)
    if produto is None:
        db.rollback()  # libera a transação aberta pelo SELECT
        return _produto_nao_encontrado()

    for campo, valor in valores.items():
        setattr(produto, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro("Não foi possível salvar as alterações do produto.", 409)

    return resposta_ok(serializar_produto(produto), "Produto atualizado com sucesso.")
