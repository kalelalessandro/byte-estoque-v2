"""Regras de validação e normalização dos campos de parceiro.

Este arquivo NÃO acessa o banco nem o Flask: recebe o JSON já lido e devolve
``(valores, erros)``. As rotas (``partners.py``) cuidam só de HTTP e banco.

Limites e regras vêm da tabela ``parceiros`` (``database/init/01_schema.sql``),
da Documentação do Banco v1.2 e do plano de testes (módulo PAR):

    nome          VARCHAR(150)  obrigatório
    documento     VARCHAR(14)   opcional; CPF (11 dígitos) ou CNPJ (14 caracteres,
                                alfanumérico), SEM pontuação; único por empresa
    email         VARCHAR(254)  opcional; único por empresa; gravado em minúsculas
    cep           VARCHAR(8)    opcional; 8 dígitos, SEM pontuação
    e_cliente     BOOLEAN       padrão falso
    e_fornecedor  BOOLEAN       padrão falso (ao menos um dos dois deve ser verdadeiro)
    observacao    TEXT          opcional

O schema só garante tamanho, NOT NULL, UNIQUE e CHECK (e os CHECKs não conferem
formato nem dígitos verificadores). Por isso o formato/DV é validado AQUI, e a
ausência de e-mail/documento/CEP/observação é sempre gravada como ``NULL``.
"""

from __future__ import annotations

import re

from ..core.auth_utils import EMAIL_REGEX
from ..core.signup import _validar_cnpj  # mesma regra do CNPJ da empresa (módulo 11)

TAMANHO_MAXIMO_NOME = 150
TAMANHO_MAXIMO_DOCUMENTO = 14
TAMANHO_MAXIMO_EMAIL = 254
# TEXT do MySQL guarda até 65.535 BYTES; com utf8mb4 (até 4 bytes por caractere),
# 16.383 caracteres cabem com folga em qualquer idioma.
TAMANHO_MAXIMO_TEXTO = 16383

# Pontuação aceita (e removida) em documento e CEP: 123.456.789-09, 11.222.333/0001-81.
MASCARA_DOCUMENTO = re.compile(r"[.\-/\s]")
MASCARA_CEP = re.compile(r"[.\-\s]")

# Campos que o cliente pode enviar. Qualquer outro (ex.: ``id_empresa``) é recusado:
# a empresa SEMPRE vem do usuário logado.
CAMPOS_PARCEIRO = {
    "nome",
    "documento",
    "email",
    "cep",
    "e_cliente",
    "e_fornecedor",
    "observacao",
}

MENSAGEM_RELACIONAMENTO = (
    "Marque ao menos um relacionamento: cliente e/ou fornecedor."
)


# ---------------------------------------------------------------------------
# Validadores de campo (cada um registra o erro em ``erros`` e devolve o valor)
# ---------------------------------------------------------------------------


def _so_espacos(valor) -> bool:
    """Texto não vazio, mas só com espaços (ex.: ``"   "``)."""
    return isinstance(valor, str) and valor != "" and valor.strip() == ""


def _validar_nome(valor, erros: dict) -> str | None:
    """Nome obrigatório, aparado (trim), até 150 caracteres."""
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


def _digitos_cpf_validos(cpf: str) -> bool:
    """Confere os 2 dígitos verificadores do CPF (módulo 11)."""
    if len(cpf) != 11 or not cpf.isascii() or not cpf.isdigit():
        return False
    if len(set(cpf)) == 1:  # 111.111.111-11 etc. passam na conta, mas são inválidos
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def _validar_documento(valor, erros: dict) -> str | None:
    """Documento opcional: CPF (11 dígitos) ou CNPJ (14 caracteres alfanuméricos).

    Remove a pontuação, coloca em maiúsculas (``p1q2...`` == ``P1Q2...``) e confere
    os dígitos verificadores. Vazio vira ``None``; só espaços é erro (o CHECK do
    banco também rejeitaria).
    """
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        erros["documento"] = "Documento deve ser um texto."
        return None
    if _so_espacos(valor):
        erros["documento"] = "Documento inválido: não pode conter apenas espaços."
        return None

    documento = MASCARA_DOCUMENTO.sub("", valor).upper()
    if not documento:
        erros["documento"] = "Documento inválido."
        return None
    if len(documento) > TAMANHO_MAXIMO_DOCUMENTO:
        erros["documento"] = (
            f"Documento deve ter no máximo {TAMANHO_MAXIMO_DOCUMENTO} caracteres."
        )
        return None

    if len(documento) == 11:
        if not _digitos_cpf_validos(documento):
            erros["documento"] = "CPF inválido (dígitos verificadores incorretos)."
            return None
        return documento

    if len(documento) == 14:
        cnpj, erro_cnpj = _validar_cnpj(documento)
        if erro_cnpj:
            erros["documento"] = erro_cnpj
            return None
        return cnpj

    erros["documento"] = (
        "Documento inválido. Informe um CPF (11 dígitos) ou um CNPJ (14 caracteres)."
    )
    return None


def _validar_email(valor, erros: dict) -> str | None:
    """E-mail opcional: aparado, em minúsculas, até 254 caracteres, formato válido."""
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        erros["email"] = "E-mail deve ser um texto."
        return None
    if _so_espacos(valor):
        erros["email"] = "E-mail inválido: não pode conter apenas espaços."
        return None

    email = valor.strip().lower()
    if len(email) > TAMANHO_MAXIMO_EMAIL:
        erros["email"] = f"E-mail deve ter no máximo {TAMANHO_MAXIMO_EMAIL} caracteres."
        return None
    if not EMAIL_REGEX.fullmatch(email):
        erros["email"] = "E-mail inválido."
        return None
    return email


