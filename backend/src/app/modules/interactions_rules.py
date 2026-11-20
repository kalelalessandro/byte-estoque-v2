"""Regras de validação dos campos de interação com parceiro.

Não acessa banco nem Flask: recebe o JSON já lido e devolve ``(valores, erros)``.

Limites da tabela ``interacoes`` (``database/init/01_schema.sql``):

    ocorrencia  DATE          obrigatório (data do contato, sem horário)
    canal       VARCHAR(30)   obrigatório
    descricao   TEXT          obrigatório

O canal é texto livre de até 30 caracteres (o plano de testes aceita qualquer valor
dentro do limite, ex.: telefone, e-mail, WhatsApp, reunião). O responsável
(``id_usuario``) NUNCA vem do JSON: é o usuário logado.
"""

from __future__ import annotations

import re
from datetime import date

TAMANHO_MAXIMO_CANAL = 30
# TEXT do MySQL guarda até 65.535 bytes; 16.383 caracteres (utf8mb4) sempre cabem.
TAMANHO_MAXIMO_DESCRICAO = 16383

# Datas aceitas: 2026-11-06 (padrão do <input type="date"> e da API) e 06/11/2026.
FORMATO_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
FORMATO_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

CAMPOS_INTERACAO = {"ocorrencia", "canal", "descricao"}


def _validar_data(valor, erros: dict) -> date | None:
    """Data obrigatória e REAL (``31/02/2026`` é recusada)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        erros["ocorrencia"] = "Data é obrigatória."
        return None
    if not isinstance(valor, str):
        erros["ocorrencia"] = "Data inválida. Use o formato AAAA-MM-DD."
        return None

    texto = valor.strip()
    correspondencia = FORMATO_ISO.fullmatch(texto)
    if correspondencia:
        ano, mes, dia = (int(parte) for parte in correspondencia.groups())
    else:
        correspondencia = FORMATO_BR.fullmatch(texto)
        if not correspondencia:
            erros["ocorrencia"] = "Data inválida. Use o formato AAAA-MM-DD."
            return None
        dia, mes, ano = (int(parte) for parte in correspondencia.groups())

    try:
        data = date(ano, mes, dia)  # recusa dias/meses que não existem
    except ValueError:
        erros["ocorrencia"] = "Data inválida: essa data não existe."
        return None
    if data.year < 1900:  # DATE do MySQL aceita 1000+, mas antes de 1900 é erro de digitação
        erros["ocorrencia"] = "Data inválida: informe um ano a partir de 1900."
        return None
    return data


def _validar_canal(valor, erros: dict) -> str | None:
    """Canal obrigatório, aparado, até 30 caracteres."""
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        erros["canal"] = "Canal deve ser um texto."
        return None
    valor = valor.strip()
    if not valor:
        erros["canal"] = "Canal é obrigatório."
        return None
    if len(valor) > TAMANHO_MAXIMO_CANAL:
        erros["canal"] = f"Canal deve ter no máximo {TAMANHO_MAXIMO_CANAL} caracteres."
        return None
    return valor


def _validar_descricao(valor, erros: dict) -> str | None:
    """Descrição obrigatória e aparada."""
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        erros["descricao"] = "Descrição deve ser um texto."
        return None
    valor = valor.strip()
    if not valor:
        erros["descricao"] = "Descrição é obrigatória."
        return None
    if len(valor) > TAMANHO_MAXIMO_DESCRICAO:
        erros["descricao"] = (
            f"Descrição deve ter no máximo {TAMANHO_MAXIMO_DESCRICAO} caracteres."
        )
        return None
    return valor


def _recusar_campos_desconhecidos(dados: dict, erros: dict) -> None:
    for campo in dados:
        if campo not in CAMPOS_INTERACAO:
            erros[str(campo)] = "Campo não permitido nesta operação."


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /parceiros/<id>/interacoes``."""
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, erros)

    valores = {
        "ocorrencia": _validar_data(dados.get("ocorrencia"), erros),
        "canal": _validar_canal(dados.get("canal"), erros),
        "descricao": _validar_descricao(dados.get("descricao"), erros),
    }
    return valores, erros


def validar_edicao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``PATCH /parceiros/<id>/interacoes/<id>`` (parcial)."""
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, erros)

    valores: dict = {}
    if "ocorrencia" in dados:
        data = _validar_data(dados["ocorrencia"], erros)
        if "ocorrencia" not in erros:
            valores["ocorrencia"] = data
    if "canal" in dados:
        canal = _validar_canal(dados["canal"], erros)
        if "canal" not in erros:
            valores["canal"] = canal
    if "descricao" in dados:
        descricao = _validar_descricao(dados["descricao"], erros)
        if "descricao" not in erros:
            valores["descricao"] = descricao

    if not erros and not valores:
        erros["corpo"] = "Informe ao menos um campo para alterar: ocorrencia, canal ou descricao."
    return valores, erros
