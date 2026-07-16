from __future__ import annotations

from pydantic import BaseModel


class FolderOut(BaseModel):
    id: str
    name: str
    count: int
    created_by_email: str | None = None


class FoldersResponse(BaseModel):
    items: list[FolderOut]
    uncategorized_count: int
    all_count: int


class CreateFolderRequest(BaseModel):
    name: str


class RenameFolderRequest(BaseModel):
    name: str


class DeleteFolderResponse(BaseModel):
    affected_experiments: int


class SetExperimentFolderRequest(BaseModel):
    folder_id: str | None = None


class BulkMoveFolderRequest(BaseModel):
    names: list[str]
    folder_id: str | None = None


class BulkMoveFolderSkipped(BaseModel):
    name: str
    reason: str


class BulkMoveFolderResult(BaseModel):
    moved: list[str]
    skipped: list[BulkMoveFolderSkipped]
