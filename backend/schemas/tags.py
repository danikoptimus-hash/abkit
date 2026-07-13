from __future__ import annotations

from pydantic import BaseModel


class TagOut(BaseModel):
    id: str
    name: str
    # Nullable, currently unused by any code path — the UI always computes a
    # deterministic color from a hash of the name instead (see
    # abkit/db/models.py::Tag). Exists for a future manual color picker.
    color: str | None = None


class TagsResponse(BaseModel):
    items: list[TagOut]


class CreateTagRequest(BaseModel):
    name: str


class SetExperimentTagsRequest(BaseModel):
    tag_ids: list[str]


class TagUsageResponse(BaseModel):
    count: int


class DeleteTagResponse(BaseModel):
    affected_experiments: int


class TagAdminOut(BaseModel):
    """GET /tags/admin row (tag management page, admin-only) — TagOut plus
    the fields only an admin needs to decide what to rename/merge/delete."""

    id: str
    name: str
    color: str | None = None
    experiment_count: int
    created_by_email: str | None = None
    created_at: str


class TagsAdminResponse(BaseModel):
    items: list[TagAdminOut]


class RenameTagRequest(BaseModel):
    name: str


class MergeTagRequest(BaseModel):
    target_id: str


class MergeTagResponse(BaseModel):
    affected_experiments: int


class BulkDeleteTagsRequest(BaseModel):
    """Mirrors BulkDeleteDatasetsRequest — one typed-DELETE confirmation for
    the whole batch (tag management page §2.4)."""

    tag_ids: list[str]
    confirm: str


class BulkDeleteTagsSkipped(BaseModel):
    tag_id: str
    reason: str


class BulkDeleteTagsResult(BaseModel):
    deleted: list[str]
    skipped: list[BulkDeleteTagsSkipped]
