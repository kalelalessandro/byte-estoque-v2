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
| GET | `/api/dashboard/resumo` | **sim** | Resumo agregado: produtos, categorias, parceiros, valor em estoque e `dinheiro` (saldo geral do último caixa fechado: contado + Pix + cartão) |
| POST | `/api/categorias` | **sim** | Cria uma categoria |
| GET | `/api/categorias` | **sim** | Lista as categorias da empresa |
| PATCH | `/api/categorias/<id>` | **sim** | Renomeia uma categoria |
| DELETE | `/api/categorias/<id>` | **sim** | Apaga categoria **sem produtos** (409 se houver produtos) |
| POST | `/api/produtos` | **sim** | Cria um produto |
| GET | `/api/produtos` | **sim** | Lista produtos (`busca`, `limit`, `offset`) |
| GET | `/api/produtos/<id>` | **sim** | Detalhe de um produto |
| PATCH | `/api/produtos/<id>` | **sim** | Altera SKU, categoria, nome, descrição, estoque e/ou preço |
| DELETE | `/api/produtos/<id>` | **sim** | Apaga produto (409 se houver registros vinculados) |
| POST | `/api/parceiros` | **sim** | Cria um parceiro (cliente, fornecedor ou ambos) |
| GET | `/api/parceiros` | **sim** | Lista parceiros (`busca`, `tipo`, `limit`, `offset`) |
| GET | `/api/parceiros/<id>` | **sim** | Dados completos do parceiro + histórico de interações |
| PATCH | `/api/parceiros/<id>` | **sim** | Altera nome, documento, e-mail, CEP, relacionamento e/ou observação |
| DELETE | `/api/parceiros/<id>` | **sim** | Apaga parceiro (409 se houver interações, operações ou títulos) |
| POST | `/api/parceiros/<id>/interacoes` | **sim** | Registra uma interação (o responsável é o usuário logado) |
| PATCH | `/api/parceiros/<id>/interacoes/<interacao_id>` | **sim** | Altera data, canal e/ou descrição da interação |
| GET | `/api/interacoes` | **sim** | Guia: interações de todos os parceiros (`id_parceiro`, `limit`, `offset`) |
| GET | `/api/caixas` | **sim** | Histórico de caixas da empresa (`situacao`, `limit`, `offset`) com valores |
| GET | `/api/caixas/atual` | **sim** | Caixa aberto agora (ou `null`), com valores e extrato |
| GET | `/api/caixas/<id>` | **sim** | Sessão de caixa com valores e extrato |
| POST | `/api/caixas` | **sim** | Abre um caixa (`valor_abertura`, zero permitido) |
| POST | `/api/caixas/<id>/movimentos` | **sim** | Registra suprimento ou sangria |
| POST | `/api/caixas/<id>/fechar` | **sim** | Fecha o caixa com o `valor_contado` e informa a diferença |
| GET | `/api/operacoes` | **sim** | Lista operações (`busca`, `tipo`, `status`, `limit`, `offset`) com itens e títulos |
| POST | `/api/operacoes` | **sim** | Registra compra/venda, atualiza estoque e gera títulos (1x ou parcelados) |
| GET | `/api/operacoes/<id>` | **sim** | Detalhe da operação, itens e títulos gerados |
| PATCH | `/api/operacoes/<id>` | **sim** | Altera operação concluída, refazendo estoque e títulos atomicamente |
| POST | `/api/operacoes/<id>/cancelar` | **sim** | Cancela operação, estorna estoque e cancela títulos sem baixas |
| GET | `/api/usuarios` | **sim** | Lista dono e funcionários da empresa |
| POST | `/api/usuarios` | **sim** | Cria funcionário vinculado à empresa (cargo Funcionario) |
| PATCH | `/api/usuarios/<id>` | **sim** | Atualiza nome, e-mail, telefone e/ou senha (funcionário não altera o Dono) |
| DELETE | `/api/usuarios/<id>` | **sim** | Exclui funcionário; bloqueia dono, própria conta e histórico vinculado |
| GET | `/api/titulos` | **sim** | Lista títulos (`busca`, `tipo`, `situacao`, `id_parceiro`, `limit`, `offset`) |
| GET | `/api/titulos/<id>` | **sim** | Consulta título: saldo, situação, parceiro e histórico de baixas |
| POST | `/api/titulos` | **sim** | Registra título manualmente (em aberto, sem baixas) |
| POST | `/api/titulos/<id>/cancelar` | **sim** | Cancela título sem baixas |
| GET | `/api/baixas` | **sim** | Lista baixas (`busca`, `tipo`, `forma`, `id_parceiro`, `limit`, `offset`) |
| GET | `/api/baixas/<id>` | **sim** | Consulta baixa + título (com saldo) + parceiro |
| GET | `/api/baixas/opcoes` | **sim** | Títulos com saldo (parceiro opcional), caixas abertos e formas de pagamento |
| POST | `/api/baixas` | **sim** | Registra uma baixa em título e caixa aberto |

