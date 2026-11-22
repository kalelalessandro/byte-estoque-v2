"""Testes do módulo PAR - Parceiros (plano de testes V1.3), pela API.

Cada teste referencia o ID do caso do plano (PAR-Pxx / PAR-Nxx). O plano descreve a
interface web ("Inserir Parceiro Novo", "Alterar Parceiro"...); aqui os mesmos
cenários são exercitados nas rotas ``/api/parceiros``. Os casos extras (isolamento
entre empresas, busca, filtros) seguem as regras da Documentação do Banco v1.2.
"""

from __future__ import annotations

import pytest

from tests.apoio_parceiros import (
    EMAIL_B,
    apagar_dados_de_parceiros,
    campos,
    criar_parceiro,
    inserir_operacao,
    inserir_titulo,
    logar,
    obter_parceiro,
    parceiro_valido,
)
from tests.helpers import CNPJ_VALIDO_2


@pytest.fixture(autouse=True)
def limpar_parceiros(app, banco_limpo):
    """Apaga os dados de parceiros ANTES de o banco_limpo remover usuários/empresas."""
    yield
    apagar_dados_de_parceiros(app)


def _outra_empresa(app):
    """Segundo cliente HTTP logado em OUTRA empresa."""
    outro = app.test_client()
    conta = logar(outro, EMAIL_B, CNPJ_VALIDO_2)
    return outro, conta


# ---------------------------------------------------------------------------
# PAR - casos positivos
# ---------------------------------------------------------------------------


def test_par_p01_inserir_cliente_com_todos_os_campos_cpf(client):
    """PAR-P01: cliente com CPF, e-mail, CEP e observação."""
    logar(client)

    resposta = client.post(
        "/api/parceiros",
        json={
            "nome": "Ana Clara Ferreira",
            "documento": "52998224725",
            "email": "ana.ferreira@cliente.com.br",
            "cep": "50050010",
            "e_cliente": True,
            "e_fornecedor": False,
            "observacao": "Cliente desde 2026",
        },
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 201
    assert dados["tipo"] == "cliente"
    assert dados["documento"] == "52998224725"
    assert dados["cep"] == "50050010"
    assert dados["observacao"] == "Cliente desde 2026"


def test_par_p02_inserir_fornecedor_com_cnpj_numerico(client):
    """PAR-P02: fornecedor com CNPJ numérico."""
    logar(client)

    dados = criar_parceiro(
        client,
        nome="Metalúrgica Capibaribe Ltda",
        documento="30313222000125",
        email="contato@metcapibaribe.com.br",
        e_cliente=False,
        e_fornecedor=True,
    )

    assert dados["tipo"] == "fornecedor"
    assert dados["documento"] == "30313222000125"


def test_par_p03_inserir_fornecedor_com_cnpj_alfanumerico(client):
    """PAR-P03: o documento alfanumérico é preservado (14 caracteres)."""
    logar(client)

    dados = criar_parceiro(
        client,
        nome="Insumos Alfanum Ltda",
        documento="P1Q2R3S4T5U600",
        email="vendas@insumosalfa.com.br",
        e_cliente=False,
        e_fornecedor=True,
    )

    assert dados["documento"] == "P1Q2R3S4T5U600"
    assert len(dados["documento"]) == 14


def test_par_p04_inserir_cliente_e_fornecedor_ao_mesmo_tempo(client):
    """PAR-P04: os dois relacionamentos marcados."""
    logar(client)

    dados = criar_parceiro(
        client,
        nome="Distribuidora Dupla Função",
        email="dupla@distribuidora.com.br",
        e_cliente=True,
        e_fornecedor=True,
    )

    assert dados["e_cliente"] is True
    assert dados["e_fornecedor"] is True
    assert dados["tipo"] == "ambos"


def test_par_p05_inserir_somente_nome_e_relacionamento(client):
    """PAR-P05: documento, e-mail, CEP e observação ficam NULL."""
    logar(client)

    dados = criar_parceiro(client, nome="Cliente Minimalista")

    assert dados["documento"] is None
    assert dados["email"] is None
    assert dados["cep"] is None
    assert dados["observacao"] is None


def test_par_p06_dois_parceiros_sem_email_coexistem(client):
    """PAR-P06: ausência de e-mail (NULL) não conflita na UNIQUE."""
    logar(client)
    criar_parceiro(client, nome="Sem Email Um")

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Sem Email Dois", email="")
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["email"] is None


def test_par_p07_email_usado_por_parceiro_de_outra_empresa(app, client):
    """PAR-P07: a unicidade do e-mail é por empresa."""
    logar(client)
    outro, _ = _outra_empresa(app)
    criar_parceiro(outro, nome="Outro", email="comum.parceiro@cliente.com.br")

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Parceiro Email Comum", email="comum.parceiro@cliente.com.br"),
    )

    assert resposta.status_code == 201


