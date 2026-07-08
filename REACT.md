# REACT.md — ТЗ: переезд фронтенда abkit на React + FastAPI (стиль Superset)

Техническое задание для миграции интерфейса с Streamlit на связку FastAPI (REST API) + React/TypeScript (Ant Design). Референс внешнего вида и UX — Apache Superset, акцентный цвет — зеленый (#2E8B6D), никакого оранжевого.

## 0. Принципы миграции

1. **Ядро неприкосновенно.** `abkit/design`, `abkit/analysis`, `abkit/validation`, `abkit/preprocessing`, `abkit/pipeline` не меняются. Все 450+ существующих тестов ядра и БД-слоя остаются зелеными на каждом этапе. API — тонкая обертка над существующими сервисными функциями.
2. **Переиспользуем всю серверную часть.** БД-слой (`abkit/db/`), auth-модели и хеширование (`abkit/auth/`), аудит, `jobs.py`, import-legacy — используются как есть. Меняется только транспорт: вместо вызовов из Streamlit — вызовы из FastAPI-эндпоинтов.
3. **Параллельное сосуществование.** Streamlit-версия продолжает работать на `/legacy` до достижения функционального паритета. Отключается отдельным финальным этапом только после явного подтверждения пользователя. Обе версии ходят в одну БД.
4. **Никаких изменений схемы БД** ради фронта. Если что-то очень нужно — отдельная миграция Alembic с обоснованием в PR.
5. **Каждый этап** заканчивается зелеными тестами (pytest + новые API-тесты + Playwright там, где появился UI), коммитом и зеленым CI.

## 1. Целевая архитектура

```
┌────────────────────────── nginx :8080 ──────────────────────────┐
│  /            → статика React (frontend/dist)                    │
│  /api/*       → FastAPI (uvicorn :8000)                          │
│  /legacy/*    → Streamlit :8501 (до конца миграции)               │
└──────────────────────────────────────────────────────────────────┘
        │                          │
   ┌────▼─────┐              ┌─────▼─────┐
   │ frontend │              │  backend   │  FastAPI + abkit core
   │ React/TS │              │  uvicorn   │
   └──────────┘              └─────┬─────┘
                                   │
                        ┌──────────┼──────────┐
                   ┌────▼───┐            ┌────▼────────┐
                   │Postgres│            │ volume /data │
                   └────────┘            └─────────────┘
```

Новые директории репозитория:

```
backend/
├── main.py                # FastAPI app, middleware, роутеры
├── deps.py                # DI: сессия БД, текущий пользователь, guard'ы ролей
├── routers/
│   ├── auth.py            # login/logout/me/change-password
│   ├── experiments.py     # CRUD, статусы, выборки, удаление с подтверждением
│   ├── design.py          # запуск дизайна (job)
│   ├── analyze.py         # запуск анализа (job), результаты
│   ├── validation.py      # A/A и A/B симуляции (job)
│   ├── datasets.py        # upload CSV/parquet, метаданные, скачивание
│   ├── admin.py           # пользователи (только admin)
│   └── audit.py           # аудит-лог
├── schemas/               # Pydantic-схемы запросов/ответов (versioned, /api/v1)
├── jobs/                  # менеджер фоновых задач (см. 2.4)
└── tests/                 # pytest + httpx AsyncClient

frontend/
├── src/
│   ├── api/               # типизированный клиент (openapi-typescript из /openapi.json)
│   ├── pages/             # Design, Analyze, Experiments, Validation, Admin, Login, Profile
│   ├── components/        # таблицы, формы метрик, графики, бейджи, диалоги
│   ├── charts/            # forest plot, распределения, кумулятивный лифт (ECharts)
│   ├── theme/             # токены: зеленая палитра, типографика (единый источник)
│   └── auth/              # контекст пользователя, guard'ы роутов по ролям
├── vite.config.ts, tsconfig.json, package.json
└── e2e/                   # Playwright-тесты
```

## 2. Бэкенд: REST API (FastAPI)

### 2.1 Общее

- Префикс `/api/v1`. OpenAPI-схема доступна на `/api/openapi.json` — из нее генерируются TS-типы фронта (single source of truth, контракт не может разъехаться).
- Аутентификация: тот же механизм, что сейчас — подписанный токен в **HttpOnly cookie** (Secure при TLS, SameSite=Lax). Логин выдает cookie, `GET /auth/me` возвращает пользователя и роль. CSRF: для мутаций — заголовок X-CSRF-Token (double-submit cookie) ИЛИ SameSite=Strict — выбрать и обосновать в PR.
- Все мутации проходят те же сервисные функции с проверкой ролей и записью в audit_log, что и сейчас. UI-проверки — только удобство, безопасность — на сервере.
- Ошибки: единый формат `{"error": {"code": "...", "message": "человекочитаемо", "details": {...}}}`. Сообщения — на русском, как в текущем UI (тексты ошибок дизайна/анализа переиспользовать).
- Лимит загрузки — из env ABKIT_MAX_UPLOAD_MB (существующий), стриминговый прием файла на диск (не в память).

### 2.2 Ключевые эндпоинты (маппинг текущих функций)

```
POST   /auth/login {email, password}         → cookie + user
POST   /auth/logout
GET    /auth/me
POST   /auth/change-password

GET    /experiments?status=&q=&page=          → список (пагинация, фильтр, поиск)
GET    /experiments/{id}                      → конфиг + design_summary + файлы
POST   /experiments/{id}/status {to}          → переходы designed→running→completed, →archived
DELETE /experiments/{id} {confirm: "DELETE"}  → удаление; сервер ТРЕБУЕТ confirm=="DELETE"
GET    /experiments/{id}/samples.zip          → ZIP всех групп; /samples/{group}.csv — по группе
GET    /experiments/{id}/reports/design       → design_report.html
GET    /experiments/{id}/reports/analysis     → report.html последнего анализа
GET    /experiments/{id}/results              → results.json последнего анализа (для рендера на фронте)

POST   /datasets {file, kind, experiment_id?} → upload; ответ: dataset_id, n_rows, columns, dtypes
GET    /datasets/{id}/preview?rows=20         → первые строки для превью в UI

POST   /design {config, dataset_id}           → job_id  (валидация конфига — те же pydantic-модели)
POST   /experiments/{id}/analyze {dataset_id, options} → job_id
POST   /experiments/{id}/analyze/demo         → job_id  (генерация демо пост-данных + анализ)
POST   /experiments/{id}/validate {n_sims, options}    → job_id

GET    /jobs/{id}                             → {status, progress: {stage, pct, message}, result?, error?}

GET    /admin/users, POST /admin/users, PATCH /admin/users/{id},
POST   /admin/users/{id}/reset-password       → только роль admin
GET    /audit?user=&action=&page=             → admin; /experiments/{id}/audit — история эксперимента
```

### 2.3 Правила изоляции при дизайне

`POST /design` перед запуском выполняет ту же изоляцию (exclude / warn / off / exclude_selected). Для режима warn: ответ job'а содержит `requires_confirmation: {overlap: N, by_experiment: {...}}`; фронт показывает диалог, повторный вызов с `confirmed: true` продолжает. Логика — существующая, только транспорт новый.

### 2.4 Фоновые задачи (jobs)

Дизайн, анализ и симуляции — длительные операции; HTTP-запрос не должен висеть минуты.

- Реализация без Celery (вне скоупа, как в DOCKER.md): встроенный менеджер на `concurrent.futures.ThreadPoolExecutor` (2-4 воркера, env ABKIT_JOB_WORKERS) + таблица jobs в Postgres (id, type, status, progress jsonb, result_ref, error, created_by, created_at, finished_at) — переживает перезапуск API-контейнера (незавершенные при старте помечаются failed с понятной ошибкой).
- Прогресс: существующие функции ядра уже структурированы по стадиям (валидация → изоляция → мощность → сплит → сохранение; джойн → проверки → метрика i из N → поправка → отчет). Обертка в `backend/jobs/` транслирует стадии в progress.
- Фронт поллит `GET /jobs/{id}` раз в 1с (простая и надежная схема; SSE — опционально позже).
- Заложить интерфейс JobRunner так, чтобы замена на Celery в будущем не трогала роутеры.

## 3. Фронтенд: React + TypeScript + Ant Design

### 3.1 Стек (зафиксировать версии в package.json)

- Vite + React 18 + TypeScript (strict)
- **Ant Design 5** — та же компонентная база, что у Superset: Table, Form, Modal, Tag, Drawer, Upload
- TanStack Query (запросы/кэш/поллинг jobs), React Router
- **ECharts** (echarts-for-react) для графиков — как в Superset; plotly не тянуть
- Типы API генерируются из OpenAPI (openapi-typescript) на этапе сборки — ручных интерфейсов для ответов API не писать

### 3.2 Тема (frontend/src/theme/tokens.ts + ConfigProvider AntD)

Единый источник правды по цветам (продублировать значения в комментарии к abkit/ui/theme.py, чтобы Streamlit-legacy и React не разъехались на время сосуществования):

```ts
colorPrimary:   '#2E8B6D',  // зеленый акцент (hover #256F57, active #1F5C46)
colorSuccess:   '#2E8B6D',
colorWarning:   '#C9A227',  // приглушенный, НЕ оранжевый
colorError:     '#D64545',
colorText:      '#484848',
colorBorder:    '#E0E0E0',
colorBgLayout:  '#F7F7F7',
fontFamily:     'Inter, -apple-system, Helvetica, Arial, sans-serif',
fontSize:       14, // таблицы 13
borderRadius:   4,
```

Проверка "никакого оранжевого": grep по итоговой сборке на #ff7f0e/#fa8c16/orange + визуальный прогон всех состояний (hover/focus/active/disabled/charts).

### 3.3 Каркас и страницы (маппинг текущих табов)

Каркас как в Superset: верхняя навигация (лого abkit слева, пункты Design / Analyze / Experiments / Validation; справа — меню пользователя: Профиль, Admin (для admin), Выйти). Никакого бокового сайдбара Streamlit-стиля.

| Текущий таб | Страница React | Ключевые компоненты |
|---|---|---|
| Login | /login | центрированная карточка, лого, зеленая кнопка |
| Design | /design | степпер-форма (см. 3.4) |
| Analyze | /analyze | выбор эксперимента → upload/демо → опции → прогресс job → отчет (см. 3.5) |
| Experiments | /experiments | AntD Table: имя, владелец, бейдж статуса, даты, действия в строке (перевод статуса, отчеты, скачать выборки, удалить с вводом DELETE в Modal); Drawer с деталями конфига |
| Validation | /validation | форма запуска симуляций, прогресс, результат (FPR с ДИ, распределение p-value, мощность vs аналитика) |
| Admin | /admin | подстраницы Users (таблица + Modal create/edit, как сейчас в Superset-стиле) и Audit (фильтры, пагинация) |
| Профиль | /profile | смена пароля |

Все охранные правила ролей повторить на роутах (Viewer не видит форм мутаций; Editor — только свои эксперименты; Admin — все) — плюс сервер все равно проверяет.

### 3.4 Страница Design — самая сложная форма, перенести ВЕСЬ текущий UX

Степпер (AntD Steps) из 4 шагов, состояние — в одном объекте конфига (типы из OpenAPI):

1. **Данные**: Upload (drag&drop, csv/parquet, лимит из /api meta) → после загрузки превью первых строк, список колонок с типами; кнопка «Демо-данные»; экспандеры-подсказки (тексты перенести из текущего UI: «Что это за данные», пример таблицы, SQL-шаблон).
2. **Группы и метрики**: группы (дефолт Control/Test 0.5/0.5, пресеты 50/50, 90/10, 33/33/33, свое, live-валидация суммы, кнопка Нормализовать); метрики — карточки с полями: отображаемое имя, столбец датафрейма (Select из колонок), тип, роль, pre-period колонка (Select числовых, для binary — подсказка 0/1-колонок).
3. **Параметры**: размер эксперимента (относительный MDE / абсолютный MDE с live-пересчетом в относительный / размер выборки / все данные); страты (мультиселект) + селект nan_strategy с предупреждением о доле пропусков; метод сплита с пояснениями (stratified/simple/hash); изоляция (4 режима с человеческими подписями; для exclude_selected — мультиселект активных экспериментов).
4. **Запуск**: сводка конфига → кнопка «Спроектировать» → прогресс по стадиям (из job) → результат: размеры групп, таблица MDE (с CUPED/без), проверки сплита (SRM, баланс, pre-A/A) с бейджами, кнопки: скачать выборки (по группам + ZIP), открыть design_report, конфиг (JSON-вьювер).

Ошибки дизайна (нет колонки, не хватает мощности, пересечение при isolation=warn) — человеческие сообщения из API в Alert, с actionable-подсказками как сейчас.

### 3.5 Страница Analyze и рендер результатов

- Выбор эксперимента (только со статусом designed/running/completed и с assignments), upload пост-данных ИЛИ кнопка «Сгенерировать демо пост-данные (+3% эффект)» (disabled без выбранного эксперимента, с tooltip-причиной).
- Опции: compare_methods, поправка, колонка даты (с текущей семантикой агрегации дневных данных и подсказкой).
- Прогресс job по стадиям («метрика 2 из 3: Bootstrap...»).
- Результаты рендерятся из results.json НА ФРОНТЕ (не iframe с HTML-отчетом):
  - карточки-вердикты по метрикам (эффект, ДИ, p, цветной статус)
  - бейджи проверок честности (SRM, потери) с деталями по клику
  - forest plot (ECharts) по каждой метрике: все цепочки, designed выделен, ноль пунктиром
  - распределения: continuous — гистограммы+ECDF с клиппингом P99 и toggle полного диапазона; binary — bar-chart долей с ДИ Уилсона
  - кумулятивный лифт (если была колонка даты) с обязательным peeking-предупреждением
  - эффект по сегментам с пометкой exploratory
  - детальная таблица всех сравнений (все колонки как сейчас) + экспорт CSV
  - у каждого графика — Collapse «Как читать этот график?» с существующими текстами (перенести из viz/help_texts.py через API или в бандл фронта)
- Скачивание классического HTML-отчета остается кнопкой (генерация на сервере не меняется).

## 4. Docker, nginx, CI

4.1. docker-compose: сервис `backend` (uvicorn backend.main:app), сервис `app` (Streamlit) переименовать в `legacy` и оставить; nginx: `/` → статика фронта, `/api` → backend, `/legacy` → Streamlit (учесть baseUrlPath у Streamlit). Фронт собирается multi-stage в образ nginx (COPY dist).
4.2. entrypoint backend: те же миграции Alembic + bootstrap-админ (перенести из текущего entrypoint, чтобы не выполнялось дважды — выполняет только backend).
4.3. CI: джоба test расширяется — pytest бэкенда; новая джоба frontend: npm ci, typecheck, eslint, unit-тесты, build; джоба e2e (Playwright против docker compose) — на PR в main и по workflow_dispatch; build-and-push собирает оба образа.
4.4. .env.example дополнить: ABKIT_JOB_WORKERS, VITE_API_BASE (по умолчанию /api/v1).

## 5. План реализации по этапам

Каждый этап: зеленые все существующие тесты + новые тесты этапа, commit, push, зеленый CI.

**R1 — скелет API + auth.** FastAPI-каркас, deps, cookie-auth (login/logout/me), guard'ы ролей, единый формат ошибок, OpenAPI. Тесты httpx: логин, роли, отказ Viewer'у в мутации. Streamlit не трогается.

**R2 — read-only API.** experiments (список/деталь/выборки/отчеты/results.json), datasets preview, audit, admin users GET. Тесты на пагинацию/фильтры/права.

**R3 — jobs + мутации.** Менеджер jobs (таблица в БД, прогресс), design/analyze/validate/demo эндпоинты, статусы, удаление с confirm=DELETE, upload датасетов, admin-мутации. Интеграционные тесты: полный цикл design→analyze через API на синтетике, изоляция warn→confirmed.

**R4 — каркас фронта + Experiments + Admin + Login.** Vite-проект, тема, навигация, типы из OpenAPI, страницы Login/Experiments/Admin/Audit/Profile. Playwright: логин, список экспериментов, права ролей, удаление с DELETE.

**R5 — Design.** Полный степпер по 3.4. Playwright: e2e дизайн на демо-данных до готового эксперимента с выборками.

**R6 — Analyze + Validation + графики.** Страницы по 3.5, все ECharts-компоненты, «Как читать график». Playwright: демо пост-данные → анализ → эффект виден, таблица экспортируется.

**R7 — сборка и сосуществование.** Docker/nginx/CI по разделу 4, обновление docker/README (два UI, /legacy), прогон test_persistence.sh. Критерий: сценарий «git clone → compose up → create-admin → полный цикл в React-UI» проходит на чистой машине.

**R8 — вывод legacy (ТОЛЬКО по явному подтверждению пользователя).** Чек-лист паритета по каждой странице; удаление Streamlit-кода, зависимостей и /legacy из nginx; чистка CSS-хаков; обновление всей документации.

## 6. Вне скоупа

Celery/Redis (интерфейс JobRunner заложен), SSE/WebSocket-прогресс (поллинг достаточен), SSO/OAuth, мобильная верстка (десктоп-first, минимальная адаптивность), i18n (интерфейс на русском, как сейчас), темная тема (светлая как в Superset; токены не хардкодить, чтобы темную можно было добавить позже).
