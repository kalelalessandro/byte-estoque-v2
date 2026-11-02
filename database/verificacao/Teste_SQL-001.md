# Casos de Teste - Banco de Dados

**Projeto:** Byte Estoque (CRM + Estoque + Financeiro)
**Componente testado:** banco de dados MySQL 8.0.43 em container Docker
**Arquivo de teste:** [`03_verificacao.sql`](03_verificacao.sql)
**Versão do schema:** conforme `crm-estoque/docs/schema_bd.md` (documentação v1.1)
**Data da execução registrada:** execução desta versão, no ambiente de desenvolvimento do projeto

---

## 1. Objetivo da verificação

O schema do banco declara **chaves primárias, chaves estrangeiras, restrições `UNIQUE`, restrições `CHECK` e valores padrão**. Uma restrição pode estar corretamente escrita no arquivo `.sql` e, ainda assim, não estar funcionando no banco em execução — por versão incorreta do MySQL, por erro de digitação, por incompatibilidade de tipo ou por tabela não criada.

Esta verificação tem **dois níveis**:

| Nível | Pergunta que responde | Onde |
|---|---|---|
| **Estrutura** | As restrições existem no banco? | Bloco 1 do script |
| **Comportamento** | As restrições realmente bloqueiam dados inválidos? | Bloco 2 do script (26 casos) |

O foco está no **segundo nível**: o teste não pergunta ao banco "você tem esta restrição?", e sim **tenta gravar um dado inválido** e confere se o banco rejeita com o erro correto. Uma restrição que existe mas não bloqueia nada é tratada como **reprovada**.

---

## 2. Escopo

**Dentro do escopo:**

- As 13 tabelas do schema
- 26 casos de teste sobre unicidade, integridade referencial, validação de valores e valores padrão
- Integridade dos dados de exemplo (Bloco 3)

**Fora do escopo** (o banco não garante, é responsabilidade da aplicação — ver seção final do README principal):

- Autenticação, sessão e permissões por cargo
- Normalização de CNPJ, CPF, CEP e telefone
- Isolamento de empresa em interações, operações, movimentos, títulos e baixas
- Controle de concorrência e transações de negócio (estoque, baixas, fechamento de caixa)
- Listas permitidas de `tipo`, `status`, `canal` e `forma_pagamento`

---

## 3. Pré-condições gerais

Todos os casos assumem o mesmo estado inicial:

1. Docker Desktop em execução.
2. Container `byte_estoque_mysql` no ar e com saúde `healthy` (`docker compose ps`).
3. Schema aplicado pelas 13 tabelas (`database/init/01_schema.sql`).
4. Dados de exemplo carregados (`database/init/02_seed.sql`), sem alterações manuais.

> Sem o passo 4, os casos que dependem de dados existentes (CNPJ da empresa 1, e-mail do usuário 1, SKU `PRES-001`) não têm o que duplicar e seriam reprovados por motivo errado.

## 4. Como executar

De dentro da pasta `database/`:

```powershell
# PowerShell (Windows)
Get-Content .\verificacao\03_verificacao.sql -Raw | docker compose exec -T mysql mysql -u root -p crm_estoque
```

```bash
# Bash (Linux / macOS / Git Bash)
docker compose exec -T mysql mysql -u root -p crm_estoque < verificacao/03_verificacao.sql
```

Digite a senha do root (chave `MYSQL_ROOT_PASSWORD` do arquivo `database/.env`) quando for pedida.

## 5. Como o mecanismo de teste funciona

Cada caso segue o mesmo padrão, dentro de um procedimento MySQL:

1. **`DECLARE CONTINUE HANDLER FOR SQLEXCEPTION`** — instrui o MySQL a **não abortar** o script quando ocorrer um erro, mas registrar o número e a mensagem do erro.
2. **`GET DIAGNOSTICS CONDITION 1 v_erro = MYSQL_ERRNO`** — copia o código do erro para a variável `v_erro`.
3. **`INSERT` inválido** — o dado que deve ser recusado.
4. **`IF v_erro = <código esperado>`** — veredito. Se o erro esperado veio, o caso é aprovado; se o banco aceitou o dado ou devolveu outro erro, é reprovado.

Quatro casos são de **aceitação** (o dado é válido e **deve** ser gravado): neles, o veredito é `v_erro = 0`.

**Códigos de erro do MySQL usados:**

