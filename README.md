Byte Estoque é um software CRM que tem como principal objetivo, unir ambas funcionalidades de um CRM e um software de Estoque.

Planos:

    Banco de dados ✅
    Login ✅
    Conectar Backend com BD ✅
    Criptografia ✅
    Caixa
    Clientes
    Compras
    Dashboard
    Relatórios

Planos Futuros:

    Assinatura

## Passo a passo para rodar o BD:

Pré-requisito: ter o [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e aberto.

Entre na pasta `database/` pelo terminal:

```powershell
cd database
```

Crie o arquivo de senhas a partir do modelo:

```powershell
Copy-Item .env.example .env
```

Abra o `.env` e troque as duas senhas de exemplo por senhas suas.

Suba o banco:

```powershell
docker compose up -d
```

Na primeira vez ele baixa a imagem do MySQL (alguns minutos). Confirme que subiu:

```powershell
docker compose ps
```

Deve aparecer `running` e `healthy`. Se ainda estiver `starting`, aguarde uns 30 segundos e rode de novo.

O banco já vem com as tabelas criadas e dados de exemplo.

## Conectando no banco

| | |
|---|---|
| Host | `127.0.0.1` |
| Porta | `3306` |
| Banco | `crm_estoque` |
| Usuário | `app_crm` |
| Senha | a que você colocou em `MYSQL_PASSWORD` no `.env` |

## Comandos úteis

```powershell
docker compose stop      # para o banco
docker compose start     # liga de novo
docker compose down      # remove o container, mas os dados continuam salvos
docker compose down -v   # apaga tudo, inclusive os dados
```

## Rodando o backend (API de cadastro/login)

Pré-requisito: banco no ar (passo anterior). Na pasta `backend/`:

```powershell
cd backend

# Só na primeira vez: criar a venv e instalar as dependências
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Subir a API (http://127.0.0.1:5000)
.\.venv\Scripts\python.exe -m src.app.main
```

Rotas disponíveis: `POST /api/auth/cadastro`, `POST /api/auth/login`,
`POST /api/auth/logout`, `GET /api/auth/me` e `GET /api/health`.
Detalhes de payload, códigos de retorno e exemplos: [backend/README.md](backend/README.md).
