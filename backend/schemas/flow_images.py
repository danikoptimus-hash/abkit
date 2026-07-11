from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FlowImageOut(BaseModel):
    id: str
    group_name: str
    flow_title: str
    position: int
    uploaded_at: datetime


class SetFlowImageGroupOrderRequest(BaseModel):
    group_name: str
    flow_title: str = ""
    image_ids: list[str]
