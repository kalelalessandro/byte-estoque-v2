# Byte Estoque

Passo a passo para rodar o projeto completo (banco + API + front-end) localmente.

## Pré-requisitos

- **Docker Desktop** instalado e aberto
- **[uv](https://docs.astral.sh/uv/)** instalado
- **Node.js 20.19+** ou **22.12+** (testado com Node 24) e **npm**

## 1. Banco de dados

Na raiz do projeto:

```powershell
cd database

# só na primeira vez
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

docker compose up -d
docker compose ps   # aguarde o status "healthy"
```

## 2. API — terminal 1

Deixe este terminal aberto:

```powershell
cd backend
uv run python -m src.app.main
```

A API sobe em **http://127.0.0.1:5000**. Na primeira execução o `uv` cria o
ambiente e instala as dependências automaticamente.

Para confirmar que está no ar (em outro terminal):

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

## 3. Front-end — terminal 2

Deixe este terminal aberto também:

```powershell
cd frontend

# só na primeira vez
npm install

npm run dev
```

Abra **http://localhost:5173**.

O Vite faz proxy de `/api` para a API Flask em `127.0.0.1:5000`, então o cookie
de sessão funciona sem configuração extra de CORS.

### Primeiro acesso

1. Clique em **Criar conta** e cadastre a empresa + o usuário.
2. Você entra no **Início**, com o resumo de produtos, categorias, parceiros, o dinheiro do
   último caixa fechado (saldo geral com Pix e cartão; o card leva ao Financeiro, aba Caixas) e
   valor em estoque.
3. Use a sidebar para gerenciar **Produtos** (criar, editar, excluir, buscar),
   **Categorias** (criar, renomear, excluir categorias sem produtos),
   **Operações** (registrar vendas/compras: o estoque é atualizado e os títulos
   financeiros são gerados em 1x ou parcelados; parceiro é opcional),
   **Equipe** (o dono cadastra, lista, edita e exclui funcionários; funcionários
   usam o sistema normalmente, mas não podem excluir o dono),
   **Parceiros** (clientes e/ou fornecedores: inserir, acessar, alterar, apagar e
   registrar interações), e **Financeiro**, uma página com três abas: **Títulos**
   (contas a pagar e a receber; ao registrar um título o guia mostra as interações do
   parceiro para preencher descrição e valor), **Baixas** (pagamentos e recebimentos de
   títulos; o parceiro do título é opcional e o caixa precisa estar aberto) e **Caixas**
   (abrir, suprimento e sangria, extrato e fechamento com o valor contado). Para baixas,
   abra antes um caixa na aba Caixas; `database/dev/demo_baixas.sql` cria títulos de exemplo.

## 4. Testes automatizados

Com o banco no ar:

```powershell
cd backend
uv run pytest
```

Resultado esperado: **382 passed, 12 skipped, 1 xfailed** (suíte de aceitação
com os 395 casos do plano V1.6).

Para gerar a cobertura do backend (linhas + branches):

```powershell
cd backend
uv run pytest --cov=src/app --cov-report=term-missing --cov-report=html
```

O relatório navegável fica em `backend/htmlcov/index.html`; o resumo também é
impresso no terminal. Cobertura atual: **77,1%**.

> Os testes usam um hash de senha rápido (`PBKDF2`) **somente no ambiente de
> teste**, para não gastar ~1 s por conta criada. Em produção o hash continua
> sendo `scrypt`.

### E2E (Cypress)

Com banco, API e front no ar:

```powershell
cd e2e
npm ci
npm run test:jornada
```

As jornadas cobrem cadastro/login, catálogo, parceiros/interações, operações,
títulos, caixa, baixas, equipe e isolamento entre empresas. A jornada completa
está em `e2e/cypress/e2e/jornada/jornada-completa.cy.js`.

## 5. Build de produção do front-end (opcional)

```powershell
cd frontend
npm run build
npm run preview
```

O `build` gera os arquivos em `frontend/dist/`; o `preview` serve o build em
**http://localhost:4173**.

## Parar o projeto

1. Pare a API e o front com `Ctrl+C` nos respectivos terminais.
2. Pare o banco:

```powershell
cd database
docker compose stop
```

## Problemas comuns

- **Front abrindo, mas API sem resposta:** confirme que a API está rodando na
  porta `5000` e que o banco está `healthy`.
- **Porta ocupada:** a API usa `5000`, o Vite usa `5173` e o preview usa `4173`.
- **`npm run dev` falhando:** rode `npm install` dentro de `frontend/` e confira a
  versão do Node.js.
- **Banco sem o `.env`:** copie `database/.env.example` para `database/.env`
  (comando mostrado no passo 1).
