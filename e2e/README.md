# Byte Estoque — testes E2E (Cypress)

Suíte E2E da versão atual do sistema, alinhada ao **Plano de Testes V1.6**. Fica na
raiz do projeto, ao lado de `backend/`, `frontend/` e `database/`.

## Estrutura

```
e2e/
├── cypress.config.js
├── cypress/
│   ├── e2e/jornada/
│   │   ├── jornada-completa.cy.js   # jornada completa (todos os módulos)
│   │   └── jornada-isolamento.cy.js # multi-tenant A × B + segurança
│   ├── support/
│   │   ├── commands.js              # comandos de tela e API
│   │   ├── data.js                  # massa válida e e-mails de teste
│   │   └── utils.js
│   ├── tasks/db.js                  # limpeza e consultas diretas no MySQL
│   └── shared/documents.js          # CNPJ/CPF
├── package.json
└── README.md
```

## Como rodar

Banco, API e front no ar (veja o README da raiz):

```powershell
cd e2e
npm ci
npm run test:jornada    # todas as jornadas no terminal
npm run open            # modo interativo
```

Outra URL do front:

```powershell
$env:BASE_URL="http://localhost:4173"; npm run test:jornada
```

A limpeza (`cypress/tasks/db.js`) apaga somente dados criados pela suíte, com e-mails
`@e2e.exemplo.com.br`, e remove na ordem correta baixas, títulos, itens/operações,
movimentos/caixas, interações/parceiros, produtos, categorias, usuários e empresas.

Resultado atual: **48/48 passando** (37 da jornada completa + 11 de isolamento).

## Jornada completa

`jornada-completa.cy.js` é encadeada (`testIsolation: false`): cada passo usa o
resultado do anterior. Ela cobre:

| Passos | Fluxo |
|---|---|
| JOR-01 a 05 | Landing, cadastro em 2 etapas (validações, CNPJ inválido, Voltar), login automático, dashboard zerado |
| JOR-06 a 10 | Categorias (criar, duplicada, ordem), produtos (completo, sem estoque, preço 0,00, SKU repetido), busca e dashboard |
| JOR-11 a 17 | Edição de produto, categoria, exclusões e dashboard |
| JOR-18 a 22 | Categoria × produto, exclusão segura, produto em operação |
| JOR-23 a 29 | Sessão, login errado/maiúsculo, hash, cadastros repetidos |
| JOR-30 a 31 | Categoria e produto para a operação |
| JOR-32 | Parceiro + interação de compra |
| JOR-33 a 34 | Venda em 2 parcelas com parceiro, título gerado e estoque reduzido |
| JOR-35 | Caixa (abrir, suprimento, baixa de título e fechamento), dashboard Dinheiro |
| JOR-36 a 37 | Funcionário: criar, login, permissão sobre o Dono, exclusão pelo Dono |

## Jornada de isolamento

`jornada-isolamento.cy.js` cobre duas empresas no mesmo sistema:

- Empresa A criada pela API com categoria/produto;
- Empresa B se cadastra pela tela e começa vazia;
- B pode repetir nome de categoria e SKU de A;
- B recebe `404` ao tentar ler/alterar/apagar dados de A;
- B não usa categoria de A nem forja `id_empresa`;
- Login sem sessão retorna `401` e a tela volta ao início;
- A permanece intacta ao final.

## Diferenças conhecidas da UI × API

- O cadastro é um wizard de duas etapas, mas a transação é única no backend.
- Campos `type="number"` (preço/estoque) barram alguns valores no navegador antes da API;
  esses casos continuam cobertos pelo pytest de API.
- A exclusão de categoria com produtos fica desabilitada na tela e também responde
  `409` na API.
- O botão de exclusão do Dono não aparece para Funcionário; a API também bloqueia
  com `403`.
