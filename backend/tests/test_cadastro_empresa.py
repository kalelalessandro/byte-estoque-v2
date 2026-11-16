"""Testes do módulo EMP - Cadastro de Empresa (plano de testes V1.2).

Na API atual o cadastro de empresa e do primeiro usuário é uma única operação
(``POST /api/auth/cadastro``), pois ``usuarios.id_empresa`` é NOT NULL. Cada
teste referencia o ID do caso do plano (EMP-Pxx / EMP-Nxx).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from src.app.db import get_engine
from tests.helpers import (
    CNPJ_VALIDO_2,
    cadastrar,
    cadastrar_ok,
    criar_conta,
    empresa_valida,
    entrar,
    usuario_valido,
)


# ---------------------------------------------------------------------------
# EMP - casos positivos
# ---------------------------------------------------------------------------


def test_emp_p01_cadastro_completo_cnpj_numerico(client):
    """EMP-P01: empresa com todos os campos e CNPJ numérico."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Distribuidora Recife Norte Ltda",
            cnpj="11222333000181",
            cep="50030230",
            inscricao="IE-0012345-67",
            telefone_empresa="8132214455",
        ),
        usuario=usuario_valido(
            nome="Dono P01", email="emp.p01@exemplo.com.br", senha="Emp#P012026"
        ),
    )
    empresa = dados["empresa"]
    usuario = dados["usuario"]

    assert empresa["razao_social"] == "Distribuidora Recife Norte Ltda"
    assert empresa["cnpj"] == "11222333000181"
    assert empresa["cep"] == "50030230"
    assert empresa["inscricao"] == "IE-0012345-67"
    assert empresa["telefone_empresa"] == "8132214455"
    assert usuario["id_empresa"] == empresa["id_empresa"]
    assert usuario["cargo"] == "Administrador"


def test_emp_p02_cadastro_apenas_campos_obrigatorios(client):
    """EMP-P02: apenas razão social e CNPJ; opcionais ficam nulos."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Comercial Boa Viagem Ltda",
            cnpj="22333444000181",
            cep=None,
            inscricao=None,
            telefone_empresa=None,
        ),
        usuario=usuario_valido(
            nome="Dono P02", email="emp.p02@exemplo.com.br", senha="Emp#P022026"
        ),
    )
    empresa = dados["empresa"]

    assert empresa["cep"] is None
    assert empresa["inscricao"] is None
    assert empresa["telefone_empresa"] is None


def test_emp_p03_cadastro_cnpj_alfanumerico(client):
    """EMP-P03: CNPJ alfanumérico válido (12 alfanuméricos + 2 DVs)."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Tech Alfa Soluções Ltda", cnpj="7K3M9Q2W0X1Z60"
        ),
        usuario=usuario_valido(
            nome="Dono P03", email="emp.p03@exemplo.com.br", senha="Emp#P032026"
        ),
    )
    assert dados["empresa"]["cnpj"] == "7K3M9Q2W0X1Z60"


def test_emp_p04_cadastro_cnpj_alfanumerico_intercalado(client):
    """EMP-P04: outro CNPJ alfanumérico válido (letras e números intercalados)."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Beta Logística Ltda", cnpj="A1B2C3D4E5F668"
        ),
        usuario=usuario_valido(
            nome="Dono P04", email="emp.p04@exemplo.com.br", senha="Emp#P042026"
        ),
    )
    assert dados["empresa"]["cnpj"] == "A1B2C3D4E5F668"


def test_emp_p05_cadastro_cnpj_alfanumerico_minusculo(client):
    """EMP-P05: CNPJ minúsculo é normalizado para maiúsculas."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Gama Atacado Ltda", cnpj="zz99yy88xx7793"
        ),
        usuario=usuario_valido(
            nome="Dono P05", email="emp.p05@exemplo.com.br", senha="Emp#P052026"
        ),
    )
    assert dados["empresa"]["cnpj"] == "ZZ99YY88XX7793"


def test_emp_p06_cadastro_cnpj_numerico_com_mascara(client):
    """EMP-P06: CNPJ numérico com máscara é salvo sem pontuação."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Delta Máscara Numérica Ltda",
            cnpj="33.444.555/0001-81",
        ),
        usuario=usuario_valido(
            nome="Dono P06", email="emp.p06@exemplo.com.br", senha="Emp#P062026"
        ),
    )
    assert dados["empresa"]["cnpj"] == "33444555000181"


def test_emp_p07_cadastro_cnpj_alfanumerico_com_mascara(client):
    """EMP-P07: CNPJ alfanumérico com máscara é salvo sem pontuação."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Épsilon Máscara Alfa Ltda",
            cnpj="B7.C8D.9E0/F1G2-46",
        ),
        usuario=usuario_valido(
            nome="Dono P07", email="emp.p07@exemplo.com.br", senha="Emp#P072026"
        ),
    )
    assert dados["empresa"]["cnpj"] == "B7C8D9E0F1G246"


