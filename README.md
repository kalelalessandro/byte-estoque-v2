# Byte Estoque

Passo a passo para rodar o projeto localmente. Os comandos partem da raiz do
projeto (`byte-estoque-v2/`).

## Pré-requisitos

- Docker Desktop instalado e aberto
- [uv](https://docs.astral.sh/uv/) instalado

## 1. Banco de dados

```powershell
cd database

# só na primeira vez
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

docker compose up -d
docker compose ps   # aguarde o status "healthy"
```

## 2. API

```powershell
cd backend
uv run python -m src.app.main
```

A API sobe em `http://127.0.0.1:5000`. Na primeira execução o uv cria o ambiente
e instala as dependências automaticamente.

## 3. Confirme que está no ar

Em outro terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

## Parar

```powershell
cd database
docker compose stop
```
