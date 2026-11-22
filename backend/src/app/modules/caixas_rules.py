"""Regras de validação dos campos do caixa (abertura, movimento e fechamento).

Não acessa banco nem Flask: recebe o JSON já lido e devolve ``(valores, erros)``. As
regras que dependem do banco (caixa aberto, da empresa, ainda aberto) ficam em
``caixas.py``.

Campos (``database/init/01_schema.sql`` e plano de testes, módulo CXA):

    abertura        valor_abertura   DECIMAL(12,2)  obrigatório, ZERO é permitido, não negativo
    movimento       tipo             VARCHAR(30)    obrigatório: "suprimento" ou "sangria"
                    valor            DECIMAL(12,2)  obrigatório, maior que zero
                    descricao        TEXT           opcional (motivo do movimento)
    fechamento      valor_contado    DECIMAL(12,2)  obrigatório, ZERO é permitido, não negativo

Datas e horários (abertura, movimento, fechamento) NUNCA vêm do JSON: são do servidor.
"""

from __future__ import annotations

import unicodedata

from .baixas_rules import validar_dinheiro

TIPOS_MOVIMENTO = ("suprimento", "sangria")
TAMANHO_MAXIMO_DESCRICAO = 16383  # TEXT (65.535 bytes) em utf8mb4 sempre comporta

CAMPOS_ABERTURA = {"valor_abertura"}
CAMPOS_MOVIMENTO = {"tipo", "valor", "descricao"}
CAMPOS_FECHAMENTO = {"valor_contado"}


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _recusar_desconhecidos(dados: dict, permitidos: set[str], erros: dict) -> None:
    for campo in dados:
        if campo not in permitidos:
            erros[str(campo)] = "Campo não permitido nesta operação."


def validar_abertura(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /caixas``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    _recusar_desconhecidos(dados, CAMPOS_ABERTURA, erros)
    valores = {
        "valor_abertura": validar_dinheiro(
            dados.get("valor_abertura"),
            erros,
            campo="valor_abertura",
            rotulo="Valor de abertura",
            permitir_zero=True,
        )
    }
    return valores, erros


def validar_movimento(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /caixas/<id>/movimentos`` (suprimento ou sangria)."""
    erros: dict = {}
    _recusar_desconhecidos(dados, CAMPOS_MOVIMENTO, erros)

    tipo = None
    bruto = dados.get("tipo")
    if _vazio(bruto):
        erros["tipo"] = "Tipo é obrigatório."
    elif not isinstance(bruto, str) or _sem_acento(bruto.strip()) not in TIPOS_MOVIMENTO:
        erros["tipo"] = "Tipo inválido. Use: suprimento ou sangria."
    else:
        tipo = _sem_acento(bruto.strip())

    descricao = None
    bruta = dados.get("descricao")
    if bruta is not None and not isinstance(bruta, str):
        erros["descricao"] = "Descrição deve ser um texto."
    elif isinstance(bruta, str) and bruta.strip():
        descricao = bruta.strip()
        if len(descricao) > TAMANHO_MAXIMO_DESCRICAO:
            erros["descricao"] = (
                f"Descrição deve ter no máximo {TAMANHO_MAXIMO_DESCRICAO} caracteres."
            )
            descricao = None

    valores = {
        "tipo": tipo,
        "valor": validar_dinheiro(dados.get("valor"), erros),
        "descricao": descricao,
    }
    return valores, erros


def validar_fechamento(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /caixas/<id>/fechar``."""
    erros: dict = {}
    _recusar_desconhecidos(dados, CAMPOS_FECHAMENTO, erros)
    valores = {
        "valor_contado": validar_dinheiro(
            dados.get("valor_contado"),
            erros,
            campo="valor_contado",
            rotulo="Valor contado",
            permitir_zero=True,
        )
    }
    return valores, erros