def test_emp_p08_cadastro_razao_social_150_caracteres(client):
    """EMP-P08: razão social no limite exato de 150 caracteres."""
    razao_social = "R" * 150
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social=razao_social, cnpj="44555666000181"
        ),
        usuario=usuario_valido(
            nome="Dono P08", email="emp.p08@exemplo.com.br", senha="Emp#P082026"
        ),
    )
    assert dados["empresa"]["razao_social"] == razao_social


def test_emp_p09_cadastro_cep_com_mascara(client):
    """EMP-P09: CEP com máscara é salvo como 8 dígitos."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="CEP Mascarado Ltda",
            cnpj="77888999000181",
            cep="52.060-110",
        ),
        usuario=usuario_valido(
            nome="Dono P09", email="emp.p09@exemplo.com.br", senha="Emp#P092026"
        ),
    )
    assert dados["empresa"]["cep"] == "52060110"


def test_emp_p10_cadastro_cep_com_zero_a_esquerda(client):
    """EMP-P10: CEP iniciado por zero preserva o zero à esquerda."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Paulista Zero CEP Ltda",
            cnpj="88999000000198",
            cep="01001000",
        ),
        usuario=usuario_valido(
            nome="Dono P10", email="emp.p10@exemplo.com.br", senha="Emp#P102026"
        ),
    )
    assert dados["empresa"]["cep"] == "01001000"


def test_emp_p11_cadastro_cnpj_com_zeros_a_esquerda(client):
    """EMP-P11: CNPJ iniciado por zeros preserva os 14 caracteres."""
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social="Zeros Iniciais Ltda", cnpj="00000001000136"
        ),
        usuario=usuario_valido(
            nome="Dono P11", email="emp.p11@exemplo.com.br", senha="Emp#P112026"
        ),
    )
    assert dados["empresa"]["cnpj"] == "00000001000136"


def test_emp_p12_razao_social_repetida_com_cnpj_diferente(client):
    """EMP-P12: razão social não é única; o CNPJ é que precisa ser diferente."""
    razao_social = "Mercantil Sol Nascente Ltda"
    primeira = cadastrar_ok(
        client,
        empresa=empresa_valida(razao_social=razao_social, cnpj="10111222000135"),
        usuario=usuario_valido(
            nome="Dono P12A", email="emp.p12a@exemplo.com.br", senha="Emp#P12A2026"
        ),
    )
    segunda = cadastrar_ok(
        client,
        empresa=empresa_valida(razao_social=razao_social, cnpj="12121333000158"),
        usuario=usuario_valido(
            nome="Dono P12B", email="emp.p12b@exemplo.com.br", senha="Emp#P12B2026"
        ),
    )

    assert primeira["empresa"]["id_empresa"] != segunda["empresa"]["id_empresa"]
    assert primeira["empresa"]["razao_social"] == segunda["empresa"]["razao_social"]


def test_emp_p13_novo_login_apos_cadastro(client):
    """EMP-P13: após cadastrar a empresa, novo login já encontra a empresa."""
    criar_conta(
        client,
        email="retorno.direto@exemplo.com.br",
        senha="Retorno#2026",
        nome="Retorno Direto",
        cnpj="14141555000168",
    )

    resposta = entrar(client, "retorno.direto@exemplo.com.br", "Retorno#2026")
    corpo = resposta.get_json()

    assert resposta.status_code == 200
    assert corpo["dados"]["empresa"]["cnpj"] == "14141555000168"


# ---------------------------------------------------------------------------
# EMP - casos negativos
# ---------------------------------------------------------------------------

TELEFONE_EMPRESA_21 = "+55 (81) 3 3221-44551"

CASOS_EMP_NEGATIVOS_VALIDACAO = [
    ("EMP-N01", {"razao_social": ""}, {"razao_social"}),
    ("EMP-N02", {"cnpj": ""}, {"cnpj"}),
    ("EMP-N03", {"razao_social": "", "cnpj": ""}, {"razao_social", "cnpj"}),
    ("EMP-N04", {"cnpj": "1616177700017"}, {"cnpj"}),
    ("EMP-N05", {"cnpj": "171718880001280"}, {"cnpj"}),
    ("EMP-N06", {"cnpj": "18181999000189"}, {"cnpj"}),
    ("EMP-N07", {"cnpj": "C1D2E3F4G5H681"}, {"cnpj"}),
    ("EMP-N08", {"cnpj": "1919200000016@"}, {"cnpj"}),
    ("EMP-N09", {"cnpj": "D4E5F6G7H8J9AB"}, {"cnpj"}),
    ("EMP-N13", {"cnpj": "00000000000000"}, {"cnpj"}),
    ("EMP-N14", {"cnpj": "11111111111111"}, {"cnpj"}),
    ("EMP-N15", {"razao_social": "S" * 151}, {"razao_social"}),
    ("EMP-N16", {"cep": "5003023"}, {"cep"}),
    ("EMP-N17", {"cep": "500302301"}, {"cep"}),
    ("EMP-N18", {"cep": "5003AB30"}, {"cep"}),
    ("EMP-N19", {"inscricao": "8" * 31}, {"inscricao"}),
    ("EMP-N20", {"telefone_empresa": TELEFONE_EMPRESA_21}, {"telefone_empresa"}),
    ("EMP-N21", {"razao_social": "     "}, {"razao_social"}),
    ("EMP-N22", {"cnpj": " " * 14}, {"cnpj"}),
]


