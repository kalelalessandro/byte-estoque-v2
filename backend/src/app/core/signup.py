"""Rotas de cadastro (signup) do Byte Estoque.

O cadastro cria, em uma única transação, a **empresa** e o **primeiro usuário**
dela. O usuário recebe o cargo ``Administrador`` (criado na tabela ``cargos``
caso ainda não exista). O schema do banco NÃO é alterado.

Regras de normalização/validação seguem o plano de testes V1.2
(``crm-estoque/docs/plano de testes.pdf``):

- CNPJ aceita formato alfanumérico (12 caracteres ``[0-9A-Z]`` + 2 dígitos
  verificadores numéricos), é normalizado para maiúsculas e sem pontuação e os
  dígitos verificadores são conferidos (módulo 11, valor = ASCII - 48).
- Telefones são texto livre de até 20 caracteres (preservam a máscara digitada).
- E-mail e demais textos são aparados (trim); o e-mail vira minúsculo.
"""

from __future__ import annotations

import re

from flask import Blueprint
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from ..db import get_db
from ..db.models import Cargo, Empresa, Usuario
from .auth_utils import (
    EMAIL_REGEX,
    ler_json,
    resposta_erro,
    resposta_ok,
    serializar_empresa,
    serializar_usuario,
)

bp = Blueprint("signup", __name__)

CARGO_PADRAO = "Administrador"

TAMANHO_MAXIMO_SENHA = 128
TAMANHO_MINIMO_SENHA = 6
TAMANHO_MAXIMO_TELEFONE = 20

PESOS_CNPJ_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_CNPJ_DV2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

CARACTERES_MASCARA_CNPJ = re.compile(r"[.\-/\s]")


def _somente_digitos(valor) -> str:
    if valor is None:
        return ""
    return re.sub(r"\D", "", str(valor))


def _normalizar_cnpj(valor) -> str:
    """Remove a máscara (. - / e espaços) e devolve em maiúsculas."""
    if valor is None:
        return ""
    return CARACTERES_MASCARA_CNPJ.sub("", str(valor)).upper()


def _calcular_digitos_verificadores_cnpj(base: str) -> str:
    """Calcula os 2 DVs do CNPJ (módulo 11; valor do caractere = ASCII - 48)."""
    valores = [ord(caractere) - 48 for caractere in base]

    soma1 = sum(valor * peso for valor, peso in zip(valores, PESOS_CNPJ_DV1))
    dv1 = 11 - soma1 % 11
    if dv1 >= 10:
        dv1 = 0

    valores_com_dv1 = valores + [dv1]
    soma2 = sum(valor * peso for valor, peso in zip(valores_com_dv1, PESOS_CNPJ_DV2))
    dv2 = 11 - soma2 % 11
    if dv2 >= 10:
        dv2 = 0

    return f"{dv1}{dv2}"


def _validar_cnpj(valor) -> tuple[str, str | None]:
    """Normaliza e valida o CNPJ. Retorna ``(cnpj, mensagem_de_erro)``."""
    cnpj = _normalizar_cnpj(valor)

    if len(cnpj) != 14:
        return cnpj, "CNPJ deve conter exatamente 14 caracteres."

    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj):
        return cnpj, (
            "CNPJ inválido. Use 12 caracteres alfanuméricos e "
            "2 dígitos verificadores numéricos."
        )

    if len(set(cnpj)) == 1:
        return cnpj, "CNPJ inválido."

    if _calcular_digitos_verificadores_cnpj(cnpj[:12]) != cnpj[12:]:
        return cnpj, "CNPJ inválido (dígitos verificadores incorretos)."

    return cnpj, None


def _validar_texto(
    campo: str,
    valor,
    erros: dict,
    *,
    rotulo: str,
    maximo: int,
    obrigatorio: bool,
) -> str:
    """Valida um campo de texto e devolve o valor já sem espaços nas pontas."""
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        erros[campo] = f"{rotulo} deve ser um texto."
        return ""
    valor = valor.strip()
    if obrigatorio and not valor:
        erros[campo] = f"{rotulo} é obrigatório."
        return ""
    if valor and len(valor) > maximo:
        erros[campo] = f"{rotulo} deve ter no máximo {maximo} caracteres."
    return valor


def _validar_telefone(campo: str, valor, erros: dict, *, rotulo: str) -> str | None:
    """Telefone opcional: texto de até 20 caracteres (máscara é preservada)."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        valor = str(int(valor))
    if not isinstance(valor, str):
        erros[campo] = f"{rotulo} deve ser um texto."
        return None
    valor = valor.strip()
    if not valor:
        return None
    if len(valor) > TAMANHO_MAXIMO_TELEFONE:
        erros[campo] = (
            f"{rotulo} deve ter no máximo {TAMANHO_MAXIMO_TELEFONE} caracteres."
        )
        return None
    return valor


def _validar_cep(campo: str, valor, erros: dict) -> str | None:
    """CEP opcional: 8 dígitos após remover a máscara."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    digitos = _somente_digitos(valor)
    if len(digitos) != 8:
        erros[campo] = "CEP deve conter exatamente 8 dígitos."
        return None
    return digitos


