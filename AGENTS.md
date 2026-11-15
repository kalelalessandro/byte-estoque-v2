# AGENTS.md — Diretrizes e Contexto do Agente de IA

> **Versão atual (V2).** Este arquivo substitui a versão antiga, que pedia para
> ignorar `crm-estoque/` e tratava o módulo de autenticação como pendente. Agora
> o login/cadastro está implementado e o foco é a **suíte de testes com pytest**
> baseada em `crm-estoque/docs/plano de testes.pdf` (V1.2).

## 1. Visão Geral do Projeto

Sistema SaaS multi-tenant de **CRM, Controle de Estoque e Gestão Financeira**
(`byte-estoque-v2`).

- **Backend:** Python + **Flask** (API JSON).
- **Banco de Dados:** **MySQL 8.0+** em container Docker
  (`database/docker-compose.yml`, schema em `database/init/01_schema.sql`).
- **Frontend:** ainda não implementado (a pasta `frontend/` está vazia).
- **Status atual:**
  - ✅ Banco de dados (Docker + schema).
  - ✅ Login/cadastro de usuário e empresa (API Flask).
  - ✅ Testes automatizados de autenticação com `pytest` (79 passed, 4 skipped).
  - ⏳ Demais módulos (produtos, parceiros, financeiro, caixa, etc.).

## 2. Regras Estritas de Escopo e Pastas

1. **Banco de dados imutável na estrutura:**
   - **NÃO** altere `database/init/01_schema.sql`, **NÃO** crie migrations e
     **NÃO** modifique `database/docker-compose.yml`.
   - **NÃO** edite `database/init/02_seed.sql` (dados de exemplo são
     desconsiderados).
   - Dados podem ser inseridos/lidos pela aplicação e pelos testes; a estrutura
     não muda.
2. **Onde trabalhar:**
   - `backend/src/app/` — código da API:
     - `__init__.py` / `main.py`: fábrica do Flask, configurações, blueprints.
     - `db/`: engine SQLAlchemy (`mysql+pymysql`) e modelos ORM.
     - `core/login.py`: login, logout e sessão.
     - `core/signup.py`: cadastro de empresa + primeiro usuário.
     - `core/auth_utils.py`: respostas JSON, serialização e `login_obrigatorio`.
   - `backend/tests/` — testes `pytest` (ver seção 5).
   - `backend/README.md` e `backend/tests/README.md` — documentação.
3. **`crm-estoque/` é material de referência antigo:**
   - **Pode ler** a documentação, principalmente
     `crm-estoque/docs/plano de testes.pdf` (fonte de verdade dos casos de teste)
     e `crm-estoque/docs/` (fluxograma, schema documentado).
   - **NÃO edite** nada em `crm-estoque/` e **não** copie código de lá: a API
     atual fica em `backend/`.
   - O PDF do plano não deve ser alterado; se precisar extrair texto, use uma
     biblioteca em memória (`pypdf`) e descarte o arquivo temporário.
4. **Instalações:** o usuário pediu explicitamente para **pedir permissão antes
   de instalar qualquer dependência**. Use a venv `backend/.venv`; nunca instale
   no Python global. (Ferramentas como `uv` podem ser usadas para instalar na
   venv, com autorização.)
5. **Idioma:** mensagens da API, testes, docstrings e documentação em português.

## 3. Módulo de Autenticação (implementado)

### Rotas (`/api/auth`)

| Método | Rota | Auth | Função |
|---|---|---|---|
| GET | `/` | não | Lista as rotas da API |
| GET | `/api/health` | não | Status da API + conexão MySQL |
| POST | `/api/auth/cadastro` | não | Cria empresa + primeiro usuário (mesma transação) |
| POST | `/api/auth/login` | não | Valida e-mail/senha e cria a sessão (cookie, 8h) |
| POST | `/api/auth/logout` | não | Encerra a sessão |
| GET | `/api/auth/me` | **sim** | Usuário logado + empresa |

### Decisões e regras importantes

- **Cadastro é uma única operação**: `usuarios.id_empresa` é `NOT NULL`, então
  não existe "usuário sem empresa". O payload tem `empresa` e `usuario`.
- **Senha**: hash `scrypt` com `werkzeug.security`; nunca texto puro.
- **Sessão**: cookie assinado do Flask (`SECRET_KEY`); `session.clear()` antes do
  login e `SameSite=Lax`.
- **CNPJ (premissa do plano V1.2)**: 14 caracteres; 12 alfanuméricos
  `[0-9A-Z]` + 2 dígitos verificadores numéricos. Máscara `.` `/` `-`/espaços é
  removida, letras viram maiúsculas e os DVs são conferidos por **módulo 11**
  (valor do caractere = ASCII − 48). CNPJ com todos os caracteres iguais é
  rejeitado.
- **E-mail**: `trim` + minúsculo, formato validado, único globalmente.
- **Telefones**: textos opcionais de até **20 caracteres** (máscara preservada).
- **Razão social/inscrição/CEP**: `trim`; razão social ≤150, inscrição ≤30,
  CEP 8 dígitos após máscara.
