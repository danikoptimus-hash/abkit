"""R2 (FRONTEND.md §3.2): глобальный журнал аудита — admin-only; в отличие
от per-experiment /experiments/{name}/audit (видимого всем ролям, живет в
experiments.py). Фильтр `user` — по AuditLog.user_email напрямую (денормали-
зован в audit_log, переживает удаление пользователя) — см. AuditRepo._filtered."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from abkit.auth.guards import CurrentUser
from abkit.db.repositories import AuditRepo
from backend.deps import require_min_role
from backend.schemas.experiments import AuditEntryOut, PaginatedAudit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=PaginatedAudit)
def list_audit(
    user: str | None = None,
    action: str | None = None,
    object_name: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_min_role("admin")),
) -> PaginatedAudit:
    repo = AuditRepo()
    offset = (page - 1) * page_size
    entries = repo.list_recent(
        limit=page_size, offset=offset, user_email=user, action=action, object_name=object_name
    )
    total = repo.count(user_email=user, action=action, object_name=object_name)
    items = [
        AuditEntryOut(
            id=e.id, ts=e.ts, user_email=e.user_email, action=e.action,
            object_type=e.object_type, object_id=e.object_id, object_name=e.object_name,
            details=e.details,
        )
        for e in entries
    ]
    return PaginatedAudit(items=items, total=total, page=page, page_size=page_size)
