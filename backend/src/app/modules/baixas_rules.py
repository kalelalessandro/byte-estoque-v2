"""Regras de validação e normalização dos campos de uma baixa financeira.

Não acessa banco nem Flask: recebe o JSON já lido e devolve ``(valores, erros)``. As
regras que dependem do banco (título cancelado, saldo, caixa aberto, empresa) ficam em
``baixas.py``.

Campos da tabela ``baixas_financeiras`` (``database/init/01_schema.sql``) e do plano
de testes (módulo BAI):

    id_titulo        INT              obrigatório (título da MESMA empresa)
    id_caixa         INT              obrigatório (caixa ABERTO da mesma empresa)
    valor            DECIMAL(12,2)    obrigatório, maior que zero, até 2 casas
    realizado_em     DATETIME         obrigatório (data e hora reais da liquidação)
    forma_pagamento  VARCHAR(30)      obrigatório; lista controlada pela aplicação:
                                      dinheiro, Pix ou cartão
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation

VALOR_MAXIMO = Decimal("9999999999.99")  # DECIMAL(12,2)
DUAS_CASAS = Decimal("0.01")
ID_MAXIMO = 2_147_483_647  # maior INT do MySQL

# Formas de pagamento aceitas (grafia gravada no banco). A comparação ignora caixa e
# acento: "cartao", "CARTÃO" e "Cartão" viram "cartão".
FORMAS_PAGAMENTO = ("dinheiro", "Pix", "cartão")

CAMPOS_BAIXA = {"id_titulo", "id_caixa", "valor", "forma_pagamento", "realizado_em"}

# 2026-11-09 09:15, 2026-11-09T09:15:30 (<input type="datetime-local">) ou 09/11/2026 09:15.
DATA_HORA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?")
DATA_HORA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})[ T](\d{2}):(\d{2})(?::(\d{2}))?")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


_FORMA_POR_CHAVE = {_sem_acento(forma): forma for forma in FORMAS_PAGAMENTO}


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _validar_id(campo: str, valor, erros: dict, rotulo: str) -> int | None:
    """Id numérico obrigatório (``5`` ou ``"5"``)."""
    if _vazio(valor):
        erros[campo] = f"{rotulo} é obrigatório."
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


def validar_dinheiro(
    valor, erros: dict, *, campo: str = "valor", rotulo: str = "Valor", permitir_zero: bool = False
) -> Decimal | None:
    """Valor monetário em ``Decimal`` com 2 casas (aceita ``12.5`` ou ``"12,50"``).

    Por padrão exige maior que zero (baixa, título, suprimento/sangria). Com
    ``permitir_zero`` aceita ``0,00`` e recusa só negativos (abertura e contagem do caixa).
    Os erros vão para ``erros[campo]``.
    """
    if _vazio(valor):
        erros[campo] = f"{rotulo} é obrigatório."
        return None
    if isinstance(valor, bool):
        erros[campo] = f"{rotulo} numérico inválido."
        return None

    if isinstance(valor, (int, float)):
        texto = str(valor)
    elif isinstance(valor, str):
        texto = valor.strip()
        # "120,50" (padrão brasileiro) -> "120.50"; "1.234,56" não é adivinhado.
        if "," in texto and "." not in texto:
            texto = texto.replace(",", ".")
    else:
        erros[campo] = f"{rotulo} numérico inválido."
        return None

    try:
        numero = Decimal(texto)
    except InvalidOperation:
        erros[campo] = f"{rotulo} numérico inválido."
        return None
    if not numero.is_finite():
        erros[campo] = f"{rotulo} numérico inválido."
        return None
    if permitir_zero and numero < 0:
        erros[campo] = f"{rotulo} não pode ser negativo."
        return None
    if not permitir_zero and numero <= 0:
        erros[campo] = f"{rotulo} deve ser maior que zero."
        return None
    if numero > VALOR_MAXIMO:
        erros[campo] = f"{rotulo} não pode ser maior que {VALOR_MAXIMO}."
        return None
    if numero != numero.quantize(DUAS_CASAS):
        erros[campo] = f"{rotulo} deve ter no máximo 2 casas decimais."
        return None
    numero = numero.quantize(DUAS_CASAS)
    return numero if numero != 0 else Decimal("0.00")  # evita "-0.00"


def validar_valor(valor, erros: dict) -> Decimal | None:
    """Valor da baixa/título: maior que zero (atalho de ``validar_dinheiro``)."""
    return validar_dinheiro(valor, erros)


def _validar_forma(valor, erros: dict) -> str | None:
    """Forma de pagamento obrigatória, dentre as permitidas."""
    if _vazio(valor):
        erros["forma_pagamento"] = "Forma de pagamento é obrigatória."
        return None
    forma = _FORMA_POR_CHAVE.get(_sem_acento(valor)) if isinstance(valor, str) else None
    if forma is None:
        erros["forma_pagamento"] = (
            "Forma de pagamento inválida. Use: " + ", ".join(FORMAS_PAGAMENTO) + "."
        )
        return None
    return forma


def _validar_data_hora(valor, erros: dict) -> datetime | None:
    """Data e hora reais obrigatórias (``2026-13-45 25:61`` é recusada)."""
    if _vazio(valor):
        erros["realizado_em"] = "Realizado em é obrigatório."
        return None
    if not isinstance(valor, str):
        erros["realizado_em"] = "Data/hora inválida. Use AAAA-MM-DD HH:MM."
        return None

    texto = valor.strip()
    correspondencia = DATA_HORA_ISO.fullmatch(texto)
    if correspondencia:
        ano, mes, dia, hora, minuto, segundo = correspondencia.groups()
    else:
        correspondencia = DATA_HORA_BR.fullmatch(texto)
        if not correspondencia:
            erros["realizado_em"] = "Data/hora inválida. Use AAAA-MM-DD HH:MM."
            return None
        dia, mes, ano, hora, minuto, segundo = correspondencia.groups()

    try:
        data_hora = datetime(
            int(ano), int(mes), int(dia), int(hora), int(minuto), int(segundo or 0)
        )
    except ValueError:
        erros["realizado_em"] = "Data/hora inválida: essa data ou hora não existe."
        return None
    if data_hora.year < 1900:
        erros["realizado_em"] = "Data/hora inválida: informe um ano a partir de 1900."
        return None
    return data_hora


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /baixas``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    for campo in dados:
        if campo not in CAMPOS_BAIXA:
            erros[str(campo)] = "Campo não permitido nesta operação."

    valores = {
        "id_titulo": _validar_id("id_titulo", dados.get("id_titulo"), erros, "Título"),
        "id_caixa": _validar_id("id_caixa", dados.get("id_caixa"), erros, "Caixa"),
        "valor": validar_valor(dados.get("valor"), erros),
        "forma_pagamento": _validar_forma(dados.get("forma_pagamento"), erros),
        "realizado_em": _validar_data_hora(dados.get("realizado_em"), erros),
    }
    return valores, erros
