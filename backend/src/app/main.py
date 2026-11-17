"""Ponto de entrada de desenvolvimento da API do Byte Estoque.

Como rodar (a partir da pasta ``backend/``):

    .venv\\Scripts\\python.exe -m src.app.main

A API sobe em http://127.0.0.1:5000 e o banco MySQL deve estar no ar
(``docker compose up -d`` dentro de ``database/``).
"""

import os

from . import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_RUN_PORT", "5000")),
        debug=app.config["DEBUG"],
        threaded=True,
    )
