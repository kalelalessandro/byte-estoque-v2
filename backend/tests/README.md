# Testes da API — Autenticação, Categorias, Produtos, Parceiros e Interações

Suíte `pytest` baseada no `crm-estoque/docs/plano de testes.pdf` (V1.3),
cobrindo **autenticação** (LOG/EMP e casos correlatos de BDD, FKN, INTG, COL e
SEG), **categorias (CAT)**, **produtos (PRD)**, **parceiros (PAR)** e
**interações (INT)** **títulos financeiros (TIT)**, **baixas financeiras (BAI)** e **caixas (CXA)**. Roda contra o **MySQL real** do
Docker, sem mock, usando o `test_client` do Flask.

- **83 casos de autenticação** → 83 passando + 3 skips + 1 xfail (LOG-P08 impossível)
- **18 casos de categorias (CAT)** → 18 passando: 14 originais (CAT-P01..P05,
  CAT-N01..N09) + **4 incorporados ao plano** (CAT-P06, CAT-N10..N12, exclusão
  segura de categorias)
- **35 casos de produtos (PRD)** → 34 passando + 1 skip de UI (PRD-N22), mais
  casos extras de segurança/isolamento entre empresas
- **35 casos de parceiros (PAR)** → 35 passando (PAR-P01..P14, PAR-N01..N21), mais
  extras: validação de CPF/CNPJ, máscara, busca, filtro por tipo, paginação e
  isolamento entre empresas
- **14 casos de interações (INT)** → 14 passando (INT-P01..P07, INT-N01..N07), mais
  extras de data, responsável, isolamento entre empresas e os tipos de negócio
  (compra, reembolso, contrato, pagamento)
- **29 casos de caixa (CXA)** → 29 passando (CXA-P01..P13, CXA-N01..N16; CXA-N11 é coberto
  pela API como "sem caixa aberto" e a tela bloqueia), mais CON-N04 (fechamento x baixa),
  um caixa aberto por empresa, extrato, histórico, isolamento entre empresas e as corridas
  abrir/fechar/lançar (forçadas de forma determinística)
- **25 casos de títulos (TIT)** → 25 passando (TIT-P01..P11, TIT-N01..N14), mais SEG-N06 e
  SEG-N09, vínculo com operação (parceiro herdado/divergente), filtros e a corrida entre
  cancelar e dar baixa (forçada de forma determinística)
- **21 casos de baixas (BAI)** → 21 passando (BAI-P01..P08, BAI-N01..N13), mais SEG-N07 e
  SEG-N08 (baixa em título/caixa de outra empresa), CON-N03 e CON-N04 (concorrência, com a
  corrida forçada de forma determinística) e a regra desta tela: toda baixa tem parceiro
- **4 extras** de fluxo/transação (`test_fluxo_empresa.py`)
- **3 extras** de performance/dashboard: resumo agregado por empresa
  (`test_dashboard.py`)
- **1 extra** de configuração: hash padrão do cadastro nunca fica `None`
  (`test_config.py`)
- Limpeza automática dos dados criados, antes e depois de cada teste
- Resultado atual da suíte: **362 passed, 4 skipped, 1 xfailed**

---

## Como rodar

