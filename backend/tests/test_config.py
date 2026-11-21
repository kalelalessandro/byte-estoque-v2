"""Teste de regressão da configuração do hash de senha.

O cadastro usa scrypt em produção. O app de teste sobrescreve o método para
PBKDF2 rápido, mas uma aplicação criada sem essa sobrescrita precisa continuar
tendo um método válido (nunca ``None``).
"""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from src.app import create_app


def test_hash_de_senha_tem_metodo_padrao_valido():
    app = create_app({"TESTING": True, "DEBUG": False})
    metodo = app.config.get("SENHA_HASH_METODO")

    assert isinstance(metodo, str) and metodo

    hash_gerado = generate_password_hash("Senha#Teste1", method=metodo)
    assert check_password_hash(hash_gerado, "Senha#Teste1")
