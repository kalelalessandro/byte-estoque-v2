// Tasks do Cypress que rodam em Node e falam direto com o MySQL do projeto.
//
// A interface é sempre testada pela tela e a massa de dados é criada pela API.
// O banco só é usado para duas coisas:
//   1) LIMPAR o que os testes criaram (nunca apaga dados de outras pessoas);
//   2) CONFERIR o que nenhuma tela/API expõe (ex.: hash da senha).
const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');

// Todo usuário criado pelos testes usa este domínio. É assim que a limpeza sabe
// o que pode apagar (o pytest do backend usa "@exemplo.com.br", sem "e2e.").
const PADRAO_EMAIL_E2E = '%@e2e.exemplo.com.br';

/** Lê o database/.env do projeto (mesmas credenciais que o backend usa). */
function lerEnvDoBanco() {
  const arquivo = path.resolve(__dirname, '../../../database/.env');
  const valores = {};
  if (fs.existsSync(arquivo)) {
    for (const linha of fs.readFileSync(arquivo, 'utf8').split(/\r?\n/)) {
      const m = linha.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/);
      if (m && !linha.trim().startsWith('#')) valores[m[1]] = m[2];
    }
  }
  return valores;
}

function createTasks() {
  const env = { ...lerEnvDoBanco(), ...process.env };
  let pool;
  const db = () =>
    (pool ??= mysql.createPool({
      host: env.MYSQL_HOST || '127.0.0.1',
      port: Number(env.MYSQL_PORT || 3306),
      user: env.MYSQL_USER,
      password: env.MYSQL_PASSWORD,
      database: env.MYSQL_DATABASE || 'crm_estoque',
      dateStrings: true,
    }));
  const sql = (texto, params = []) => db().query(texto, params);

  return {
    /** Apaga empresas, usuários, categorias e produtos criados pelos testes. */
    async 'db:cleanup'() {
      const [empresas] = await sql(
        'SELECT DISTINCT id_empresa FROM usuarios WHERE email LIKE ?',
        [PADRAO_EMAIL_E2E],
      );
      if (empresas.length === 0) return null;
      const ids = empresas.map((e) => e.id_empresa);

      // Ordem importa: quem depende (FK RESTRICT) é apagado primeiro.
      await sql(
        `DELETE oi FROM operacao_itens oi
           JOIN operacoes o ON o.id_operacao = oi.id_operacao
           JOIN usuarios u ON u.id_usuario = o.id_usuario
          WHERE u.email LIKE ?`,
        [PADRAO_EMAIL_E2E],
      );
      await sql(
        `DELETE o FROM operacoes o
           JOIN usuarios u ON u.id_usuario = o.id_usuario
          WHERE u.email LIKE ?`,
        [PADRAO_EMAIL_E2E],
      );
      await sql('DELETE FROM produtos WHERE id_empresa IN (?)', [ids]);
      await sql('DELETE FROM categorias WHERE id_empresa IN (?)', [ids]);
      await sql('DELETE FROM usuarios WHERE email LIKE ?', [PADRAO_EMAIL_E2E]);
      await sql('DELETE FROM empresas WHERE id_empresa IN (?)', [ids]);
      return null;
    },

    /** Devolve o usuário como está gravado no banco (inclui hash_senha e cargo). */
    async 'db:usuario'({ email }) {
      const [linhas] = await sql(
        `SELECT u.*, c.cargo
           FROM usuarios u JOIN cargos c ON c.id_cargo = u.id_cargo
          WHERE u.email = ?`,
        [email],
      );
      return linhas[0] || null;
    },

    /**
     * Cria uma operação com 1 item para o produto. Serve para testar a regra
     * "produto que já participou de uma operação não pode ser apagado"
     * (o módulo de operações ainda não existe na interface).
     */
    async 'db:vincularProdutoEmOperacao'({ sku, email }) {
      const [[usuario]] = await sql(
        'SELECT id_usuario, id_empresa FROM usuarios WHERE email = ?',
        [email],
      );
      const [[produto]] = await sql(
        'SELECT id_produto FROM produtos WHERE sku = ? AND id_empresa = ?',
        [sku, usuario.id_empresa],
      );
      const [operacao] = await sql(
        `INSERT INTO operacoes (id_usuario, tipo, status, ocorrencia)
         VALUES (?, 'venda', 'pendente', NOW())`,
        [usuario.id_usuario],
      );
      await sql(
        `INSERT INTO operacao_itens (id_operacao, id_produto, quantidade, valor_unitario)
         VALUES (?, ?, 1, 1.00)`,
        [operacao.insertId, produto.id_produto],
      );
      return null;
    },
  };
}

module.exports = { createTasks };
