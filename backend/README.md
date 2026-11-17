# Backend — API de Autenticação (Flask)

API responsável pelo **cadastro** (empresa + primeiro usuário) e **login** do
Byte Estoque. Responde em JSON e usa sessão por cookie do Flask.

- Flask 3.1 + SQLAlchemy 2.1 (ORM) + PyMySQL (driver) + python-dotenv
- Banco: MySQL 8.0 no Docker (`database/docker-compose.yml`), schema imutável
- Senhas: hash `scrypt` via `werkzeug.security` (nunca texto puro)
- Ambiente e dependências: [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`)
- Testes: `pytest`, contra o MySQL real (veja [tests/README.md](tests/README.md))

---

## Como rodar

Pré-requisitos: **banco no ar**, `database/.env` criado (veja o README da raiz) e
[uv instalado](https://docs.astral.sh/uv/getting-started/installation/).

```powershell
cd backend

# 1) Criar/atualizar a venv (backend/.venv) e instalar as dependências
uv sync

# 2) Subir a API
uv run python -m src.app.main
```

A API sobe em **http://127.0.0.1:5000**. Para conferir banco + app:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

> Configure `backend/.env` (copie de `backend/.env.example`) se quiser trocar a
> `FLASK_SECRET_KEY`, a porta ou as origens de CORS. As credenciais do MySQL
> continuam vindo de `database/.env`.

### Gerenciamento de dependências (uv)

O `uv` cuida da venv e do lockfile — não é preciso ativar a venv manualmente:

```powershell
uv sync                 # recria/atualiza backend/.venv a partir do uv.lock
uv add <pacote>         # adiciona dependência de runtime
uv add --dev <pacote>   # adiciona dependência de desenvolvimento
uv lock                 # recalcula o uv.lock após editar o pyproject.toml
uv run <comando>        # roda um comando dentro da venv
```

Se quiser ativar a venv no terminal: `.\.venv\Scripts\Activate.ps1` e use
`python -m src.app.main` normalmente. O `pyproject.toml` é a fonte da verdade;
o `uv.lock` deve ser versionado no Git.

---

## Rotas

| Método | Rota | Autenticada | Descrição |
|---|---|---|---|
| GET | `/` | não | Lista as rotas da API |
| GET | `/api/health` | não | Status da API e conexão com o MySQL |
| POST | `/api/auth/cadastro` | não | Cria empresa + primeiro usuário |
| POST | `/api/auth/login` | não | Autentica e cria a sessão |
| POST | `/api/auth/logout` | não | Encerra a sessão |
| GET | `/api/auth/me` | **sim** | Dados do usuário logado |
| GET | `/api/dashboard/resumo` | **sim** | Resumo agregado: produtos, categorias e valor em estoque |
| POST | `/api/categorias` | **sim** | Cria uma categoria |
| GET | `/api/categorias` | **sim** | Lista as categorias da empresa |
| PATCH | `/api/categorias/<id>` | **sim** | Renomeia uma categoria |
| DELETE | `/api/categorias/<id>` | **sim** | Apaga categoria **sem produtos** (409 se houver produtos) |
| POST | `/api/produtos` | **sim** | Cria um produto |
| GET | `/api/produtos` | **sim** | Lista produtos (`busca`, `limit`, `offset`) |
| GET | `/api/produtos/<id>` | **sim** | Detalhe de um produto |
| PATCH | `/api/produtos/<id>` | **sim** | Altera SKU, categoria, nome, descrição, estoque e/ou preço |
| DELETE | `/api/produtos/<id>` | **sim** | Apaga produto (409 se houver registros vinculados) |

> Nas rotas de categorias e produtos a **empresa vem sempre da sessão**; o
> `id_empresa` enviado no JSON é recusado. Categoria e SKU são únicos por
> empresa, e a categoria do produto precisa ser da mesma empresa.

### `POST /api/auth/cadastro`

Corpo (JSON):

```json
{
  "empresa": {
    "razao_social": "Byte Estoque Ltda",
    "cnpj": "11222333000181",
    "cep": "50030-230",
    "inscricao": "IE-0012345-67",
    "telefone_empresa": "8132214455"
  },
  "usuario": {
    "nome": "Maria Silva",
    "email": "maria@byteestoque.com",
    "senha": "senha123",
    "telefone": "81987654321",
    "cargo": "Administrador"
  }
}
```

- `empresa.razao_social`: obrigatório, até 150 caracteres
- `empresa.cnpj`: obrigatório, 14 caracteres — **alfanumérico** no padrão do
  plano de testes (12 caracteres `[0-9A-Z]` + 2 dígitos verificadores
  numéricos). Máscara (`.` `/` `-` e espaços) é removida, letras viram
  maiúsculas e os **dígitos verificadores são validados** (módulo 11)
- `empresa.cep`: opcional, 8 dígitos (máscara removida)
- `empresa.inscricao`: opcional, até 30 caracteres
- `empresa.telefone_empresa` / `usuario.telefone`: opcionais, texto de até
  **20 caracteres** (a máscara digitada é preservada)
- `usuario.nome`: obrigatório, até 150
- `usuario.email`: obrigatório, único no sistema (trim + minúsculo)
- `usuario.senha`: obrigatória, mínimo 6 caracteres
- `usuario.cargo`: opcional (padrão **Administrador**; é criado em `cargos` se não existir)

Resposta **201**:

```json
{
  "ok": true,
  "mensagem": "Cadastro realizado com sucesso.",
  "dados": {
    "empresa": { "id_empresa": 1, "razao_social": "...", "cnpj": "11222333000181", "..." : "..." },
    "usuario": { "id_usuario": 1, "nome": "...", "email": "...", "cargo": "Administrador" }
  }
}
```

### `POST /api/auth/login`

```json
{ "email": "maria@byteestoque.com", "senha": "senha123" }
```

O e-mail é validado (formato), aparado e comparado sem diferenciar
maiúsculas/minúsculas; a senha diferencia maiúsculas/minúsculas.

Resposta **200** com `Set-Cookie` da sessão (vale 8 horas):

```json
{
  "ok": true,
  "mensagem": "Login realizado com sucesso.",
  "dados": {
    "id_usuario": 1,
    "nome": "...",
    "email": "...",
    "cargo": "Administrador",
    "empresa": { "id_empresa": 1, "razao_social": "...", "cnpj": "..." },
    "precisa_cadastrar_empresa": false,
    "redirecionar_para": null
  }
}
```

Regra defensiva: se um usuário autenticado não tiver empresa vinculada — algo
impossível pelo schema atual (`usuarios.id_empresa NOT NULL`), mas tratado — a
resposta traz `"empresa": null`, `"precisa_cadastrar_empresa": true` e
`"redirecionar_para": "/cadastro-empresa"`, e o front-end o envia ao cadastro
de empresa antes de liberar o sistema. A rota `GET /api/auth/me` devolve o mesmo
contexto.

### `GET /api/auth/me`

Envie o cookie de sessão. Sem sessão válida: **401**.

### Códigos de erro

| Status | Quando |
|---|---|
| `400` | JSON inválido |
| `401` | Login inválido ou rota protegida sem sessão |
| `409` | CNPJ ou e-mail já cadastrado |
| `415` | `Content-Type` diferente de `application/json` |
| `422` | Campos inválidos (detalhes em `campos`) |

Erro de validação:

```json
{
  "ok": false,
  "erro": "Dados inválidos. Corrija os campos indicados.",
  "campos": { "email": "E-mail inválido.", "senha": "A senha deve ter pelo menos 6 caracteres." }
}
```

---

## Testes automatizados

Os testes usam `pytest` + o `test_client` do Flask e rodam contra o MySQL real
do Docker. O mapeamento completo dos casos do plano de testes está em
[tests/README.md](tests/README.md).

```powershell
cd backend

# Rodar tudo (o uv sync já instala o pytest do grupo dev)
uv run pytest

# Só o módulo de login/cadastro de usuário
uv run pytest tests/test_login.py

# Ver o nome de cada caso e o status
uv run pytest -v

# Só os testes de banco (SQL direto)
uv run pytest -m banco

# Só categorias / só produtos
uv run pytest tests/test_categorias.py
uv run pytest tests/test_produtos.py
```

Resultado esperado: **148 passed, 4 skipped, 1 xfailed** (3 skips de UI/E2E da
autenticação + PRD-N22 de confirmação visual; o xfail é o LOG-P08, impossível
pelo schema `usuarios.id_empresa NOT NULL`; veja
[tests/README.md](tests/README.md)).

> A suíte limpa os dados que cria (e-mails `@exemplo.com.br`, CNPJs de teste e
> registros criados pela API) antes e depois de cada teste, sem apagar dados de
> demonstração. Ainda assim, rode com o banco de demonstração vazio para a
> apresentação.

---

## Testando rapidamente (PowerShell)

```powershell
# Cadastro (guarda os cookies da sessão em $sessao)
$sessao = $null
$cadastro = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/auth/cadastro `
  -ContentType 'application/json' -SessionVariable sessao -Body (@{
    empresa = @{ razao_social = 'Byte Estoque Ltda'; cnpj = '11222333000181' }
    usuario = @{ nome = 'Maria Silva'; email = 'maria@byteestoque.com'; senha = 'senha123' }
  } | ConvertTo-Json)

# Login (reaproveita a sessão)
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/auth/login `
  -ContentType 'application/json' -WebSession $sessao -Body (@{
    email = 'maria@byteestoque.com'; senha = 'senha123'
  } | ConvertTo-Json)

# Usuário logado
Invoke-RestMethod http://127.0.0.1:5000/api/auth/me -WebSession $sessao

# Logout
Invoke-RestMethod -Method Post http://127.0.0.1:5000/api/auth/logout -WebSession $sessao
```

> Evite rodar o exemplo duas vezes sem limpar o banco: o CNPJ/e-mail já existirá
> e a API responderá **409** (comportamento correto).

---

## Estrutura

```
backend/
├── pyproject.toml            # dependências, grupo dev e config do pytest
├── uv.lock                   # versões travadas (versionar no Git)
├── .env.example
├── src/app/
│   ├── __init__.py           # create_app, config, CORS, health, handlers de erro
│   ├── main.py               # ponto de entrada (python -m src.app.main)
│   ├── core/
│   │   ├── login.py          # POST /login, POST /logout, GET /me
│   │   ├── signup.py         # POST /cadastro (empresa + usuário)
│   │   └── auth_utils.py     # respostas JSON, serialização, login_obrigatorio
│   └── db/
│       ├── __init__.py       # engine + scoped_session
│       └── models.py         # mapeamento ORM de empresas, cargos, usuarios
└── tests/
    ├── conftest.py           # fixtures (app, client, limpeza do banco)
    ├── helpers.py            # payloads e atalhos (cadastro/login/me)
    ├── test_login.py         # LOG-Pxx / LOG-Nxx + COL/SEG correlatos
    ├── test_cadastro_empresa.py  # EMP-Pxx / EMP-Nxx
    ├── test_fluxo_empresa.py # transação atômica + contexto de empresa
    └── test_integridade_banco_auth.py  # BDD/FKN/INTG de autenticação
```

## Limitações conhecidas (projeto de faculdade)

- Sessão por cookie: `SECRET_KEY` de desenvolvimento se `FLASK_SECRET_KEY` não for definida.
- Sem CSRF explícito, sem rate limit e sem verificação de e-mail.
- `admin_sistema` fica `false` para todo usuário criado pelo cadastro público.
- Não há recuperação de senha nem troca de senha ainda.
