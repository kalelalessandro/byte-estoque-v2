"""Fábrica do app Flask do Byte Estoque.

Responsabilidades deste módulo:
- carregar as variáveis de ambiente (``backend/.env`` e ``database/.env``);
- montar a URL do MySQL (SQLAlchemy + PyMySQL) a partir de ``database/.env``;
- registrar os blueprints (autenticação, dashboard, categorias, produtos e parceiros);
- expor rotas básicas (``/`` e ``/api/health``) e respostas JSON de erro.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import text
from sqlalchemy.engine import URL

from .core.login import bp as bp_login
from .core.signup import bp as bp_signup
from .db import get_engine, init_db
from .modules.categories import bp as bp_categorias
from .modules.dashboard import bp as bp_dashboard
from .modules.interactions import bp as bp_interacoes
from .modules.partners import bp as bp_parceiros
from .modules.products import bp as bp_produtos

# app/__init__.py -> app -> src -> backend -> raiz do projeto
RAIZ_PROJETO = Path(__file__).resolve().parents[3]
PASTA_BACKEND = Path(__file__).resolve().parents[2]
ARQUIVO_ENV_BANCO = RAIZ_PROJETO / "database" / ".env"

SECRET_KEY_DEV = "dev-byte-estoque-troque-esta-chave"


def create_app(configuracao: dict | None = None) -> Flask:
    """Cria e configura a aplicação Flask (padrão application factory)."""
    carregar_variaveis_ambiente()

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or SECRET_KEY_DEV,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # dev local (HTTP); use True em produção/HTTPS
        CORS_ORIGINS=os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ),
        SENHA_HASH_METODO=os.environ.get("SENHA_HASH_METODO") or "scrypt",
        DEBUG=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
    if configuracao:
        app.config.update(configuracao)

    # API respondendo em português sem escapar acentos (ex.: "Sessão encerrada.").
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    init_db(app, montar_url_banco())
    registrar_blueprints(app)
    registrar_rotas_basicas(app)
    registrar_handlers_erro(app)
    registrar_cors(app)
    return app


def carregar_variaveis_ambiente() -> None:
    """Carrega ``backend/.env`` e ``database/.env`` sem sobrescrever o já definido."""
    for arquivo in (PASTA_BACKEND / ".env", ARQUIVO_ENV_BANCO):
        if arquivo.is_file():
            load_dotenv(arquivo, override=False)


def montar_url_banco() -> URL:
    """Monta a URL do MySQL a partir de ``database/.env`` (com override por env)."""
    if not ARQUIVO_ENV_BANCO.is_file():
        raise RuntimeError(
            f"Arquivo não encontrado: {ARQUIVO_ENV_BANCO}. "
            "Copie database/.env.example para database/.env e suba o banco "
            "com 'docker compose up -d'."
        )

    valores = dotenv_values(ARQUIVO_ENV_BANCO)
    obrigatorios = {
        "MYSQL_USER": "usuário do banco",
        "MYSQL_PASSWORD": "senha do banco",
        "MYSQL_DATABASE": "nome do banco",
    }
    config: dict = {}
    for chave, descricao in obrigatorios.items():
        valor = os.environ.get(chave) or valores.get(chave)
        if not valor:
            raise RuntimeError(f"{descricao} ausente: defina {chave} em database/.env.")
        config[chave] = valor

    porta = os.environ.get("MYSQL_PORT") or valores.get("MYSQL_PORT") or "3306"
    try:
        config["MYSQL_PORT"] = int(porta)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"MYSQL_PORT inválida em database/.env: {porta!r}") from exc

    return URL.create(
        "mysql+pymysql",
        username=config["MYSQL_USER"],
        password=config["MYSQL_PASSWORD"],
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=config["MYSQL_PORT"],
        database=config["MYSQL_DATABASE"],
        query={"charset": "utf8mb4"},
    )


def registrar_blueprints(app: Flask) -> None:
    app.register_blueprint(bp_login, url_prefix="/api/auth")
    app.register_blueprint(bp_signup, url_prefix="/api/auth")
    app.register_blueprint(bp_categorias, url_prefix="/api/categorias")
    app.register_blueprint(bp_dashboard, url_prefix="/api/dashboard")
    app.register_blueprint(bp_produtos, url_prefix="/api/produtos")
    app.register_blueprint(bp_parceiros, url_prefix="/api/parceiros")
    # Interações moram sob /api/parceiros/<id>/interacoes (mesma tela de parceiros).
    app.register_blueprint(bp_interacoes, url_prefix="/api/parceiros")


def registrar_rotas_basicas(app: Flask) -> None:
    @app.get("/")
    def index():
        return jsonify(
            {
                "ok": True,
                "api": "Byte Estoque",
                "descricao": "API de autenticação, dashboard, categorias, produtos e parceiros.",
                "rotas": {
                    "health": "GET /api/health",
                    "cadastro": "POST /api/auth/cadastro",
                    "login": "POST /api/auth/login",
                    "logout": "POST /api/auth/logout",
                    "me": "GET /api/auth/me",
                    "dashboard": "GET /api/dashboard/resumo",
                    "categorias": (
                        "GET/POST /api/categorias, "
                        "PATCH/DELETE /api/categorias/<id>"
                    ),
                    "produtos": (
                        "GET/POST /api/produtos, "
                        "GET/PATCH/DELETE /api/produtos/<id>"
                    ),
                    "parceiros": (
                        "GET/POST /api/parceiros, "
                        "GET/PATCH/DELETE /api/parceiros/<id>"
                    ),
                    "interacoes": (
                        "POST /api/parceiros/<id>/interacoes, "
                        "PATCH /api/parceiros/<id>/interacoes/<interacao_id>"
                    ),
                },
            }
        )

    @app.get("/api/health")
    def health():
        try:
            with get_engine().connect() as conexao:
                conexao.execute(text("SELECT 1"))
        except Exception as exc:  # banco fora do ar / credenciais erradas
            app.logger.error("Falha ao conectar no MySQL: %s", exc)
            return jsonify({"ok": False, "status": "erro", "banco": "desconectado"}), 503
        return jsonify({"ok": True, "status": "ok", "banco": "conectado"})


def registrar_handlers_erro(app: Flask) -> None:
    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return jsonify({"ok": False, "erro": "Rota não encontrada."}), 404

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        return jsonify({"ok": False, "erro": "Método HTTP não permitido para esta rota."}), 405

    @app.errorhandler(500)
    def erro_interno(_erro):
        return jsonify({"ok": False, "erro": "Erro interno no servidor."}), 500


def registrar_cors(app: Flask) -> None:
    """CORS simples para o frontend em desenvolvimento (sem dependência extra)."""
    origens = [
        origem.strip().rstrip("/")
        for origem in app.config.get("CORS_ORIGINS", "").split(",")
        if origem.strip()
    ]

    @app.after_request
    def adicionar_cabecalhos_cors(resposta):
        origem = request.headers.get("Origin")
        if origem and (origem.rstrip("/") in origens or "*" in origens):
            resposta.headers["Access-Control-Allow-Origin"] = origem
            resposta.headers["Access-Control-Allow-Credentials"] = "true"
            resposta.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resposta.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PATCH, DELETE, OPTIONS"
            )
            resposta.headers["Vary"] = "Origin"
        return resposta
