"""Rotas do módulo de categorias do Byte Estoque.

Rotas (todas exigem login):

    POST   /api/categorias        cria uma categoria
    GET    /api/categorias        lista as categorias da empresa
    PATCH  /api/categorias/<id>   renomeia uma categoria
    DELETE /api/categorias/<id>   apaga uma categoria SEM produtos vinculados

Regras:

- **Multi-tenant:** a empresa vem SEMPRE do usuário logado; categoria de outra
  empresa responde 404 e não aparece na listagem.
- **Unicidade por empresa:** ``UNIQUE (id_empresa, nome)`` com collation
  ``utf8mb4_0900_ai_ci``, então "Eletrodomésticos" e "ELETRODOMESTICOS" são o
  mesmo nome. A checagem amigável devolve 409; o banco continua sendo a garantia.
- Renomear NÃO afeta o vínculo dos produtos: eles referenciam
  ``id_categoria``, não o nome.
- **Exclusão segura:** só é permitida se a categoria não tiver produtos. Com
  produtos vinculados a resposta é 409; assim nenhum produto é apagado junto.
"""

from __future__ import annotations

from flask import Blueprint, g
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError

from ..core.auth_utils import ler_json, login_obrigatorio, resposta_erro, resposta_ok
from ..db import get_db
from ..db.models import Categoria, Produto
from .categories_rules import validar_criacao, validar_edicao

bp = Blueprint("categories", __name__)


def serializar_categoria(categoria: Categoria, produtos_count: int = 0) -> dict:
    return {
        "id_categoria": categoria.id_categoria,
        "id_empresa": categoria.id_empresa,
        "nome": categoria.nome,
        "produtos_count": produtos_count,
    }


def _quantidade_produtos(id_categoria: int, id_empresa: int) -> int:
    """Quantidade de produtos vinculados à categoria (para a tela de categorias)."""
    return (
        get_db().scalar(
            select(func.count())
            .select_from(Produto)
            .where(
                Produto.id_categoria == id_categoria,
                Produto.id_empresa == id_empresa,
            )
        )
        or 0
    )


def _buscar_categoria_da_empresa(
    id_categoria: int, *, travar: bool = False
) -> Categoria | None:
    """Busca filtrando pela empresa do usuário; outra empresa -> ``None`` (404)."""
    consulta = select(Categoria).where(
        Categoria.id_categoria == id_categoria,
        Categoria.id_empresa == g.usuario.id_empresa,
    )
    if travar:
        consulta = consulta.with_for_update()
    return get_db().scalar(consulta)


def _nome_duplicado(id_empresa: int, nome: str, ignorar_id: int | None = None):
    """Retorna o id de uma categoria com o mesmo nome na empresa (ou ``None``)."""
    consulta = select(Categoria.id_categoria).where(
        Categoria.id_empresa == id_empresa,
        Categoria.nome == nome,
    )
    if ignorar_id is not None:
        consulta = consulta.where(Categoria.id_categoria != ignorar_id)
    return get_db().scalar(consulta)


@bp.post("")
@login_obrigatorio
def criar_categoria():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    id_empresa = g.usuario.id_empresa

    if _nome_duplicado(id_empresa, valores["nome"]) is not None:
        return resposta_erro(
            "Já existe uma categoria com este nome nesta empresa.",
            409,
            campos={"nome": "Nome já cadastrado."},
        )

    db = get_db()
    try:
        categoria = Categoria(id_empresa=id_empresa, nome=valores["nome"])
        db.add(categoria)
        db.flush()  # gera o id_categoria
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Já existe uma categoria com este nome nesta empresa.",
            409,
            campos={"nome": "Nome já cadastrado."},
        )

    return resposta_ok(
        serializar_categoria(categoria, 0),
        "Categoria criada com sucesso.",
        201,
    )


@bp.get("")
@login_obrigatorio
def listar_categorias():
    """Lista as categorias da empresa com a quantidade de produtos de cada uma."""
    linhas = get_db().execute(
        select(
            Categoria,
            func.count(Produto.id_produto).label("produtos_count"),
        )
        .outerjoin(
            Produto,
            and_(
                Produto.id_categoria == Categoria.id_categoria,
                Produto.id_empresa == Categoria.id_empresa,
            ),
        )
        .where(Categoria.id_empresa == g.usuario.id_empresa)
        .group_by(Categoria.id_categoria, Categoria.id_empresa, Categoria.nome)
        .order_by(Categoria.nome, Categoria.id_categoria)
    ).all()

    return resposta_ok(
        {
            "categorias": [
                serializar_categoria(categoria, quantidade)
                for categoria, quantidade in linhas
            ],
            "total": len(linhas),
        }
    )


@bp.patch("/<int:id_categoria>")
@login_obrigatorio
def renomear_categoria(id_categoria: int):
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_edicao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    categoria = _buscar_categoria_da_empresa(id_categoria, travar=True)
    if categoria is None:
        db.rollback()  # libera a transação aberta pelo SELECT
        return resposta_erro("Categoria não encontrada.", 404)

    if (
        _nome_duplicado(
            categoria.id_empresa, valores["nome"], ignorar_id=categoria.id_categoria
        )
        is not None
    ):
        db.rollback()
        return resposta_erro(
            "Já existe uma categoria com este nome nesta empresa.",
            409,
            campos={"nome": "Nome já cadastrado."},
        )

    categoria.nome = valores["nome"]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Já existe uma categoria com este nome nesta empresa.",
            409,
            campos={"nome": "Nome já cadastrado."},
        )

    return resposta_ok(
        serializar_categoria(
            categoria,
            _quantidade_produtos(categoria.id_categoria, categoria.id_empresa),
        ),
        "Categoria renomeada com sucesso.",
    )


@bp.delete("/<int:id_categoria>")
@login_obrigatorio
def apagar_categoria(id_categoria: int):
    """Apaga uma categoria da empresa do usuário, desde que não tenha produtos.

    A FK ``produtos.id_categoria`` é ``ON DELETE RESTRICT``: para não perder
    produtos por acidente, a API responde 409 quando existe qualquer produto
    vinculado e orienta mover/apagar os produtos antes.
    """
    db = get_db()

    categoria = _buscar_categoria_da_empresa(id_categoria, travar=True)
    if categoria is None:
        db.rollback()  # libera a transação aberta pelo SELECT
        return resposta_erro("Categoria não encontrada.", 404)

    produto_vinculado = db.scalar(
        select(Produto.id_produto)
        .where(
            Produto.id_categoria == categoria.id_categoria,
            Produto.id_empresa == categoria.id_empresa,
        )
        .limit(1)
    )
    if produto_vinculado is not None:
        db.rollback()
        return resposta_erro(
            "Não é possível apagar a categoria: existem produtos vinculados a ela. "
            "Mova ou apague os produtos antes.",
            409,
        )

    try:
        db.delete(categoria)
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não é possível apagar a categoria: existem registros vinculados a ela.",
            409,
        )

    return resposta_ok(
        {"id_categoria": id_categoria}, "Categoria apagada com sucesso."
    )
