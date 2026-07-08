import { defineConfig, devices } from '@playwright/test'

// FRONTEND.md §7 R4: "Playwright: логин, список, права, удаление с DELETE."
// webServer не настроен здесь намеренно — backend (uvicorn) и frontend (vite
// dev) поднимаются отдельно в CI/docker compose (R7); локально см.
// docker/README.md после R7, либо `npm run dev` + uvicorn вручную.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  // Один воркер: несколько спеков делят один backend + Postgres (реальный
  // rate-limit логина считает попытки по email в БД) — параллельные воркеры
  // могли бы гоняться друг с другом и залочить общий admin@e2e.test.
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
