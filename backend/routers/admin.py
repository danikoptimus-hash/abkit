"""R2 (FRONTEND.md §3.2): admin-only чтение (список пользователей). Мутации
(роль, активность, сброс пароля) — R3."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from abkit.auth.guards import CurrentUser
from abkit.db.repositories import UserRepo
from backend.deps import require_min_role
from backend.schemas.admin import UserAdminOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserAdminOut])
def list_users(user: CurrentUser = Depends(require_min_role("admin"))) -> list[UserAdminOut]:
    return [
        UserAdminOut(
            id=str(u.id), email=u.email, name=u.name, role=u.role, is_active=u.is_active,
            must_change_password=u.must_change_password, created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in UserRepo().list_all()
    ]
