# Byte Estoque — testes E2E (Cypress)

Baseados no **Plano de Testes V1.2**. Esta pasta fica na **raiz do projeto**, ao lado de
`backend/`, `frontend/` e `database/` (a task de banco lê `../database/.env`).

```
byte-estoque-v2/
├── backend/  frontend/  database/
└── e2e/                          <── esta pasta
    ├── cypress.config.js
    ├── package.json
    └── cypress/
        ├── e2e/jornada/
        │   ├── jornada-completa.cy.js     29 passos: conta > categoria > produto > ... > apagar categoria
        │   └── jornada-isolamento.cy.js    8 passos: duas empresas + acesso sem login
        ├── support/  e2e.js (NOVO)  commands.js (NOVO)  data.js  utils.js
        ├── tasks/db.js
        └── shared/documents.js
```

## Como rodar

Banco, API e front no ar (veja o README da raiz), depois:

```powershell
cd e2e
npm install
npm run open            # modo interativo
npm run test:jornada    # as duas jornadas, no terminal
```

Outra URL do front: `$env:BASE_URL="http://localhost:4173"; npm run test:jornada`.

## O que a jornada completa cobre

| Passos | Fluxo | Casos do plano |
|---|---|---|
| JOR-01 a 05 | Tela inicial, cadastro em 2 etapas (validações, CNPJ inválido, "Voltar"), entrada no sistema, dashboard zerado | LOG-P01, LOG-N13/14/16, EMP-N02/06/16, EMP-P06/P09 |
| JOR-06 a 07 | Criar categoria (vazia, duplicada, ordem alfabética) | CAT-P01, CAT-N01, CAT-N05 |
| JOR-08 a 10 | Criar 3 produtos (completo, sem estoque, preço 0,00, SKU repetido), buscar, conferir dashboard | PRD-P01/02/03, PRD-N15/16 |
| JOR-11 a 14 | Atualizar produto (cancelar, SKU duplicado, nome/descrição/SKU/preço/estoque, mudar de categoria) e recalcular dashboard | PRD-P09 a P12, PRD-N17 |
| JOR-15 a 17 | Vínculo categoria × produto, apagar produtos (cancelar e confirmar) | PRD-P13, PRD-N22 |
| JOR-18 a 19 | Renomear categoria (produto continua vinculado, nome duplicado, vazio) | CAT-P04/P05, CAT-N06/N07 |
| JOR-20 a 22 | Apagar categoria (só sem produtos); produto em operação não pode ser apagado | PRD-N21 |
| JOR-23 a 27 | Sessão: recarregar, sair, login errado, login com e-mail em maiúsculas, hash da senha | LOG-N03/04/05, LOG-P10, BDD-P08 |
| JOR-28 a 29 | Cadastro repetido (e-mail e CNPJ) | LOG-N10/11, EMP-N10/12 |
| ISO-01 a 08 | Empresa B não vê, não altera e não apaga nada de A; sem login = 401 | SEG-P01, SEG-N01/02/09/11/12, CAT-P03, PRD-P07 |

Os `it` são encadeados (`testIsolation: false`): o resultado de um é a pré-condição do próximo.
Se um falhar, os seguintes também falham — corrija sempre o primeiro vermelho.

## O que o plano prevê e o sistema ainda não tem

Parceiros, Interações, Operações, Títulos, Baixas e Caixa aparecem como "em breve" na sidebar,
então os ~250 casos desses módulos não têm tela para testar. Conforme cada módulo ficar pronto,
a jornada ganha os passos novos (ex.: criar parceiro > criar venda > gerar título > baixar > fechar caixa).

## Diferenças entre o plano e o sistema atual (vale alinhar)

1. **Empresa no cadastro.** O plano descreve cadastro de usuário e *depois* uma página
   "Cadastrar empresa" (LOG-P02, EMP-P01...). O sistema faz tudo em um wizard de 2 etapas, numa
   transação só. Os casos EMP-* foram adaptados para a etapa 2.
2. **EMP-P09 (CEP `52.060-110`).** O campo CEP tem `maxLength=9`; o valor do plano tem 10
   caracteres e é cortado na digitação. Use `52060-110` ou ajuste o plano.
3. **Validação nativa do navegador.** Em Produtos, preço e estoque são `type="number"` com
   `min`/`step`, então PRD-N08/N09/N11/N14 (negativo, decimal, 3 casas) são barrados pelo
   navegador antes de chegar à API. Esses casos continuam válidos via `cy.request`/pytest.
4. **Plano vs. UI em "apagar categoria com produtos".** O botão fica desabilitado (a API também
   responde 409). O teste confere os dois lados.