@pytest.mark.parametrize(
    ("case_id", "sobrescrita", "campos_esperados"),
    CASOS_EMP_NEGATIVOS_VALIDACAO,
    ids=[caso[0] for caso in CASOS_EMP_NEGATIVOS_VALIDACAO],
)
def test_emp_negativos_validacao(client, case_id, sobrescrita, campos_esperados):
    """EMP-N01..N22: validações de campos e limites do cadastro de empresa."""
    resposta = cadastrar(client, empresa=empresa_valida(**sobrescrita))
    corpo = resposta.get_json()

    assert resposta.status_code == 422, corpo
    assert campos_esperados <= set(corpo["campos"]), corpo["campos"]


def test_emp_n10_cnpj_duplicado_exato(client):
    """EMP-N10: CNPJ duplicado exato é recusado."""
    criar_conta(
        client,
        email="emp.n10a@exemplo.com.br",
        senha="Emp#N10A2026",
        nome="Dono N10A",
        cnpj="11222333000181",
    )

    resposta = cadastrar(
        client,
        empresa=empresa_valida(
            razao_social="Duplicata Exata Ltda", cnpj="11222333000181"
        ),
        usuario=usuario_valido(
            nome="Dono N10B", email="emp.n10b@exemplo.com.br", senha="Emp#N10B2026"
        ),
    )

    assert resposta.status_code == 409
    assert "cnpj" in resposta.get_json()["campos"]


def test_emp_n11_cnpj_alfanumerico_duplicado_em_minusculas(client):
    """EMP-N11: CNPJ alfanumérico duplicado digitado em minúsculas é recusado."""
    criar_conta(
        client,
        email="emp.n11a@exemplo.com.br",
        senha="Emp#N11A2026",
        nome="Dono N11A",
        cnpj="7K3M9Q2W0X1Z60",
    )

    resposta = cadastrar(
        client,
        empresa=empresa_valida(
            razao_social="Duplicata Minuscula Ltda", cnpj="7k3m9q2w0x1z60"
        ),
        usuario=usuario_valido(
            nome="Dono N11B", email="emp.n11b@exemplo.com.br", senha="Emp#N11B2026"
        ),
    )

    assert resposta.status_code == 409
    assert "cnpj" in resposta.get_json()["campos"]


def test_emp_n12_cnpj_duplicado_digitado_com_mascara(client):
    """EMP-N12: CNPJ duplicado digitado com máscara é recusado."""
    criar_conta(
        client,
        email="emp.n12a@exemplo.com.br",
        senha="Emp#N12A2026",
        nome="Dono N12A",
        cnpj="22333444000181",
    )

    resposta = cadastrar(
        client,
        empresa=empresa_valida(
            razao_social="Duplicata Mascara Ltda", cnpj="22.333.444/0001-81"
        ),
        usuario=usuario_valido(
            nome="Dono N12B", email="emp.n12b@exemplo.com.br", senha="Emp#N12B2026"
        ),
    )

    assert resposta.status_code == 409
    assert "cnpj" in resposta.get_json()["campos"]


@pytest.mark.skip(
    reason="Caso de UI/E2E do front-end React (Tela Principal) e de um usuário "
    "sem empresa, estado impossível pelo schema (usuarios.id_empresa NOT NULL). "
    "A suíte pytest cobre apenas a API."
)
def test_emp_n23_usuario_sem_empresa_acessa_tela_principal(client):
    """EMP-N23: (caso de UI/E2E; não automatizado no pytest de API)."""


@pytest.mark.skip(
    reason="Caso de UI/E2E (bloqueio da página 'Cadastrar empresa'); o pytest "
    "cobre a API, onde /api/auth/cadastro é público e cria empresa + usuário."
)
def test_emp_n24_usuario_com_empresa_acessa_cadastrar_empresa(client):
    """EMP-N24: (caso de UI/E2E; não automatizado no pytest de API)."""


def test_emp_n25_sql_injection_na_razao_social(client, app):
    """EMP-N25: SQL injection na razão social é tratado como texto literal."""
    razao_social = "'); DROP TABLE empresas;--"
    dados = cadastrar_ok(
        client,
        empresa=empresa_valida(
            razao_social=razao_social, cnpj="27272888000178"
        ),
        usuario=usuario_valido(
            nome="Dono N25", email="emp.n25@exemplo.com.br", senha="Emp#N252026"
        ),
    )
    assert dados["empresa"]["razao_social"] == razao_social

    # A tabela continua existindo e íntegra.
    with app.app_context():
        with get_engine().connect() as conexao:
            total = conexao.execute(text("SELECT COUNT(*) FROM empresas")).scalar()
            gravada = conexao.execute(
                text("SELECT razao_social FROM empresas WHERE cnpj = :cnpj"),
                {"cnpj": "27272888000178"},
            ).scalar()
    assert total >= 1
    assert gravada == razao_social
