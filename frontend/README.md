# abkit frontend

React 19 + TypeScript (strict) + Vite + Ant Design 6 + TanStack Query + React
Router + ECharts. См. `FRONTEND.md` в корне репозитория — единственное
действующее ТЗ.

## Разработка

```bash
npm install
npm run dev          # http://localhost:5173, проксирует /api на localhost:8000 (vite.config.ts)
```

Backend должен быть поднят отдельно: `uvicorn backend.main:app` (нужны
`ABKIT_SECRET_KEY`, `DATABASE_URL`, `ABKIT_MODE=db` в окружении — см. корневой
`.env.example`).

## Проверки

```bash
npm run typecheck    # tsc -b --noEmit
npm run lint         # eslint .
npm run build        # tsc -b && vite build
npm run test:e2e      # playwright test — нужен реально запущенный backend+frontend (см. e2e/helpers.ts)
```

## Типы API

`src/api/schema.ts` генерируется из живой OpenAPI-схемы backend'а —
**не редактировать вручную**. Перегенерировать после изменения backend-роутеров:

```bash
npm run gen:api
```

(активирует backend/scripts/dump_openapi.py — печатает схему через
`create_app().openapi()`, без поднятого сервера/БД).

## Структура

- `src/api/` — типизированный клиент (`openapi-fetch` + сгенерированные типы)
- `src/auth/` — контекст текущего пользователя, гварды роутов по ролям
- `src/theme/tokens.ts` — единственный источник цветов/шрифтов (зеленый акцент,
  без оранжевого — см. FRONTEND.md §5.1)
- `src/charts/theme.ts` — палитра ECharts (значимое — зеленый, незначимое — серый)
- `src/pages/` — страницы; часть — заглушки до R5/R6 (визард дизайна, страница
  теста целиком, секция Анализ, /validation) — см. комментарии в файлах
- `e2e/` — Playwright: логин, список, права, удаление с подтверждением DELETE
