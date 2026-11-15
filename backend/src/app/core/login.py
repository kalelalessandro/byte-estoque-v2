"""Rotas de login, logout e sessão do Byte Estoque.

Autenticação simples baseada em cookie de sessão do Flask (adequada para a
apresentação do projeto). A senha é verificada com ``werkzeug.security``
(hash scrypt gerado no cadastro; nunca guardamos senha em texto puro).
"""

from __future__ import annotations

from flask import Blueprint, g, session
from sqlalchemy import select
from werkzeug.security import check_password_hash

from ..db import get_db
from ..db.models import Usuario
from .auth_utils import (
    EMAIL_REGEX,
    ler_json,
    login_obrigatorio,
    resposta_erro,
    resposta_ok,
    serializar_usuario,
)

bp = Blueprint("login", __name__)


@bp.post("/login")
def login():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    email = dados.get("email")
    senha = dados.get("senha")

    campos: dict = {}
    if not isinstance(email, str) or not email.strip():
        campos["email"] = "E-mail é obrigatório."
    elif not EMAIL_REGEX.fullmatch(email.strip()):
        campos["email"] = "E-mail inválido."
    if not isinstance(senha, str) or not senha:
        campos["senha"] = "Senha é obrigatória."
    if campos:
        return resposta_erro("Informe e-mail e senha.", 422, campos=campos)

    email = email.strip().lower()
    usuario = get_db().scalar(select(Usuario).where(Usuario.email == email))

    # Mensagem genérica de propósito: não revela se o e-mail existe.
    if usuario is None or not check_password_hash(usuario.hash_senha, senha):
        return resposta_erro("E-mail ou senha incorretos.", 401)

    # Evita fixação de sessão: limpa a sessão anterior antes de autenticar.
    session.clear()
    session["id_usuario"] = usuario.id_usuario
    session.permanent = True

    return resposta_ok(serializar_usuario(usuario), "Login realizado com sucesso.")


@bp.post("/logout")
def logout():
    session.clear()
    return resposta_ok(None, "Sessão encerrada.")


@bp.get("/me")
@login_obrigatorio
def me():
    """Retorna o usuário da sessão atual (rota protegida de exemplo)."""
    return resposta_ok(serializar_usuario(g.usuario))
