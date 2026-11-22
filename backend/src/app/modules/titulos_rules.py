"""Regras de validação e normalização dos campos de um título financeiro.

Não acessa banco nem Flask: recebe o JSON já lido e devolve ``(valores, erros)``. As
regras que dependem do banco (parceiro e operação da mesma empresa, parceiro igual ao da
operação) ficam em ``titulos.py``.

Campos da tabela ``titulos_financeiros`` (``database/init/01_schema.sql``) e do plano de
testes (módulo TIT):

    tipo          VARCHAR(30)    obrigatório; lista controlada pela aplicação:
                                 "a pagar" ou "a receber"
    valor         DECIMAL(12,2)  obrigatório, maior que zero, até 2 casas
    descricao     VARCHAR(500)   obrigatório
    vencimento    DATE           obrigatório (data real)
    id_parceiro   INT            opcional (parceiro da MESMA empresa)
    id_operacao   INT            opcional (operação de origem, da MESMA empresa)

``id_empresa`` NUNCA vem do JSON: é a do usuário logado (o campo é recusado).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from .baixas_rules import validar_valor

TAMANHO_MAXIMO_DESCRICAO = 500
ID_MAXIMO = 2_147_483_647  # maior INT do MySQL

TIPOS_TITULO = ("a pagar", "a receber")
CAMPOS_TITULO = {"tipo", "valor", "descricao", "vencimento", "id_parceiro", "id_operacao"}

# 2026-12-01 (padrão do <input type="date"> e da API) ou 01/12/2026.
FORMATO_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
FORMATO_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _validar_tipo(valor, erros: dict) -> str | None:
    """Tipo obrigatório: "a pagar" ou "a receber" (ignora caixa e espaços extras)."""
    if _vazio(valor):
        erros["tipo"] = "Tipo é obrigatório."
        return None
    chave = " ".join(_sem_acento(valor).split()) if isinstance(valor, str) else None
    if chave not in TIPOS_TITULO:
        erros["tipo"] = "Tipo inválido. Use: a pagar ou a receber."
        return None
    return chave


def _validar_descricao(valor, erros: dict) -> str | None:
    """Descrição obrigatória, aparada, até 500 caracteres."""
    if _vazio(valor):
        erros["descricao"] = "Descrição é obrigatória."
        return None
    if not isinstance(valor, str):
        erros["descricao"] = "Descrição deve ser um texto."
        return None
    valor = valor.strip()
    if len(valor) > TAMANHO_MAXIMO_DESCRICAO:
        erros["descricao"] = (
            f"Descrição deve ter no máximo {TAMANHO_MAXIMO_DESCRICAO} caracteres."
        )
        return None
    return valor


def _validar_vencimento(valor, erros: dict) -> date | None:
    """Vencimento obrigatório e REAL (``30/02/2027`` é recusado)."""
    if _vazio(valor):
        erros["vencimento"] = "Vencimento é obrigatório."
        return None
    if not isinstance(valor, str):
        erros["vencimento"] = "Vencimento inválido. Use o formato AAAA-MM-DD."
        return None

    texto = valor.strip()
    correspondencia = FORMATO_ISO.fullmatch(texto)
    if correspondencia:
        ano, mes, dia = (int(parte) for parte in correspondencia.groups())
    else:
        correspondencia = FORMATO_BR.fullmatch(texto)
        if not correspondencia:
            erros["vencimento"] = "Vencimento inválido. Use o formato AAAA-MM-DD."
            return None
        dia, mes, ano = (int(parte) for parte in correspondencia.groups())

    try:
        data = date(ano, mes, dia)  # recusa dias/meses que não existem
    except ValueError:
        erros["vencimento"] = "Vencimento inválido: essa data não existe."
        return None
    if data.year < 1900:
        erros["vencimento"] = "Vencimento inválido: informe um ano a partir de 1900."
        return None
    return data


def _validar_id_opcional(campo: str, valor, erros: dict, rotulo: str) -> int | None:
    """Id opcional: vazio vira ``None``; senão precisa ser inteiro positivo."""
    if _vazio(valor):
        return None
    if isinstance(valor, bool):
        erros[campo] = f"{rotulo} inválido."
        return None
    if isinstance(valor, str) and re.fullmatch(r"[0-9]+", valor.strip()):
        valor = int(valor.strip())
    if not isinstance(valor, int) or valor < 1 or valor > ID_MAXIMO:
        erros[campo] = f"{rotulo} inválido."
        return None
    return valor


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /titulos``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    for campo in dados:
        if campo not in CAMPOS_TITULO:
            erros[str(campo)] = "Campo não permitido nesta operação."

    valores = {
        "tipo": _validar_tipo(dados.get("tipo"), erros),
        "valor": validar_valor(dados.get("valor"), erros),
        "descricao": _validar_descricao(dados.get("descricao"), erros),
        "vencimento": _validar_vencimento(dados.get("vencimento"), erros),
        "id_parceiro": _validar_id_opcional(
            "id_parceiro", dados.get("id_parceiro"), erros, "Parceiro"
        ),
        "id_operacao": _validar_id_opcional(
            "id_operacao", dados.get("id_operacao"), erros, "Operação"
        ),
    }
    return valores, erros
