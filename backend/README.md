# Backend — API de Autenticação (Flask)

API responsável pelo **cadastro** (empresa + primeiro usuário) e **login** do
Byte Estoque. Responde em JSON e usa sessão por cookie do Flask.

- Flask 3.1 + SQLAlchemy 2.1 (ORM) + PyMySQL (driver) + python-dotenv
- Banco: MySQL 8.0 no Docker (`database/docker-compose.yml`), schema imutável
- Senhas: hash `scrypt` via `werkzeug.security` (nunca texto puro)

---

## Como rodar

Pré-requisitos: **banco no ar** e o `database/.env` criado (veja o README da raiz).

```powershell
cd backend

# 1) Criar a venv (só na primeira vez)
python -m venv .venv

# 2) Instalar as dependências
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# (se o pip falhar por causa do sandbox, use o uv:
#  uv pip install --python .venv\Scripts\python.exe -r requirements.txt)

# 3) Subir a API
.\.venv\Scripts\python.exe -m src.app.main
```

A API sobe em **http://127.0.0.1:5000**. Para conferir banco + app:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

> Configure `backend/.env` (copie de `backend/.env.example`) se quiser trocar a
> `FLASK_SECRET_KEY`, a porta ou as origens de CORS. As credenciais do MySQL
> continuam vindo de `database/.env`.

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

### `POST /api/auth/cadastro`

Corpo (JSON):

```json
{
  "empresa": {
    "razao_social": "Byte Estoque Ltda",
    "cnpj": "12.345.678/0001-90",
    "cep": "01310-100",
    "inscricao": "123.456.789.000",
    "telefone_empresa": "(11) 4000-1000"
  },
  "usuario": {
    "nome": "Maria Silva",
    "email": "maria@byteestoque.com",
    "senha": "senha123",
    "telefone": "(11) 99999-0000",
    "cargo": "Administrador"
  }
}
```

- `empresa.razao_social`: obrigatório, até 150 caracteres
- `empresa.cnpj`: obrigatório, **14 dígitos** (pontuação é descartada)
- `empresa.cep`: opcional, 8 dígitos · `empresa.inscricao`: opcional, até 30
- `empresa.telefone_empresa` / `usuario.telefone`: opcionais, 10 ou 11 dígitos
- `usuario.nome`: obrigatório, até 150
- `usuario.email`: obrigatório, único no sistema
- `usuario.senha`: obrigatória, mínimo 6 caracteres
- `usuario.cargo`: opcional (padrão **Administrador**; é criado em `cargos` se não existir)

Resposta **201**:

```json
{
  "ok": true,
  "mensagem": "Cadastro realizado com sucesso.",
  "dados": {
    "empresa": { "id_empresa": 1, "razao_social": "...", "cnpj": "12345678000190", "..." : "..." },
    "usuario": { "id_usuario": 1, "nome": "...", "email": "...", "cargo": "Administrador" }
  }
}
```

### `POST /api/auth/login`

```json
{ "email": "maria@byteestoque.com", "senha": "senha123" }
```

Resposta **200** com `Set-Cookie` da sessão (vale 8 horas):

```json
{
  "ok": true,
  "mensagem": "Login realizado com sucesso.",
  "dados": { "id_usuario": 1, "nome": "...", "email": "...", "cargo": "Administrador", "empresa": { "...": "..." } }
}
```

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

## Testando rapidamente (PowerShell)

```powershell
# Cadastro (guarda os cookies da sessão em $sessao)
$sessao = $null
$cadastro = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/auth/cadastro `
  -ContentType 'application/json' -SessionVariable sessao -Body (@{
    empresa = @{ razao_social = 'Byte Estoque Ltda'; cnpj = '12345678000190' }
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

---

## Estrutura

```
backend/
├── requirements.txt
├── .env.example
└── src/app/
    ├── __init__.py          # create_app, config, CORS, health, handlers de erro
    ├── main.py              # ponto de entrada (python -m src.app.main)
    ├── core/
    │   ├── login.py         # POST /login, POST /logout, GET /me
    │   ├── signup.py        # POST /cadastro (empresa + usuário)
    │   └── auth_utils.py    # respostas JSON, serialização, login_obrigatorio
    └── db/
        ├── __init__.py      # engine + scoped_session
        └── models.py        # mapeamento ORM de empresas, cargos, usuarios
```

## Limitações conhecidas (projeto de faculdade)

- Sessão por cookie: `SECRET_KEY` de desenvolvimento se `FLASK_SECRET_KEY` não for definida.
- Sem CSRF explícito, sem rate limit e sem verificação de e-mail.
- `admin_sistema` fica `false` para todo usuário criado pelo cadastro público.
- Não há recuperação de senha nem troca de senha ainda.
