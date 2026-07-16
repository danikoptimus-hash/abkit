# syntax=docker/dockerfile:1
# Мультистейдж-сборка (DOCKER.md §7.1). Версия (item 8, audit-details+
# пакет — CLAUDE.md "Правило: релизный процесс"): на тегированном CI-билде
# (build-and-push, .github/workflows/ci.yml) ABKIT_VERSION приходит снаружи
# как build-arg, посчитанный из git-тега (`vX.Y.Z` -> `X.Y.Z`) — и это же
# значение записывается в OCI-лейбл ниже. На ЛОКАЛЬНОМ билде (просто
# `docker compose up -d --build`, без --build-arg) ARG остается на дефолте
# "dev" — тогда abkit/__init__.py::_read_version() падает на файл GIT_SHA
# (стадия `version` ниже, git rev-parse внутри билда, без участия
# разработчика) и показывает "dev (<short sha>)".
#
# Образ backend-сервиса (FastAPI/uvicorn, FRONTEND.md) — интерфейс React
# (сервис frontend в docker-compose.yml, отдельный образ frontend/Dockerfile).
# Streamlit-интерфейс (app.py) удален на этапе R8 FRONTEND.md.

FROM python:3.12-slim AS builder
WORKDIR /app

# Сначала только pyproject.toml + пакет abkit — чтобы этот слой (самый долгий,
# тянет все зависимости) кэшировался, пока не меняется код/зависимости.
COPY pyproject.toml ./
COPY abkit ./abkit
# [db-connectors]: clickhouse-connect + pymssql (Database Connections
# feature) — pymssql ships prebuilt manylinux wheels (bundled FreeTDS), no
# system ODBC driver/EULA needed in the image, unlike pyodbc.
RUN pip install --no-cache-dir --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels ".[db-connectors]"

# Отдельная стадия (не задевает кэш builder'а выше — .git меняется на каждый
# коммит, а слой с зависимостями должен оставаться закэшированным). Просто
# короткий hex sha, без git-describe/тегов — тег-версию отдает ABKIT_VERSION
# build-arg (CI), эта стадия только про fallback-отображение для локальных
# билетов без явного тега.
FROM python:3.12-slim AS version
WORKDIR /repo
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
COPY .git ./.git
RUN git rev-parse --short HEAD > /GIT_SHA 2>/dev/null || echo "unknown" > /GIT_SHA

FROM python:3.12-slim

ARG ABKIT_VERSION=dev
ENV ABKIT_VERSION=${ABKIT_VERSION}
LABEL org.opencontainers.image.title="abkit" \
      org.opencontainers.image.version="${ABKIT_VERSION}" \
      org.opencontainers.image.source="https://github.com/danikoptimus-hash/abkit"

RUN useradd -m -u 1000 abkit \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# cli.py/cli_admin.py — не часть пакета abkit (setuptools include=["abkit*"]),
# а top-level скрипты в /app. Консольный энтрипоинт abkit-admin (из
# pyproject.toml: abkit-admin = "cli_admin:app") — это обычный shebang-стаб в
# /usr/local/bin, он НЕ добавляет CWD в sys.path сам по себе (в отличие от
# `python cli_admin.py`) — без PYTHONPATH=/app он не найдет модуль cli_admin
# при вызове `docker compose exec backend abkit-admin ...`.
ENV PYTHONPATH=/app

# Устанавливаем все колёса (abkit + все его зависимости) одним слоем.
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-compile /wheels/*.whl \
 && rm -rf /wheels /root/.cache

# Остальной код (cli.py/cli_admin.py/backend/alembic.ini/migrations/templates) —
# он не входит в пакет abkit (setuptools include=["abkit*"]), поэтому нужен
# отдельной копией; abkit/ копируется тоже — report.py вычисляет путь к
# templates/ относительно расположения ФАЙЛА пакета (Path(__file__).parent...),
# что работает только если abkit/ и templates/ — соседи в одном дереве, как при
# локальной editable-разработке. Локальная копия в sys.path имеет приоритет
# перед версией из site-packages (тем же wheel'ом) — это осознанно и безвредно.
COPY . .
COPY --from=version /GIT_SHA /app/GIT_SHA
RUN mkdir -p /data/experiments \
 && chown -R abkit:abkit /app /data \
 && chmod +x /app/docker/entrypoint-backend.sh

USER abkit
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/docker/entrypoint-backend.sh"]
