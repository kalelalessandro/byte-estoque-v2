"""Gestão de usuários/funcionários da empresa (multi-tenant).

Regras:

- O primeiro usuário da empresa é o **Dono** (cargo Administrador). Funcionários
  recebem o cargo ``Funcionario`` e ``admin_sistema = False``.
- Todos os usuários pertencem à empresa da sessão; listar/alterar/apagar usuário
  de outra empresa responde ``404``.
- O Dono aparece na listagem e não pode ser apagado por um Funcionário (403).
  Ninguém apaga a própria conta.
- Se o usuário tiver registros vinculados (operações, caixas, interações...), o
  ``ON DELETE RESTRICT`` do MySQL bloqueia; a API devolve ``409`` com mensagem clara.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from ..core.auth_utils import (
    eh_dono,
    ler_json,
    login_obrigatorio,
    resposta_erro,
    resposta_ok,
)
from ..db import get_db
from ..db.models import Cargo, Usuario
from .users_rules import validar_criacao, validar_edicao

bp = Blueprint("users", __name__)

CARGO_DONO = "Administrador"
CARGO_FUNCIONARIO = "Funcionario"


def _serializar(usuario: Usuario) -> dict:
    return {
        "id_usuario": usuario.id_usuario,
        "id_empresa": usuario.id_empresa,
        "nome": usuario.nome,
        "email": usuario.email,
        "telefone": usuario.telefone,
        "cargo": usuario.cargo.cargo if usuario.cargo is not None else None,
        "admin_sistema": bool(usuario.admin_sistema),
        "dono": eh_dono(usuario),
    }


def _usuario_da_empresa(id_usuario: int) -> Usuario | None:
    return get_db().scalar(
        select(Usuario).where(
            Usuario.id_usuario == id_usuario,
            Usuario.id_empresa == g.usuario.id_empresa,
        )
    )


def _email_em_uso(email: str, ignorar_id: int | None = None) -> bool:
    consulta = select(Usuario.id_usuario).where(Usuario.email == email)
    if ignorar_id is not None:
        consulta = consulta.where(Usuario.id_usuario != ignorar_id)
    return get_db().scalar(consulta) is not None


def _obter_ou_criar_cargo_funcionario(db) -> Cargo:
    """Get-or-create do cargo ``Funcionario`` (cargos são globais no schema)."""
    cargo = db.scalar(select(Cargo).where(Cargo.cargo == CARGO_FUNCIONARIO))
    if cargo is not None:
        return cargo
    cargo = Cargo(cargo=CARGO_FUNCIONARIO)
    db.add(cargo)
    db.flush()
    return cargo


def _hash_senha(senha: str) -> str:
    metodo = current_app.config.get("SENHA_HASH_METODO") or "scrypt"
    return generate_password_hash(senha, method=metodo)


# ---------------------------------------------------------------------------
# GET /api/usuarios -> listar equipe (dono incluso)
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_usuarios():
    usuarios = get_db().scalars(
        select(Usuario).where(Usuario.id_empresa == g.usuario.id_empresa)
    ).all()
    usuarios.sort(
        key=lambda usuario: (
            not eh_dono(usuario),
            (usuario.nome or "").casefold(),
            usuario.id_usuario,
        )
    )
    return resposta_ok(
        {
            "usuarios": [_serializar(usuario) for usuario in usuarios],
            "total": len(usuarios),
        }
    )


# ---------------------------------------------------------------------------
# POST /api/usuarios -> criar funcionário
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def criar_usuario():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    if _email_em_uso(valores["email"]):
        return resposta_erro(
            "Este e-mail já está cadastrado.",
            409,
            campos={"email": "E-mail já cadastrado."},
        )

    try:
        cargo = _obter_ou_criar_cargo_funcionario(db)
        usuario = Usuario(
            id_empresa=g.usuario.id_empresa,
            id_cargo=cargo.id_cargo,
            nome=valores["nome"],
            email=valores["email"],
            telefone=valores["telefone"],
            hash_senha=_hash_senha(valores["senha"]),
            admin_sistema=False,
        )
        db.add(usuario)
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não foi possível criar o funcionário: e-mail já cadastrado.",
            409,
            campos={"email": "E-mail já cadastrado."},
        )

    return resposta_ok(
        _serializar(usuario),
        "Funcionário cadastrado com sucesso.",
        201,
    )


# ---------------------------------------------------------------------------
# PATCH /api/usuarios/<id> -> atualizar funcionário (ou o próprio usuário)
# ---------------------------------------------------------------------------


@bp.patch("/<int:id_usuario>")
@login_obrigatorio
def alterar_usuario(id_usuario: int):
    dados, erro = ler_json()
    if erro is not None:
        return erro

    db = get_db()
    usuario = _usuario_da_empresa(id_usuario)
    if usuario is None:
        return resposta_erro("Usuário não encontrado.", 404)

    # Funcionário pode operar os módulos, mas NÃO altera a conta do Dono.
    if eh_dono(usuario) and not eh_dono(g.usuario):
        return resposta_erro(
            "Um funcionário não pode alterar a conta do dono da empresa.",
            403,
        )

    valores, erros = validar_edicao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    if "email" in valores and _email_em_uso(
        valores["email"], ignorar_id=usuario.id_usuario
    ):
        return resposta_erro(
            "Este e-mail já está cadastrado.",
            409,
            campos={"email": "E-mail já cadastrado."},
        )

    if "senha" in valores:
        usuario.hash_senha = _hash_senha(valores.pop("senha"))
    for campo, valor in valores.items():
        setattr(usuario, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não foi possível alterar o usuário: e-mail já cadastrado.",
            409,
            campos={"email": "E-mail já cadastrado."},
        )

    return resposta_ok(
        _serializar(usuario),
        "Usuário atualizado com sucesso.",
    )


# ---------------------------------------------------------------------------
# DELETE /api/usuarios/<id> -> apagar funcionário
# ---------------------------------------------------------------------------


@bp.delete("/<int:id_usuario>")
@login_obrigatorio
def apagar_usuario(id_usuario: int):
    db = get_db()
    usuario = _usuario_da_empresa(id_usuario)
    if usuario is None:
        return resposta_erro("Usuário não encontrado.", 404)

    if usuario.id_usuario == g.usuario.id_usuario:
        return resposta_erro(
            "Não é possível excluir a própria conta.", 409
        )

    if eh_dono(usuario):
        if not eh_dono(g.usuario):
            return resposta_erro(
                "Um funcionário não pode excluir a conta do dono da empresa.",
                403,
            )
        return resposta_erro(
            "A conta do dono da empresa não pode ser excluída.", 403
        )

    try:
        db.delete(usuario)
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Este usuário possui registros vinculados (operações, caixas, interações…)"
            " e não pode ser excluído.",
            409,
        )

    return resposta_ok(
        {"id_usuario": id_usuario},
        "Funcionário excluído com sucesso.",
    )
