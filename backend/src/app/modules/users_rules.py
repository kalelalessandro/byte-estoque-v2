"""Regras de validação e normalização do cadastro de funcionários.

Não acessa banco nem Flask. O cargo é sempre definido pela API (Funcionario);
``id_empresa``, ``cargo`` e ``admin_sistema`` nunca vêm do JSON.
"""

from __future__ import annotations

import re

from ..core.auth_utils import EMAIL_REGEX

NOME_MAXIMO = 150
EMAIL_MAXIMO = 254
TELEFONE_MAXIMO = 20
SENHA_MINIMA = 6
SENHA_MAXIMA = 128

CAMPOS_USUARIO = {"nome", "email", "telefone", "senha"}


def _validar_nome(valor, erros: dict) -> str | None:
    if not isinstance(valor, str):
        erros["nome"] = "Nome é obrigatório."
        return None
    nome = valor.strip()
    if not nome:
        erros["nome"] = "Nome é obrigatório."
        return None
    if len(nome) > NOME_MAXIMO:
        erros["nome"] = f"Nome deve ter no máximo {NOME_MAXIMO} caracteres."
        return None
    return nome


def _validar_email(valor, erros: dict) -> str | None:
    if not isinstance(valor, str):
        erros["email"] = "E-mail é obrigatório."
        return None
    email = valor.strip().lower()
    if not email:
        erros["email"] = "E-mail é obrigatório."
        return None
    if len(email) > EMAIL_MAXIMO:
        erros["email"] = f"E-mail deve ter no máximo {EMAIL_MAXIMO} caracteres."
        return None
    if not EMAIL_REGEX.fullmatch(email):
        erros["email"] = "E-mail inválido."
        return None
    return email


def _validar_telefone(valor, erros: dict) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        erros["telefone"] = "Telefone deve ser um texto."
        return None
    telefone = valor.strip()
    if not telefone:
        return None
    if len(telefone) > TELEFONE_MAXIMO:
        erros["telefone"] = f"Telefone deve ter no máximo {TELEFONE_MAXIMO} caracteres."
        return None
    return telefone


def _validar_senha(valor, erros: dict, *, obrigatoria: bool) -> str | None:
    if valor is None or valor == "":
        if obrigatoria:
            erros["senha"] = "Senha é obrigatória."
        return None
    if not isinstance(valor, str):
        erros["senha"] = "Senha inválida."
        return None
    if len(valor) < SENHA_MINIMA:
        erros["senha"] = f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
        return None
    if len(valor) > SENHA_MAXIMA:
        erros["senha"] = f"A senha deve ter no máximo {SENHA_MAXIMA} caracteres."
        return None
    if not valor.strip():
        erros["senha"] = "A senha não pode ser composta apenas de espaços."
        return None
    return valor


def _recusar_desconhecidos(dados: dict, erros: dict) -> None:
    for campo in dados:
        if campo not in CAMPOS_USUARIO:
            erros[str(campo)] = "Campo não permitido nesta operação."


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida ``POST /usuarios``; senha é obrigatória."""
    erros: dict = {}
    _recusar_desconhecidos(dados, erros)
    valores = {
        "nome": _validar_nome(dados.get("nome"), erros),
        "email": _validar_email(dados.get("email"), erros),
        "telefone": _validar_telefone(dados.get("telefone"), erros),
        "senha": _validar_senha(dados.get("senha"), erros, obrigatoria=True),
    }
    return valores, erros


def validar_edicao(dados: dict) -> tuple[dict, dict]:
    """Valida ``PATCH /usuarios/<id>``; senha vazia/ausente não troca a senha."""
    erros: dict = {}
    _recusar_desconhecidos(dados, erros)
    valores: dict = {}

    if "nome" in dados:
        nome = _validar_nome(dados.get("nome"), erros)
        if nome is not None:
            valores["nome"] = nome
    if "email" in dados:
        email = _validar_email(dados.get("email"), erros)
        if email is not None:
            valores["email"] = email
    if "telefone" in dados:
        telefone = _validar_telefone(dados.get("telefone"), erros)
        if "telefone" not in erros:
            valores["telefone"] = telefone
    if "senha" in dados:
        senha = _validar_senha(dados.get("senha"), erros, obrigatoria=False)
        if senha is not None:
            valores["senha"] = senha

    if not erros and not valores:
        erros["corpo"] = "Informe ao menos um campo para alterar."
    return valores, erros
