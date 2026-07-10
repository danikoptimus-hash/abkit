"""Schema/table browser for the "From SQL" dataset form (UX package,
Datasets §1) — GET /db-connections/{id}/schemas and .../schemas/{schema}/tables.
Postgres/MSSQL go through SQLAlchemy's generic `Inspector` (works unmodified
against `build_engine()`'s plain `Engine`); ClickHouse's `clickhousedb`
dialect doesn't support `Inspector.get_schema_names()`/`get_table_names()`
reliably (best-effort/unofficial dialect, see sql_dataset.py's own docstring)
so it queries `system.databases`/`system.tables` directly instead — same
"driver layer" split already used for streaming (sql_dataset.py) and error
classification (testing.py).

A tiny in-process TTL cache (60s) sits in front of both — no Redis in this
project (CLAUDE.md/DOCKER.md: single-process ThreadPoolExecutor job runner,
deliberately no separate cache service) — keyed by (conn_id, schema) so a
cascading Select doesn't round-trip to the external DB on every render;
callers can force a refresh (the 🗘 button) to bypass it.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text as sa_text

from abkit.db_connections.engines import ConnectionSpec, build_engine
from abkit.db_connections.sql_dataset import SqlExecutionError

_CACHE_TTL_SEC = 60
_cache: dict[tuple[str, str | None], tuple[float, list[str]]] = {}


def _cache_get(key: tuple[str, str | None]) -> list[str] | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL_SEC:
        del _cache[key]
        return None
    return value


def _cache_set(key: tuple[str, str | None], value: list[str]) -> None:
    _cache[key] = (time.monotonic(), value)


def _list_schemas_clickhouse(conn: Any) -> list[str]:
    rows = conn.execute(sa_text("SELECT name FROM system.databases ORDER BY name"))
    return [r[0] for r in rows]


def _list_tables_clickhouse(conn: Any, schema: str) -> list[str]:
    rows = conn.execute(
        sa_text("SELECT name FROM system.tables WHERE database = :db ORDER BY name"), {"db": schema}
    )
    return [r[0] for r in rows]


def list_schemas(spec: ConnectionSpec, cache_key: str, *, force_refresh: bool = False, timeout_sec: int = 10) -> list[str]:
    key = (cache_key, None)
    if not force_refresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    engine = build_engine(spec, timeout_sec=timeout_sec)
    try:
        if spec.engine == "clickhouse":
            with engine.connect() as conn:
                schemas = _list_schemas_clickhouse(conn)
        else:
            from sqlalchemy import inspect as sa_inspect

            with engine.connect() as conn:
                schemas = sa_inspect(conn).get_schema_names()
    except Exception as e:  # noqa: BLE001 — сообщение уже безопасно для показа пользователю
        raise SqlExecutionError(f"Could not list schemas: {e}") from e
    finally:
        engine.dispose()

    _cache_set(key, schemas)
    return schemas


def list_tables(
    spec: ConnectionSpec, cache_key: str, schema: str, *, force_refresh: bool = False, timeout_sec: int = 10
) -> list[str]:
    key = (cache_key, schema)
    if not force_refresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    engine = build_engine(spec, timeout_sec=timeout_sec)
    try:
        if spec.engine == "clickhouse":
            with engine.connect() as conn:
                tables = _list_tables_clickhouse(conn, schema)
        else:
            from sqlalchemy import inspect as sa_inspect

            with engine.connect() as conn:
                tables = sa_inspect(conn).get_table_names(schema=schema)
    except Exception as e:  # noqa: BLE001
        raise SqlExecutionError(f"Could not list tables: {e}") from e
    finally:
        engine.dispose()

    _cache_set(key, tables)
    return tables