Pré-requisitos: banco no ar (`docker compose up -d` em `database/`) e
[uv](https://docs.astral.sh/uv/) instalado.

```powershell
cd backend
uv sync                        # cria/atualiza a venv e instala o pytest (grupo dev)

uv run pytest                  # suíte completa
uv run pytest -v               # nome de cada caso
uv run pytest tests/test_login.py            # só LOG
uv run pytest tests/test_cadastro_empresa.py # só EMP
uv run pytest tests/test_categorias.py       # só CAT
uv run pytest tests/test_produtos.py         # só PRD
uv run pytest tests/test_dashboard.py        # resumo agregado do dashboard
uv run pytest -m banco         # só SQL direto
uv run pytest -k "LOG-N"       # filtra por ID
```

> Não é preciso ativar a venv: o `uv run` executa o comando dentro de
> `backend/.venv`. A configuração do pytest fica no `pyproject.toml`.

---

## Cobertura por módulo do plano

| Módulo do plano | Casos cobertos | Arquivo | Status |
|---|---|---|---|
| LOG — Login e Cadastro de Usuário | LOG-P01..P11, LOG-N01..N20 | `test_login.py` | 31 (1 skip + 1 xfail) |
| EMP — Cadastro de Empresa | EMP-P01..P13, EMP-N01..N25 | `test_cadastro_empresa.py` | 38 (2 skips) |
| COL — Texto/Collation (auth) | COL-N01 | `test_login.py` | 1 |
| SEG — Segurança (auth) | SEG-N11, SEG-N12 | `test_login.py` | 2 |
| BDD — Integridade do banco (auth) | BDD-P01, P02, P07, P08, N01, N05, N06 | `test_integridade_banco_auth.py` | 7 |
| FKN — Campos obrigatórios (auth) | FKN-N01, FKN-N02 | `test_integridade_banco_auth.py` | 2 |
| INTG — Integridade referencial (auth) | INTG-N01, INTG-N11 | `test_integridade_banco_auth.py` | 2 |
| CAT — Categorias | CAT-P01..P06, CAT-N01..N12 | `test_categorias.py` | 18 (plano atualizado) |
| PRD — Produtos | PRD-P01..P13, PRD-N01..N22 | `test_produtos.py` | 35 (34 + 1 skip) + extras |
| PAR — Parceiros | PAR-P01..P14, PAR-N01..N21 | `test_parceiros.py` | 35 + extras |
| INT — Interações | INT-P01..P07, INT-N01..N07 | `test_interacoes.py` | 14 + extras |
| CXA — Caixa | CXA-P01..P13, CXA-N01..N16 (+ CON-N04, SEG) | `test_caixas.py` | 32 + extras |
| TIT — Títulos financeiros | TIT-P01..P11, TIT-N01..N14 (+ SEG-N06/N09) | `test_titulos.py` | 25 + extras |
| BAI — Baixas financeiras | BAI-P01..P08, BAI-N01..N13 (+ SEG-N07/N08, CON-N03/N04) | `test_baixas.py` | 21 + extras |
| Fluxo/transação (extras, fora do plano) | contexto de empresa, sinal defensivo e rollback atômico | `test_fluxo_empresa.py` | 4 |
| Dashboard (extras, performance) | `GET /api/dashboard/resumo`: contagens (produtos, categorias, parceiros) + valor em estoque no banco, isolamento por empresa, 401 | `test_dashboard.py` | 3 |
| Dashboard — Dinheiro (extras) | `dinheiro` = saldo geral (contado + Pix + cartão) do último caixa fechado: nulo sem fechamento, caixa aberto não conta, aparece ao fechar, o mais recente vence, zero é zero, isolamento por empresa, Pix/cartão somam | `test_dashboard_dinheiro.py` | 7 |
| Configuração (extra, regressão) | hash de senha padrão do cadastro é válido (nunca `None`) | `test_config.py` | 1 |

Os IDs dos casos aparecem no nome de cada teste (ex.:
`test_log_p02_cadastro_usuario_com_campos_validos`,
`test_emp_negativos_validacao[EMP-N06]`).

> O plano de testes (PDF) está na **V1.3**, com os casos de exclusão de
> categoria CAT-P06 e CAT-N10..N12 na página 47 e o **controle de versões na
> página 48**.

---

## Adaptações em relação ao plano (interface web → API JSON)

O plano descreve a interface web em etapas; a API atual foi testada no nível de
requisição, mantendo o resultado esperado de cada caso:

1. **Cadastro de usuário + empresa é uma única operação** (`POST /api/auth/cadastro`).
   O schema define `usuarios.id_empresa NOT NULL`, então não existe o estado
   "usuário sem empresa" citado no plano. Casos de LOG que só criam usuário usam
   um payload completo (usuário + empresa) e verificam os campos do usuário.
2. **Sem redirecionamento de páginas**: a API devolve JSON com `201` (cadastro) e
   `200` (login). O "redirecionar para a Tela Principal" foi verificado pela
   presença da empresa vinculada na resposta/login.
3. **CNPJ alfanumérico**: implementado conforme a premissa 2 do plano — máscara
   removida, letras em maiúsculas e **dígitos verificadores validados** (módulo
   11, valor do caractere = ASCII − 48).
4. **Telefone**: texto de até 20 caracteres, preservando a máscara digitada
   (o plano aceita `+55 (81) 9 8888-7777`, com 20 caracteres).
5. **E-mail**: `trim` + minúsculo, unicidade global; no login, formato inválido
   devolve `422` com mensagem de e-mail inválido.
6. **Acesso direto sem sessão** (LOG-N20): adaptado para a rota protegida
   `GET /api/auth/me`, que responde `401`.
7. **SQL injection**: os casos são executados via API e verificam que nenhuma
   sessão é criada (login) e que o texto é gravado literalmente, com a tabela
   íntegra (razão social).
8. **Categorias e produtos**: CAT e PRD foram testados no nível HTTP da API
   (`/api/categorias` e `/api/produtos`), com a empresa vinda sempre da sessão.
   O caso PRD-N22 é de confirmação visual (front-end) e ficou como skip; a
   exclusão bloqueada por operação (PRD-N21) é testada criando a operação via
   SQL e verificando o `409` do `DELETE`.

## Skips justificados (4) + 1 XFAIL (impossível)

| Caso | Situação / motivo |
|---|---|
| LOG-P08 | **XFAIL**: "IMPOSSÍVEL" — `usuarios.id_empresa` é NOT NULL, então não existe usuário sem empresa para logar. O teste verifica o schema e falha de propósito; se o schema mudar, vira XPASS e a suíte acusa. |
| LOG-P11 | SKIP — exige a Tela Principal (front-end React); é caso de UI/E2E, não de API. |
| EMP-N23 | SKIP — exige Tela Principal (UI/E2E) + usuário sem empresa (impossível pelo schema). |
| EMP-N24 | SKIP — exige o bloqueio da página "Cadastrar empresa" (UI/E2E); o pytest cobre a API. |
| PRD-N22 | SKIP — "Cancelar a confirmação ao apagar produto" é fluxo de confirmação do front-end; a API expõe apenas o `DELETE` direto. |

> Os 4 skips podem ser automatizados no futuro com um teste E2E do front
> (Cypress/Playwright), como o plano original previa.

---

## Dados de teste e limpeza

- Fixtures: `tests/conftest.py` (`app`, `client`, `banco_limpo` autouse).
- E-mails terminam em `@exemplo.com.br` (exceto o e-mail de 254 caracteres do
  LOG-P05, que é registrado explicitamente); CNPJs vêm do próprio plano.
- `test_produtos.py` e `test_categorias.py` têm fixtures próprias que apagam
  operações, produtos e categorias antes de o `banco_limpo` remover as empresas
  (por causa das FKs com `ON DELETE RESTRICT`).
- `test_parceiros.py` e `test_interacoes.py` usam `tests/apoio_parceiros.py`, cuja
  limpeza apaga títulos, operações, interações e parceiros das empresas de teste
  antes de o `banco_limpo` remover usuários e empresas (FKs `RESTRICT`).
  PAR-N20 e PAR-N21 criam a operação e o título por SQL direto, pois esses módulos
  ainda não têm API.
- **Interação = contratos e compras.** O tipo da interação fica na coluna `canal`
  (texto livre, até 30). Os casos INT do plano usam "telefone"/"WhatsApp" apenas
  como exemplos de texto; o texto desses casos no PDF ainda descreve "contato" e
  precisa ser atualizado na documentação. O schema não mudou.
- `test_baixas.py` cria títulos e caixas por SQL (esses módulos ainda não têm API) via
  `tests/apoio_baixas.py`. BAI-P06 ("pela opção do Financeiro") usa a mesma rota
  `POST /api/baixas`. CON-N03/N04 seguram a trava da linha em uma segunda sessão do banco
  enquanto a requisição espera, e só então confirmam a mudança concorrente.
- `test_caixas.py` cria títulos e baixas por SQL e abre/fecha caixas pela API. CON-N04 confere
  que o valor devolvido pelo fechamento já inclui a baixa confirmada durante a espera (sem a
  leitura travada, a diferença sairia errada).
- `test_titulos.py` cria operações, caixas e baixas por SQL (sem API ainda). TIT-P04 (título
  sem parceiro) é válido no cadastro; o título só não recebe baixa na tela de baixas.
- **Regra do parceiro:** o plano permite título sem parceiro, mas a tela de baixas só
  liquida títulos com parceiro (decisão de produto); isso é coberto por testes extras.
- O app de teste usa PBKDF2 com poucas iterações via `SENHA_HASH_METODO` para
  acelerar a suíte; em produção o cadastro continua usando `scrypt`.
- Os dados criados via API são registrados em `tests/helpers.py`
  (`EMAILS_CRIADOS`/`CNPJS_CRIADOS`). O fixture `banco_limpo` remove:
  usuários registrados/padrão, empresas vinculadas, empresas `BD...` inseridas
  via SQL direto e o cargo `Administrador` órfão.
- Nenhum dado de demonstração é apagado.

## Observações

- Casos dos módulos **categorias (CAT)**, **produtos (PRD)**, **parceiros (PAR)**
  e **interações (INT)** já estão implementados e testados; os demais módulos do
  plano (financeiro, caixa, etc.) ainda não têm rotas na API.
- Casos `CAR-N0x` (cargos) e `INTG-N02..N04` (exclusão de usuário com operações/
  interações/caixas) dependem de módulos que ainda não têm API; ficam para a
  próxima etapa.
- O console do PowerShell pode exibir acentos como `�`; é só a codificação do
  terminal, o JSON da API é UTF-8 (testado em `test_bdd_p07...` e `COL-N01`).
