"""Regras de validação e normalização dos campos de categoria.

Não acessa banco nem Flask: recebe o JSON já lido e devolve ``(valores, erros)``.
Limite do schema: ``categorias.nome VARCHAR(100) NOT NULL``.
"""

from __future__ import annotations

TAMANHO_MAXIMO_NOME = 100

CAMPOS_CRIACAO = {"nome"}
CAMPOS_EDICAO = {"nome"}


def _validar_nome(valor, erros: dict) -> str | None:
    """Nome obrigatório, aparado (trim) e com no máximo 100 caracteres."""
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        erros["nome"] = "Nome deve ser um texto."
        return None
    valor = valor.strip()
    if not valor:
        erros["nome"] = "Nome é obrigatório."
        return None
    if len(valor) > TAMANHO_MAXIMO_NOME:
        erros["nome"] = f"Nome deve ter no máximo {TAMANHO_MAXIMO_NOME} caracteres."
        return None
    return valor


def _recusar_campos_desconhecidos(dados: dict, permitidos: set[str], erros: dict) -> None:
    for campo in dados:
        if campo not in permitidos:
            erros[str(campo)] = "Campo não permitido nesta operação."


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /categorias``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, CAMPOS_CRIACAO, erros)

    nome = _validar_nome(dados.get("nome"), erros)
    return {"nome": nome}, erros


def validar_edicao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``PATCH /categorias/<id>`` (só o nome é editável)."""
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, CAMPOS_EDICAO, erros)

    valores: dict = {}
    if "nome" in dados:
        nome = _validar_nome(dados["nome"], erros)
        if "nome" not in erros:
            valores["nome"] = nome

    if not erros and not valores:
        erros["corpo"] = "Informe o nome da categoria."
    return valores, erros
