"""Tags for A/B tests (Superset-style dashboard tags, CLAUDE.md) — typeahead
search/create here; assignment to a specific experiment is
PUT /experiments/{name}/tags (backend/routers/experiments.py, same router as
the rest of that resource)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from abkit.auth.guards import CurrentUser
from backend.deps import get_current_user
from backend.errors import APIError
from backend.schemas.tags import (
    BulkDeleteTagsRequest,
    BulkDeleteTagsResult,
    BulkDeleteTagsSkipped,
    CreateTagRequest,
    DeleteTagResponse,
    MergeTagRequest,
    MergeTagResponse,
    RenameTagRequest,
    TagAdminOut,
    TagOut,
    TagsAdminResponse,
    TagsResponse,
    TagUsageResponse,
)

router = APIRouter(prefix="/tags", tags=["tags"])


def _to_tag_out(t) -> TagOut:
    return TagOut(id=str(t.id), name=t.name, color=t.color)


@router.get("", response_model=TagsResponse)
def search_tags(
    q: str | None = Query(default=None, description="Typeahead substring match"),
    user: CurrentUser = Depends(get_current_user),
) -> TagsResponse:
    from abkit.jobs import search_tags as _search_tags

    return TagsResponse(items=[_to_tag_out(t) for t in _search_tags(user, q)])


@router.post("", response_model=TagOut, status_code=201)
def create_tag(body: CreateTagRequest, user: CurrentUser = Depends(get_current_user)) -> TagOut:
    """Get-or-create (abkit/jobs.py::run_create_tag) — typing an existing
    name (case-insensitively) reuses it instead of erroring."""
    from abkit.jobs import run_create_tag

    return _to_tag_out(run_create_tag(user, body.name))


@router.get("/{tag_id}/usage", response_model=TagUsageResponse)
def get_tag_usage(tag_id: str, user: CurrentUser = Depends(get_current_user)) -> TagUsageResponse:
    """The frontend calls this before showing the delete-tag confirmation,
    so the affected-experiment count is visible up front."""
    from abkit.jobs import get_tag_usage_count

    return TagUsageResponse(count=get_tag_usage_count(user, tag_id))


@router.delete("/{tag_id}", response_model=DeleteTagResponse)
def delete_tag(tag_id: str, user: CurrentUser = Depends(get_current_user)) -> DeleteTagResponse:
    """Admin-only (enforced in abkit/jobs.py::run_delete_tag) — detaches from
    every experiment via ON DELETE CASCADE, not a separate step."""
    from abkit.jobs import run_delete_tag

    affected = run_delete_tag(user, tag_id)
    return DeleteTagResponse(affected_experiments=affected)


@router.get("/admin", response_model=TagsAdminResponse)
def list_tags_admin(
    q: str | None = Query(default=None, description="Live search by name"),
    user: CurrentUser = Depends(get_current_user),
) -> TagsAdminResponse:
    """Tag management page (/settings/tags, admin-only) — every tag plus its
    usage count and creator, which the plain typeahead (GET /tags) never
    exposes."""
    from abkit.db.repositories import UserRepo
    from abkit.jobs import list_tags_admin as _list_tags_admin

    rows = _list_tags_admin(user, q)
    email_by_id = {u.id: u.email for u in UserRepo().list_all()}
    return TagsAdminResponse(
        items=[
            TagAdminOut(
                id=str(tag.id), name=tag.name, color=tag.color, experiment_count=count,
                created_by_email=email_by_id.get(tag.created_by) if tag.created_by else None,
                created_at=tag.created_at.isoformat(),
            )
            for tag, count in rows
        ]
    )


@router.patch("/{tag_id}", response_model=TagOut)
def rename_tag(tag_id: str, body: RenameTagRequest, user: CurrentUser = Depends(get_current_user)) -> TagOut:
    """Admin-only (enforced in abkit/jobs.py::run_rename_tag). A name
    colliding case-insensitively with a DIFFERENT existing tag raises
    TagNameConflictError (409, backend/errors.py) instead of failing
    generically — the frontend uses that to offer Merge."""
    from abkit.jobs import run_rename_tag

    return _to_tag_out(run_rename_tag(user, tag_id, body.name))


@router.post("/{tag_id}/merge", response_model=MergeTagResponse)
def merge_tag(tag_id: str, body: MergeTagRequest, user: CurrentUser = Depends(get_current_user)) -> MergeTagResponse:
    """Admin-only (enforced in abkit/jobs.py::run_merge_tag) — reassigns
    every experiment carrying `tag_id` onto `body.target_id` and deletes
    `tag_id`, transactionally."""
    from abkit.jobs import run_merge_tag

    affected = run_merge_tag(user, tag_id, body.target_id)
    return MergeTagResponse(affected_experiments=affected)


@router.post("/bulk-delete", response_model=BulkDeleteTagsResult)
def bulk_delete_tags(
    body: BulkDeleteTagsRequest, user: CurrentUser = Depends(get_current_user),
) -> BulkDeleteTagsResult:
    """Bulk select + Delete on the tag management page (§2.4) — mirrors
    /datasets/bulk-delete's shape, but unlike datasets there's no per-item
    permission variance (tag delete is admin-only, full stop, enforced
    identically for every id) — only "not found" can cause a per-item skip."""
    from abkit import storage
    from abkit.jobs import run_delete_tag

    if body.confirm != "DELETE":
        raise APIError(400, "confirmation_required", "Type DELETE to confirm")

    deleted: list[str] = []
    skipped: list[BulkDeleteTagsSkipped] = []
    for tag_id in body.tag_ids:
        try:
            run_delete_tag(user, tag_id)
            deleted.append(tag_id)
        except storage.StorageError:
            skipped.append(BulkDeleteTagsSkipped(tag_id=tag_id, reason="not found"))
    return BulkDeleteTagsResult(deleted=deleted, skipped=skipped)