> Nas rotas de categorias, produtos e parceiros a **empresa vem sempre da
> sessão**; o `id_empresa` enviado no JSON é recusado. Categoria e SKU são únicos
> por empresa, e a categoria do produto precisa ser da mesma empresa.

### Caixas

Sessão de caixa (`caixas`) com movimentos adicionais (`operacoes_caixa`). Regras
(Documentação do Banco v1.2 e plano de testes CXA/CON/SEG):

- A empresa do caixa é a de quem o abriu (`aberto_por_usuario`); a tabela não tem
  `id_empresa`. Caixa de outra empresa responde 404. **Um caixa aberto por empresa**
  (409 ao tentar abrir outro); aberturas simultâneas são serializadas travando a linha da
  empresa.
- `valor_abertura` e `valor_contado` aceitam **zero**, não negativos. Suprimento e sangria
  exigem valor > 0; `tipo` é `suprimento` (entrada) ou `sangria` (saída). Datas e horas são
  do servidor, nunca do JSON.
- **Saldo esperado em dinheiro** = abertura + suprimentos − sangrias + recebimentos em
  dinheiro − pagamentos em dinheiro (as baixas vêm de `baixas_financeiras`). **Pix e cartão
  não entram na contagem da gaveta**: aparecem em linhas separadas (`por_forma`). Nada é
  contado em dobro (baixas e movimentos ficam em tabelas diferentes).
- **Saldo geral** (`saldo_geral`) = dinheiro do caixa + líquido de Pix + líquido de cartão
  (recebimentos − pagamentos). O dinheiro é o saldo esperado com o caixa aberto e o
  `valor_contado` depois do fechamento. **Pix e cartão alteram o saldo geral.** A página
  Caixas mostra o saldo geral no detalhe e no histórico.
- Fechamento: `diferenca` = contado − esperado (negativa = faltou dinheiro). Caixa fechado
  não aceita lançamentos, novas baixas nem novo fechamento (409; data/hora e valor contado
  originais são mantidos).
- **Concorrência:** movimento e fechamento travam o caixa (`SELECT ... FOR UPDATE`); o
  fechamento soma baixas e movimentos com leitura travada (uma leitura comum veria o snapshot
  antigo da transação). Assim uma baixa concorrente entra no esperado ou é recusada, e o
  fechamento devolve exatamente o resumo calculado sob trava. Ordem de travas do sistema:
  empresa → título → caixa.
- `GET /api/caixas/<id>` traz o `extrato`: baixas (com parceiro) e suprimentos/sangrias.
- **Dashboard:** `GET /api/dashboard/resumo` devolve `dinheiro` = `{ valor, id_caixa, fechado_em }`
  do **último caixa fechado** da empresa, onde `valor` é o `saldo_geral` desse caixa (valor
  contado + Pix + cartão), ou `null` até o primeiro fechamento. Caixa ainda aberto não conta:
  o dinheiro só é confirmado na contagem.
  O card "Dinheiro" do Início mostra esse valor assim que o caixa fecha (qualquer escrita limpa
  o cache do front-end) e leva ao Financeiro, na aba Caixas.

### Títulos financeiros

Título = conta a pagar ou a receber (`titulos_financeiros`). Regras (Documentação do Banco
v1.2 e plano de testes TIT/SEG):

- Campos: `tipo` (`a pagar` ou `a receber`), `valor` (> 0, até 9.999.999.999,99, 2 casas;
  aceita `1250,00`), `descricao` (até 500) e `vencimento` (`AAAA-MM-DD` ou `DD/MM/AAAA`, data
  real) obrigatórios; `id_parceiro` e `id_operacao` opcionais. `id_empresa` é recusado: a
  empresa vem da sessão.
- O parceiro precisa ser da mesma empresa. A operação também; se ela tem parceiro, o título
  deve ter o **mesmo** parceiro (se o título não informar, herda o da operação).
