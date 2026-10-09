Byte Estoque é um software CRM que tem como principal objetivo, unir ambas funcionalidades de um CRM e um software de Estoque.

Planos:

    Banco de dados ✅
    Login ⌛
    Conectar Backend com BD ⌛
    Criptografia
    Caixa
    Clientes
    Compras
    Dashboard
    Relatórios

Planos Futuros:

    Assinatura

## Passo a passo para rodar o BD:

Pré-requisito: ter o [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e aberto.

Entre na pasta `database/` pelo terminal:

```powershell
cd database
```

Crie o arquivo de senhas a partir do modelo:

```powershell
Copy-Item .env.example .env
```

Abra o `.env` e troque as duas senhas de exemplo por senhas suas.

Suba o banco:

```powershell
docker compose up -d
```

Na primeira vez ele baixa a imagem do MySQL (alguns minutos). Confirme que subiu:

```powershell
docker compose ps
```

Deve aparecer `running` e `healthy`. Se ainda estiver `starting`, aguarde uns 30 segundos e rode de novo.

O banco já vem com as tabelas criadas e dados de exemplo.

## Testando o banco

Com o banco no ar, ainda dentro de `database/`:

```powershell
Get-Content .\verificacao\03_verificacao.sql -Raw | docker compose exec -T mysql mysql -u root -p crm_estoque
```

Digite a senha do root (a que você colocou no `.env`). No fim deve aparecer:

    testes_ok   testes_com_falha   veredito
    26          0                  TODAS AS RESTRICOES FUNCIONAM

São 26 testes que conferem as regras do banco. Pode rodar quantas vezes quiser: o teste não altera os dados.

Cada teste está explicado em `database/verificacao/Teste_SQL-001.md`.

## Conectando no banco

| | |
|---|---|
| Host | `127.0.0.1` |
| Porta | `3306` |
| Banco | `crm_estoque` |
| Usuário | `app_crm` |
| Senha | a que você colocou em `MYSQL_PASSWORD` no `.env` |

## Comandos úteis

```powershell
docker compose stop      # para o banco
docker compose start     # liga de novo
docker compose down      # remove o container, mas os dados continuam salvos
docker compose down -v   # apaga tudo, inclusive os dados
```
