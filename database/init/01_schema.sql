-- =============================================================================
-- Byte Estoque - Schema do banco de dados (MySQL 8.0)
-- =============================================================================
-- Fonte da verdade: crm-estoque/docs/schema_bd.md (documentacao v1.1).
-- Este arquivo eh a transcricao EXATA do bloco SQL daquele documento, mais os
-- comandos de sessao necessarios para a execucao automatica pelo container.
--
-- Contem 13 tabelas: empresas, cargos, usuarios, parceiros, interacoes,
-- categorias, produtos, operacoes, operacao_itens, caixas, operacoes_caixa,
-- titulos_financeiros, baixas_financeiras.
--
-- Requisitos: MySQL 8.0.16+ (por causa das restricoes CHECK).
-- =============================================================================

-- Garante que a leitura deste arquivo seja interpretada como UTF-8.
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS crm_estoque
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE crm_estoque;

CREATE TABLE empresas (
    id_empresa INT NOT NULL AUTO_INCREMENT,
    razao_social VARCHAR(150) NOT NULL,
    cnpj VARCHAR(14) NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cep VARCHAR(8) NULL,
    inscricao VARCHAR(30) NULL,
    telefone_empresa VARCHAR(20) NULL,
    PRIMARY KEY (id_empresa),
    CONSTRAINT uq_empresas_cnpj UNIQUE (cnpj)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE cargos (
    id_cargo INT NOT NULL AUTO_INCREMENT,
    cargo VARCHAR(50) NOT NULL,
    PRIMARY KEY (id_cargo),
    CONSTRAINT uq_cargos_cargo UNIQUE (cargo)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE usuarios (
    id_usuario INT NOT NULL AUTO_INCREMENT,
    id_empresa INT NOT NULL,
    id_cargo INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,
    telefone VARCHAR(20) NULL,
    hash_senha VARCHAR(255) NOT NULL,
    admin_sistema BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id_usuario),
    CONSTRAINT uq_usuarios_email UNIQUE (email),
    CONSTRAINT chk_usuarios_admin_sistema CHECK (admin_sistema IN (0, 1)),
    CONSTRAINT fk_usuarios_empresa
        FOREIGN KEY (id_empresa) REFERENCES empresas (id_empresa)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_usuarios_cargo
        FOREIGN KEY (id_cargo) REFERENCES cargos (id_cargo)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE parceiros (
    id_parceiro INT NOT NULL AUTO_INCREMENT,
    id_empresa INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    documento VARCHAR(14) NULL,
    email VARCHAR(254) NULL,
    cep VARCHAR(8) NULL,
    e_cliente BOOLEAN NOT NULL DEFAULT FALSE,
    e_fornecedor BOOLEAN NOT NULL DEFAULT FALSE,
    observacao TEXT NULL,
    PRIMARY KEY (id_parceiro),
    CONSTRAINT uq_parceiros_empresa_email UNIQUE (id_empresa, email),
    CONSTRAINT uq_parceiros_empresa_documento UNIQUE (id_empresa, documento),
    CONSTRAINT chk_parceiros_e_cliente CHECK (e_cliente IN (0, 1)),
    CONSTRAINT chk_parceiros_e_fornecedor CHECK (e_fornecedor IN (0, 1)),
    CONSTRAINT chk_parceiros_relacionamento CHECK (e_cliente = TRUE OR e_fornecedor = TRUE),
    CONSTRAINT chk_parceiros_email CHECK (email IS NULL OR CHAR_LENGTH(TRIM(email)) > 0),
    CONSTRAINT chk_parceiros_documento CHECK (documento IS NULL OR CHAR_LENGTH(TRIM(documento)) > 0),
    CONSTRAINT fk_parceiros_empresa
        FOREIGN KEY (id_empresa) REFERENCES empresas (id_empresa)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE interacoes (
    interacao_id INT NOT NULL AUTO_INCREMENT,
    id_parceiro INT NOT NULL,
    id_usuario INT NOT NULL,
    ocorrencia DATE NOT NULL,
    canal VARCHAR(30) NOT NULL,
    descricao TEXT NOT NULL,
    PRIMARY KEY (interacao_id),
    CONSTRAINT fk_interacoes_parceiro
        FOREIGN KEY (id_parceiro) REFERENCES parceiros (id_parceiro)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_interacoes_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE categorias (
    id_categoria INT NOT NULL AUTO_INCREMENT,
    id_empresa INT NOT NULL,
    nome VARCHAR(100) NOT NULL,
    PRIMARY KEY (id_categoria),
    CONSTRAINT uq_categorias_empresa_nome UNIQUE (id_empresa, nome),
    CONSTRAINT uq_categorias_id_empresa UNIQUE (id_categoria, id_empresa),
    CONSTRAINT fk_categorias_empresa
        FOREIGN KEY (id_empresa) REFERENCES empresas (id_empresa)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE produtos (
    id_produto INT NOT NULL AUTO_INCREMENT,
    id_empresa INT NOT NULL,
    sku VARCHAR(64) NOT NULL,
    id_categoria INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    descricao VARCHAR(500) NULL,
    unidade_estoque INT NOT NULL DEFAULT 0,
    preco DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (id_produto),
    CONSTRAINT uq_produtos_empresa_sku UNIQUE (id_empresa, sku),
    CONSTRAINT chk_produtos_estoque CHECK (unidade_estoque >= 0),
    CONSTRAINT chk_produtos_preco CHECK (preco >= 0),
    CONSTRAINT fk_produtos_empresa
        FOREIGN KEY (id_empresa) REFERENCES empresas (id_empresa)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_produtos_categoria
        FOREIGN KEY (id_categoria, id_empresa) REFERENCES categorias (id_categoria, id_empresa)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE operacoes (
    id_operacao INT NOT NULL AUTO_INCREMENT,
    id_parceiro INT NOT NULL,
    id_usuario INT NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    ocorrencia DATETIME NOT NULL,
    observacoes TEXT NULL,
    PRIMARY KEY (id_operacao),
    CONSTRAINT fk_operacoes_parceiro
        FOREIGN KEY (id_parceiro) REFERENCES parceiros (id_parceiro)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_operacoes_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE operacao_itens (
    id_operacao INT NOT NULL,
    id_produto INT NOT NULL,
    quantidade INT NOT NULL,
    valor_unitario DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (id_operacao, id_produto),
    CONSTRAINT chk_operacao_itens_quantidade CHECK (quantidade > 0),
    CONSTRAINT chk_operacao_itens_valor_unitario CHECK (valor_unitario >= 0),
    CONSTRAINT fk_operacao_itens_operacao
        FOREIGN KEY (id_operacao) REFERENCES operacoes (id_operacao)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_operacao_itens_produto
        FOREIGN KEY (id_produto) REFERENCES produtos (id_produto)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE caixas (
    id_caixa INT NOT NULL AUTO_INCREMENT,
    aberto_por_usuario INT NOT NULL,
    aberto_em DATETIME NOT NULL,
    valor_abertura DECIMAL(12,2) NOT NULL,
    fechado_em DATETIME NULL,
    valor_contado DECIMAL(12,2) NULL,
    PRIMARY KEY (id_caixa),
    CONSTRAINT chk_caixas_valor_abertura CHECK (valor_abertura >= 0),
    CONSTRAINT chk_caixas_valor_contado CHECK (valor_contado IS NULL OR valor_contado >= 0),
    CONSTRAINT chk_caixas_fechamento CHECK (
        (fechado_em IS NULL AND valor_contado IS NULL)
        OR
        (fechado_em IS NOT NULL AND valor_contado IS NOT NULL AND fechado_em >= aberto_em)
    ),
    CONSTRAINT fk_caixas_usuario_abertura
        FOREIGN KEY (aberto_por_usuario) REFERENCES usuarios (id_usuario)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE operacoes_caixa (
    movimento_id INT NOT NULL AUTO_INCREMENT,
    id_caixa INT NOT NULL,
    id_usuario INT NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    ocorrencia DATETIME NOT NULL,
    descricao TEXT NULL,
    PRIMARY KEY (movimento_id),
    CONSTRAINT chk_operacoes_caixa_valor CHECK (valor > 0),
    CONSTRAINT fk_operacoes_caixa_caixa
        FOREIGN KEY (id_caixa) REFERENCES caixas (id_caixa)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_operacoes_caixa_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios (id_usuario)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE titulos_financeiros (
    id_titulo INT NOT NULL AUTO_INCREMENT,
    id_parceiro INT NOT NULL,
    id_operacao INT NULL,
    tipo VARCHAR(30) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    descricao VARCHAR(500) NOT NULL,
    vencimento DATE NOT NULL,
    cancelado BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id_titulo),
    CONSTRAINT chk_titulos_financeiros_valor CHECK (valor > 0),
    CONSTRAINT chk_titulos_financeiros_cancelado CHECK (cancelado IN (0, 1)),
    CONSTRAINT fk_titulos_financeiros_parceiro
        FOREIGN KEY (id_parceiro) REFERENCES parceiros (id_parceiro)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_titulos_financeiros_operacao
        FOREIGN KEY (id_operacao) REFERENCES operacoes (id_operacao)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE baixas_financeiras (
    id_baixa INT NOT NULL AUTO_INCREMENT,
    id_titulo INT NOT NULL,
    id_caixa INT NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    realizado_em DATETIME NOT NULL,
    forma_pagamento VARCHAR(30) NOT NULL,
    PRIMARY KEY (id_baixa),
    CONSTRAINT chk_baixas_financeiras_valor CHECK (valor > 0),
    CONSTRAINT fk_baixas_financeiras_titulo
        FOREIGN KEY (id_titulo) REFERENCES titulos_financeiros (id_titulo)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_baixas_financeiras_caixa
        FOREIGN KEY (id_caixa) REFERENCES caixas (id_caixa)
        ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
-- =============================================================================
-- Fim do schema. Os dados de exemplo ficam em 02_seed.sql.
-- =============================================================================