def _validar_cep(valor, erros: dict) -> str | None:
    """CEP opcional: exatamente 8 dígitos (aceita ``50050-010``; guarda ``50050010``).

    Letras NÃO são descartadas (``5005AB10`` é inválido), diferente de apenas
    "tirar tudo que não é dígito".
    """
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        erros["cep"] = "CEP deve ser um texto."
        return None

    cep = MASCARA_CEP.sub("", valor)
    if not re.fullmatch(r"[0-9]{8}", cep):
        erros["cep"] = "CEP inválido. Informe exatamente 8 dígitos."
        return None
    return cep


def _validar_observacao(valor, erros: dict) -> str | None:
    """Observação opcional (TEXT): aparada; vazia vira ``None``."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        erros["observacao"] = "Observação deve ser um texto."
        return None
    valor = valor.strip()
    if not valor:
        return None
    if len(valor) > TAMANHO_MAXIMO_TEXTO:
        erros["observacao"] = (
            f"Observação deve ter no máximo {TAMANHO_MAXIMO_TEXTO} caracteres."
        )
        return None
    return valor


def _validar_booleano(campo: str, valor, erros: dict, rotulo: str) -> bool | None:
    """Aceita só ``true``/``false`` do JSON (texto como ``"false"`` seria truthy)."""
    if not isinstance(valor, bool):
        erros[campo] = f"{rotulo} deve ser verdadeiro ou falso."
        return None
    return valor


def _recusar_campos_desconhecidos(dados: dict, erros: dict) -> None:
    for campo in dados:
        if campo not in CAMPOS_PARCEIRO:
            erros[str(campo)] = "Campo não permitido nesta operação."


# ---------------------------------------------------------------------------
# Funções públicas usadas pelas rotas
# ---------------------------------------------------------------------------


def validar_criacao(dados: dict) -> tuple[dict, dict]:
    """Valida o corpo do ``POST /parceiros``. Devolve ``(valores, erros)``."""
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, erros)

    nome = _validar_nome(dados.get("nome"), erros)
    documento = _validar_documento(dados.get("documento"), erros)
    email = _validar_email(dados.get("email"), erros)
    cep = _validar_cep(dados.get("cep"), erros)
    observacao = _validar_observacao(dados.get("observacao"), erros)

    # Relacionamentos omitidos (ou null) começam desmarcados, como no schema.
    e_cliente = False
    if dados.get("e_cliente") is not None:
        e_cliente = _validar_booleano("e_cliente", dados["e_cliente"], erros, "Cliente")
    e_fornecedor = False
    if dados.get("e_fornecedor") is not None:
        e_fornecedor = _validar_booleano(
            "e_fornecedor", dados["e_fornecedor"], erros, "Fornecedor"
        )

    # Só confere a regra "ao menos um" quando os dois valores são válidos.
    if "e_cliente" not in erros and "e_fornecedor" not in erros:
        if not (e_cliente or e_fornecedor):
            erros["relacionamento"] = MENSAGEM_RELACIONAMENTO

    valores = {
        "nome": nome,
        "documento": documento,
        "email": email,
        "cep": cep,
        "e_cliente": e_cliente,
        "e_fornecedor": e_fornecedor,
        "observacao": observacao,
    }
    return valores, erros


def validar_edicao(
    dados: dict, *, e_cliente_atual: bool, e_fornecedor_atual: bool
) -> tuple[dict, dict]:
    """Valida o corpo do ``PATCH /parceiros/<id>`` (edição PARCIAL).

    Só os campos ENVIADOS são validados e devolvidos. Enviar ``null`` ou ``""`` em
    documento/e-mail/CEP/observação LIMPA o campo (vira ``NULL``). Os valores atuais
    de cliente/fornecedor entram na conta: desmarcar o único relacionamento marcado
    é erro.
    """
    erros: dict = {}
    _recusar_campos_desconhecidos(dados, erros)

    valores: dict = {}

    if "nome" in dados:
        nome = _validar_nome(dados["nome"], erros)
        if "nome" not in erros:
            valores["nome"] = nome

    if "documento" in dados:
        documento = _validar_documento(dados["documento"], erros)
        if "documento" not in erros:
            valores["documento"] = documento

    if "email" in dados:
        email = _validar_email(dados["email"], erros)
        if "email" not in erros:
            valores["email"] = email

    if "cep" in dados:
        cep = _validar_cep(dados["cep"], erros)
        if "cep" not in erros:
            valores["cep"] = cep

    if "observacao" in dados:
        observacao = _validar_observacao(dados["observacao"], erros)
        if "observacao" not in erros:
            valores["observacao"] = observacao

    if "e_cliente" in dados:
        e_cliente = _validar_booleano("e_cliente", dados["e_cliente"], erros, "Cliente")
        if "e_cliente" not in erros:
            valores["e_cliente"] = e_cliente

    if "e_fornecedor" in dados:
        e_fornecedor = _validar_booleano(
            "e_fornecedor", dados["e_fornecedor"], erros, "Fornecedor"
        )
        if "e_fornecedor" not in erros:
            valores["e_fornecedor"] = e_fornecedor

    # Estado FINAL dos relacionamentos = o que veio no corpo, senão o que já era.
    if "e_cliente" not in erros and "e_fornecedor" not in erros:
        cliente_final = valores.get("e_cliente", e_cliente_atual)
        fornecedor_final = valores.get("e_fornecedor", e_fornecedor_atual)
        if not (cliente_final or fornecedor_final):
            erros["relacionamento"] = MENSAGEM_RELACIONAMENTO

    if not erros and not valores:
        erros["corpo"] = (
            "Informe ao menos um campo para alterar: nome, documento, email, cep, "
            "e_cliente, e_fornecedor ou observacao."
        )

    return valores, erros
