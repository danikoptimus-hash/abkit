# abkit — заметки для Claude Code

Инструмент для A/B-тестирования (дизайн выборки, анализ результатов, A/A-/A/B-валидация). Полная техническая спецификация — в отдельных документах, читать их, а не пересказ здесь:

- [DESIGN.md](DESIGN.md) — ядро (`abkit/`): дизайн эксперимента, статистика, отчеты.
- [DOCKER.md](DOCKER.md) — командный Docker-режим: Postgres, роли/аутентификация, аудит-лог.
- [FRONTEND.md](FRONTEND.md) — миграция интерфейса со Streamlit на React+FastAPI (этапы R1-R8), архитектура `backend/` и `frontend/`.
- [README.md](README.md) — пользовательская документация (файловый и Docker-режимы).
- [docker/README.md](docker/README.md) — развертывание.

## Текущее состояние (после R7.5, до R8)

Интерфейс — **React-UI** (`frontend/`, за `backend/` на FastAPI). Старый Streamlit (`app.py`) пока жив на `/legacy/` только на период миграции — будет полностью удален на этапе R8 FRONTEND.md (уже согласовано пользователем, ждет исполнения/уже выполнено — см. FRONTEND.md §7 на предмет актуального состояния).

## Тесты

- Backend/ядро: `python -m pytest -q` (из корня, venv `.venv`), lint — `python -m pyflakes abkit backend tests migrations app.py cli.py cli_admin.py conftest.py`.
- Frontend: `cd frontend && npm run typecheck && npm run lint && npm run build`.
- E2E (Playwright, против реального docker-compose стека, НЕ dev-сервера): `cd frontend && npx playwright test` с `E2E_BASE_URL`/`E2E_API_BASE`, см. `.github/workflows/ci.yml` job `e2e`.
- После правок backend-роутов — перегенерировать типы фронта: `cd frontend && npm run gen:api`.

## Осознанные решения по скоупу

- Сырой список файлов эксперимента (легаси-таб «Файлы»: имя+размер каждого файла без действий) в React-UI не портирован — чисто отладочная информация, реально не используется. См. FRONTEND.md §8 «Вне скоупа».
