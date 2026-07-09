"""DB2 (CLAUDE.md): выполнение SELECT-запроса против внешней БД и
материализация результата в parquet, чанками — не накапливая весь результат
в памяти процесса. Работает поверх любого зарегистрированного движка
(abkit/db_connections/engines.py); честный server-side streaming
(execution_options(stream_results=True) -> курсор на стороне сервера)
гарантирован только для PostgreSQL (psycopg) — у ClickHouse/MSSQL это
best-effort (см. DB5/README): драйвер может проигнорировать опцию и
буферизовать результат целиком перед тем, как pandas начнет резать его на
чанки, но чанкинг ЗАПИСИ в parquet (а значит и итоговое использование памяти
для больших датасетов на диске) работает одинаково для всех движков.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text as sa_text

from abkit.db_connections.engines import ConnectionSpec, build_engine
from abkit.db_connections.sql_guard import validate_select_only

_DEFAULT_CHUNK_SIZE = 50_000
_CONNECT_TIMEOUT_SEC = 15


class SqlExecutionError(Exception):
    """Ошибка выполнения (не валидации) — сетевая, таймаут, синтаксис в
    конкретном движке и т.п. Сообщение уже безопасно для показа пользователю
    (не деталь драйвера как есть — см. вызывающую сторону, abkit/jobs.py)."""


def _default_max_rows() -> int:
    return int(os.environ.get("ABKIT_SQL_MAX_ROWS", "5000000"))


def _default_timeout_sec() -> int:
    return int(os.environ.get("ABKIT_SQL_TIMEOUT_SEC", "300"))


@dataclass
class SqlExecutionResult:
    n_rows: int
    columns: list[str]
    truncated: bool


def execute_select_to_parquet(
    spec: ConnectionSpec,
    sql: str,
    dest_path: Path,
    *,
    max_rows: int | None = None,
    timeout_sec: int | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    progress_callback=None,
) -> SqlExecutionResult:
    """progress_callback(n_rows_so_far) — called after each chunk (jobs
    progress: "Fetched N rows...", see abkit/jobs.py::run_create_dataset_from_sql)."""
    validate_select_only(sql, spec.engine)
    max_rows = max_rows if max_rows is not None else _default_max_rows()
    timeout_sec = timeout_sec if timeout_sec is not None else _default_timeout_sec()

    engine = build_engine(spec, timeout_sec=_CONNECT_TIMEOUT_SEC)
    start = time.monotonic()
    n_rows = 0
    truncated = False
    columns: list[str] = []
    writer: pq.ParquetWriter | None = None
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        try:
            raw_conn = engine.connect()
        except Exception as e:
            raise SqlExecutionError(f"Could not connect: {e}") from e

        with raw_conn as conn:
            conn = conn.execution_options(stream_results=True)
            try:
                # empty-but-typed probe: guarantees `columns` is known even
                # when the real query returns zero rows (pandas' chunked
                # read_sql yields no chunks at all in that case).
                probe = pd.read_sql(
                    sa_text(f"SELECT * FROM ({sql}) AS __abkit_probe WHERE 1 = 0"), conn
                )
                columns = list(probe.columns)

                for chunk in pd.read_sql(sa_text(sql), conn, chunksize=chunk_size):
                    if time.monotonic() - start > timeout_sec:
                        raise SqlExecutionError(f"Query exceeded the {timeout_sec}s timeout")
                    if not columns:
                        columns = list(chunk.columns)

                    remaining = max_rows - n_rows
                    if remaining <= 0:
                        truncated = True
                        break
                    if len(chunk) > remaining:
                        chunk = chunk.iloc[:remaining]
                        truncated = True

                    table = pa.Table.from_pandas(chunk, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(str(dest_path), table.schema)
                    writer.write_table(table)
                    n_rows += len(chunk)
                    if progress_callback is not None:
                        progress_callback(n_rows)
                    if truncated:
                        break
            except SqlExecutionError:
                raise
            except Exception as e:
                raise SqlExecutionError(f"Query failed: {e}") from e
    finally:
        if writer is not None:
            writer.close()
        engine.dispose()

    if writer is None:
        # Zero rows: still write an empty-but-schema'd parquet file so the
        # dataset is a normal, loadable (if useless) dataset rather than a
        # missing file.
        empty_table = pa.Table.from_pandas(pd.DataFrame(columns=columns), preserve_index=False)
        pq.write_table(empty_table, str(dest_path))

    return SqlExecutionResult(n_rows=n_rows, columns=columns, truncated=truncated)


def preview_select(spec: ConnectionSpec, sql: str, limit: int = 100, timeout_sec: int = 15) -> pd.DataFrame:
    """POST /db-connections/{id}/preview (DB2) — first `limit` rows, without
    engine-specific LIMIT/TOP/FETCH syntax: just take the first DBAPI fetch
    batch of that size via pandas' chunked read_sql."""
    validate_select_only(sql, spec.engine)
    engine = build_engine(spec, timeout_sec=timeout_sec)
    try:
        with engine.connect() as raw_conn:
            conn = raw_conn.execution_options(stream_results=True)
            try:
                df = next(pd.read_sql(sa_text(sql), conn, chunksize=limit), None)
                if df is None:
                    df = pd.read_sql(
                        sa_text(f"SELECT * FROM ({sql}) AS __abkit_probe WHERE 1 = 0"), conn
                    )
            except Exception as e:
                raise SqlExecutionError(f"Query failed: {e}") from e
    except SqlExecutionError:
        raise
    except Exception as e:
        raise SqlExecutionError(f"Could not connect: {e}") from e
    finally:
        engine.dispose()
    return df