- **Cargo**: padrão `Administrador`, criado em `cargos` se não existir.
- **Status codes**: 201 cadastro, 200 login/health, 401 credenciais/sessão,
  404/405 rotas, 409 duplicidade, 415 content-type, 422 validação, 503 banco fora.
- Formato de resposta: `{"ok": true, "mensagem": ..., "dados": ...}` ou
  `{"ok": false, "erro": ..., "campos": {...}}`.

### Schema envolvido (não alterar)

- `empresas` (id_empresa, razao_social, cnpj UNIQUE, criado_em, cep, inscricao,
  telefone_empresa).
- `cargos` (id_cargo, cargo UNIQUE).
- `usuarios` (id_usuario, id_empresa FK, id_cargo FK, nome, email UNIQUE,
  telefone, hash_senha, admin_sistema BOOLEAN).

## 4. Como rodar o projeto

Pré-requisitos: Docker Desktop aberto, banco no ar e
[uv instalado](https://docs.astral.sh/uv/getting-started/installation/).

```powershell
# Banco (na pasta database/)
cd database
docker compose up -d
docker compose ps          # deve aparecer healthy

# API (na pasta backend/)
cd ..\backend
uv sync                     # cria/atualiza backend/.venv a partir do uv.lock
uv run python -m src.app.main   # http://127.0.0.1:5000
```

Conferir: `Invoke-RestMethod http://127.0.0.1:5000/api/health`.

### Ambiente virtual e dependências (uv)

- **Fonte da verdade:** `backend/pyproject.toml` (dependências + grupo `dev` com
  pytest) e `backend/uv.lock` (versões travadas, versionado no Git).
- `backend/.venv` é criada/reparada pelo `uv sync` e **não** vai para o Git.
  Em um clone novo, basta `uv sync`.
- Adicionar dependência: `uv add <pacote>`; dev: `uv add --dev <pacote>`.
  Rode `uv lock` se editar o `pyproject.toml` manualmente.
- Rodar comandos: `uv run <comando>` (ex.: `uv run pytest`,
  `uv run python -m src.app.main`). Não é necessário ativar a venv.
- Instalar `uv` (se faltar) exige **pedir permissão ao usuário** antes.

## 5. Testes automatizados (pytest)

- **Plano de testes:** `crm-estoque/docs/plano de testes.pdf` (V1.2).
- **Escopo coberto:** módulos **LOG** (31 casos), **EMP** (38 casos) e casos
  correlatos de autenticação: COL-N01, SEG-N11/N12, BDD-P01/P02/P07/P08,
  BDD-N01/N05/N06, FKN-N01/N02, INTG-N01/N11.
- **Total:** 83 casos mapeados → **79 passed + 4 skipped** (skips justificados
  em `backend/tests/README.md`).
- **Arquitetura da suíte:**
  - `tests/conftest.py`: fixtures `app` (session), `client` e `banco_limpo`
    (autouse) que apaga somente dados criados pelos testes antes/depois.
  - `tests/helpers.py`: payloads válidos, `cadastrar`, `criar_conta`, `entrar`,
    `me`, registro de e-mails/CNPJs criados.
  - `tests/test_login.py`: LOG + COL/SEG.
  - `tests/test_cadastro_empresa.py`: EMP.
  - `tests/test_integridade_banco_auth.py`: BDD/FKN/INTG (SQL direto, marker
    `banco`).
- **Regras para novos testes:**
  1. Nomear referenciando o ID do plano (ex.: `test_log_n05_login_senha_incorreta`).
  2. Rodar contra o MySQL real (sem mock); usar `client`/`app` do conftest.
  3. Dados de teste: e-mails `@exemplo.com.br`, CNPJs do plano ou prefixo `BD`;
     nunca apagar dados de demonstração.
  4. Registrar dados criados via API em `EMAILS_CRIADOS`/`CNPJS_CRIADOS` (feito
     automaticamente por `helpers.cadastrar`).
  5. Teste que depende de frontend/estado impossível no schema deve ser marcado
     com `pytest.mark.skip(reason=...)` e documentado.
- **Comandos:**

```powershell
cd backend
uv sync                        # instala runtime + pytest (grupo dev)
uv run pytest                  # suíte completa
uv run pytest -v               # nome de cada caso
uv run pytest -m banco         # só SQL direto
uv run pytest -k "LOG-N"       # filtra por ID
```

- A configuração do pytest fica em `backend/pyproject.toml`
  (`testpaths = tests`, `pythonpath = .`, cache desabilitado). Rode a partir de
  `backend/`.

## 6. Pendências / Próximas etapas

- Implementar os demais módulos da API (produtos, parceiros, financeiro, caixa,
  operações) e só então seus casos do plano (`USR`, `CAT`, `PRD`, `PAR`, `INT`,
  `OPE`, `TIT`, `BAI`, `CXA`, `CAR`, `INTG-N02..N04`, etc.).
- Frontend para as telas do fluxograma (Tela Principal, Cadastro de Empresa).
- Casos do plano que dependem de frontend permanecem `skip` até lá.
- Manter este AGENTS.md atualizado quando o escopo mudar.