- Título sem parceiro é permitido pela API, mas **a tela não deixa criar**: o formulário exige
  o parceiro (sem a opção "Sem parceiro"). Título sem parceiro **não aceita baixa** (toda baixa tem
  parceiro); a resposta traz `pode_baixar` e `motivo_sem_baixa` para a tela explicar.
- Situação: `aberto`, `parcial`, `quitado` ou `cancelado`; `saldo_pendente` = valor − baixas.
- `GET /api/titulos/<id>` inclui `baixas` (histórico, mais recentes primeiro).
- Cancelar: bloqueado (409) com baixas ou se já cancelado; o cancelamento trava o título
  (`FOR UPDATE`) antes de contar as baixas, igual à baixa, então os dois não se atropelam.
  Título cancelado não aceita baixas. Não há exclusão (FK `RESTRICT`) nem edição dos dados
  (W.I.P. no fluxograma).
- **Vínculo com a interação do parceiro:** o schema não tem coluna ligando título a interação.
  Na tela, ao escolher o parceiro o Guia mostra as interações dele (a descrição costuma trazer
  valor e detalhes); o usuário pode "Usar na descrição" (a descrição do título passa a citar
  `Interação #id`) e "Usar R$ …" (valor sugerido a partir do texto) e confere antes de salvar.

### Baixas financeiras

Baixa = pagamento ou recebimento efetivo de um título (`baixas_financeiras`). Regras
(Documentação do Banco v1.2 e plano de testes BAI/SEG/CON):

- **Toda baixa tem parceiro.** O schema liga a baixa ao parceiro pelo **título**
  (`titulos_financeiros.id_parceiro`, opcional no banco). Por regra desta tela, título
  **sem parceiro** é recusado (422) e não é oferecido no formulário; a resposta de
  `GET /api/baixas/opcoes` traz títulos com saldo, inclusive os sem parceiro.
- Campos: `id_titulo`, `id_caixa`, `valor` (> 0, até 2 casas; aceita `120,50`),
  `forma_pagamento` (`dinheiro`, `Pix` ou `cartão`, sem diferenciar caixa/acento) e
  `realizado_em` (`AAAA-MM-DD HH:MM`, `AAAA-MM-DDTHH:MM` ou `DD/MM/AAAA HH:MM`).
- Saldo pendente = valor do título − soma das baixas. Recusadas: valor acima do saldo
  (422), título cancelado ou já quitado (409), caixa fechado (409) e **sem caixa aberto
  na empresa** (409, "Abra um caixa"). Título, caixa e parceiro precisam ser da empresa
  do usuário (a empresa do caixa é a de quem o abriu).
- **Concorrência:** a baixa trava o título e depois o caixa (`SELECT ... FOR UPDATE`,
  nessa ordem) e soma as baixas com leitura travada. Duas baixas simultâneas não passam
  do saldo e nenhuma baixa entra num caixa que está sendo fechado.
- Não há edição nem exclusão de baixa (o schema não tem estorno).
- Títulos e caixas têm tela própria (na página Financeiro). Para experimentar baixas abra um
  caixa na aba Caixas; `database/dev/demo_baixas.sql` só cria títulos de exemplo.
- **Guia de interações:** `GET /api/interacoes` lista as interações (contratos e compras)
  de todos os parceiros da empresa, ou só de um (`id_parceiro`). A tela de baixas usa isso
  como guia ao lado da lista e ao escolher o título.

### Parceiros e interações

Parceiro é todo cliente e/ou fornecedor da empresa (`e_cliente` / `e_fornecedor`,
ao menos um marcado). Regras (Documentação do Banco v1.2 e plano de testes PAR/INT):

- `nome` obrigatório (até 150). `documento` (CPF de 11 dígitos ou CNPJ de 14
  caracteres, alfanumérico), `e-mail` (até 254), `cep` (8 dígitos) e `observacao`
  são opcionais; quando ausentes são gravados como `NULL`. A pontuação de documento
  e CEP é removida, o documento vai em maiúsculas e o e-mail em minúsculas. Os
  dígitos verificadores de CPF/CNPJ são conferidos pela API (o banco não confere).
- **E-mail e documento são únicos por empresa** (409 se repetidos; a comparação
  ignora maiúsculas e acentos). Texto só com espaços em documento/e-mail é recusado.
- Em `PATCH`, enviar `null` em documento, e-mail, CEP ou observação limpa o campo.
  A empresa do parceiro nunca muda.
