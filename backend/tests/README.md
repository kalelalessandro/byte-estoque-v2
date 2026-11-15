# Testes de Autenticação — mapeamento do plano de testes V1.2

Suíte `pytest` que cobre o módulo de **autenticação** do projeto, baseada no
`crm-estoque/docs/plano de testes.pdf` (V1.2): módulos **LOG** (Login e Cadastro
de Usuário) e **EMP** (Cadastro de Empresa), mais os casos correlatos que tocam
`empresas`, `cargos` e `usuarios` (BDD, FKN, INTG, COL e SEG).

- **83 casos de teste** mapeados → **79 passando + 4 skips justificados**
- Rodam contra o **MySQL real** do Docker (sem mock), usando o `test_client` do Flask
- Limpeza automática dos dados criados, antes e depois de cada teste

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
uv run pytest -m banco         # só SQL direto
uv run pytest -k "LOG-N"       # filtra por ID
```

> Não é preciso ativar a venv: o `uv run` executa o comando dentro de
> `backend/.venv`. A configuração do pytest fica no `pyproject.toml`.

---

## Cobertura por módulo do plano

| Módulo do plano | Casos cobertos | Arquivo | Status |
|---|---|---|---|
| LOG — Login e Cadastro de Usuário | LOG-P01..P11, LOG-N01..N20 | `test_login.py` | 31 (2 skips) |
| EMP — Cadastro de Empresa | EMP-P01..P13, EMP-N01..N25 | `test_cadastro_empresa.py` | 38 (2 skips) |
| COL — Texto/Collation (auth) | COL-N01 | `test_login.py` | 1 |
| SEG — Segurança (auth) | SEG-N11, SEG-N12 | `test_login.py` | 2 |
| BDD — Integridade do banco (auth) | BDD-P01, P02, P07, P08, N01, N05, N06 | `test_integridade_banco_auth.py` | 7 |
| FKN — Campos obrigatórios (auth) | FKN-N01, FKN-N02 | `test_integridade_banco_auth.py` | 2 |
| INTG — Integridade referencial (auth) | INTG-N01, INTG-N11 | `test_integridade_banco_auth.py` | 2 |

Os IDs dos casos aparecem no nome de cada teste (ex.:
`test_log_p02_cadastro_usuario_com_campos_validos`,
`test_emp_negativos_validacao[EMP-N06]`).

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

## Skips justificados (4)

| Caso | Motivo do skip |
|---|---|
| LOG-P08 | Exige "usuário sem empresa"; `usuarios.id_empresa` é NOT NULL no schema imutável. |
| LOG-P11 | Exige a Tela Principal com menu de módulos (frontend ainda não existe). |
| EMP-N23 | Exige página "Tela Principal" + usuário sem empresa (frontend/schema). |
| EMP-N24 | Exige página "Cadastrar empresa" para usuário já logado (não existe no backend atual). |

---

## Dados de teste e limpeza

- Fixtures: `tests/conftest.py` (`app`, `client`, `banco_limpo` autouse).
- E-mails terminam em `@exemplo.com.br` (exceto o e-mail de 254 caracteres do
  LOG-P05, que é registrado explicitamente); CNPJs vêm do próprio plano.
- Os dados criados via API são registrados em `tests/helpers.py`
  (`EMAILS_CRIADOS`/`CNPJS_CRIADOS`). O fixture `banco_limpo` remove:
  usuários registrados/padrão, empresas vinculadas, empresas `BD...` inseridas
  via SQL direto e o cargo `Administrador` órfão.
- Nenhum dado de demonstração é apagado.

## Observações

- Casos do plano de outros módulos (produtos, parceiros, financeiro, etc.) não
  foram implementados porque as rotas correspondentes ainda não existem.
- Casos `CAR-N0x` (cargos) e `INTG-N02..N04` (exclusão de usuário com operações/
  interações/caixas) dependem de módulos que ainda não têm API; ficam para a
  próxima etapa.
- O console do PowerShell pode exibir acentos como `�`; é só a codificação do
  terminal, o JSON da API é UTF-8 (testado em `test_bdd_p07...` e `COL-N01`).
