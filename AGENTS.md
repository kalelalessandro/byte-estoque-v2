# AGENTS.md — Diretrizes e Contexto do Agente de IA

## 1. Visão Geral do Projeto
Sistema SaaS Multi-tenant de **CRM, Controle de Estoque e Gestão Financeira** (`byte-estoque-v2`).
- **Backend:** Python com **Flask**.
- **Banco de Dados:** **MySQL 8.0+** rodando em container Docker (100% pronto e em execução).
- **Escopo Atual:** Finalizar exclusivamente o módulo de **Autenticação (Login e Cadastro/Signup)** e gerar um documento Markdown com sugestões de testes para `pytest`.

---

## 2. Regras Estritas de Escopo e Pastas (LEIA PRIMEIRO)

1. **PASTAS IGNORADAS (PROIBIDO LER OU EDITAR):**
   - Ignore completamente o diretório `crm-estoque/` (e qualquer variação como `CRM-Estoque/`).
   - Ignore a pasta `database/migrations/` e qualquer arquivo de seed (`02_seed.sql`), pois serão removidos/desconsiderados.
2. **BANCO DE DADOS IMUTÁVEL NA ESTRUTURA:**
   - O banco de dados MySQL já está rodando via Docker (`database/docker-compose.yml`) com o schema inicial (`database/init/01_schema.sql`).
   - **NÃO** altere arquivos `.sql`, **NÃO** crie migrations e **NÃO** modifique o `docker-compose.yml`.
3. **ESTRUTURA DE DIRETÓRIOS RESPEITADA:**
   - Trabalhe dentro da arquitetura existente em `backend/src/app/`:
     - `backend/src/app/__init__.py` e `backend/src/app/main.py` (Inicialização do Flask, Blueprints e configurações).
     - `backend/src/app/db/` (Configuração de conexão com o MySQL rodando no Docker, lendo variáveis do `.env` baseadas em `database/.env.example`).
     - `backend/src/app/core/login.py` (Lógica, validações e rotas de Login / Sessão / Token).
     - `backend/src/app/core/signup.py` (Lógica, validações e rotas de Cadastro de Empresa e Usuário).
   - *Atenção:* Caso encontre arquivos nomeados `init.py` (sem underlines) dentro de `backend/`, renomeie-os para `__init__.py` para garantir o funcionamento correto dos pacotes Python.

---

## 3. Schema do Banco de Dados (Contexto de Autenticação)

O banco chama-se `crm_estoque` (`utf8mb4_0900_ai_ci`). As tabelas envolvidas no Login/Cadastro possuem a seguinte estrutura exata no MySQL:

```sql
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