- `DELETE` é bloqueado (409) quando existem **interações, operações ou títulos
  financeiros** vinculados; a resposta traz `vinculos` com a contagem de cada tipo.
- **Interação = contratos e compras com o parceiro**: cliente comprou, cliente
  pediu reembolso, fornecedor assinou contrato, fornecedor foi pago pelo
  fornecimento. Campos: `ocorrencia` (data do fato, `AAAA-MM-DD` ou `DD/MM/AAAA`,
  tem que existir), `canal` e `descricao`, todos obrigatórios. O **tipo** do fato
  (Compra, Reembolso, Contrato, Pagamento...) vai em `canal` (nome da coluna no
  schema; a tela mostra "Tipo de interação"), texto livre de até 30 caracteres;
  a tela sugere os tipos conforme o parceiro seja cliente, fornecedor ou ambos.
  Valores, número do pedido etc. vão na `descricao`. Várias interações no mesmo dia
  são permitidas. A consulta do histórico vem em `GET /api/parceiros/<id>` (campo
  `interacoes`, mais recentes primeiro). Não há exclusão de interação.
- A tabela `interacoes` não tem colunas de valor nem de vínculo com operação ou
  título; compras, vendas e pagamentos com valor e estoque são tratados pelos
  módulos de operações e financeiro (ainda sem API).

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

# Só caixas (CXA/CON)
uv run pytest tests/test_caixas.py

# Só títulos financeiros (TIT/SEG)
uv run pytest tests/test_titulos.py

# Só baixas financeiras (BAI/SEG/CON)
uv run pytest tests/test_baixas.py

# Só parceiros (PAR) / só interações (INT)
uv run pytest tests/test_parceiros.py
uv run pytest tests/test_interacoes.py
```

Resultado esperado: **382 passed, 12 skipped, 1 xfailed** na suíte de
aceitação (395 casos do plano V1.5; 6 skips são E2E e os outros são lacunas de
escopo documentadas). Para rodar também a suíte estendida:
`uv run pytest --all-tests`.

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
│   ├── modules/
│   │   ├── partners.py       # parceiros: criar, listar, acessar, alterar, apagar
│   │   ├── partners_rules.py # validação/normalização dos campos de parceiro
│   │   ├── interactions.py   # interações: registrar, alterar e guia (GET /api/interacoes)
│   │   ├── interactions_rules.py  # validação dos campos de interação
│   │   ├── baixas.py         # baixas financeiras: listar, consultar, opções e registrar
│   │   ├── baixas_rules.py   # validação dos campos da baixa
│   │   ├── titulos.py        # títulos: listar, consultar, registrar e cancelar
│   │   ├── titulos_rules.py  # validação dos campos do título
│   │   ├── caixas.py         # caixas: abrir, movimentos, extrato, fechar
│   │   └── caixas_rules.py   # validação dos campos do caixa
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
    ├── test_parceiros.py     # PAR-Pxx / PAR-Nxx + isolamento, busca, filtros
    ├── test_interacoes.py    # INT-Pxx / INT-Nxx + isolamento entre empresas
    ├── apoio_parceiros.py    # login, payloads e limpeza de PAR/INT
    ├── test_baixas.py        # BAI-Pxx / BAI-Nxx + SEG-N07/N08 + CON-N03/N04 + regra do parceiro
    ├── apoio_baixas.py       # títulos, caixas, operações, baixas e limpeza (BAI/TIT)
    ├── test_titulos.py       # TIT-Pxx / TIT-Nxx + SEG-N06/N09 + cancelar x baixar (concorrência)
    ├── test_caixas.py        # CXA-Pxx / CXA-Nxx + CON-N04 + abrir/fechar/lançar (concorrência)
    ├── test_dashboard_dinheiro.py  # card Dinheiro do dashboard ligado ao fechamento do caixa
    ├── test_fluxo_empresa.py # transação atômica + contexto de empresa
    └── test_integridade_banco_auth.py  # BDD/FKN/INTG de autenticação
```

## Limitações conhecidas (projeto de faculdade)

- Sessão por cookie: `SECRET_KEY` de desenvolvimento se `FLASK_SECRET_KEY` não for definida.
- Sem CSRF explícito, sem rate limit e sem verificação de e-mail.
- `admin_sistema` fica `false` para todo usuário criado pelo cadastro público.
- Não há recuperação de senha nem troca de senha ainda.
