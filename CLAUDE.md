# abkit — заметки для Claude Code

Инструмент для A/B-тестирования (дизайн выборки, анализ результатов, A/A-/A/B-валидация). Полная техническая спецификация — в отдельных документах, читать их, а не пересказ здесь:

- [DESIGN.md](DESIGN.md) — ядро (`abkit/`): дизайн эксперимента, статистика, отчеты.
- [DOCKER.md](DOCKER.md) — командный Docker-режим: Postgres, роли/аутентификация, аудит-лог.
- [FRONTEND.md](FRONTEND.md) — история миграции интерфейса со Streamlit на React+FastAPI (этапы R1-R8, все завершены), архитектура `backend/` и `frontend/`.
- [README.md](README.md) — пользовательская документация (файловый и Docker-режимы).
- [docker/README.md](docker/README.md) — развертывание.

## Текущее состояние (после R8, миграция завершена)

Интерфейс — **React-UI** (`frontend/`, за `backend/` на FastAPI) плюс минимальный CLI (`cli.py`/`cli_admin.py`). Streamlit (`app.py`) полностью удален вместе с сервисом `legacy` и маршрутом `/legacy` — DESIGN.md §7 и DOCKER.md описывают его только как историю (см. примечания в начале этих файлов), актуальная архитектура — FRONTEND.md + `docker-compose.yml`.

## Тесты

- Backend/ядро: `python -m pytest -q` (из корня, venv `.venv`), lint — `python -m pyflakes abkit backend tests migrations cli.py cli_admin.py conftest.py`.
- Frontend: `cd frontend && npm run typecheck && npm run lint && npm run build`.
- E2E (Playwright, против реального docker-compose стека, НЕ dev-сервера): `cd frontend && npx playwright test` с `E2E_BASE_URL`/`E2E_API_BASE`, см. `.github/workflows/ci.yml` job `e2e`.
- После правок backend-роутов — перегенерировать типы фронта: `cd frontend && npm run gen:api`.

## Осознанные решения по скоупу

- Сырой список файлов эксперимента (легаси-таб «Файлы»: имя+размер каждого файла без действий) в React-UI не портирован — чисто отладочная информация, реально не используется. См. FRONTEND.md §8 «Вне скоупа».
