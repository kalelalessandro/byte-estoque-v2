# AGENTS.md — Diretrizes e Contexto do Agente de IA

> **Atenção para o Agente:** Este arquivo é a fonte de verdade para o comportamento do agente neste repositório. **NÃO** remova as regras de escopo, as diretrizes de ferramentas (`uv`), as restrições de pastas e a arquitetura de testes ao atualizar este documento.

## 1. Visão Geral do Projeto
Sistema SaaS multi-tenant de **CRM, Controle de Estoque e Gestão Financeira** (`byte-estoque-v2`).

- **Backend:** Python + **Flask** (API JSON).
- **Banco de Dados:** **MySQL 8.0+** em container Docker (`database/docker-compose.yml`, schema em `database/init/01_schema.sql`).
- **Frontend:** Interface integrada ao backend.
  - **Identidade Visual:** Cores principais **laranja**, **preto** e detalhes em **cinza**.
  - **Logo/Marca d'água:** Folha canadense cinza.
- **Status atual:**
  - ✅ Banco de dados Docker configurado e rodando.
  - ✅ Módulo de Autenticação implementado (Login e Cadastro integrados com validação de empresa obrigatória).
  - ✅ Suíte de testes automatizados com `pytest` estruturada.
  - ✅ Módulo de Produtos e Categorias implementado (CRUD multi-tenant + testes).
  - ✅ Módulo de Parceiros e Interações implementado (clientes/fornecedores, CRUD multi-tenant, histórico de contatos + testes PAR/INT + tela no front-end).
  - ✅ Módulos Financeiro e Caixa implementados (Caixas, Movimentos de Caixa, Títulos Financeiros e Baixas Financeiras + telas no front-end).
  - ✅ Módulo de Operações implementado (vendas/compras, estoque, títulos 1x/parcelados, edição, cancelamento + testes).
  - ✅ Módulo de Gestão de Usuários/Funcionários implementado (cargos Dono/Funcionário, CRUD, permissões de exclusão e isolamento + testes).
  - ✅ Plano de testes V1.6 finalizado: 395 casos, suíte pytest com exatamente 395 testes (382 passed, 12 skipped, 1 xfailed), sem testes ocultos/deselected e casos E2E documentados como skip.
  - ✅ E2E Cypress atualizados para a UI V1.6: jornada completa com todos os módulos, isolamento multi-tenant e limpeza de banco ampliada.
  - ✅ Suíte E2E validada: 48/48 testes passando (37 da jornada completa + 11 de isolamento).
  - ✅ Módulos finalizados: autenticação, produtos/categorias, parceiros/interações, financeiro/caixa, operações e usuários.

---

## 2. Regras Estritas de Escopo e Pastas

1. **Estrutura do Banco de Dados Imutável:**
   - **NÃO** altere `database/init/01_schema.sql`, **NÃO** crie migrations e **NÃO** modifique `database/docker-compose.yml`.
   - **NÃO** utilize arquivos de seed na inicialização do banco (`02_seed.sql` é desconsiderado).
2. **Onde Trabalhar no Código:**
   - `backend/src/app/` — Código da API Flask.
   - `backend/tests/` — Testes automatizados com `pytest`.
   - `frontend/` — Código da interface (seguindo rigorosamente a paleta laranja, preto e cinza já adotada nas demais telas).
3. **Pasta `crm-estoque/` (Material de Referência Antigo):**
   - **Pode ler** a documentação e os arquivos de referência, especialmente `crm-estoque/docs/plano de testes.pdf`.
   - **NÃO edite** nada dentro de `crm-estoque/` e **não** copie código de lá para o backend atual.
4. **Gerenciamento de Dependências e Ferramentas (`uv`):**
   - **Proibido instalar pacotes globalmente.** Utilize exclusivamente o ambiente virtual em `backend/.venv` gerenciado pelo `uv`.
   - Caso seja necessária a instalação de qualquer nova dependência, **você deve pedir autorização explícita ao usuário antes de executar o comando**.
5. **Idioma:** Mensagens de erro da API, docstrings, comentários e documentação devem ser estritamente em **português do Brasil**.

---

## 3. Regras de Negócio: Autenticação e Vínculo Multi-tenant