| Código | Significado |
|---|---|
| `1062` | Entrada duplicada (violação de `UNIQUE` ou de chave primária) |
| `3819` | Restrição `CHECK` violada |
| `1452` | Chave estrangeira inválida (registro pai não existe) |
| `1451` | Exclusão bloqueada: existem dependentes (`ON DELETE RESTRICT`) |

**Garantia de não interferência:** os 26 casos rodam dentro de **uma única transação**, iniciada com `START TRANSACTION` e encerrada com `ROLLBACK`. Nenhum registro de teste permanece no banco após a execução. Por isso o teste pode ser repetido quantas vezes for necessário, inclusive em ambiente de apresentação.

Cada caso roda em um bloco `BEGIN ... END` próprio, com seu **próprio** tratador de erro, para que a falha de um caso não contamine o resultado dos demais.

---

## 6. Resumo dos casos de teste

| ID | Título | Restrição verificada | Esperado | Obtido | Status |
|---|---|---|---|---|---|
| BD-001 | CNPJ duplicado | `uq_empresas_cnpj` | erro 1062 | erro 1062 | Aprovado |
| BD-002 | E-mail de usuário duplicado | `uq_usuarios_email` | erro 1062 | erro 1062 | Aprovado |
| BD-003 | SKU repetido na mesma empresa | `uq_produtos_empresa_sku` | erro 1062 | erro 1062 | Aprovado |
| BD-004 | Mesmo SKU em outra empresa (aceitação) | `uq_produtos_empresa_sku` | aceito | aceito (id_produto 67) | Aprovado |
| BD-005 | Produto com categoria de outra empresa | `fk_produtos_categoria` (FK composta) | erro 1452 | erro 1452 | Aprovado |
| BD-006 | Parceiro sem ser cliente nem fornecedor | `chk_parceiros_relacionamento` | erro 3819 | erro 3819 | Aprovado |
| BD-007 | E-mail de parceiro só com espaços | `chk_parceiros_email` | erro 3819 | erro 3819 | Aprovado |
| BD-008 | Estoque negativo | `chk_produtos_estoque` | erro 3819 | erro 3819 | Aprovado |
| BD-009 | Preço negativo | `chk_produtos_preco` | erro 3819 | erro 3819 | Aprovado |
| BD-010 | Item de operação com quantidade zero | `chk_operacao_itens_quantidade` | erro 3819 | erro 3819 | Aprovado |
| BD-011 | Produto repetido na mesma operação | PK composta `(id_operacao, id_produto)` | erro 1062 | erro 1062 | Aprovado |
| BD-012 | Caixa com fechamento incompleto | `chk_caixas_fechamento` | erro 3819 | erro 3819 | Aprovado |
| BD-013 | Fechamento anterior à abertura | `chk_caixas_fechamento` | erro 3819 | erro 3819 | Aprovado |
| BD-014 | Movimento de caixa com valor zero | `chk_operacoes_caixa_valor` | erro 3819 | erro 3819 | Aprovado |
| BD-015 | Título com valor zero | `chk_titulos_financeiros_valor` | erro 3819 | erro 3819 | Aprovado |
| BD-016 | Baixa com valor negativo | `chk_baixas_financeiras_valor` | erro 3819 | erro 3819 | Aprovado |
| BD-017 | Usuário em empresa inexistente | `fk_usuarios_empresa` | erro 1452 | erro 1452 | Aprovado |
| BD-018 | Exclusão de empresa com dependentes | `ON DELETE RESTRICT` (19 FKs) | erro 1451 | erro 1451 | Aprovado |
| BD-019 | Valores padrão de estoque e `admin_sistema` | `DEFAULT 0` | 0 e 0 | 0 e 0 | Aprovado |
| BD-020 | Collation sem diferenciar maiúsculas no SKU | `utf8mb4_0900_ai_ci` + `uq_produtos_empresa_sku` | erro 1062 | erro 1062 | Aprovado |
| BD-021 | Documento repetido na mesma empresa | `uq_parceiros_empresa_documento` | erro 1062 | erro 1062 | Aprovado |
| BD-022 | Categoria repetida na mesma empresa | `uq_categorias_empresa_nome` | erro 1062 | erro 1062 | Aprovado |
| BD-023 | Cargo repetido | `uq_cargos_cargo` | erro 1062 | erro 1062 | Aprovado |
| BD-024 | Caixa fechado de forma coerente (aceitação) | `chk_caixas_fechamento` | aceito | aceito (id_caixa 10) | Aprovado |
| BD-025 | Título sem informar `cancelado` | `DEFAULT 0` em `cancelado` | aceito, cancelado = 0 | aceito, cancelado = 0 | Aprovado |
| BD-026 | Título sem operação de origem (`NULL`) | `id_operacao` aceita `NULL` | aceito | aceito (id_titulo 21) | Aprovado |