def _obter_ou_criar_cargo(db, nome: str) -> Cargo:
    """Busca o cargo pelo nome; cria se não existir (tabela de apoio ``cargos``)."""
    cargo = db.scalar(select(Cargo).where(Cargo.cargo == nome))
    if cargo is not None:
        return cargo
    cargo = Cargo(cargo=nome)
    db.add(cargo)
    db.flush()
    return cargo


def _validar_cadastro(dados: dict) -> tuple[dict, dict]:
    """Valida o payload de cadastro e devolve ``(valores, erros)``."""
    erros: dict = {}

    empresa = dados.get("empresa")
    usuario = dados.get("usuario")
    if not isinstance(empresa, dict):
        erros["empresa"] = "Envie o objeto 'empresa' no corpo JSON."
        empresa = {}
    if not isinstance(usuario, dict):
        erros["usuario"] = "Envie o objeto 'usuario' no corpo JSON."
        usuario = {}

    razao_social = _validar_texto(
        "razao_social",
        empresa.get("razao_social"),
        erros,
        rotulo="Razão social",
        maximo=150,
        obrigatorio=True,
    )

    cnpj, erro_cnpj = _validar_cnpj(empresa.get("cnpj"))
    if erro_cnpj:
        erros["cnpj"] = erro_cnpj

    cep = _validar_cep("cep", empresa.get("cep"), erros)
    inscricao = _validar_texto(
        "inscricao",
        empresa.get("inscricao"),
        erros,
        rotulo="Inscrição estadual",
        maximo=30,
        obrigatorio=False,
    )
    telefone_empresa = _validar_telefone(
        "telefone_empresa",
        empresa.get("telefone_empresa"),
        erros,
        rotulo="Telefone da empresa",
    )

    nome = _validar_texto(
        "nome",
        usuario.get("nome"),
        erros,
        rotulo="Nome",
        maximo=150,
        obrigatorio=True,
    )

    email = _validar_texto(
        "email",
        usuario.get("email"),
        erros,
        rotulo="E-mail",
        maximo=254,
        obrigatorio=True,
    ).lower()
    if email and not EMAIL_REGEX.fullmatch(email):
        erros["email"] = "E-mail inválido."

    senha = usuario.get("senha")
    if not isinstance(senha, str) or len(senha) < TAMANHO_MINIMO_SENHA:
        erros["senha"] = (
            f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres."
        )
    elif len(senha) > TAMANHO_MAXIMO_SENHA:
        erros["senha"] = (
            f"A senha deve ter no máximo {TAMANHO_MAXIMO_SENHA} caracteres."
        )
    elif not senha.strip():
        erros["senha"] = "A senha não pode ser composta apenas de espaços."

    telefone = _validar_telefone(
        "telefone", usuario.get("telefone"), erros, rotulo="Telefone do usuário"
    )

    cargo = usuario.get("cargo")
    if cargo is None:
        cargo = CARGO_PADRAO
    elif not isinstance(cargo, str) or not cargo.strip():
        erros["cargo"] = "Cargo inválido."
        cargo = CARGO_PADRAO
    else:
        cargo = cargo.strip()
        if len(cargo) > 50:
            erros["cargo"] = "Cargo deve ter no máximo 50 caracteres."

    valores = {
        "razao_social": razao_social,
        "cnpj": cnpj,
        "cep": cep,
        "inscricao": inscricao or None,
        "telefone_empresa": telefone_empresa,
        "nome": nome,
        "email": email,
        "senha": senha,
        "telefone": telefone,
        "cargo": cargo,
    }
    return valores, erros


@bp.post("/cadastro")
def cadastro():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    valores, erros = _validar_cadastro(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.",
            422,
            campos=erros,
        )

    db = get_db()

    # Checagens amigáveis antes do INSERT (as UNIQUEs do banco continuam valendo).
    if db.scalar(select(Empresa).where(Empresa.cnpj == valores["cnpj"])) is not None:
        return resposta_erro(
            "Já existe uma empresa cadastrada com este CNPJ.",
            409,
            campos={"cnpj": "CNPJ já cadastrado."},
        )
    if db.scalar(select(Usuario).where(Usuario.email == valores["email"])) is not None:
        return resposta_erro(
            "Já existe um usuário cadastrado com este e-mail.",
            409,
            campos={"email": "E-mail já cadastrado."},
        )

    try:
        empresa = Empresa(
            razao_social=valores["razao_social"],
            cnpj=valores["cnpj"],
            cep=valores["cep"],
            inscricao=valores["inscricao"],
            telefone_empresa=valores["telefone_empresa"],
        )
        db.add(empresa)
        db.flush()  # gera o id_empresa (FK do usuário)
        db.refresh(empresa)  # traz o criado_em (DEFAULT CURRENT_TIMESTAMP)

        cargo = _obter_ou_criar_cargo(db, valores["cargo"])

        usuario = Usuario(
            id_empresa=empresa.id_empresa,
            id_cargo=cargo.id_cargo,
            nome=valores["nome"],
            email=valores["email"],
            telefone=valores["telefone"],
            hash_senha=generate_password_hash(valores["senha"]),
            admin_sistema=False,
        )
        db.add(usuario)
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não foi possível concluir o cadastro: CNPJ ou e-mail já cadastrado.",
            409,
        )

    dados_resposta = {
        "empresa": serializar_empresa(empresa),
        "usuario": serializar_usuario(usuario, incluir_empresa=False),
    }
    return resposta_ok(dados_resposta, "Cadastro realizado com sucesso.", 201)