def test_par_p08_documento_usado_por_parceiro_de_outra_empresa(app, client):
    """PAR-P08: a unicidade do documento é por empresa."""
    logar(client)
    outro, _ = _outra_empresa(app)
    criar_parceiro(outro, nome="Outro", documento="11144477735")

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Parceiro Documento Comum", documento="11144477735"),
    )

    assert resposta.status_code == 201


def test_par_p09_nome_com_exatamente_150_caracteres(client):
    """PAR-P09."""
    logar(client)

    dados = criar_parceiro(client, nome="P" * 150)

    assert len(dados["nome"]) == 150


def test_par_p10_observacao_longa_de_5000_caracteres(client):
    """PAR-P10: observação armazenada integralmente."""
    logar(client)

    dados = criar_parceiro(client, nome="Parceiro Observacao Longa", observacao="o" * 5000)

    assert len(obter_parceiro(client, dados["id_parceiro"])["observacao"]) == 5000


def test_par_p11_listar_parceiros_da_empresa(client):
    """PAR-P11: a lista traz nome, documento, e-mail e tipo de relacionamento."""
    logar(client)
    criar_parceiro(
        client,
        nome="Parceiro Listado Alfa",
        documento="52998224725",
        email="alfa@cliente.com.br",
    )

    resposta = client.get("/api/parceiros")
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["total"] == 1
    item = dados["parceiros"][0]
    assert item["nome"] == "Parceiro Listado Alfa"
    assert item["documento"] == "52998224725"
    assert item["email"] == "alfa@cliente.com.br"
    assert item["tipo"] == "cliente"


def test_par_p12_acessar_parceiro_exibe_dados_completos_e_interacoes(client):
    """PAR-P12: o detalhe inclui os dados e o histórico de interações."""
    logar(client)
    parceiro = criar_parceiro(
        client, nome="Parceiro Acesso Beta", email="acesso.beta@cliente.com.br"
    )
    client.post(
        f"/api/parceiros/{parceiro['id_parceiro']}/interacoes",
        json={"ocorrencia": "2026-11-03", "canal": "telefone", "descricao": "Primeiro contato"},
    )

    dados = obter_parceiro(client, parceiro["id_parceiro"])

    assert dados["nome"] == "Parceiro Acesso Beta"
    assert dados["email"] == "acesso.beta@cliente.com.br"
    assert len(dados["interacoes"]) == 1


def test_par_p13_alterar_cliente_para_tambem_fornecedor(client):
    """PAR-P13."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Somente Cliente Gama")

    resposta = client.patch(
        f"/api/parceiros/{parceiro['id_parceiro']}", json={"e_fornecedor": True}
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["e_cliente"] is True
    assert dados["e_fornecedor"] is True
    assert dados["tipo"] == "ambos"


def test_par_p14_apagar_parceiro_sem_registro_vinculado(client):
    """PAR-P14: o parceiro some da lista."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Parceiro Apagar Delta")

    resposta = client.delete(f"/api/parceiros/{parceiro['id_parceiro']}")

    assert resposta.status_code == 200
    assert client.get(f"/api/parceiros/{parceiro['id_parceiro']}").status_code == 404
    assert client.get("/api/parceiros").get_json()["dados"]["total"] == 0


# ---------------------------------------------------------------------------
# PAR - casos negativos
# ---------------------------------------------------------------------------


def test_par_n01_inserir_com_nome_vazio(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="", email="nome.vazio@cliente.com.br")
    )

    assert resposta.status_code == 422
    assert "nome" in campos(resposta)