**Resultado consolidado:**

```
testes_ok   testes_com_falha   veredito
26          0                  TODAS AS RESTRICOES FUNCIONAM
```

> Os identificadores numéricos em BD-004, BD-024, BD-025 e BD-026 (`id_produto`, `id_caixa`, `id_titulo`) variam a cada execução, porque o MySQL não reaproveita números de `AUTO_INCREMENT`. O que importa é que o registro foi gravado com sucesso.

---

## 7. Detalhamento dos casos

### BD-001 — CNPJ duplicado

- **Título / Descrição:** garantir que não existam duas empresas com o mesmo CNPJ no sistema.
- **Justificativa:** o CNPJ é o identificador fiscal da organização. Duplicá-lo permitiria dois cadastros para a mesma empresa, quebrando relatórios e o isolamento de dados.
- **Pré-condições:** empresa com CNPJ `11222333000181` cadastrada (dados de exemplo).
- **Passos de execução:**
  1. Inserir em `empresas` uma nova linha com `razao_social = 'Empresa Duplicada'` e `cnpj = '11222333000181'`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** o banco recusa com erro **1062** (Duplicate entry), por causa da restrição `uq_empresas_cnpj`.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-002 — E-mail de usuário duplicado

- **Título / Descrição:** garantir que o e-mail de usuário seja único em toda a tabela, inclusive entre empresas diferentes.
- **Justificativa:** o e-mail é a identificação de acesso da conta. Dois usuários com o mesmo e-mail tornariam o login ambíguo.
- **Pré-condições:** usuário com e-mail `ana.souza@padariaaurora.com.br` cadastrado na empresa 1.
- **Passos de execução:**
  1. Inserir em `usuarios` um novo usuário pertencente à **empresa 2**, com o mesmo e-mail do usuário da empresa 1.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062**, por causa de `uq_usuarios_email`. A unicidade é global, não por empresa.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-003 — SKU repetido na mesma empresa

- **Título / Descrição:** impedir dois produtos com o mesmo SKU dentro da mesma empresa.
- **Justificativa:** o SKU é o código de identificação do produto dentro da empresa. Repeti-lo causaria ambiguidade em pedidos e no estoque.
- **Pré-condições:** produto com SKU `PRES-001` cadastrado na empresa 1; categoria `Padaria` (id 2) pertencente à empresa 1.
- **Passos de execução:**
  1. Inserir em `produtos` um novo produto na **empresa 1** com `sku = 'PRES-001'`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062**, por causa de `uq_produtos_empresa_sku` (`id_empresa`, `sku`).
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-004 — Mesmo SKU em outra empresa (aceitação)

- **Título / Descrição:** garantir que o mesmo SKU **possa** ser usado por empresas diferentes.
- **Justificativa:** é o par `(id_empresa, sku)` que é único, não o SKU isolado. Este caso é o contraponto de BD-003: prova que a restrição não é global, o que permite que duas empresas clientes do sistema usem códigos iguais.
- **Pré-condições:** SKU `ZZ-TESTE-SKU-REPETIDO` inexistente na empresa 2; categoria `Mercearia` (id 3) pertencente à empresa 2.
- **Passos de execução:**
  1. Inserir em `produtos` um produto na **empresa 2** com `sku = 'ZZ-TESTE-SKU-REPETIDO'`.
  2. Confirmar que a gravação ocorreu.
- **Resultado esperado:** gravação **aceita**, sem erro.
- **Resultado obtido:** `aceito (id_produto 67)`.
- **Status:** Aprovado.

### BD-005 — Produto com categoria de outra empresa

- **Título / Descrição:** garantir que a categoria de um produto pertença à mesma empresa do produto.
- **Justificativa:** o catálogo de categorias é por empresa. Permitir que um produto da empresa 1 use uma categoria da empresa 2 misturaria dados de organizações diferentes — falha grave em sistema multiusuário.
- **Pré-condições:** categoria `Mercearia` pertence à empresa 2; existe a empresa 1.
- **Passos de execução:**
  1. Inserir em `produtos` um produto na **empresa 1** apontando para `id_categoria = 3` (categoria da empresa 2).
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1452**, por causa da **chave estrangeira composta** `fk_produtos_categoria`, que compara `(id_categoria, id_empresa)` em conjunto.
- **Resultado obtido:** `erro 1452`.
- **Status:** Aprovado.

