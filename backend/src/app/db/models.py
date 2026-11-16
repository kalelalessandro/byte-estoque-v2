"""Modelos ORM das tabelas usadas pelo projeto.

O schema do banco é imutável (ver AGENTS.md): este módulo apenas MAPEIA as
tabelas existentes em ``database/init/01_schema.sql``. Nunca chamamos
``Base.metadata.create_all()`` — quem cria as tabelas é o container Docker.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarativa do SQLAlchemy para todos os modelos do projeto."""


class Empresa(Base):
    __tablename__ = "empresas"

    id_empresa: Mapped[int] = mapped_column(primary_key=True)
    razao_social: Mapped[str] = mapped_column(String(150))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    cep: Mapped[str | None] = mapped_column(String(8))
    inscricao: Mapped[str | None] = mapped_column(String(30))
    telefone_empresa: Mapped[str | None] = mapped_column(String(20))

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="empresa")


class Cargo(Base):
    __tablename__ = "cargos"

    id_cargo: Mapped[int] = mapped_column(primary_key=True)
    cargo: Mapped[str] = mapped_column(String(50), unique=True)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="cargo")


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id_empresa"))
    id_cargo: Mapped[int] = mapped_column(ForeignKey("cargos.id_cargo"))
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    telefone: Mapped[str | None] = mapped_column(String(20))
    hash_senha: Mapped[str] = mapped_column(String(255))
    admin_sistema: Mapped[bool] = mapped_column(Boolean, default=False)

    empresa: Mapped[Empresa] = relationship(back_populates="usuarios", lazy="joined")
    cargo: Mapped[Cargo] = relationship(back_populates="usuarios", lazy="joined")


class Categoria(Base):
    __tablename__ = "categorias"

    id_categoria: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id_empresa"))
    nome: Mapped[str] = mapped_column(String(100))


class Produto(Base):
    __tablename__ = "produtos"

    id_produto: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id_empresa"))
    sku: Mapped[str] = mapped_column(String(64))
    id_categoria: Mapped[int] = mapped_column(ForeignKey("categorias.id_categoria"))
    nome: Mapped[str] = mapped_column(String(150))
    descricao: Mapped[str | None] = mapped_column(String(500))
    unidade_estoque: Mapped[int] = mapped_column(Integer, default=0)
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
