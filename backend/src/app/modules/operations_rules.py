"""Regras de validação e normalização do módulo de operações.

Não acessa banco nem Flask: recebe o JSON já lido e devolve ``(valores, erros)``.
As regras que dependem do banco (produtos/parceiro da empresa, estoque, título)
ficam em ``operations.py``.

Campos aceitos na criação/edição de uma operação:

    tipo          "venda" ou "compra"
    id_parceiro   opcional (parceiro da mesma empresa)
    ocorrencia    DATETIME opcional (padrão: agora)
    observacoes   texto opcional
    itens         lista com 1..100 itens:
                    id_produto (INT), quantidade (INT > 0), valor_unitario (>= 0)
    parcelas      inteiro 1..120 (padrão 1)
    vencimento    data opcional do primeiro título (padrão: hoje + 30 dias)
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

LIMITE_ITENS = 100
LIMITE_OBSERVACOES = 2000
MAX_PARCELAS = 120
INT_MAXIMO = 2_147_483_647
VALOR_MAXIMO = Decimal("9999999999.99")
DUAS_CASAS = Decimal("0.01")

TIPOS = ("venda", "compra")
CAMPOS_OPERACAO = {
    "tipo",
    "id_parceiro",
    "ocorrencia",
    "observacoes",
    "itens",
    "parcelas",
    "vencimento",
}
CAMPOS_ITEM = {"id_produto", "quantidade", "valor_unitario"}

_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATA_HORA_ISO = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?$"
)


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


_TIPO_POR_CHAVE = {_sem_acento(tipo): tipo for tipo in TIPOS}


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _validar_tipo(valor, erros: dict) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        erros["tipo"] = "Tipo é obrigatório: venda ou compra."
        return None
    tipo = _TIPO_POR_CHAVE.get(_sem_acento(valor.strip()))
    if tipo is None:
        erros["tipo"] = "'tipo' deve ser: venda ou compra."
    return tipo


def _validar_id_opcional(valor, erros: dict) -> int | None:
    """Parceiro opcional: null/vazio/0 significa sem parceiro."""
    if _vazio(valor) or valor == 0 or valor == "0":
        return None
    if isinstance(valor, str) and re.fullmatch(r"[0-9]+", valor.strip()):
        valor = int(valor.strip())
    if not isinstance(valor, int) or isinstance(valor, bool):
        erros["id_parceiro"] = "Parceiro inválido."
        return None
    if valor < 1 or valor > INT_MAXIMO:
        erros["id_parceiro"] = "Parceiro inválido."
        return None
    return valor


def _validar_data(valor, erros: dict):
    if _vazio(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not isinstance(valor, str):
        erros["vencimento"] = "Data de vencimento inválida."
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        erros["vencimento"] = "Data de vencimento inválida (use AAAA-MM-DD)."
        return None


def _validar_data_hora(valor, erros: dict) -> datetime | None:
    if _vazio(valor):
        return None
    if isinstance(valor, datetime):
        return valor
    if not isinstance(valor, str):
        erros["ocorrencia"] = "Data/hora de ocorrência inválida."
        return None
    texto = valor.strip().replace("Z", "+00:00")
    if not (_DATA_HORA_ISO.match(texto) or "T" in texto or " " in texto):
        erros["ocorrencia"] = "Data/hora de ocorrência inválida."
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        erros["ocorrencia"] = "Data/hora de ocorrência inválida."
        return None


def _validar_inteiro_positivo(campo: str, valor, erros: dict, rotulo: str):
    if isinstance(valor, bool):
        erros[campo] = f"{rotulo} deve ser um número inteiro."
        return None
    if isinstance(valor, str) and re.fullmatch(r"[0-9]+", valor.strip()):
        valor = int(valor.strip())
    if not isinstance(valor, int) or valor < 1 or valor > INT_MAXIMO:
        erros[campo] = f"{rotulo} deve ser um número inteiro maior que zero."
        return None
    return valor


def _validar_dinheiro(valor, erros: dict, rotulo: str):
    if isinstance(valor, bool):
        erros["itens"] = f"{rotulo} inválido."
        return None
    if isinstance(valor, str):
        valor = valor.strip().replace(",", ".")
    if _vazio(valor):
        erros["itens"] = f"{rotulo} é obrigatório."
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        erros["itens"] = f"{rotulo} inválido."
        return None
    if not numero.is_finite() or numero < 0:
        erros["itens"] = f"{rotulo} não pode ser negativo."
        return None
    if numero > VALOR_MAXIMO:
        erros["itens"] = f"{rotulo} acima do máximo permitido."
        return None
    if numero.as_tuple().exponent < -2:
        erros["itens"] = f"{rotulo} aceita no máximo 2 casas decimais."
        return None
    return numero.quantize(DUAS_CASAS)


def _validar_itens(valor, erros: dict) -> list[dict]:
    if not isinstance(valor, list) or not valor:
        erros["itens"] = "Informe ao menos um item na operação."
        return []
    if len(valor) > LIMITE_ITENS:
        erros["itens"] = f"A operação pode ter no máximo {LIMITE_ITENS} itens."
        return []

    itens: list[dict] = []
    vistos: set[int] = set()
    for indice, bruto in enumerate(valor, start=1):
        if not isinstance(bruto, dict):
            erros["itens"] = f"Item {indice} inválido."
            return []
        desconhecidos = set(bruto) - CAMPOS_ITEM
        if desconhecidos:
            erros["itens"] = (
                f"Item {indice}: campo(s) não permitido(s): "
                + ", ".join(sorted(desconhecidos))
                + "."
            )
            return []

        id_produto = _validar_inteiro_positivo(
            "id_produto", bruto.get("id_produto"), {}, "Produto"
        )
        quantidade = _validar_inteiro_positivo(
            "quantidade", bruto.get("quantidade"), {}, "Quantidade"
        )
        valor_unitario = _validar_dinheiro(
            bruto.get("valor_unitario"), {}, "Valor unitário"
        )
        if id_produto is None or quantidade is None or valor_unitario is None:
            erros["itens"] = f"Item {indice} inválido. Confira produto, quantidade e valor."
            return []
        if id_produto in vistos:
            erros["itens"] = (
                f"O produto {id_produto} aparece mais de uma vez; junte as quantidades."
            )
            return []
        vistos.add(id_produto)
        itens.append(
            {
                "id_produto": id_produto,
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
            }
        )
    return itens


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST/PATCH /operacoes``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    for campo in dados:
        if campo not in CAMPOS_OPERACAO:
            erros[str(campo)] = "Campo não permitido nesta operação."

    parcelas = dados.get("parcelas", 1)
    if isinstance(parcelas, str) and re.fullmatch(r"[0-9]+", parcelas.strip()):
        parcelas = int(parcelas.strip())
    if (
        isinstance(parcelas, bool)
        or not isinstance(parcelas, int)
        or parcelas < 1
        or parcelas > MAX_PARCELAS
    ):
        erros["parcelas"] = f"Parcelas deve ser um inteiro entre 1 e {MAX_PARCELAS}."
        parcelas = None

    observacoes = dados.get("observacoes")
    if observacoes is not None and not isinstance(observacoes, str):
        erros["observacoes"] = "Observações deve ser um texto."
        observacoes = None
    elif isinstance(observacoes, str):
        observacoes = observacoes.strip() or None
        if observacoes and len(observacoes) > LIMITE_OBSERVACOES:
            erros["observacoes"] = (
                f"Observações deve ter no máximo {LIMITE_OBSERVACOES} caracteres."
            )

    valores = {
        "tipo": _validar_tipo(dados.get("tipo"), erros),
        "id_parceiro": _validar_id_opcional(dados.get("id_parceiro"), erros),
        "ocorrencia": _validar_data_hora(dados.get("ocorrencia"), erros),
        "observacoes": observacoes,
        "itens": _validar_itens(dados.get("itens"), erros),
        "parcelas": parcelas,
        "vencimento": _validar_data(dados.get("vencimento"), erros),
    }
    return valores, erros
