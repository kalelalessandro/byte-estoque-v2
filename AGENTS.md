# AGENTS.md — Diretrizes e Contexto do Agente de IA

> **Atenção para o Agente:** Este arquivo é a fonte de verdade para o comportamento do agente neste repositório. **NÃO** remova as regras de escopo, as diretrizes de ferramentas (`uv`), as restrições de pastas e a arquitetura de testes ao atualizar este documento.

## 1. Visão Geral do Projeto
Sistema SaaS multi-tenant de **CRM, Controle de Estoque e Gestão Financeira** (`byte-estoque-v2`).

- **Backend:** Python + **Flask** (API JSON).
- **Banco de Dados:** **MySQL 8.0+** em container Docker (`database/docker-compose.yml`, schema em `database/init/01_schema.sql`).
- **Frontend:** Interface básica inicial integrada ao backend.
  - **Identidade Visual:** Cores principais **laranja**, **preto** e detalhes em **cinza**.
  - **Logo/Marca d'água:** Folha canadense cinza.
- **Status atual:**
  - ✅ Banco de dados Docker configurado e rodando.
  - ✅ Módulo de Autenticação implementado (Login e Cadastro integrados com validação de empresa obrigatória).
  - ✅ Suíte de testes automatizados com `pytest` estruturada.
  - 🛠️ **Front-End Inicial (Em andamento):** Telas de Tela Inicial, Login/Cadastro, Cadastro Obrigatório de Empresa e Tela Principal Pós-Login (WIP).
  - ✅ Módulo de Produtos e Categorias implementado (CRUD multi-tenant + testes).
  - ✅ Módulo de Parceiros e Interações implementado (clientes/fornecedores, CRUD multi-tenant, histórico de contatos + testes PAR/INT + tela no front-end).
  - ⏳ Demais módulos (operações, financeiro, caixa, etc.) pendentes.

---

## 2. Regras Estritas de Escopo e Pastas

1. **Estrutura do Banco de Dados Imutável:**
   - **NÃO** altere `database/init/01_schema.sql`, **NÃO** crie migrations e **NÃO** modifique `database/docker-compose.yml`.
   - **NÃO** utilize arquivos de seed na inicialização do banco (`02_seed.sql` é desconsiderado).
2. **Onde Trabalhar no Código:**
   - `backend/src/app/` — Código da API Flask.
   - `backend/tests/` — Testes automatizados com `pytest`.
   - `frontend/` — Código da interface inicial (HTML/CSS/JS ou templates do Flask conforme a estrutura adotada).
3. **Pasta `crm-estoque/` (Material de Referência Antigo):**
   - **Pode ler** a documentação e os arquivos de referência, especialmente `crm-estoque/docs/plano de testes.pdf`.
   - **NÃO edite** nada dentro de `crm-estoque/` e **não** copie código de lá para o backend atual.
4. **Gerenciamento de Dependências e Ferramentas (`uv`):**
   - **Proibido instalar pacotes globalmente.** Utilize exclusivamente o ambiente virtual em `backend/.venv` gerenciado pelo `uv`.
   - Caso seja necessária a instalação de qualquer nova dependência, **você deve pedir autorização explícita ao usuário antes de executar o comando**.
5. **Idioma:** Mensagens de erro da API, docstrings, comentários e documentação devem ser estritamente em **português do Brasil**.

---

## 3. Regras de Negócio: Autenticação e Fluxo de Telas (Front-End & Back-End)

### Vínculo Obrigatório de Empresa (Multi-tenant)
- **Regra de Ouro:** Conforme o schema do banco (`usuarios.id_empresa NOT NULL`), **nenhum usuário pode existir sem estar vinculado a uma empresa**. 
- **No Cadastro / Onboarding (`signup.py`):** 
  - O fluxo inicial obriga o usuário a preencher e cadastrar uma **Empresa** obrigatoriamente junto com a conta de acesso em uma **transação atômica única**. 
  - Caso um usuário autenticado por algum motivo não possua empresa associada (edge-case defensivo), o sistema deve interceptá-lo e redirecioná-lo obrigatoriamente para a interface de **Cadastro de Empresa** antes de permitir o uso do sistema.
- **No Login (`login.py` e Pós-Login):** 
  - Ao autenticar com sucesso o e-mail e a senha, a API valida o vínculo empresarial e direciona o usuário direto para a **Interface Principal (Pós-Login)**.
- **Padrão Visual da Interface Principal (WIP):**
  - A tela principal exibida após o login deve conter claramente a indicação **(WORK IN PROGRESS)**.
  - Deve exibir a **folha canadense cinza** como logo/marca d'água na parte inferior da tela.
  - A paleta de cores de todo o front-end básico deve seguir rigorosamente o padrão **laranja, preto e cinza**.

---

## 4. Como Rodar e Testar o Projeto

- **Gerenciamento via `uv` (na pasta `backend/`):**
  ```powershell
  uv sync                # Sincroniza dependências na venv
  uv run pytest          # Executa a suíte de testes do pytest
  uv run python -m src.app.main   # Inicia a API localmente