### BD-006 — Parceiro sem ser cliente nem fornecedor

- **Título / Descrição:** impedir cadastro de parceiro que não seja cliente nem fornecedor.
- **Justificativa:** um parceiro sem papel comercial definido não tem função no sistema; normaliza o cadastro e evita registros vazios.
- **Pré-condições:** empresa 1 cadastrada.
- **Passos de execução:**
  1. Inserir em `parceiros` um registro com `e_cliente = FALSE` e `e_fornecedor = FALSE`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_parceiros_relacionamento`.
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-007 — E-mail de parceiro só com espaços

- **Título / Descrição:** impedir que o e-mail opcional de parceiro seja gravado como texto vazio ou apenas espaços.
- **Justificativa:** o campo é opcional, e a ausência correta é `NULL`. Gravar `'   '` cria um dado "sujo" que passa a parecer preenchido em relatórios e consultas.
- **Pré-condições:** empresa 1 cadastrada.
- **Passos de execução:**
  1. Inserir em `parceiros` um registro com `email = '   '` (três espaços).
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_parceiros_email`, que exige `CHAR_LENGTH(TRIM(email)) > 0` quando o valor não é `NULL`.
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-008 — Estoque negativo

- **Título / Descrição:** impedir quantidade de estoque negativa.
- **Justificativa:** o modelo considera unidades inteiras de estoque físico. Um saldo negativo indica erro de lançamento e corromperia relatórios e a lógica de reposição.
- **Pré-condições:** empresa 1 e categoria `Padaria` (id 2) cadastradas.
- **Passos de execução:**
  1. Inserir em `produtos` um produto com `unidade_estoque = -1`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_produtos_estoque` (`unidade_estoque >= 0`).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-009 — Preço negativo

- **Título / Descrição:** impedir preço de produto com valor negativo.
- **Justificativa:** preço é valor monetário; negativo não tem significado comercial e geraria totais incorretos nas operações.
- **Pré-condições:** empresa 1 e categoria `Padaria` (id 2) cadastradas.
- **Passos de execução:**
  1. Inserir em `produtos` um produto com `preco = -5.00`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_produtos_preco` (`preco >= 0`).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-010 — Item de operação com quantidade zero

- **Título / Descrição:** impedir item de compra/venda com quantidade igual a zero.
- **Justificativa:** um item com quantidade zero não representa transação alguma e distorceria o total da operação e a movimentação de estoque.
- **Pré-condições:** operação 1 cadastrada; produto 3 cadastrado.
- **Passos de execução:**
  1. Inserir em `operacao_itens` uma linha com `quantidade = 0`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_operacao_itens_quantidade` (`quantidade > 0`).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-011 — Produto repetido na mesma operação

- **Título / Descrição:** garantir que o mesmo produto apareça uma única vez em cada operação.
- **Justificativa:** a chave primária composta `(id_operacao, id_produto)` consolida a quantidade por produto. Repetir o produto permitiria dois preços unitários diferentes para o mesmo item na mesma operação.
- **Pré-condições:** operação 1 já possui o produto 1 (quantidade 20).
- **Passos de execução:**
  1. Inserir em `operacao_itens` novamente o par `(id_operacao = 1, id_produto = 1)`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062**, por violação da chave primária composta.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-012 - Caixa com fechamento incompleto

- **Título / Descrição:** impedir que uma sessão de caixa fique com data de fechamento mas sem valor contado.
- **Justificativa:** o fechamento de caixa exige a conferência do dinheiro. Registrar a data sem o valor contado deixaria a sessão em estado inconsistente, sem como apurar diferença.
- **Pré-condições:** usuário 3 cadastrado.
- **Passos de execução:**
  1. Inserir em `caixas` uma sessão com `fechado_em` preenchido e `valor_contado` nulo.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_caixas_fechamento`, que exige as duas colunas nulas (caixa aberto) ou as duas preenchidas (caixa fechado).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-013 - Fechamento anterior à abertura

