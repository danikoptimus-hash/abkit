from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DatasetOut(BaseModel):
    id: str
    experiment_id: str
    experiment_name: str | None
    kind: str
    filename: str
    n_rows: int
    columns: list[str]
    uploaded_by_email: str | None
    uploaded_at: datetime


class PaginatedDatasets(BaseModel):
    items: list[DatasetOut]
    total: int
    page: int
    page_size: int


class DatasetPreview(BaseModel):
    filename: str
    n_rows: int
    columns: list[str]
    rows: list[dict[str, Any]]