def test_par_n02_inserir_sem_cliente_nem_fornecedor(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros",
        json={"nome": "Sem Relacionamento", "e_cliente": False, "e_fornecedor": False},
    )

    assert resposta.status_code == 422
    assert "relacionamento" in campos(resposta)


def test_par_n02b_inserir_sem_informar_relacionamento(client):
    """Extra: omitir os dois campos equivale a falso/falso."""
    logar(client)

    resposta = client.post("/api/parceiros", json={"nome": "Sem Campos"})

    assert resposta.status_code == 422
    assert "relacionamento" in campos(resposta)


def test_par_n03_email_ja_usado_na_mesma_empresa(client):
    logar(client)
    criar_parceiro(client, nome="Ana Clara Ferreira", email="ana.ferreira@cliente.com.br")

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Ana Duplicada", email="ana.ferreira@cliente.com.br"),
    )

    assert resposta.status_code == 409
    assert "email" in campos(resposta)


def test_par_n04_email_duplicado_diferindo_apenas_na_caixa(client):
    logar(client)
    criar_parceiro(client, nome="Metal", email="contato@metcapibaribe.com.br")

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Metal Caixa", email="CONTATO@METCAPIBARIBE.COM.BR"),
    )

    assert resposta.status_code == 409
    assert "email" in campos(resposta)


def test_par_n05_documento_ja_usado_na_mesma_empresa(client):
    logar(client)
    criar_parceiro(client, nome="Ana", documento="52998224725")

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Documento Duplicado", documento="52998224725"),
    )

    assert resposta.status_code == 409
    assert "documento" in campos(resposta)


def test_par_n06_documento_alfanumerico_duplicado_em_minusculas(client):
    logar(client)
    criar_parceiro(client, nome="Insumos", documento="P1Q2R3S4T5U600")

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Documento Alfa Duplicado", documento="p1q2r3s4t5u600"),
    )

    assert resposta.status_code == 409
    assert "documento" in campos(resposta)


def test_par_n07_documento_apenas_espacos(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Documento Em Branco", documento="   ")
    )

    assert resposta.status_code == 422
    assert "documento" in campos(resposta)


def test_par_n08_email_apenas_espacos(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Email Em Branco", email="   ")
    )

    assert resposta.status_code == 422
    assert "email" in campos(resposta)


def test_par_n09_nome_com_151_caracteres(client):
    logar(client)

    resposta = client.post("/api/parceiros", json=parceiro_valido(nome="Q" * 151))

    assert resposta.status_code == 422
    assert "nome" in campos(resposta)


def test_par_n10_documento_com_15_caracteres(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Documento Longo", documento="123456789012345"),
    )

    assert resposta.status_code == 422
    assert "no máximo 14" in campos(resposta)["documento"]


def test_par_n11_email_com_255_caracteres(client):
    logar(client)
    email_255 = "h" * 64 + "@" + "h" * 63 + "." + "h" * 63 + "." + "h" * 58 + ".com"
    assert len(email_255) == 255

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Email Longo Parceiro", email=email_255)
    )

    assert resposta.status_code == 422
    assert "no máximo 254" in campos(resposta)["email"]


def test_par_n12_email_em_formato_invalido(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros",
        json=parceiro_valido(nome="Email Invalido Parceiro", email="parceiro.sem.arroba.com"),
    )

    assert resposta.status_code == 422
    assert "email" in campos(resposta)


def test_par_n13_cep_com_9_digitos(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Cep Longo Parceiro", cep="500500101")
    )

    assert resposta.status_code == 422
    assert "cep" in campos(resposta)


def test_par_n14_cep_com_letras(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Cep Letras Parceiro", cep="5005AB10")
    )

    assert resposta.status_code == 422
    assert "cep" in campos(resposta)


def test_par_n15_alterar_email_para_o_de_outro_parceiro_da_empresa(client):
    logar(client)
    criar_parceiro(client, nome="Troca Email B", email="troca.b@cliente.com.br")
    a = criar_parceiro(client, nome="Troca Email A", email="troca.a@cliente.com.br")

    resposta = client.patch(
        f"/api/parceiros/{a['id_parceiro']}", json={"email": "troca.b@cliente.com.br"}
    )

    assert resposta.status_code == 409
    assert "email" in campos(resposta)
    assert obter_parceiro(client, a["id_parceiro"])["email"] == "troca.a@cliente.com.br"


