"""DB2 (CLAUDE.md dataset-from-SQL feature): execute_select_to_parquet /
preview_select against testcontainers-postgres — real streaming execution,
not mocked."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text as sa_text
from sqlalchemy.engine import make_url

from abkit.db_connections.engines import ConnectionSpec
from abkit.db_connections.sql_dataset import execute_select_to_parquet, preview_select
from abkit.db_connections.sql_guard import SqlValidationError


@pytest.fixture
def spec(db_url) -> ConnectionSpec:
    url = make_url(db_url)
    return ConnectionSpec(
        engine="postgresql", host=url.host, port=url.port, database=url.database,
        username=url.username, password=url.password, ssl=False,
    )


def _seed_rows(db_url, n=250):
    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        conn.execute(sa_text("DROP TABLE IF EXISTS sql_dataset_probe"))
        conn.execute(sa_text("CREATE TABLE sql_dataset_probe (id INT, name TEXT)"))
        conn.execute(
            sa_text("INSERT INTO sql_dataset_probe SELECT generate_series(1, :n), 'row_' || generate_series(1, :n)"),
            {"n": n},
        )
    engine.dispose()


def test_execute_select_to_parquet_writes_correct_data(spec, db_url, tmp_path):
    _seed_rows(db_url, n=250)
    dest = tmp_path / "out.parquet"
    result = execute_select_to_parquet(
        spec, "SELECT id, name FROM sql_dataset_probe ORDER BY id", dest, chunk_size=50,
    )
    assert result.n_rows == 250
    assert not result.truncated
    assert result.columns == ["id", "name"]

    df = pd.read_parquet(dest)
    assert len(df) == 250
    assert df["id"].tolist() == list(range(1, 251))


def test_execute_select_to_parquet_truncates_at_max_rows(spec, db_url, tmp_path):
    _seed_rows(db_url, n=100)
    dest = tmp_path / "out.parquet"
    result = execute_select_to_parquet(
        spec, "SELECT id FROM sql_dataset_probe ORDER BY id", dest, chunk_size=10, max_rows=25,
    )
    assert result.n_rows == 25
    assert result.truncated
    df = pd.read_parquet(dest)
    assert len(df) == 25


def test_execute_select_to_parquet_handles_zero_rows(spec, db_url, tmp_path):
    _seed_rows(db_url, n=0)
    dest = tmp_path / "out.parquet"
    result = execute_select_to_parquet(spec, "SELECT id, name FROM sql_dataset_probe", dest)
    assert result.n_rows == 0
    assert result.columns == ["id", "name"]
    df = pd.read_parquet(dest)
    assert len(df) == 0
    assert list(df.columns) == ["id", "name"]


def test_execute_select_to_parquet_rejects_non_select(spec, db_url, tmp_path):
    _seed_rows(db_url, n=5)
    dest = tmp_path / "out.parquet"
    with pytest.raises(SqlValidationError):
        execute_select_to_parquet(spec, "DELETE FROM sql_dataset_probe", dest)
    assert not dest.exists()


def test_preview_select_returns_first_rows(spec, db_url):
    _seed_rows(db_url, n=250)
    df = preview_select(spec, "SELECT id, name FROM sql_dataset_probe ORDER BY id", limit=10)
    assert len(df) == 10
    assert df["id"].tolist() == list(range(1, 11))


def test_preview_select_handles_zero_rows(spec, db_url):
    _seed_rows(db_url, n=0)
    df = preview_select(spec, "SELECT id, name FROM sql_dataset_probe", limit=10)
    assert len(df) == 0
    assert list(df.columns) == ["id", "name"]
