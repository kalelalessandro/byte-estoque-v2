"""Testes do módulo de produtos (criar, alterar, listar e apagar).

Rodam contra o MySQL real, como o restante da suíte. Como ``produtos``,
``categorias`` e ``operacao_itens`` referenciam outras tabelas com ON DELETE
RESTRICT, o fixture ``limpar_produtos`` apaga primeiro operações, produtos e
categorias criados aqui; só depois o ``banco_limpo`` (conftest) consegue apagar
as empresas de teste.
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, text

from src.app.db import get_engine
from tests.helpers import CNPJ_VALIDO, CNPJ_VALIDO_2, criar_conta, entrar

SENHA = "Senha#Teste1"
EMPRESAS_COM_PRODUTOS: set[int] = set()
OPERACOES_CRIADAS: set[int] = set()


@pytest.fixture(autouse=True)
def limpar_produtos(app, banco_limpo):
    """Remove operações, produtos e categorias das empresas criadas pelo teste."""
    yield

    if not EMPRESAS_COM_PRODUTOS and not OPERACOES_CRIADAS:
        return

    with app.app_context(), get_engine().begin() as conexao:
        if OPERACOES_CRIADAS:
            ids_operacoes = list(OPERACOES_CRIADAS)
            conexao.execute(
                text(
                    "DELETE FROM operacao_itens WHERE id_operacao IN :ids"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids_operacoes},
            )
            conexao.execute(
                text("DELETE FROM operacoes WHERE id_operacao IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": ids_operacoes},
            )
            OPERACOES_CRIADAS.clear()

        if EMPRESAS_COM_PRODUTOS:
            ids_empresas = list(EMPRESAS_COM_PRODUTOS)
            for tabela in ("produtos", "categorias"):
                conexao.execute(
                    text(f"DELETE FROM {tabela} WHERE id_empresa IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": ids_empresas},
                )
            EMPRESAS_COM_PRODUTOS.clear()


def _categoria(app, id_empresa: int, nome: str = "Geral") -> int:
    """Cria uma categoria direto no banco (ainda não há rota de categorias)."""
    EMPRESAS_COM_PRODUTOS.add(id_empresa)
    with app.app_context(), get_engine().begin() as conexao:
        resultado = conexao.execute(
            text("INSERT INTO categorias (id_empresa, nome) VALUES (:e, :n)"),
            {"e": id_empresa, "n": nome},
        )
        return resultado.lastrowid


def _logar(client, email="prod.a@exemplo.com.br", cnpj=CNPJ_VALIDO) -> int:
    """Cria empresa + usuário, faz login e devolve o id_empresa."""
    conta = criar_conta(client, email=email, senha=SENHA, cnpj=cnpj)
    assert entrar(client, email, SENHA).status_code == 200
    return conta["empresa"]["id_empresa"]


def _payload(id_categoria: int, **extra) -> dict:
    dados = {
        "sku": "CAN-001",
        "id_categoria": id_categoria,
        "nome": "Caneta azul",
        "descricao": "Caneta esferográfica",
        "unidade_estoque": 10,
        "preco": 3.5,
    }
    dados.update(extra)
    return dados


# ---------------------------------------------------------------------------
# Criar produto
# ---------------------------------------------------------------------------


def test_prd_p01_criar_produto_valido(app, client):
    id_empresa = _logar(client)
    id_cat = _categoria(app, id_empresa)

    resposta = client.post("/api/produtos", json=_payload(id_cat))
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 201
    assert dados["id_empresa"] == id_empresa  # veio da sessão
    assert dados["preco"] == "3.50"
    assert dados["unidade_estoque"] == 10
    assert dados["categoria_nome"] == "Geral"


def test_prd_p02_estoque_omitido_comeca_em_zero(app, client):
    id_cat = _categoria(app, _logar(client))
    corpo = _payload(id_cat)
    del corpo["unidade_estoque"]
    corpo["descricao"] = None

    resposta = client.post("/api/produtos", json=corpo)
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 201
    assert dados["unidade_estoque"] == 0
    assert dados["descricao"] is None


def test_prd_n01_criar_sem_login(client):
    resposta = client.post("/api/produtos", json=_payload(1))
    assert resposta.status_code == 401


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("sku", ""),
    ],
)
def test_prd_n02_criar_com_campo_invalido(app, client, campo, valor):
    id_cat = _categoria(app, _logar(client))

    resposta = client.post("/api/produtos", json=_payload(id_cat, **{campo: valor}))

    assert resposta.status_code == 422
    assert campo in resposta.get_json()["campos"]




def test_prd_n15_sku_duplicado_exato(app, client):
    """PRD-N15: SKU já existente na mesma empresa é recusado."""
    id_cat = _categoria(app, _logar(client))
    corpo = _payload(id_cat, sku="PRD-1001")
    assert client.post("/api/produtos", json=corpo).status_code == 201

    resposta = client.post("/api/produtos", json=corpo)

    assert resposta.status_code == 409
    assert "sku" in resposta.get_json()["campos"]


def test_prd_n16_sku_duplicado_por_acento_e_caixa(app, client):
    """PRD-N16: SKU difere só por acento/caixa; collation considera igual."""
    id_cat = _categoria(app, _logar(client))
    assert (
        client.post("/api/produtos", json=_payload(id_cat, sku="Pré-Dup-01")).status_code
        == 201
    )

    resposta = client.post("/api/produtos", json=_payload(id_cat, sku="PRE-DUP-01"))

    assert resposta.status_code == 409
    assert "sku" in resposta.get_json()["campos"]




def test_prd_n04_categoria_de_outra_empresa(app, client):
    """PRD-N04/SEG-N02: produto com categoria de outra empresa é recusado."""
    _logar(client)
    outro = app.test_client()
    id_empresa_b = _logar(outro, "prod.b@exemplo.com.br", CNPJ_VALIDO_2)
    id_cat_b = _categoria(app, id_empresa_b)

    resposta = client.post("/api/produtos", json=_payload(id_cat_b))

    assert resposta.status_code == 422
    assert "id_categoria" in resposta.get_json()["campos"]


# ---------------------------------------------------------------------------
# Alterar produto
# ---------------------------------------------------------------------------


def _criar(client, app) -> int:
    id_empresa = _logar(client)
    id_cat = _categoria(app, id_empresa)
    return client.post("/api/produtos", json=_payload(id_cat)).get_json()["dados"][
        "id_produto"
    ]


def test_prd_p04_alterar_preco_e_estoque(app, client):
    id_produto = _criar(client, app)

    resposta = client.patch(
        f"/api/produtos/{id_produto}", json={"preco": "12,90", "unidade_estoque": 0}
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["preco"] == "12.90"
    assert dados["unidade_estoque"] == 0
    assert dados["nome"] == "Caneta azul"  # o que não foi enviado não muda




@pytest.mark.parametrize(
    "corpo",
    [
        {},
    ],
)
def test_prd_n05_alterar_com_dados_invalidos(app, client, corpo):
    id_produto = _criar(client, app)

    resposta = client.patch(f"/api/produtos/{id_produto}", json=corpo)

    assert resposta.status_code == 422


def test_prd_n06_alterar_produto_de_outra_empresa(app, client):
    id_produto = _criar(client, app)
    outro = app.test_client()
    _logar(outro, "prod.b@exemplo.com.br", CNPJ_VALIDO_2)

    resposta = outro.patch(f"/api/produtos/{id_produto}", json={"preco": 1})

    assert resposta.status_code == 404
    # e o produto original continua intacto
    original = client.get(f"/api/produtos/{id_produto}").get_json()["dados"]
    assert original["preco"] == "3.50"


def test_prd_n07_alterar_sem_login(client):
    assert client.patch("/api/produtos/1", json={"preco": 1}).status_code == 401


def test_prd_n08_alterar_produto_inexistente(app, client):
    _logar(client)
    assert client.patch("/api/produtos/999999", json={"preco": 1}).status_code == 404


# ---------------------------------------------------------------------------
# Casos restantes do plano (PRD)
# ---------------------------------------------------------------------------


def _id_usuario(client) -> int:
    return client.get("/api/auth/me").get_json()["dados"]["id_usuario"]


def _criar_operacao_com_item(app, id_usuario: int, id_produto: int) -> int:
    """Cria uma operação + item apontando para o produto (para o RESTRICT)."""
    with app.app_context(), get_engine().begin() as conexao:
        resultado = conexao.execute(
            text(
                "INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia) "
                "VALUES (:usuario, 'venda', 'pendente', NOW())"
            ),
            {"usuario": id_usuario},
        )
        id_operacao = resultado.lastrowid
        conexao.execute(
            text(
                "INSERT INTO operacao_itens "
                "(id_operacao, id_produto, quantidade, valor_unitario) "
                "VALUES (:operacao, :produto, 1, 1.00)"
            ),
            {"operacao": id_operacao, "produto": id_produto},
        )

    OPERACOES_CRIADAS.add(id_operacao)
    return id_operacao


def test_prd_p03_criar_produto_preco_zero(app, client):
    id_cat = _categoria(app, _logar(client))

    resposta = client.post("/api/produtos", json=_payload(id_cat, preco=0))

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["preco"] == "0.00"




def test_prd_p05_criar_nome_150_caracteres(app, client):
    id_cat = _categoria(app, _logar(client))
    nome = "N" * 150

    resposta = client.post("/api/produtos", json=_payload(id_cat, nome=nome))

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["nome"] == nome


def test_prd_p06_criar_descricao_500_caracteres(app, client):
    id_cat = _categoria(app, _logar(client))
    descricao = "D" * 500

    resposta = client.post(
        "/api/produtos", json=_payload(id_cat, descricao=descricao)
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["dados"]["descricao"] == descricao


def test_prd_p08_listar_produtos_da_empresa(app, client):
    id_produto = _criar(client, app)

    resposta = client.get("/api/produtos")
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["total"] >= 1
    ids = [produto["id_produto"] for produto in dados["produtos"]]
    assert id_produto in ids
    produto = next(p for p in dados["produtos"] if p["id_produto"] == id_produto)
    assert produto["categoria_nome"] == "Geral"


def test_prd_p11_alterar_sku(app, client):
    id_produto = _criar(client, app)

    resposta = client.patch(
        f"/api/produtos/{id_produto}", json={"sku": "CAN-002"}
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["id_produto"] == id_produto
    assert dados["sku"] == "CAN-002"


def test_prd_p12_alterar_categoria(app, client):
    id_empresa = _logar(client)
    id_cat_original = _categoria(app, id_empresa, "Categoria Original")
    id_cat_nova = _categoria(app, id_empresa, "Categoria Nova")
    criado = client.post(
        "/api/produtos", json=_payload(id_cat_original, sku="CAT-001")
    ).get_json()["dados"]

    resposta = client.patch(
        f"/api/produtos/{criado['id_produto']}",
        json={"id_categoria": id_cat_nova},
    )
    dados = resposta.get_json()["dados"]

    assert resposta.status_code == 200
    assert dados["id_categoria"] == id_cat_nova


def test_prd_p13_apagar_produto(app, client):
    id_produto = _criar(client, app)

    resposta = client.delete(f"/api/produtos/{id_produto}")

    assert resposta.status_code == 200
    assert client.get(f"/api/produtos/{id_produto}").status_code == 404
    listagem = client.get("/api/produtos").get_json()["dados"]["produtos"]
    assert all(produto["id_produto"] != id_produto for produto in listagem)


def test_prd_n03_criar_sem_categoria(app, client):
    id_cat = _categoria(app, _logar(client))
    corpo = _payload(id_cat)
    del corpo["id_categoria"]

    resposta = client.post("/api/produtos", json=corpo)

    assert resposta.status_code == 422
    assert "id_categoria" in resposta.get_json()["campos"]


def test_prd_n04_criar_com_preco_vazio(app, client):
    id_cat = _categoria(app, _logar(client))

    resposta = client.post("/api/produtos", json=_payload(id_cat, preco=None))

    assert resposta.status_code == 422
    assert "preco" in resposta.get_json()["campos"]


def test_prd_n10_criar_com_estoque_nao_numerico(app, client):
    id_cat = _categoria(app, _logar(client))

    resposta = client.post(
        "/api/produtos", json=_payload(id_cat, unidade_estoque="abc")
    )

    assert resposta.status_code == 422
    assert "unidade_estoque" in resposta.get_json()["campos"]


def test_prd_n17_alterar_sku_duplicado(app, client):
    id_cat = _categoria(app, _logar(client))
    primeiro = client.post(
        "/api/produtos", json=_payload(id_cat, sku="ALT-1")
    ).get_json()["dados"]
    client.post("/api/produtos", json=_payload(id_cat, sku="ALT-2"))

    resposta = client.patch(
        f"/api/produtos/{primeiro['id_produto']}", json={"sku": "ALT-2"}
    )

    assert resposta.status_code == 409
    assert "sku" in resposta.get_json()["campos"]
    assert (
        client.get(f"/api/produtos/{primeiro['id_produto']}")
        .get_json()["dados"]["sku"]
        == "ALT-1"
    )


def test_prd_n21_nao_apagar_produto_com_operacao(app, client):
    id_empresa = _logar(client)
    id_cat = _categoria(app, id_empresa)
    produto = client.post(
        "/api/produtos", json=_payload(id_cat, sku="DEL-6001")
    ).get_json()["dados"]

    _criar_operacao_com_item(app, _id_usuario(client), produto["id_produto"])

    resposta = client.delete(f"/api/produtos/{produto['id_produto']}")

    assert resposta.status_code == 409
    assert "vinculados" in resposta.get_json()["erro"].lower()
    assert client.get(f"/api/produtos/{produto['id_produto']}").status_code == 200


@pytest.mark.skip(
    reason="UI/E2E: a confirmação antes de apagar é do front-end; a API expõe "
    "apenas o DELETE direto. O caso PRD-N22 não é aplicável ao pytest de API."
)
def test_prd_n22_cancelar_confirmacao_nao_apaga(app, client):
    """PRD-N22: (caso de UI/E2E; não automatizado no pytest de API)."""


# ---------------------------------------------------------------------------
# Casos do plano V1.4 ainda sem teste específico (validações de criação/edição)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "id_caso,campo,valor",
    [
        ("PRD-N09", "unidade_estoque", 1.5),
        ("PRD-N11", "preco", -1),
        ("PRD-N12", "preco", "abc"),
        ("PRD-N13", "preco", "10000000000.01"),
        ("PRD-N14", "preco", "1.234"),
    ],
)
def test_prd_criacao_negativa_do_plano(app, client, id_caso, campo, valor):
    """Cobre PRD-N01/N02/N05/N06/N07/N08/N09/N11/N12/N13/N14 do PDF."""
    id_cat = _categoria(app, _logar(client))

    resposta = client.post("/api/produtos", json=_payload(id_cat, **{campo: valor}))

    assert resposta.status_code == 422, (id_caso, resposta.get_json())
    assert campo in resposta.get_json()["campos"], (id_caso, resposta.get_json())


@pytest.mark.parametrize(
    "id_caso,campo,valor",
    [
        ("PRD-N18", "preco", -1),
        ("PRD-N19", "unidade_estoque", -1),
        ("PRD-N20", "nome", "   "),
    ],
)
def test_prd_edicao_negativa_do_plano(app, client, id_caso, campo, valor):
    """Cobre PRD-N18/N19/N20 do PDF."""
    id_cat = _categoria(app, _logar(client))
    criado = client.post(
        "/api/produtos", json=_payload(id_cat, sku=f"ED-{id_caso}")
    ).get_json()["dados"]

    resposta = client.patch(
        f"/api/produtos/{criado['id_produto']}", json={campo: valor}
    )

    assert resposta.status_code == 422, (id_caso, resposta.get_json())
    assert campo in resposta.get_json()["campos"], (id_caso, resposta.get_json())


def test_prd_p07_mesmo_sku_em_empresas_diferentes(app, client):
    """PRD-P07: mesmo SKU de produto de outra empresa é aceito."""
    primeira = _categoria(app, _logar(client, email="prd.p07.a@exemplo.com.br"))
    resposta_a = client.post(
        "/api/produtos", json=_payload(primeira, sku="PRD-P07-SKU")
    )
    assert resposta_a.status_code == 201

    segunda = _categoria(
        app,
        _logar(
            client,
            email="prd.p07.b@exemplo.com.br",
            cnpj=CNPJ_VALIDO_2,
        ),
    )
    resposta_b = client.post(
        "/api/produtos", json=_payload(segunda, sku="PRD-P07-SKU")
    )
    assert resposta_b.status_code == 201, resposta_b.get_json()


def test_prd_p09_alterar_nome_do_produto(app, client):
    """PRD-P09: alterar o nome de um produto."""
    id_cat = _categoria(app, _logar(client))
    criado = client.post(
        "/api/produtos", json=_payload(id_cat, sku="PRD-P09")
    ).get_json()["dados"]

    resposta = client.patch(
        f"/api/produtos/{criado['id_produto']}", json={"nome": "Produto Renomeado"}
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["nome"] == "Produto Renomeado"


def test_prd_p10_alterar_preco_do_produto(app, client):
    """PRD-P10: alterar o preço de um produto."""
    id_cat = _categoria(app, _logar(client))
    criado = client.post(
        "/api/produtos", json=_payload(id_cat, sku="PRD-P10")
    ).get_json()["dados"]

    resposta = client.patch(
        f"/api/produtos/{criado['id_produto']}", json={"preco": 9.99}
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["dados"]["preco"] == "9.99"


def test_seg_p01_listar_produtos_somente_da_propria_empresa(app, client):
    """SEG-P01: lista de produtos mostra apenas os da empresa logada."""
    cat_a = _categoria(app, _logar(client))
    produto_a = client.post(
        "/api/produtos",
        json=_payload(cat_a, sku="SEG-P01-A", nome="Produto SEG P01 A"),
    ).get_json()["dados"]

    outro = app.test_client()
    cat_b = _categoria(
        app,
        _logar(outro, email="seg.p01.b@exemplo.com.br", cnpj=CNPJ_VALIDO_2),
    )
    produto_b = outro.post(
        "/api/produtos",
        json=_payload(cat_b, sku="SEG-P01-B", nome="Produto SEG P01 B"),
    ).get_json()["dados"]

    nomes_a = [
        p["nome"] for p in client.get("/api/produtos").get_json()["dados"]["produtos"]
    ]
    nomes_b = [
        p["nome"] for p in outro.get("/api/produtos").get_json()["dados"]["produtos"]
    ]
    assert produto_a["nome"] in nomes_a
    assert produto_b["nome"] not in nomes_a
    assert produto_b["nome"] in nomes_b


def test_seg_n01_acessar_produto_de_outra_empresa_por_id(app, client):
    """SEG-N01: produto de outra empresa por identificador direto responde 404."""
    cat_a = _categoria(app, _logar(client))
    produto = client.post(
        "/api/produtos", json=_payload(cat_a, sku="SEG-N01-A")
    ).get_json()["dados"]

    outro = app.test_client()
    _logar(outro, email="seg.n01.b@exemplo.com.br", cnpj=CNPJ_VALIDO_2)

    assert outro.get(f"/api/produtos/{produto['id_produto']}").status_code == 404


def test_seg_n15_xss_no_nome_do_produto_fica_como_texto(app, client):
    """SEG-N15: payload de XSS no nome é aceito como texto JSON (front escapa)."""
    cat = _categoria(app, _logar(client))
    nome = "<script>alert('xss')</script>"
    dados = client.post(
        "/api/produtos", json=_payload(cat, sku="SEG-N15", nome=nome)
    ).get_json()["dados"]

    assert dados["nome"] == nome
    assert client.get(f"/api/produtos/{dados['id_produto']}").is_json
