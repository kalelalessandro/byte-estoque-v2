const { defineConfig } = require('cypress');
const { createTasks } = require('./cypress/tasks/db');

module.exports = defineConfig({
  e2e: {
    // O front (Vite) faz proxy de /api para o Flask: o cookie de sessão fica no
    // mesmo host, então cy.request e a tela compartilham a mesma sessão.
    baseUrl: process.env.BASE_URL || 'http://localhost:5173',
    specPattern: 'cypress/e2e/**/*.cy.js',
    supportFile: 'cypress/support/e2e.js',
    viewportWidth: 1366,
    viewportHeight: 768,
    video: false,
    defaultCommandTimeout: 8000,
    setupNodeEvents(on) {
      on('task', createTasks());
    },
  },
});
