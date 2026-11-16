"""Demonstração do CRUD de produtos via API (sem subir servidor).

O front-end ainda não tem tela de produtos, então este script usa o
``test_client`` do Flask (mesmas rotas/regras do servidor real) e imprime cada
resposta HTTP.

Uso, na pasta ``backend/``:

    uv run python scripts/demo_produtos_crud.py          # cria e altera um produto
    uv run python scripts/demo_produtos_crud.py --limpar # remove os dados de demo

Os dados ficam em uma empresa de demonstração própria
(``produto.demo@demo.byteestoque.com``) para não conflitar com os testes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

from sqlalchemy import text  # noqa: E402

from src.app import create_app  # noqa: E402
from src.app.db import get_engine  # noqa: E402

EMAIL = "produto.demo@demo.byteestoque.com"
SENHA = "Demo#2026"
CNPJ = "55443322000105"
RAZAO_SOCIAL = "Loja Demo Produtos Ltda"
NOME_CATEGORIA = "Geral"


def mostrar(etapa: str, resposta) -> None:
    """Imprime status e corpo JSON de uma resposta da API."""
    corpo = resposta.get_json()
    print(f"\n=== {etapa} ===")
    print(f"HTTP {resposta.status_code}")
    print(json.dumps(corpo, ensure_ascii=False, indent=2))


def garantir_conta(client) -> dict:
    """Cria (ou reaproveita) a conta de demonstração e faz login."""
    cadastro = client.post(
        "/api/auth/cadastro",
        json={
            "empresa": {"razao_social": RAZAO_SOCIAL, "cnpj": CNPJ},
            "usuario": {
                "nome": "Usuário Demo Produtos",
                "email": EMAIL,
                "senha": SENHA,
            },
        },
    )
    if cadastro.status_code not in (201, 409):
        mostrar("Erro ao criar a conta de demonstração", cadastro)
        raise SystemExit(1)

    login = client.post("/api/auth/login", json={"email": EMAIL, "senha": SENHA})
    mostrar("Login da conta de demonstração", login)
    if login.status_code != 200:
        raise SystemExit(1)
    return login.get_json()["dados"]


def garantir_categoria(app, id_empresa: int) -> int:
    """Cria a categoria 'Geral' direto no banco (ainda não há rota de categorias)."""
    with app.app_context():
        with get_engine().begin() as conexao:
            existente = conexao.execute(
                text(
                    "SELECT id_categoria FROM categorias "
                    "WHERE id_empresa = :empresa AND nome = :nome"
                ),
                {"empresa": id_empresa, "nome": NOME_CATEGORIA},
            ).scalar()
            if existente is not None:
                print(f"\n=== Categoria existente (id_categoria={existente}) ===")
                return existente

            resultado = conexao.execute(
                text(
                    "INSERT INTO categorias (id_empresa, nome) "
                    "VALUES (:empresa, :nome)"
                ),
                {"empresa": id_empresa, "nome": NOME_CATEGORIA},
            )
            id_categoria = resultado.lastrowid
            print(f"\n=== Categoria criada (id_categoria={id_categoria}) ===")
            return id_categoria


def limpar_dados(app) -> None:
    """Remove produtos, categorias, usuário e empresa da demonstração."""
    with app.app_context():
        with get_engine().begin() as conexao:
            id_empresa = conexao.execute(
                text(
                    "SELECT u.id_empresa FROM usuarios u "
                    "WHERE u.email = :email"
                ),
                {"email": EMAIL},
            ).scalar()
            if id_empresa is not None:
                conexao.execute(
                    text("DELETE FROM produtos WHERE id_empresa = :empresa"),
                    {"empresa": id_empresa},
                )
                conexao.execute(
                    text("DELETE FROM categorias WHERE id_empresa = :empresa"),
                    {"empresa": id_empresa},
                )
            conexao.execute(
                text("DELETE FROM usuarios WHERE email = :email"),
                {"email": EMAIL},
            )
            conexao.execute(
                text("DELETE FROM empresas WHERE cnpj = :cnpj"), {"cnpj": CNPJ}
            )
    print("Dados de demonstração de produtos removidos.")


def main() -> int:
    app = create_app({"TESTING": True, "DEBUG": False})

    if "--limpar" in sys.argv:
        limpar_dados(app)
        return 0

    client = app.test_client()

    conta = garantir_conta(client)
    id_empresa = conta["id_empresa"]
    id_categoria = garantir_categoria(app, id_empresa)

    sku = f"DEMO-{datetime.now():%Y%m%d%H%M%S}"
    payload = {
        "sku": sku,
        "id_categoria": id_categoria,
        "nome": "Caneta azul (demo)",
        "descricao": "Produto criado pelo script de demonstração",
        "unidade_estoque": 10,
        "preco": 3.5,
    }

    criado = client.post("/api/produtos", json=payload)
    mostrar("1) POST /api/produtos (criar)", criado)
    if criado.status_code != 201:
        return 1
    id_produto = criado.get_json()["dados"]["id_produto"]

    listagem = client.get("/api/produtos")
    mostrar("2) GET /api/produtos (listar da empresa)", listagem)

    detalhe = client.get(f"/api/produtos/{id_produto}")
    mostrar(f"3) GET /api/produtos/{id_produto} (detalhar)", detalhe)

    alterado = client.patch(
        f"/api/produtos/{id_produto}",
        json={"preco": "12,90", "unidade_estoque": 25},
    )
    mostrar(f"4) PATCH /api/produtos/{id_produto} (alterar)", alterado)

    final = client.get(f"/api/produtos/{id_produto}")
    mostrar(f"5) GET /api/produtos/{id_produto} (confirmar alterações)", final)

    print(
        f"""
=== Concluído ===
Produto de demonstração: id_produto={id_produto}, sku={sku}, id_empresa={id_empresa}
Conta: {EMAIL} / senha {SENHA}

Para conferir direto no MySQL:
  SELECT * FROM produtos WHERE id_empresa = {id_empresa};
  SELECT * FROM categorias WHERE id_empresa = {id_empresa};

Para remover os dados de demonstração:
  uv run python scripts/demo_produtos_crud.py --limpar
"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
