import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Дев-прокси /api -> FastAPI backend (localhost:8000) — в проде frontend и
// /api/* всегда на одном origin через nginx (FRONTEND.md §2), прокси нужен
// только для локальной разработки (vite dev server на другом порту).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
