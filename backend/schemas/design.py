from __future__ import annotations

from pydantic import BaseModel

from abkit.config import DesignConfig


class DesignRequest(BaseModel):
    config: DesignConfig
    # Optional only for config.split_source == "external" (item 12) — that
    # flow needs no dataset at all; validated in backend/routers/design.py.
    dataset_id: str | None = None
    confirmed: bool = False


class JobAccepted(BaseModel):
    job_id: str
