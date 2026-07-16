"""Folders for A/B tests (item 5, folders package) — CRUD + counts here;
assignment to a specific experiment is PUT /experiments/{name}/folder and
POST /experiments/bulk-move-folder (backend/routers/experiments.py, same
router as the rest of that resource, mirroring how tag assignment works)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from abkit.auth.guards import CurrentUser
from backend.deps import get_current_user
from backend.schemas.folders import (
    CreateFolderRequest,
    DeleteFolderResponse,
    FolderOut,
    FoldersResponse,
    RenameFolderRequest,
)

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("", response_model=FoldersResponse)
def list_folders_route(user: CurrentUser = Depends(get_current_user)) -> FoldersResponse:
    from abkit.db.repositories import UserRepo
    from abkit.jobs import list_folders

    folders_with_counts, uncategorized_count, all_count = list_folders(user)
    email_by_id = {u.id: u.email for u in UserRepo().list_all()}
    return FoldersResponse(
        items=[
            FolderOut(
                id=str(f.id), name=f.name, count=count,
                created_by_email=email_by_id.get(f.created_by) if f.created_by else None,
            )
            for f, count in folders_with_counts
        ],
        uncategorized_count=uncategorized_count,
        all_count=all_count,
    )


@router.post("", response_model=FolderOut, status_code=201)
def create_folder(body: CreateFolderRequest, user: CurrentUser = Depends(get_current_user)) -> FolderOut:
    """editor+ (abkit/jobs.py::run_create_folder)."""
    from abkit.jobs import run_create_folder

    folder = run_create_folder(user, body.name)
    return FolderOut(id=str(folder.id), name=folder.name, count=0, created_by_email=user.email)


@router.patch("/{folder_id}", response_model=FolderOut)
def rename_folder(
    folder_id: str, body: RenameFolderRequest, user: CurrentUser = Depends(get_current_user),
) -> FolderOut:
    """Creator or Admin only (abkit/jobs.py::run_rename_folder)."""
    from abkit.jobs import run_rename_folder

    folder = run_rename_folder(user, folder_id, body.name)
    return FolderOut(id=str(folder.id), name=folder.name, count=0)


@router.delete("/{folder_id}", response_model=DeleteFolderResponse)
def delete_folder(folder_id: str, user: CurrentUser = Depends(get_current_user)) -> DeleteFolderResponse:
    """Creator or Admin only (abkit/jobs.py::run_delete_folder) — moves its
    experiments to Uncategorized via ON DELETE SET NULL, not a separate step."""
    from abkit.jobs import run_delete_folder

    affected = run_delete_folder(user, folder_id)
    return DeleteFolderResponse(affected_experiments=affected)
