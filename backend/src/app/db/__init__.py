"""Conexão com o MySQL (container Docker) via SQLAlchemy + PyMySQL.

A URL de conexão é montada em ``app.create_app()`` a partir de
``database/.env``. A sessão é escopada por requisição (``scoped_session``) e
removida no fim de cada requisição pelo ``teardown_appcontext`` do Flask.
"""

from __future__ import annotations

from flask import current_app
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, scoped_session, sessionmaker


def init_db(app, url: URL) -> None:
    """Cria o engine e a fábrica de sessões e registra tudo no app Flask."""
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=280,
        pool_size=5,
        max_overflow=5,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    app.extensions["db_engine"] = engine
    app.extensions["db_session"] = scoped_session(session_factory)
    app.teardown_appcontext(_remover_sessao)


def _remover_sessao(excecao=None) -> None:
    """Devolve a conexão da requisição para o pool ao final do app context."""
    db = current_app.extensions.get("db_session")
    if db is not None:
        db.remove()


def get_engine() -> Engine:
    return current_app.extensions["db_engine"]


def get_db() -> Session:
    """Retorna a sessão SQLAlchemy da requisição atual (commit é manual)."""
    return current_app.extensions["db_session"]
