"""Helpers compartilhados pelas rotas de autenticação.

Concentra o formato padrão das respostas JSON, a leitura do corpo da
requisição, a serialização de empresa/usuário e o decorador de rota
protegida por sessão.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request, session

from ..db import get_db
from ..db.models import Empresa, Usuario


def resposta_ok(dados: Any = None, mensagem: str | None = None, status: int = 200):
    """Resposta de sucesso padrão: ``{"ok": true, "mensagem": ..., "dados": ...}``."""
    payload: dict[str, Any] = {"ok": True}
    if mensagem is not None:
        payload["mensagem"] = mensagem
    if dados is not None:
        payload["dados"] = dados
    return jsonify(payload), status


def resposta_erro(mensagem: str, status: int = 400, **extra):
    """Resposta de erro padrão: ``{"ok": false, "erro": ..., ...}``."""
    payload: dict[str, Any] = {"ok": False, "erro": mensagem}
    payload.update(extra)
    return jsonify(payload), status


def ler_json():
    """Lê o corpo JSON da requisição.

    Retorna ``(dados, None)`` em caso de sucesso ou ``(None, resposta)``
    quando o Content-Type está errado ou o JSON é inválido.
    """
    if not request.is_json:
        return None, resposta_erro(
            "Envie o corpo da requisição como JSON "
            "(cabeçalho Content-Type: application/json).",
            415,
        )

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, resposta_erro("JSON inválido. Envie um objeto JSON.", 400)
    return dados, None


def serializar_empresa(empresa: Empresa) -> dict:
    return {
        "id_empresa": empresa.id_empresa,
        "razao_social": empresa.razao_social,
        "cnpj": empresa.cnpj,
        "cep": empresa.cep,
        "inscricao": empresa.inscricao,
        "telefone_empresa": empresa.telefone_empresa,
        "criado_em": empresa.criado_em.isoformat() if empresa.criado_em else None,
    }


def serializar_usuario(usuario: Usuario, incluir_empresa: bool = True) -> dict:
    dados = {
        "id_usuario": usuario.id_usuario,
        "nome": usuario.nome,
        "email": usuario.email,
        "telefone": usuario.telefone,
        "admin_sistema": bool(usuario.admin_sistema),
        "id_cargo": usuario.id_cargo,
        "cargo": usuario.cargo.cargo if usuario.cargo is not None else None,
    }
    if incluir_empresa and usuario.empresa is not None:
        dados["empresa"] = serializar_empresa(usuario.empresa)
    return dados


def login_obrigatorio(rota: Callable):
    """Exige sessão ativa e injeta o usuário logado em ``flask.g.usuario``."""

    @wraps(rota)
    def wrapper(*args, **kwargs):
        id_usuario = session.get("id_usuario")
        if id_usuario is None:
            return resposta_erro("Não autenticado. Faça login para continuar.", 401)

        usuario = get_db().get(Usuario, id_usuario)
        if usuario is None:
            session.clear()
            return resposta_erro("Sessão inválida. Faça login novamente.", 401)

        g.usuario = usuario
        return rota(*args, **kwargs)

    return wrapper
