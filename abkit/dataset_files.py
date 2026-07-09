"""Чтение файла датасета (backend, db-режим) независимо от формата на
диске — CSV для source='upload'/'demo' (как раньше), parquet для
source='sql' (DB2, CLAUDE.md: результат SQL-запроса материализуется в
parquet, не CSV, чтобы стриминг чанками не терял типы столбцов)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_dataset_file(
    path: str, *, nrows: int | None = None, dtype: dict[str, type] | None = None
) -> pd.DataFrame:
    if Path(path).suffix.lower() == ".parquet":
        return _read_parquet(path, nrows=nrows, dtype=dtype)
    return pd.read_csv(path, nrows=nrows, dtype=dtype)


def _read_parquet(path: str, *, nrows: int | None, dtype: dict[str, type] | None) -> pd.DataFrame:
    if nrows is None:
        df = pd.read_parquet(path)
    else:
        # Avoid loading a potentially huge parquet file just to preview a
        # handful of rows — read only the first batch(es) needed.
        import pyarrow as pa
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        batches = list(pf.iter_batches(batch_size=nrows))
        table = pa.Table.from_batches(batches, schema=pf.schema_arrow) if batches else pf.schema_arrow.empty_table()
        df = table.to_pandas().head(nrows)
    if dtype:
        cast_cols = {k: v for k, v in dtype.items() if k in df.columns}
        if cast_cols:
            df = df.astype(cast_cols)
    return df
