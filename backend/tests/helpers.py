"""Funções de apoio compartilhadas pelos testes de autenticação."""

from __future__ import annotations

from typing import Any

CNPJ_VALIDO = "11222333000181"
CNPJ_VALIDO_2 = "22333444000181"
EMAIL_PADRAO = "usuario.teste@exemplo.com.br"
SENHA_PADRAO = "Senha#Teste1"

# Registro dos dados criados pela API durante a execução dos testes. O fixture
# `banco_limpo` usa esses conjuntos para apagar exatamente o que foi criado,
# inclusive e-mails que não seguem o padrão @exemplo.com.br (ex.: LOG-P05).
EMAILS_CRIADOS: set[str] = set()
CNPJS_CRIADOS: set[str] = set()


def empresa_valida(**sobrescritas: Any) -> dict:
    """Payload de empresa com valores válidos, permitindo sobrescrever campos."""
    dados = {
        "razao_social": "Empresa Teste Ltda",
        "cnpj": CNPJ_VALIDO,
        "cep": None,
        "inscricao": None,
        "telefone_empresa": None,
    }
    dados.update(sobrescritas)
    return dados


def usuario_valido(**sobrescritas: Any) -> dict:
    """Payload de usuário com valores válidos, permitindo sobrescrever campos."""
    dados = {
        "nome": "Usuário Teste",
        "email": EMAIL_PADRAO,
        "senha": SENHA_PADRAO,
        "telefone": None,
        "cargo": None,
    }
    dados.update(sobrescritas)
    return dados


def cadastrar(client, *, empresa=None, usuario=None):
    """Envia um POST /api/auth/cadastro com os payloads informados."""
    corpo = {
        "empresa": empresa if empresa is not None else empresa_valida(),
        "usuario": usuario if usuario is not None else usuario_valido(),
    }
    resposta = client.post("/api/auth/cadastro", json=corpo)

    # Guarda o que foi criado para a limpeza automática dos testes.
    if resposta.status_code == 201:
        dados = resposta.get_json()["dados"]
        EMAILS_CRIADOS.add(dados["usuario"]["email"].lower())
        CNPJS_CRIADOS.add(dados["empresa"]["cnpj"])

    return resposta


def cadastrar_ok(client, *, empresa=None, usuario=None) -> dict:
    """Como ``cadastrar``, mas exige 201 e devolve a chave ``dados`` da resposta."""
    resposta = cadastrar(client, empresa=empresa, usuario=usuario)
    corpo = resposta.get_json()
    assert resposta.status_code == 201, corpo
    return corpo["dados"]


def criar_conta(
    client,
    email: str = EMAIL_PADRAO,
    senha: str = SENHA_PADRAO,
    *,
    nome: str = "Usuário Teste",
    cnpj: str = CNPJ_VALIDO,
    usuario_extra: dict | None = None,
) -> dict:
    """Cria uma conta completa (empresa + usuário) e devolve os dados criados."""
    usuario = usuario_valido(nome=nome, email=email, senha=senha)
    if usuario_extra:
        usuario.update(usuario_extra)
    return cadastrar_ok(client, empresa=empresa_valida(cnpj=cnpj), usuario=usuario)


def entrar(client, email: str, senha: str):
    """Envia um POST /api/auth/login."""
    return client.post("/api/auth/login", json={"email": email, "senha": senha})


def me(client):
    """Chama a rota protegida GET /api/auth/me."""
    return client.get("/api/auth/me")
