from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserAdminOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None
