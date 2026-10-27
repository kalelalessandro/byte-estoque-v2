INÍCIO
├── Login
│   ├── Informar e-mail e senha
│   ├── Validar usuário e permissões
│   └── Tela principal
│
└── Cadastro inicial
    └── Cadastrar empresa e usuário dono
        ├── Validar os dados
        ├── Criar empresa e usuário dono
        └── Tela principal

TELA PRINCIPAL
├── Usuários e configurações
│   ├── Gerenciar usuários funcionários
│   │   ├── Criar usuário funcionário
│   │   │   ├── Informar nome
│   │   │   ├── Informar e-mail
│   │   │   ├── Definir credenciais de acesso
│   │   │   └── Atribuir cargo e permissões disponíveis
│   │   ├── Listar e consultar funcionários
│   │   ├── Alterar dados do funcionário
│   │   └── Gerenciar acesso conforme as permissões
│   └── Configurações da empresa
│
├── Parceiros
│   ├── Criar parceiro
│   ├── Listar e consultar parceiros
│   ├── Alterar parceiro
│   ├── Acessar parceiro
│   │   └── Registrar e consultar interações
│   └── Excluir parceiro, quando permitido
│
├── Produtos e categorias
│   ├── Listar produtos
│   ├── Criar produto
│   ├── Alterar produto
│   ├── Criar categoria
│   └── Alterar categoria
│
├── Operações
│   ├── Criar compra ou venda
│   ├── Selecionar parceiro
│   ├── Adicionar produtos e quantidades
│   ├── Definir condição de pagamento
│   └── Concluir operação
│       ├── Atualizar estoque
│       └── Gerar títulos financeiros, quando aplicável
│
├── Financeiro
│   ├── Listar e filtrar títulos
│   ├── Criar título manual
│   ├── Consultar título
│   ├── Alterar título, conforme as regras
│   ├── Registrar pagamento/recebimento
│   │   └── Informar dados da baixa
│   └── Consultar histórico de baixas
│
├── Caixa
│   ├── Abrir caixa
│   ├── Consultar movimentações
│   ├── Registrar suprimento ou sangria
│   ├── Conferir valores
│   └── Fechar caixa
│       └── Informar valor contado
│
└── Baixas financeiras
    ├── Listar baixas
    ├── Consultar uma baixa
    └── Registrar baixa manualmente pela interface
        ├── Selecionar título
        ├── Selecionar caixa aberto
        ├── Informar valor, data e forma de pagamento
        └── Confirmar e salvar