- **Título / Descrição:** impedir data de fechamento anterior à data de abertura do caixa.
- **Justificativa:** incoerência temporal. Um fechamento antes da abertura produziria duração negativa e invalidaria relatórios de turno.
- **Pré-condições:** usuário 3 cadastrado.
- **Passos de execução:**
  1. Inserir em `caixas` uma sessão com `aberto_em = '2026-03-01 18:00:00'` e `fechado_em = '2026-03-01 08:00:00'`, com `valor_contado` preenchido.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_caixas_fechamento`, que exige `fechado_em >= aberto_em`.
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-014 - Movimento de caixa com valor zero

- **Título / Descrição:** impedir lançamento de suprimento ou sangria com valor zero.
- **Justificativa:** movimento de valor zero não movimenta nada e poluiria o histórico do caixa, dificultando a conferência.
- **Pré-condições:** caixa 1 e usuário 3 cadastrados.
- **Passos de execução:**
  1. Inserir em `operacoes_caixa` um movimento do tipo `sangria` com `valor = 0`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_operacoes_caixa_valor` (`valor > 0`).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-015 - Título com valor zero

- **Título / Descrição:** impedir título financeiro com valor zero.
- **Justificativa:** um título representa uma obrigação a pagar ou receber. Valor zero não é obrigação e criaria lançamentos inúteis no financeiro.
- **Pré-condições:** parceiro 1 cadastrado.
- **Passos de execução:**
  1. Inserir em `titulos_financeiros` um título com `valor = 0`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_titulos_financeiros_valor` (`valor > 0`).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-016 - Baixa com valor negativo

- **Título / Descrição:** impedir baixa (pagamento/recebimento) com valor negativo.
- **Justificativa:** a baixa registra o que foi efetivamente liquidado. Valor negativo inverteria a natureza da operação e corromperia o saldo do título.
- **Pré-condições:** título 2 e caixa 1 cadastrados.
- **Passos de execução:**
  1. Inserir em `baixas_financeiras` uma baixa com `valor = -10.00`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **3819**, por causa de `chk_baixas_financeiras_valor` (`valor > 0`).
- **Resultado obtido:** `erro 3819`.
- **Status:** Aprovado.

### BD-017 - Usuário em empresa inexistente

- **Título / Descrição:** garantir que um usuário não possa ser vinculado a uma empresa que não existe.
- **Justificativa:** integridade referencial básica. Um usuário órfão ficaria inacessível e sem contexto de empresa, quebrando o isolamento de dados.
- **Pré-condições:** cargo 1 cadastrado; empresa de id `99999` inexistente.
- **Passos de execução:**
  1. Inserir em `usuarios` um usuário com `id_empresa = 99999`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1452**, por causa de `fk_usuarios_empresa`.
- **Resultado obtido:** `erro 1452`.
- **Status:** Aprovado.

### BD-018 - Exclusão de empresa com dependentes

- **Título / Descrição:** garantir que uma empresa com dados vinculados não possa ser excluída.
- **Justificativa:** preservação de histórico. Todas as 19 chaves estrangeiras usam `ON DELETE RESTRICT`, então excluir um registro principal apagaria (ou deixaria órfãos) usuários, produtos, operações e lançamentos financeiros.
- **Pré-condições:** empresa 1 com usuários, parceiros, categorias, produtos e operações vinculados.
- **Passos de execução:**
  1. Executar `DELETE FROM empresas WHERE id_empresa = 1`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1451** (Cannot delete or update a parent row), por causa de alguma das FKs com `RESTRICT`.
- **Resultado obtido:** `erro 1451`.
- **Status:** Aprovado.

### BD-019 — Valores padrão de estoque e admin_sistema

- **Título / Descrição:** garantir que `produtos.unidade_estoque` e `usuarios.admin_sistema` iniciem em zero quando não informados.
- **Justificativa:** o schema define esses campos como obrigatórios com valor inicial zero/falso. Se o padrão não funcionasse, toda inserção que omitisse o campo falharia ou gravaria valor indefinido.
- **Pré-condições:** empresa 1 e categoria `Padaria` (id 2) cadastradas; cargo 2 cadastrado.
- **Passos de execução:**
  1. Inserir em `produtos` um produto **sem informar** `unidade_estoque`.
  2. Inserir em `usuarios` um usuário **sem informar** `admin_sistema`.
  3. Ler as duas colunas gravadas.
- **Resultado esperado:** `unidade_estoque = 0` e `admin_sistema = 0`.
- **Resultado obtido:** `0 e 0`.
- **Status:** Aprovado.

### BD-020 — Collation sem diferenciar maiúsculas no SKU

- **Título / Descrição:** verificar o efeito da collation `utf8mb4_0900_ai_ci` sobre a unicidade do SKU.
- **Justificativa:** a collation do schema **não diferencia maiúsculas, minúsculas nem acentos**. Isso significa que `pres-001` e `PRES-001` são considerados o mesmo código. É um comportamento intencional do modelo e precisa estar documentado e testado, porque afeta como a aplicação deve tratar o SKU.
- **Pré-condições:** produto com SKU `PRES-001` na empresa 1.
- **Passos de execução:**
  1. Inserir em `produtos` um produto na empresa 1 com `sku = 'pres-001'` (minúsculas).
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062** — a comparação ignora a diferença de caixa e considera o código duplicado.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-021 — Documento repetido na mesma empresa

- **Título / Descrição:** impedir dois parceiros com o mesmo CPF/CNPJ dentro da mesma empresa.
- **Justificativa:** o documento identifica a pessoa ou organização. A unicidade é **por empresa**, permitindo que empresas diferentes atendam o mesmo cliente.
- **Pré-condições:** parceiro com documento `88777666000155` na empresa 1.
- **Passos de execução:**
  1. Inserir em `parceiros` um registro na empresa 1 com o mesmo `documento`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062**, por causa da restrição composta `uq_parceiros_empresa_documento`.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-022 — Categoria repetida na mesma empresa

- **Título / Descrição:** impedir duas categorias com o mesmo nome dentro da mesma empresa.
- **Justificativa:** nomes repetidos dificultam a organização do catálogo e a seleção de categoria no cadastro de produtos.
- **Pré-condições:** categoria `Bebidas` na empresa 1.
- **Passos de execução:**
  1. Inserir em `categorias` outra categoria com `nome = 'Bebidas'` na empresa 1.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062**, por causa da restrição composta `uq_categorias_empresa_nome`.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-023 — Cargo repetido

- **Título / Descrição:** garantir que os cargos sejam únicos, já que a tabela `cargos` é compartilhada por todas as empresas.
- **Justificativa:** `cargos` não possui `id_empresa`; é uma lista global (`Dono`, `Funcionário`, `Financeiro`). Cargos duplicados tornariam ambígua a definição de permissões.
- **Pré-condições:** cargo `Dono` cadastrado.
- **Passos de execução:**
  1. Inserir em `cargos` um novo cargo com `cargo = 'Dono'`.
  2. Ler o código de erro devolvido.
- **Resultado esperado:** erro **1062**, por causa de `uq_cargos_cargo`.
- **Resultado obtido:** `erro 1062`.
- **Status:** Aprovado.

### BD-024 — Caixa fechado de forma coerente (aceitação)

- **Título / Descrição:** garantir que o **fechamento correto** do caixa seja aceito.
- **Justificativa:** contraponto de BD-012 e BD-013. Uma restrição `CHECK` mal escrita poderia bloquear operações legítimas; este caso prova que o fechamento válido passa.
- **Pré-condições:** usuário 3 cadastrado.
- **Passos de execução:**
  1. Inserir em `caixas` uma sessão com `aberto_em = '2026-03-01 08:00:00'`, `valor_abertura = 100.00`, `fechado_em = '2026-03-01 18:00:00'` e `valor_contado = 480.00`.
  2. Confirmar que a gravação ocorreu.
- **Resultado esperado:** gravação **aceita**, sem erro.
- **Resultado obtido:** `aceito (id_caixa 10)`.
- **Status:** Aprovado.

### BD-025 — Título sem informar `cancelado`

- **Título / Descrição:** garantir que `titulos_financeiros.cancelado` inicie como falso quando não informado.
- **Justificativa:** a maioria dos títulos é criada ativa. Sem o valor padrão funcionando, todo lançamento precisaria informar o campo explicitamente, e um esquecimento poderia marcar títulos como cancelados por engano.
- **Pré-condições:** parceiro 1 cadastrado.
- **Passos de execução:**
  1. Inserir em `titulos_financeiros` um título **sem informar** a coluna `cancelado`.
  2. Ler o valor gravado em `cancelado`.
- **Resultado esperado:** gravação aceita, com `cancelado = 0`.
- **Resultado obtido:** `aceito, cancelado = 0`.
- **Status:** Aprovado.

### BD-026 — Título sem operação de origem (`NULL`)

- **Título / Descrição:** garantir que um título possa existir sem operação comercial vinculada.
- **Justificativa:** nem todo lançamento financeiro nasce de uma compra ou venda — contas de energia, aluguel e outros lançamentos manuais existem. A coluna `id_operacao` é opcional e precisa aceitar `NULL`.
- **Pré-condições:** parceiro 1 cadastrado.
- **Passos de execução:**
  1. Inserir em `titulos_financeiros` um título com `id_operacao = NULL`.
  2. Confirmar que a gravação ocorreu.
- **Resultado esperado:** gravação **aceita**, sem erro.
- **Resultado obtido:** `aceito (id_titulo 21)`.
- **Status:** Aprovado.

---

## 8. Verificações de estrutura (Bloco 1)

Antes dos 26 casos funcionais, o script confere a estrutura efetivamente criada no banco:

| Verificação | Consulta | Esperado | Obtido |
|---|---|---|---|
| Versão e configuração | `VERSION()`, `DATABASE()`, charset e collation padrão | 8.0.43 / crm_estoque / utf8mb4 / utf8mb4_0900_ai_ci | conforme |
| Tabelas criadas | `information_schema.tables` | 13 tabelas, todas InnoDB e utf8mb4 | 13 |
| Tabela faltando | lista esperada × tabelas existentes | nenhuma linha (lista vazia) | vazio |
| Chaves primárias | `information_schema.table_constraints` | 13 | 13 |
| Chaves estrangeiras | `information_schema.referential_constraints` | 19, todas com `RESTRICT` em delete e update | 19 / 19 / 19 |
| Restrições `CHECK` | `table_constraints` + `check_constraints` | 17 | 17 |
| Restrições `UNIQUE` | `table_constraints` (distintas) | 8 | 8 |
| Colunas com valor padrão | `information_schema.columns` | 6 | 6 |

---

## 9. Verificações de integridade dos dados de exemplo (Bloco 3)

Conferem se os dados do `02_seed.sql` estão coerentes entre si:

| Verificação | O que calcula | Esperado | Obtido |
|---|---|---|---|
| Saldo pendente dos títulos | valor do título − soma das baixas | 3 títulos, nenhum saldo negativo | Título 1: 0,00 · Título 2: 400,00 · Título 3: 320,00 |
| Baixa acima do título | quantos títulos têm baixas somando mais que o valor | 0 | 0 |
| Composição do caixa 1 | abertura + movimentos + recebimentos − pagamentos | valores coerentes | abertura 800,00 · movimentos 50,00 · recebimentos 500,00 · pagamentos 1.000,00 |
| Produto com categoria de outra empresa | junção produto × categoria por empresa diferente | 0 | 0 |
| Resumo de registros | contagem por tabela | conforme o seed | 3 empresas, 4 usuários, 5 produtos, 3 operações, 3 títulos, 3 baixas |

---

## 10. Conclusão

| Item | Resultado |
|---|---|
| Casos de teste executados | 26 |
| Aprovados | 26 |
| Reprovados | 0 |
| **Status geral** | **Aprovado** |

O banco de dados em execução **aplica e respeita** todas as restrições declaradas no schema: unicidades simples e compostas, integridade referencial (incluindo a chave estrangeira composta do catálogo), validações de valor e coerência, preservação de histórico por `RESTRICT` e valores padrão.

**Limite desta verificação:** ela comprova o comportamento do **banco**. As regras de negócio que dependem da aplicação (autenticação, isolamento de empresa nas consultas, controle de concorrência, baixa acima do saldo, cancelamento com estorno) **não são cobertas por estes testes** e devem ser verificadas quando o backend FastAPI for implementado.

---

## 11. Rastreabilidade

| Documento | Caminho |
|---|---|
| Script executável dos 26 casos | [`03_verificacao.sql`](03_verificacao.sql) |
| Especificação do schema (fonte da verdade) | [`crm-estoque/docs/schema_bd.md`](../../crm-estoque/docs/schema_bd.md) |
| Documentação do modelo de dados v1.1 | [`crm-estoque/docs/Documentacao_Banco_de_Dados_CRM_Estoque_v1_1-1.pdf`](../../crm-estoque/docs/Documentacao_Banco_de_Dados_CRM_Estoque_v1_1-1.pdf) |
| Dados de exemplo usados nas pré-condições | [`database/init/02_seed.sql`](../init/02_seed.sql) |
| Instruções de instalação e operação | [`README.md`](../../README.md) |