def test_par_n16_alterar_documento_para_o_de_outro_parceiro_da_empresa(client):
    logar(client)
    criar_parceiro(client, nome="Troca Doc B", documento="98765432100")
    a = criar_parceiro(client, nome="Troca Doc A", documento="12345678909")

    resposta = client.patch(
        f"/api/parceiros/{a['id_parceiro']}", json={"documento": "98765432100"}
    )

    assert resposta.status_code == 409
    assert "documento" in campos(resposta)


def test_par_n17_alterar_desmarcando_cliente_e_fornecedor(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Remove Relacao")

    resposta = client.patch(
        f"/api/parceiros/{parceiro['id_parceiro']}",
        json={"e_cliente": False, "e_fornecedor": False},
    )

    assert resposta.status_code == 422
    assert "relacionamento" in campos(resposta)


def test_par_n17b_desmarcar_so_o_unico_relacionamento_marcado(client):
    """Extra: o estado atual entra na conta (cliente-only + e_cliente=false)."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Remove Relacao Dois")

    resposta = client.patch(
        f"/api/parceiros/{parceiro['id_parceiro']}", json={"e_cliente": False}
    )

    assert resposta.status_code == 422
    assert obter_parceiro(client, parceiro["id_parceiro"])["e_cliente"] is True


def test_par_n18_alterar_deixando_o_nome_vazio(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Nome Vazio Alterar")

    resposta = client.patch(f"/api/parceiros/{parceiro['id_parceiro']}", json={"nome": ""})

    assert resposta.status_code == 422
    assert "nome" in campos(resposta)
    assert obter_parceiro(client, parceiro["id_parceiro"])["nome"] == "Nome Vazio Alterar"


def test_par_n19_apagar_parceiro_com_interacoes(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Apagar Com Interacao")
    client.post(
        f"/api/parceiros/{parceiro['id_parceiro']}/interacoes",
        json={"ocorrencia": "2026-11-03", "canal": "telefone", "descricao": "Contato"},
    )

    resposta = client.delete(f"/api/parceiros/{parceiro['id_parceiro']}")

    assert resposta.status_code == 409
    assert "interações" in resposta.get_json()["vinculos"]
    assert client.get(f"/api/parceiros/{parceiro['id_parceiro']}").status_code == 200


def test_par_n20_apagar_parceiro_com_operacao_vinculada(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Apagar Com Operacao")
    inserir_operacao(app, parceiro["id_parceiro"], conta["id_usuario"])

    resposta = client.delete(f"/api/parceiros/{parceiro['id_parceiro']}")

    assert resposta.status_code == 409
    assert "operações" in resposta.get_json()["vinculos"]
    assert client.get(f"/api/parceiros/{parceiro['id_parceiro']}").status_code == 200


def test_par_n21_apagar_parceiro_com_titulo_financeiro(app, client):
    conta = logar(client)
    parceiro = criar_parceiro(client, nome="Apagar Com Titulo")
    inserir_titulo(app, parceiro["id_parceiro"], conta["id_empresa"])

    resposta = client.delete(f"/api/parceiros/{parceiro['id_parceiro']}")

    assert resposta.status_code == 409
    assert "títulos financeiros" in resposta.get_json()["vinculos"]
    assert client.get(f"/api/parceiros/{parceiro['id_parceiro']}").status_code == 200


# ---------------------------------------------------------------------------
# Extras: normalização, busca/filtros, isolamento entre empresas e segurança
# ---------------------------------------------------------------------------


def test_normaliza_documento_e_cep_com_mascara_e_email_minusculo(client):
    logar(client)

    dados = criar_parceiro(
        client,
        nome="  Mascara  ",
        documento="529.982.247-25",
        cep="50050-010",
        email="  ANA@Cliente.com.BR ",
    )

    assert dados["nome"] == "Mascara"
    assert dados["documento"] == "52998224725"
    assert dados["cep"] == "50050010"
    assert dados["email"] == "ana@cliente.com.br"


def test_cnpj_com_mascara_e_em_minusculas_e_normalizado(client):
    logar(client)

    dados = criar_parceiro(client, nome="Mascara CNPJ", documento="30.313.222/0001-25")

    assert dados["documento"] == "30313222000125"


@pytest.mark.parametrize(
    "documento",
    [
        "52998224724",  # CPF com dígito verificador errado
        "11111111111",  # CPF com todos os dígitos iguais
        "30313222000124",  # CNPJ com dígito verificador errado
        "1234567890",  # tamanho que não é CPF nem CNPJ
        "5299822472A",  # CPF com letra
    ],
)
def test_documento_invalido_e_recusado(client, documento):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json=parceiro_valido(nome="Doc Invalido", documento=documento)
    )

    assert resposta.status_code == 422
    assert "documento" in campos(resposta)


def test_cep_aceita_mascara(client):
    logar(client)

    assert criar_parceiro(client, nome="Cep Mascara", cep="50050-010")["cep"] == "50050010"


def test_email_com_254_caracteres_e_aceito(client):
    logar(client)
    email_254 = "g" * 64 + "@" + "g" * 63 + "." + "g" * 63 + "." + "g" * 57 + ".com"
    assert len(email_254) == 254

    assert criar_parceiro(client, nome="Email 254", email=email_254)["email"] == email_254


def test_relacionamento_precisa_ser_booleano_json(client):
    logar(client)

    resposta = client.post(
        "/api/parceiros", json={"nome": "Texto", "e_cliente": "false", "e_fornecedor": 0}
    )

    assert resposta.status_code == 422
    assert {"e_cliente", "e_fornecedor"} <= set(campos(resposta))


def test_alterar_limpa_campos_opcionais_com_null(client):
    logar(client)
    parceiro = criar_parceiro(
        client, nome="Com Tudo", documento="52998224725", email="tudo@cliente.com.br",
        cep="50050010", observacao="obs",
    )

    resposta = client.patch(
        f"/api/parceiros/{parceiro['id_parceiro']}",
        json={"documento": None, "email": "", "cep": None, "observacao": None},
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["documento"] is None
    assert dados["email"] is None
    assert dados["cep"] is None
    assert dados["observacao"] is None


def test_alterar_para_o_proprio_email_nao_e_duplicidade(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Mesmo", email="mesmo@cliente.com.br")

    resposta = client.patch(
        f"/api/parceiros/{parceiro['id_parceiro']}",
        json={"nome": "Mesmo Renomeado", "email": "MESMO@cliente.com.br"},
    )

    assert resposta.status_code == 200


def test_alterar_corpo_vazio_e_campo_proibido(client):
    logar(client)
    parceiro = criar_parceiro(client, nome="Campos")

    assert client.patch(f"/api/parceiros/{parceiro['id_parceiro']}", json={}).status_code == 422
    resposta = client.patch(
        f"/api/parceiros/{parceiro['id_parceiro']}", json={"id_empresa": 999}
    )
    assert resposta.status_code == 422
    assert "id_empresa" in campos(resposta)


def test_criar_ignora_empresa_do_corpo_e_recusa_o_campo(client):
    conta = logar(client)

    resposta = client.post("/api/parceiros", json=parceiro_valido(id_empresa=999))

    assert resposta.status_code == 422
    assert "id_empresa" in campos(resposta)
    assert criar_parceiro(client, nome="Normal")["id_empresa"] == conta["id_empresa"]


def test_listar_busca_por_nome_email_e_documento_com_mascara(client):
    logar(client)
    criar_parceiro(client, nome="Ana Clara", documento="52998224725", email="ana@cliente.com.br")
    criar_parceiro(client, nome="Bruno Souza", email="bruno@fornecedor.com.br")

    def nomes(busca):
        dados = client.get("/api/parceiros", query_string={"busca": busca}).get_json()["dados"]
        return [p["nome"] for p in dados["parceiros"]]

    assert nomes("clara") == ["Ana Clara"]
    assert nomes("FORNECEDOR.com") == ["Bruno Souza"]
    assert nomes("529.982.247-25") == ["Ana Clara"]
    assert nomes("%") == []  # "%" é texto comum, não curinga


def test_listar_filtra_por_tipo(client):
    logar(client)
    criar_parceiro(client, nome="Só Cliente")
    criar_parceiro(client, nome="Só Fornecedor", e_cliente=False, e_fornecedor=True)
    criar_parceiro(client, nome="Os Dois", e_fornecedor=True)

    def nomes(tipo):
        dados = client.get("/api/parceiros", query_string={"tipo": tipo}).get_json()["dados"]
        return [p["nome"] for p in dados["parceiros"]]

    assert nomes("cliente") == ["Os Dois", "Só Cliente"]
    assert nomes("fornecedor") == ["Os Dois", "Só Fornecedor"]
    assert nomes("ambos") == ["Os Dois"]
    assert len(nomes("todos")) == 3
    assert client.get("/api/parceiros?tipo=xyz").status_code == 422


def test_listar_paginacao_e_parametros_invalidos(client):
    logar(client)
    for numero in range(3):
        criar_parceiro(client, nome=f"Paginado {numero}")

    dados = client.get("/api/parceiros?limit=2&offset=2").get_json()["dados"]

    assert dados["total"] == 3
    assert len(dados["parceiros"]) == 1
    assert client.get("/api/parceiros?limit=0").status_code == 422
    assert client.get("/api/parceiros?offset=abc").status_code == 422


def test_isolamento_entre_empresas(app, client):
    """SEG-P02: a listagem de parceiros mostra somente os da empresa logada."""
    logar(client)
    parceiro = criar_parceiro(client, nome="Da Empresa A", email="a@cliente.com.br")
    outro, _ = _outra_empresa(app)
    criar_parceiro(outro, nome="Da Empresa B")

    # B não enxerga, não altera e não apaga o parceiro de A (sempre 404).
    assert outro.get(f"/api/parceiros/{parceiro['id_parceiro']}").status_code == 404
    assert (
        outro.patch(f"/api/parceiros/{parceiro['id_parceiro']}", json={"nome": "X"}).status_code
        == 404
    )
    assert outro.delete(f"/api/parceiros/{parceiro['id_parceiro']}").status_code == 404
    assert [p["nome"] for p in outro.get("/api/parceiros").get_json()["dados"]["parceiros"]] == [
        "Da Empresa B"
    ]
    assert obter_parceiro(client, parceiro["id_parceiro"])["nome"] == "Da Empresa A"


def test_rotas_exigem_login(client):
    assert client.get("/api/parceiros").status_code == 401
    assert client.post("/api/parceiros", json=parceiro_valido()).status_code == 401
    assert client.get("/api/parceiros/1").status_code == 401
    assert client.patch("/api/parceiros/1", json={"nome": "x"}).status_code == 401
    assert client.delete("/api/parceiros/1").status_code == 401
    assert client.post("/api/parceiros/1/interacoes", json={}).status_code == 401


def test_corpo_nao_json_e_recusado(client):
    logar(client)

    assert client.post("/api/parceiros", data="nome=x").status_code == 415


def test_dashboard_conta_parceiros_da_empresa(app, client):
    logar(client)
    criar_parceiro(client, nome="Um")
    criar_parceiro(client, nome="Dois")
    outro, _ = _outra_empresa(app)
    criar_parceiro(outro, nome="De Outra Empresa")

    assert client.get("/api/dashboard/resumo").get_json()["dados"]["parceiros"] == 2
    assert outro.get("/api/dashboard/resumo").get_json()["dados"]["parceiros"] == 1


def test_seg_n13_xss_na_observacao_do_parceiro_fica_como_texto(client):
    """SEG-N13: payload de XSS na observação não é interpretado pela API."""
    logar(client)
    payload = "<script>alert('xss')</script>"
    criado = criar_parceiro(client, nome="Parceiro SEG N13", observacao=payload)

    assert criado["observacao"] == payload
    assert client.get(f"/api/parceiros/{criado['id_parceiro']}").is_json


def test_seg_n16_sql_injection_na_busca_de_parceiros(client):
    """SEG-N16: busca trata aspas/comandos SQL como texto, sem injeção."""
    logar(client)
    criar_parceiro(client, nome="Parceiro Normal SEG N16")

    resposta = client.get(
        "/api/parceiros", query_string={"busca": "' OR 1=1 --"}
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["total"] == 0
