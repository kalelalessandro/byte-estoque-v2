# Front-end — Byte Estoque (React + Vite)

Interface integrada à API Flask: boas-vindas, login, cadastro em duas etapas
(usuário → empresa) e aplicação autenticada com dashboard, **produtos** e
**categorias**.

## Como rodar

Pré-requisitos: backend rodando em `http://127.0.0.1:5000` (veja o README da
raiz) e Node.js 20.19+ ou 22.12+ (testado com Node 24).

```powershell
cd frontend
npm install
npm run dev
```

Abra **http://localhost:5173**. O Vite faz proxy de `/api` para o Flask, então
o cookie de sessão funciona sem configuração de CORS.

Outros comandos:

```powershell
npm run build     # build de produção em dist/
npm run preview   # serve o build localmente
```

> Se o backend estiver em outra porta/host, copie `.env.example` para `.env` e
> ajuste `VITE_API_URL` (e o proxy em `vite.config.js`).

## Identidade visual

- Paleta: **azul profundo** `#233d4d` como cor primária, **laranja** `#f97316`
  como destaque secundário e textos claros.
- Fundo com **gradiente de fundo do mar** (azul escuro → `#233d4d`, com raios
  de luz suaves) para evitar cansaço visual.
- Folha canadense cinza como logo e marca d'água na parte inferior das telas.
- Dashboard com cards de produtos, categorias, parceiros, dinheiro e valor em
  estoque; os cards de parceiros/dinheiro estão marcados como **em breve** até
  os módulos financeiro/parceiros existirem na API.
- A seção inferior do dashboard mantém o `(WORK IN PROGRESS)`.

## Fluxo de telas

1. **Tela inicial** — apresentação e botões "Criar conta" / "Já tenho conta".
2. **Cadastro de usuário** (etapa 1) — dados da conta de acesso.
3. **Cadastro de empresa** (etapa 2) — dados da empresa, enviados junto com o
   usuário em uma única transação atômica (`POST /api/auth/cadastro`).
4. **Início** — pós-login, sidebar com navegação e resumo do estoque.
5. **Produtos** — listar/buscar, criar, editar e excluir produtos; o formulário
   exige a seleção de uma categoria da empresa. A exclusão é bloqueada quando o
   produto tem operações vinculadas.
6. **Categorias** — criar, renomear e excluir categorias. A exclusão só é
   liberada para categorias sem produtos; com produtos vinculados o botão fica
   desabilitado e a API também responde `409`.

Após o cadastro, o front faz login automaticamente. Se a API sinalizar
`precisa_cadastrar_empresa: true` (regra defensiva), a tela de empresa
pendente é exibida.