- **Regra de Ouro:** Conforme o schema do banco (`usuarios.id_empresa NOT NULL`), **nenhum usuário pode existir sem estar vinculado a uma empresa**.
- **No Cadastro / Onboarding (`signup.py`):** O fluxo inicial cria a Empresa e o primeiro usuário (Dono/Administrador) em uma transação atômica única.
- **No Login (`login.py`):** Valida credenciais, confirma o vínculo empresarial e injeta o contexto (`id_usuario`, `id_empresa`, `id_cargo`, `admin_sistema`) na sessão.
- **Isolamento Multi-tenant:** Todas as consultas e gravações devem filtrar e validar o `id_empresa` obtido exclusivamente da sessão autenticada no servidor.

---

## 4. Regras de Negócio: Módulos Finais (Foco Atual)

### 4.1. Módulo de Operações (`operacoes` e `operacao_itens`)
Responsável por registrar **compras, vendas e exibir o histórico de transações da empresa**.
- **Estrutura no Banco:**
  - `operacoes`: `id_operacao`, `id_parceiro` (opcional/NULL), `id_usuario` (obrigatório), `tipo` (ex: compra, venda), `status` (ex: pendente, concluida, cancelada), `ocorrencia` (DATETIME), `observacoes`.
  - `operacao_itens`: PK composta `(id_operacao, id_produto)`, `quantidade` (> 0), `valor_unitario` (>= 0).
- **Regras Obrigatórias:**
  - **Isolamento Multi-tenant:** Validar que o usuário, todos os produtos dos itens e o parceiro (quando informado) pertencem à mesma `id_empresa` da sessão.
  - **Consistência Transacional:** A conclusão de uma operação exige pelo menos 1 item e deve ocorrer em transação atômica:
    - Atualizar `produtos.unidade_estoque` (compra soma; venda subtrai, impedindo estoque negativo) sem aplicar a mesma operação duas vezes.
    - Gerar o título financeiro correspondente em `titulos_financeiros` quando aplicável, vinculando `id_empresa`, `id_operacao` e `id_parceiro` (se houver).
  - **Cancelamento:** Cancelar uma operação concluída deve tratar seus efeitos no estoque e no financeiro (não apenas alterar a coluna `status`).
  - **Histórico:** Fornecer listagem filtrável das transações da empresa (com seus itens, totais calculados, parceiro e usuário responsável) e tela correspondente no front-end.

### 4.2. Gestão de Usuários / Funcionários (`usuarios` e `cargos`)
Permite que a empresa tenha múltiplos usuários acessando os mesmos dados, com hierarquia simples entre **Dono (Administrador)** e **Funcionário**.
- **Criar Usuário Funcionário:**
  - Permite cadastrar uma nova conta vinculada automaticamente ao mesmo `id_empresa` da sessão autenticada.
  - O cargo atribuído deve ser `Funcionario` (usar *get-or-create* na tabela `cargos` caso não exista).
  - `admin_sistema` permanece `False` (`0`). E-mail continua único globalmente (HTTP 409 se já existir).
- **Listagem de Usuários:**
  - Lista todos os usuários da empresa atual. **O usuário Dono também aparece nesta listagem** (ele consegue ver a própria conta junto aos funcionários).
- **Regra de Permissão e Exclusão:**
  - **Usuário Dono (Administrador):** Tem acesso total e **pode apagar** contas de usuários Funcionários da sua empresa. (Não deve conseguir apagar a si mesmo acidentalmente se for o único dono).
  - **Usuário Funcionário:** Pode operar normalmente **todos os módulos do sistema**, **EXCETO apagar o usuário Dono** (a API deve bloquear com HTTP 403 Forbidden e o front-end não deve exibir/permitir essa ação).
  - **Integridade do Banco (`ON DELETE RESTRICT`):** Como todas as FKs do banco usam `RESTRICT`, se um funcionário já tiver registros vinculados (operações, caixas, interações), o MySQL bloqueará o `DELETE`. A API deve capturar esse erro de integridade e retornar uma mensagem clara em português (ex: HTTP 409 informando que o usuário possui histórico vinculado e não pode ser excluído).

---

## 5. Como Rodar e Testar o Projeto

- **Gerenciamento via `uv` (na pasta `backend/`):**
  ```powershell
  uv sync                         # Sincroniza dependências na venv
  uv run pytest                   # Executa a suíte de testes do pytest
  uv run python -m src.app.main   # Inicia a API localmente