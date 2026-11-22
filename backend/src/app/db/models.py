"""Modelos ORM das tabelas usadas pelo projeto.

O schema do banco é imutável (ver AGENTS.md): este módulo apenas MAPEIA as
tabelas existentes em ``database/init/01_schema.sql``. Nunca chamamos
``Base.metadata.create_all()`` — quem cria as tabelas é o container Docker.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
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


class Parceiro(Base):
    """Cliente e/ou fornecedor de uma empresa (tabela ``parceiros``).

    - ``documento`` (CPF/CNPJ sem pontuação) e ``email`` são únicos POR EMPRESA
      quando informados; ausência é ``NULL`` (nunca texto vazio).
    - Pelo menos um entre ``e_cliente`` e ``e_fornecedor`` deve ser verdadeiro
      (CHECK do banco); os dois podem ser verdadeiros.
    """

    __tablename__ = "parceiros"

    id_parceiro: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id_empresa"))
    nome: Mapped[str] = mapped_column(String(150))
    documento: Mapped[str | None] = mapped_column(String(14))
    email: Mapped[str | None] = mapped_column(String(254))
    cep: Mapped[str | None] = mapped_column(String(8))
    e_cliente: Mapped[bool] = mapped_column(Boolean, default=False)
    e_fornecedor: Mapped[bool] = mapped_column(Boolean, default=False)
    observacao: Mapped[str | None] = mapped_column(Text)


class Interacao(Base):
    """Fato comercial registrado com um parceiro (tabela ``interacoes``).

    Contratos e compras: venda a cliente, reembolso, contrato de fornecimento,
    pagamento a fornecedor... O tipo do fato fica em ``canal`` (nome do schema).
    ``id_usuario`` é o responsável pelo registro. O banco só confere que o
    parceiro e o usuário EXISTEM; a aplicação garante que são da mesma empresa.
    """

    __tablename__ = "interacoes"

    interacao_id: Mapped[int] = mapped_column(primary_key=True)
    id_parceiro: Mapped[int] = mapped_column(ForeignKey("parceiros.id_parceiro"))
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"))
    ocorrencia: Mapped[date] = mapped_column(Date)
    canal: Mapped[str] = mapped_column(String(30))
    descricao: Mapped[str] = mapped_column(Text)


class TituloFinanceiro(Base):
    """Valor a pagar ou a receber (tabela ``titulos_financeiros``).

    ``id_parceiro`` é opcional no schema (lançamentos sem parceiro existem); a tela de
    baixas financeiras só liquida títulos COM parceiro. ``tipo`` é controlado pela
    aplicação: "a pagar" ou "a receber".
    """

    __tablename__ = "titulos_financeiros"

    id_titulo: Mapped[int] = mapped_column(primary_key=True)
    id_parceiro: Mapped[int | None] = mapped_column(ForeignKey("parceiros.id_parceiro"))
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id_empresa"))
    id_operacao: Mapped[int | None] = mapped_column()
    tipo: Mapped[str] = mapped_column(String(30))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    descricao: Mapped[str] = mapped_column(String(500))
    vencimento: Mapped[date] = mapped_column(Date)
    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)


class Caixa(Base):
    """Sessão de caixa (tabela ``caixas``). Aberta enquanto ``fechado_em`` é NULL.

    Não há ``id_empresa``: a empresa da sessão é a de ``aberto_por_usuario``.
    """

    __tablename__ = "caixas"

    id_caixa: Mapped[int] = mapped_column(primary_key=True)
    aberto_por_usuario: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"))
    aberto_em: Mapped[datetime] = mapped_column(DateTime)
    valor_abertura: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime)
    valor_contado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class BaixaFinanceira(Base):
    """Pagamento ou recebimento efetivo de um título (tabela ``baixas_financeiras``).

    Saldo pendente do título = valor do título - soma das baixas. Toda baixa pertence a
    uma sessão de caixa (``id_caixa`` NOT NULL).
    """

    __tablename__ = "baixas_financeiras"

    id_baixa: Mapped[int] = mapped_column(primary_key=True)
    id_titulo: Mapped[int] = mapped_column(ForeignKey("titulos_financeiros.id_titulo"))
    id_caixa: Mapped[int] = mapped_column(ForeignKey("caixas.id_caixa"))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    realizado_em: Mapped[datetime] = mapped_column(DateTime)
    forma_pagamento: Mapped[str] = mapped_column(String(30))


class OperacaoCaixa(Base):
    """Movimento adicional de caixa: suprimento (entrada) ou sangria (saída).

    Tabela ``operacoes_caixa``. Pagamentos e recebimentos de títulos NÃO entram aqui:
    ficam em ``baixas_financeiras`` (o mesmo evento não pode estar nas duas tabelas).
    ``tipo`` é controlado pela aplicação: "suprimento" ou "sangria".
    """

    __tablename__ = "operacoes_caixa"

    movimento_id: Mapped[int] = mapped_column(primary_key=True)
    id_caixa: Mapped[int] = mapped_column(ForeignKey("caixas.id_caixa"))
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"))
    tipo: Mapped[str] = mapped_column(String(30))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    ocorrencia: Mapped[datetime] = mapped_column(DateTime)
    descricao: Mapped[str | None] = mapped_column(Text)
