"""Testes do módulo LOG - Login e Cadastro de Usuário (plano de testes V1.2).

Cada teste referencia o ID do caso do plano (LOG-Pxx / LOG-Nxx). O plano
descreve uma interface web em etapas; adaptações necessárias estão anotadas no
próprio teste (a API cria usuário + empresa na mesma requisição e devolve JSON
em vez de redirecionar páginas).
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from src.app.db import get_engine
from tests.helpers import (
    CNPJ_VALIDO_2,
    cadastrar,
    cadastrar_ok,
    criar_conta,
    entrar,
    me,
    usuario_valido,
)

# E-mails de exatamente 254 e 255 caracteres, montados como no plano.
EMAIL_254 = "e" * 64 + "@" + "e" * 63 + "." + "e" * 63 + "." + "e" * 57 + ".com"
EMAIL_255 = "f" * 64 + "@" + "f" * 63 + "." + "f" * 63 + "." + "f" * 58 + ".com"


def _campos(resposta) -> dict:
    return resposta.get_json()["campos"]


# ---------------------------------------------------------------------------
# LOG - casos positivos
# ---------------------------------------------------------------------------


def test_log_p01_rota_inicial_expoe_login_e_cadastro(client):
    """LOG-P01: ponto de entrada informa as rotas de login/cadastro."""
    resposta = client.get("/")
    corpo = resposta.get_json()

    assert resposta.status_code == 200
    assert {"cadastro", "login", "logout", "me"} <= set(corpo["rotas"])


def test_log_p02_cadastro_usuario_com_campos_validos(client):
    """LOG-P02: cadastro com Nome, E-mail, Telefone e Senha válidos."""
    dados = cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome="Marina Albuquerque",
            email="marina.albuquerque@exemplo.com.br",
            telefone="81987654321",
            senha="Sen#Mar2026",
        ),
    )
    usuario = dados["usuario"]

    assert usuario["nome"] == "Marina Albuquerque"
    assert usuario["email"] == "marina.albuquerque@exemplo.com.br"
    assert usuario["telefone"] == "81987654321"
    assert usuario["cargo"] == "Administrador"
    assert usuario["admin_sistema"] is False
    # A empresa é criada junto (o schema exige usuarios.id_empresa NOT NULL).
    assert dados["empresa"]["razao_social"] == "Empresa Teste Ltda"


def test_log_p03_cadastro_usuario_sem_telefone(client):
    """LOG-P03: telefone é opcional."""
    dados = cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome="Ricardo Tavares",
            email="ricardo.tavares@exemplo.com.br",
            telefone=None,
            senha="Ric@Tav2026",
        ),
    )

    assert dados["usuario"]["telefone"] is None


def test_log_p04_cadastro_nome_com_150_caracteres(client):
    """LOG-P04: nome no limite exato de 150 caracteres."""
    nome = "A" * 150
    dados = cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome=nome, email="nome150@exemplo.com.br", senha="Nom#150Ok"
        ),
    )

    assert len(nome) == 150
    assert dados["usuario"]["nome"] == nome


def test_log_p05_cadastro_email_com_254_caracteres(client):
    """LOG-P05: e-mail no limite exato de 254 caracteres."""
    dados = cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome="Teste Email Limite", email=EMAIL_254, senha="Ema#254Ok"
        ),
    )

    assert len(EMAIL_254) == 254
    assert dados["usuario"]["email"] == EMAIL_254.lower()


def test_log_p06_cadastro_telefone_com_20_caracteres(client):
    """LOG-P06: telefone no limite exato de 20 caracteres (máscara preservada)."""
    telefone = "+55 (81) 9 8888-7777"
    dados = cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome="Carla Telefone Longo",
            email="carla.tel20@exemplo.com.br",
            telefone=telefone,
            senha="Tel#20Ok1",
        ),
    )

    assert len(telefone) == 20
    assert dados["usuario"]["telefone"] == telefone


def test_log_p07_dois_usuarios_com_mesmo_telefone(client):
    """LOG-P07: telefone não é único (dois usuários podem repetir)."""
    telefone = "81955550000"
    cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome="Ana Telefone Repetido",
            email="tel.repetido1@exemplo.com.br",
            telefone=telefone,
            senha="Rep#Tel2026",
        ),
    )
    dados = cadastrar_ok(
        client,
        empresa={"razao_social": "Empresa Teste Dois Ltda", "cnpj": CNPJ_VALIDO_2},
        usuario=usuario_valido(
            nome="Bruno Telefone Repetido",
            email="tel.repetido2@exemplo.com.br",
            telefone=telefone,
            senha="Rep#Tel2026",
        ),
    )

    assert dados["usuario"]["telefone"] == telefone


@pytest.mark.xfail(
    strict=True,
    reason=(
        "IMPOSSÍVEL: o schema define usuarios.id_empresa como NOT NULL; "
        "não existe usuário sem empresa para o LOG-P08 tentar logar."
    ),
)
def test_log_p08_login_usuario_sem_empresa(client, app):
    """LOG-P08: impossível no schema atual — o teste comprova o motivo."""
    with app.app_context():
        with get_engine().connect() as conexao:
            nullable = conexao.execute(
                text(
                    "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = 'crm_estoque' "
                    "AND TABLE_NAME = 'usuarios' "
                    "AND COLUMN_NAME = 'id_empresa'"
                )
            ).scalar()

    # Assert intencionalmente impossível de passar com o schema atual: por isso
    # o teste fica XFAIL. Se id_empresa virar NULL, ele passa a XPASS e, como
    # strict=True, a suíte falha avisando que o LOG-P08 precisa ser implementado.
    assert nullable == "YES", (
        "IMPOSSÍVEL: usuarios.id_empresa é NOT NULL; "
        "não existe login de usuário sem empresa (LOG-P08)."
    )


def test_log_p09_login_usuario_com_empresa(client):
    """LOG-P09: login de usuário já vinculado a uma empresa."""
    criar_conta(
        client,
        email="dono.login01@exemplo.com.br",
        senha="Dono#Login01",
        nome="Dono Login",
    )

    resposta = entrar(client, "dono.login01@exemplo.com.br", "Dono#Login01")
    corpo = resposta.get_json()

    assert resposta.status_code == 200
    assert corpo["dados"]["empresa"]["cnpj"] == "11222333000181"


def test_log_p10_login_email_em_maiusculas(client):
    """LOG-P10: comparação de e-mail não diferencia maiúsculas/minúsculas."""
    criar_conta(
        client,
        email="caso.login@exemplo.com.br",
        senha="Caso#Login2",
        nome="Caso Login",
    )

    resposta = entrar(client, "CASO.LOGIN@EXEMPLO.COM.BR", "Caso#Login2")

    assert resposta.status_code == 200


@pytest.mark.skip(
    reason="A Tela Principal é uma tela do front-end React; este caso é de "
    "UI/E2E e não é automatizado pela suíte pytest (que cobre a API)."
)
def test_log_p11_tela_principal_exibe_modulos(client):
    """LOG-P11: (caso de UI/E2E; não automatizado no pytest de API)."""


# ---------------------------------------------------------------------------
# LOG - casos negativos
# ---------------------------------------------------------------------------


def test_log_n01_login_email_vazio(client):
    """LOG-N01: login com e-mail vazio é recusado."""
    resposta = entrar(client, "", "Qualquer#01")

    assert resposta.status_code == 422
    assert "email" in _campos(resposta)
    assert me(client).status_code == 401


def test_log_n02_login_senha_vazia(client):
    """LOG-N02: login com senha vazia é recusado."""
    resposta = entrar(client, "login.semsenha@exemplo.com.br", "")

    assert resposta.status_code == 422
    assert "senha" in _campos(resposta)


def test_log_n03_login_email_e_senha_vazios(client):
    """LOG-N03: login com os dois campos vazios é recusado."""
    resposta = entrar(client, "", "")

    assert resposta.status_code == 422
    assert {"email", "senha"} <= set(_campos(resposta))


def test_log_n04_login_email_nao_cadastrado(client):
    """LOG-N04: e-mail inexistente gera credenciais inválidas."""
    resposta = entrar(client, "inexistente.xyz@exemplo.com.br", "Inex#2026")

    assert resposta.status_code == 401
    assert "incorretos" in resposta.get_json()["erro"].lower()


def test_log_n05_login_senha_incorreta(client):
    """LOG-N05: senha errada para e-mail cadastrado é recusada."""
    criar_conta(
        client,
        email="senha.errada@exemplo.com.br",
        senha="Correta#01",
        nome="Senha Errada",
    )

    resposta = entrar(client, "senha.errada@exemplo.com.br", "Errada#99")

    assert resposta.status_code == 401
    assert me(client).status_code == 401


def test_log_n06_login_senha_diferente_apenas_na_caixa(client):
    """LOG-N06: senha diferencia maiúsculas/minúsculas."""
    criar_conta(
        client,
        email="caixa.senha@exemplo.com.br",
        senha="SenhaCase#9",
        nome="Caixa Senha",
    )

    resposta = entrar(client, "caixa.senha@exemplo.com.br", "senhacase#9")

    assert resposta.status_code == 401


def test_log_n07_login_email_formato_invalido(client):
    """LOG-N07: e-mail sem '@' é recusado com mensagem de formato."""
    resposta = entrar(client, "usuario.semarroba.com", "Fmt#Inv01")

    assert resposta.status_code == 422
    assert "inválido" in _campos(resposta)["email"].lower()


def test_log_n08_login_email_com_apenas_espacos(client):
    """LOG-N08: e-mail com apenas espaços é tratado como obrigatório."""
    resposta = entrar(client, "   ", "Esp#Brc01")

    assert resposta.status_code == 422
    assert "email" in _campos(resposta)


def test_log_n09_login_sql_injection_no_email(client):
    """LOG-N09: tentativa de SQL injection no e-mail não autentica."""
    resposta = entrar(client, "' OR '1'='1' --", "x")

    assert resposta.status_code == 422
    assert me(client).status_code == 401


def test_log_n10_cadastro_email_duplicado(client):
    """LOG-N10: e-mail já cadastrado é recusado."""
    criar_conta(
        client,
        email="marina.albuquerque@exemplo.com.br",
        senha="Sen#Mar2026",
        nome="Marina Albuquerque",
    )

    resposta = cadastrar(
        client,
        empresa={"razao_social": "Outra Empresa Ltda", "cnpj": CNPJ_VALIDO_2},
        usuario=usuario_valido(
            nome="Marina Duplicada",
            email="marina.albuquerque@exemplo.com.br",
            senha="Dup#Mar2026",
        ),
    )

    assert resposta.status_code == 409
    assert "email" in _campos(resposta)


def test_log_n11_cadastro_email_duplicado_diferindo_na_caixa(client):
    """LOG-N11: unicidade do e-mail ignora maiúsculas/minúsculas."""
    criar_conta(
        client,
        email="ricardo.tavares@exemplo.com.br",
        senha="Ric@Tav2026",
        nome="Ricardo Tavares",
    )

    resposta = cadastrar(
        client,
        empresa={"razao_social": "Outra Empresa Ltda", "cnpj": CNPJ_VALIDO_2},
        usuario=usuario_valido(
            nome="Ricardo Caixa",
            email="RICARDO.TAVARES@EXEMPLO.COM.BR",
            senha="Cx#Ric2026",
        ),
    )

    assert resposta.status_code == 409
    assert "email" in _campos(resposta)


def test_log_n12_cadastro_email_usado_por_outra_empresa(client):
    """LOG-N12: e-mail é único globalmente, não só por empresa."""
    criar_conta(
        client,
        email="outra.empresa@exemplo.com.br",
        senha="Out#Emp2026",
        nome="Usuário Empresa Alfa",
    )

    resposta = cadastrar(
        client,
        empresa={"razao_social": "Empresa Beta Ltda", "cnpj": CNPJ_VALIDO_2},
        usuario=usuario_valido(
            nome="Usuário Outra Empresa",
            email="outra.empresa@exemplo.com.br",
            senha="Out#Emp2026",
        ),
    )

    assert resposta.status_code == 409


@pytest.mark.parametrize(
    ("case_id", "sobrescrita", "campos_esperados"),
    [
        ("LOG-N13", {"nome": ""}, {"nome"}),
        ("LOG-N14", {"email": ""}, {"email"}),
        ("LOG-N15", {"senha": ""}, {"senha"}),
        ("LOG-N16", {"email": "email@@exemplo..com"}, {"email"}),
        ("LOG-N17", {"email": EMAIL_255}, {"email"}),
        ("LOG-N18", {"nome": "B" * 151}, {"nome"}),
        (
            "LOG-N19",
            {"telefone": "+55 (81) 9 8888-77771"},
            {"telefone"},
        ),
    ],
    ids=[
        "LOG-N13",
        "LOG-N14",
        "LOG-N15",
        "LOG-N16",
        "LOG-N17",
        "LOG-N18",
        "LOG-N19",
    ],
)
def test_log_negativos_validacao_cadastro(
    client, case_id, sobrescrita, campos_esperados
):
    """LOG-N13..N19: validações de campos obrigatórios e limites do cadastro."""
    resposta = cadastrar(client, usuario=usuario_valido(**sobrescrita))
    corpo = resposta.get_json()

    assert resposta.status_code == 422, corpo
    assert campos_esperados <= set(corpo["campos"]), corpo["campos"]


def test_log_n20_acesso_direto_rota_protegida_sem_sessao(client):
    """LOG-N20: acesso direto sem sessão é bloqueado (adaptado p/ /api/auth/me)."""
    resposta = me(client)

    assert resposta.status_code == 401
    corpo = resposta.get_json()
    assert corpo["ok"] is False
    assert "dados" not in corpo


# ---------------------------------------------------------------------------
# Casos correlatos do plano que também envolvem autenticação
# ---------------------------------------------------------------------------


def test_col_n01_email_com_espacos_nas_extremidades(client, app):
    """COL-N01: e-mail é gravado sem espaços nas extremidades."""
    dados = cadastrar_ok(
        client,
        usuario=usuario_valido(
            nome="Espaco Borda",
            email="  espaco.borda@exemplo.com.br  ",
            senha="Esp#Bor2026",
        ),
    )
    assert dados["usuario"]["email"] == "espaco.borda@exemplo.com.br"

    with app.app_context():
        with get_engine().connect() as conexao:
            gravado = conexao.execute(
                text("SELECT email FROM usuarios WHERE id_usuario = :id"),
                {"id": dados["usuario"]["id_usuario"]},
            ).scalar()
    assert gravado == "espaco.borda@exemplo.com.br"


def test_seg_n11_rota_protegida_sem_autenticacao(client):
    """SEG-N11: rota protegida exige autenticação (401, sem dados)."""
    resposta = me(client)

    assert resposta.status_code == 401
    assert "dados" not in resposta.get_json()


def test_seg_n12_resposta_nao_expoe_hash_de_senha(client):
    """SEG-N12: respostas da API não expõem hash nem senha em texto puro."""
    senha = "Seg#N12Pass"
    resposta_cadastro = cadastrar(
        client,
        usuario=usuario_valido(
            nome="Seg N12", email="seg.n12@exemplo.com.br", senha=senha
        ),
    )
    assert resposta_cadastro.status_code == 201

    resposta_login = entrar(client, "seg.n12@exemplo.com.br", senha)
    assert resposta_login.status_code == 200

    for resposta in (resposta_cadastro, resposta_login, me(client)):
        corpo = json.dumps(resposta.get_json(), ensure_ascii=False)
        assert "hash_senha" not in corpo
        assert senha not in corpo
