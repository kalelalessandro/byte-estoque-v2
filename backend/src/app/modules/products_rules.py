"""Regras de validação e normalização dos campos de produto.

Este arquivo NÃO acessa o banco nem o Flask: recebe o JSON já lido e devolve
``(valores, erros)``. Assim as regras ficam fáceis de ler e de testar, e as
rotas (``products.py``) cuidam só de HTTP e banco.

Limites seguem a tabela ``produtos`` do schema:

    sku              VARCHAR(64)    obrigatório (único por empresa)
    id_categoria     INT            obrigatório (categoria da MESMA empresa)
    nome             VARCHAR(150)   obrigatório
    descricao        VARCHAR(500)   opcional
    unidade_estoque  INT >= 0       padrão 0
    preco            DECIMAL(12,2)  >= 0, obrigatório
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

TAMANHO_MAXIMO_SKU = 64
TAMANHO_MAXIMO_NOME = 150
TAMANHO_MAXIMO_DESCRICAO = 500

# Limites numéricos das colunas do MySQL.
ESTOQUE_MAXIMO = 2_147_483_647  # maior INT (com sinal) do MySQL
PRECO_MAXIMO = Decimal("9999999999.99")  # DECIMAL(12,2) -> 10 dígitos + 2 casas
DUAS_CASAS = Decimal("0.01")

# Campos que o cliente pode enviar em cada operação. Qualquer outro campo
# (ex.: ``id_empresa``) é recusado: a empresa SEMPRE vem do usuário logado.
CAMPOS_CRIACAO = {"sku", "id_categoria", "nome", "descricao", "unidade_estoque", "preco"}
CAMPOS_EDICAO = {"sku", "id_categoria", "nome", "descricao", "unidade_estoque", "preco"}


# ---------------------------------------------------------------------------
# Validadores de campo (cada um registra o erro em ``erros`` e devolve o valor)
# ---------------------------------------------------------------------------


def _validar_texto(
    campo: str,
    valor,
    erros: dict,
    *,
    rotulo: str,
    maximo: int,
    obrigatorio: bool,
) -> str | None:
    """Texto aparado (trim). Vazio vira ``None`` quando o campo é opcional."""
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        erros[campo] = f"{rotulo} deve ser um texto."
        return None

    valor = valor.strip()
    if not valor:
        if obrigatorio:
            erros[campo] = f"{rotulo} é obrigatório."
        return None
    if len(valor) > maximo:
        erros[campo] = f"{rotulo} deve ter no máximo {maximo} caracteres."
        return None
    return valor


def _validar_inteiro(
    campo: str, valor, erros: dict, *, rotulo: str, minimo: int, maximo: int
) -> int | None:
    """Inteiro entre ``minimo`` e ``maximo``.

    Aceita número JSON inteiro (``5``) ou texto só com dígitos (``"5"``, útil
    para formulários HTML). Recusa ``true/false``, decimais (``5.5``) e vazio.
    """
    if isinstance(valor, bool):  # em Python, bool é subclasse de int
        erros[campo] = f"{rotulo} deve ser um número inteiro."
        return None

    if isinstance(valor, str) and re.fullmatch(r"[0-9]+", valor.strip()):
        valor = int(valor.strip())

    if not isinstance(valor, int):
        erros[campo] = f"{rotulo} deve ser um número inteiro."
        return None
    if valor < minimo:
        erros[campo] = f"{rotulo} não pode ser menor que {minimo}."
        return None
    if valor > maximo:
        erros[campo] = f"{rotulo} não pode ser maior que {maximo}."
        return None
    return valor


def _validar_preco(campo: str, valor, erros: dict) -> Decimal | None:
    """Preço em ``Decimal`` com exatamente 2 casas, entre 0 e 9.999.999.999,99.

    Aceita número JSON (``10.5``) ou texto (``"10.50"`` / ``"10,50"``).
    Usamos ``Decimal`` (e não ``float``) para não perder centavos.
    """
    if valor is None or isinstance(valor, bool):
        erros[campo] = "Preço é obrigatório e deve ser um número."
        return None

    if isinstance(valor, (int, float)):
        texto = str(valor)  # repr mais curto do float (0.1 -> "0.1", não 0.1000000000000000055...)
    elif isinstance(valor, str):
        texto = valor.strip()
        # "10,50" (padrão brasileiro) -> "10.50". Só trocamos se não houver ponto,
        # para não adivinhar "1.234,56" de forma errada.
        if "," in texto and "." not in texto:
            texto = texto.replace(",", ".")
    else:
        erros[campo] = "Preço deve ser um número."
        return None

    try:
        preco = Decimal(texto)
    except InvalidOperation:
        erros[campo] = "Preço deve ser um número válido."
        return None

    if not preco.is_finite():  # recusa NaN e Infinity
        erros[campo] = "Preço deve ser um número válido."
        return None
    if preco < 0:
        erros[campo] = "Preço não pode ser negativo."
        return None
    if preco > PRECO_MAXIMO:
        erros[campo] = f"Preço não pode ser maior que {PRECO_MAXIMO}."
        return None
    if preco != preco.quantize(DUAS_CASAS):
        erros[campo] = "Preço deve ter no máximo 2 casas decimais."
        return None

    preco = preco.quantize(DUAS_CASAS)
    return preco if preco != 0 else Decimal("0.00")  # evita "-0.00"


def _recusar_campos_desconhecidos(dados: dict, permitidos: set[str], erros: dict) -> None:
    """Recusa campos fora da lista (inclusive ``id_empresa``, ``sku`` na edição, etc.)."""
    for campo in dados:
        if campo not in permitidos:
            erros[str(campo)] = "Campo não permitido nesta operação."


# ---------------------------------------------------------------------------
# Funções públicas usadas pelas rotas
# ---------------------------------------------------------------------------


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /produtos``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, CAMPOS_CRIACAO, erros)

    sku = _validar_texto(
        "sku", dados.get("sku"), erros,
        rotulo="SKU", maximo=TAMANHO_MAXIMO_SKU, obrigatorio=True,
    )
    nome = _validar_texto(
        "nome", dados.get("nome"), erros,
        rotulo="Nome", maximo=TAMANHO_MAXIMO_NOME, obrigatorio=True,
    )
    descricao = _validar_texto(
        "descricao", dados.get("descricao"), erros,
        rotulo="Descrição", maximo=TAMANHO_MAXIMO_DESCRICAO, obrigatorio=False,
    )

    # id_categoria: aqui só checamos o formato; a rota confere se existe e se é
    # da mesma empresa do usuário (precisa do banco).
    id_categoria = _validar_inteiro(
        "id_categoria", dados.get("id_categoria"), erros,
        rotulo="Categoria", minimo=1, maximo=ESTOQUE_MAXIMO,
    )

    # Estoque é opcional na criação: se omitido (ou null), começa em 0 (padrão do schema).
    estoque_bruto = dados.get("unidade_estoque")
    if estoque_bruto is None:
        unidade_estoque = 0
    else:
        unidade_estoque = _validar_inteiro(
            "unidade_estoque", estoque_bruto, erros,
            rotulo="Estoque", minimo=0, maximo=ESTOQUE_MAXIMO,
        )

    preco = _validar_preco("preco", dados.get("preco"), erros)

    valores = {
        "sku": sku,
        "id_categoria": id_categoria,
        "nome": nome,
        "descricao": descricao,
        "unidade_estoque": unidade_estoque,
        "preco": preco,
    }
    return valores, erros


def validar_edicao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``PATCH /produtos/<id>``.

    Edição parcial: só os campos ENVIADOS são validados e devolvidos em
    ``valores``. Campos ausentes não são alterados.
    """
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, CAMPOS_EDICAO, erros)

    valores: dict = {}

    if "sku" in dados:
        sku = _validar_texto(
            "sku", dados["sku"], erros,
            rotulo="SKU", maximo=TAMANHO_MAXIMO_SKU, obrigatorio=True,
        )
        if sku is not None:
            valores["sku"] = sku

    if "id_categoria" in dados:
        # Aqui só o formato; a rota confere existência e empresa.
        id_categoria = _validar_inteiro(
            "id_categoria", dados["id_categoria"], erros,
            rotulo="Categoria", minimo=1, maximo=ESTOQUE_MAXIMO,
        )
        if id_categoria is not None:
            valores["id_categoria"] = id_categoria

    if "nome" in dados:
        nome = _validar_texto(
            "nome", dados["nome"], erros,
            rotulo="Nome", maximo=TAMANHO_MAXIMO_NOME, obrigatorio=True,
        )
        if nome is not None:
            valores["nome"] = nome

    if "descricao" in dados:
        # Enviar null ou "" LIMPA a descrição (vira NULL no banco).
        descricao = _validar_texto(
            "descricao", dados["descricao"], erros,
            rotulo="Descrição", maximo=TAMANHO_MAXIMO_DESCRICAO, obrigatorio=False,
        )
        if "descricao" not in erros:
            valores["descricao"] = descricao

    if "unidade_estoque" in dados:
        estoque = _validar_inteiro(
            "unidade_estoque", dados["unidade_estoque"], erros,
            rotulo="Estoque", minimo=0, maximo=ESTOQUE_MAXIMO,
        )
        if estoque is not None:
            valores["unidade_estoque"] = estoque

    if "preco" in dados:
        preco = _validar_preco("preco", dados["preco"], erros)
        if preco is not None:
            valores["preco"] = preco

    # Corpo sem nenhum campo editável (ex.: {}) não faz sentido.
    if not erros and not valores:
        erros["corpo"] = (
            "Informe ao menos um campo para alterar: "
            "sku, id_categoria, nome, descricao, unidade_estoque ou preco."
        )

    return valores, erros
