"""R2 (FRONTEND.md §3.2): read-only чтение экспериментов — тонкая обертка над
ExperimentRepo/AuditRepo/DbExperimentStore, без изменений в статистическом
ядре. design_summary никогда не заполняется в create_experiment (см.
abkit/db/store.py) — в ExperimentDetail поле честно прокидывается как None,
а не подделывается (то же решение, что и в
app.py::_render_experiment_detail_panel, которая берет данные MDE-таблицы
из уже отрендеренного design_report.html, а не пересобирает их)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from abkit.auth.guards import CurrentUser
from abkit.db.repositories import AuditRepo, ExperimentRepo, UserRepo
from abkit.db.store import DbExperimentStore
from backend.deps import get_current_user
from backend.errors import APIError
from backend.schemas.experiments import (
    REPORT_FILENAMES,
    AuditEntryOut,
    ExperimentDetail,
    ExperimentSummary,
    FileInfo,
    PaginatedAudit,
    PaginatedExperiments,
    SampleInfo,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _artifact_dir(name: str) -> Path:
    return DbExperimentStore().data_dir / name


def _get_experiment_or_404(name: str):
    exp = ExperimentRepo().get_by_name(name)
    if exp is None:
        raise APIError(404, "not_found", f"Эксперимент '{name}' не найден")
    return exp


def _owner_email(owner_id) -> str | None:
    user = UserRepo().get_by_id(owner_id)
    return user.email if user else None


@router.get("", response_model=PaginatedExperiments)
def list_experiments(
    status: str | None = None,
    owner: str | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedExperiments:
    # Резолвим email владельца одним проходом по users вместо N+1 запроса
    # на эксперимент (FRONTEND.md §3.2: список фильтруется по owner).
    owner_email_by_id = {u.id: u.email for u in UserRepo().list_all()}

    all_exps = ExperimentRepo().list_all()
    if status:
        all_exps = [e for e in all_exps if e.status == status]
    if owner:
        needle = owner.lower()
        all_exps = [
            e for e in all_exps if needle in (owner_email_by_id.get(e.owner_id) or "").lower()
        ]
    if q:
        needle = q.lower()
        all_exps = [e for e in all_exps if needle in e.name.lower()]
    total = len(all_exps)
    start = (page - 1) * page_size
    page_items = all_exps[start : start + page_size]
    items = [
        ExperimentSummary(
            name=e.name, status=e.status, owner_email=owner_email_by_id.get(e.owner_id),
            created_at=e.created_at, started_at=e.started_at,
            completed_at=e.completed_at, archived_at=e.archived_at,
        )
        for e in page_items
    ]
    return PaginatedExperiments(items=items, total=total, page=page, page_size=page_size)


@router.get("/{name}", response_model=ExperimentDetail)
def get_experiment(name: str, user: CurrentUser = Depends(get_current_user)) -> ExperimentDetail:
    exp = _get_experiment_or_404(name)
    owner = UserRepo().get_by_id(exp.owner_id)
    path = _artifact_dir(name)
    available_reports = [r for r in REPORT_FILENAMES if (path / r).exists()]
    files = (
        [
            FileInfo(path=str(p.relative_to(path)), size_kb=round(p.stat().st_size / 1024, 1))
            for p in sorted(path.rglob("*"))
            if p.is_file()
        ]
        if path.exists()
        else []
    )
    return ExperimentDetail(
        name=exp.name, status=exp.status,
        owner_email=owner.email if owner else None, owner_name=owner.name if owner else None,
        config=exp.config, design_summary=exp.design_summary,
        created_at=exp.created_at, started_at=exp.started_at,
        completed_at=exp.completed_at, archived_at=exp.archived_at,
        available_reports=available_reports, files=files,
    )


@router.get("/{name}/reports/{report_name}", response_class=HTMLResponse)
def get_report(report_name: str, name: str, user: CurrentUser = Depends(get_current_user)) -> HTMLResponse:
    _get_experiment_or_404(name)
    if report_name not in REPORT_FILENAMES:
        raise APIError(404, "not_found", f"Отчет '{report_name}' не поддерживается")
    report_path = _artifact_dir(name) / report_name
    if not report_path.exists():
        raise APIError(404, "not_found", f"Отчет '{report_name}' еще не создан")
    return HTMLResponse(content=report_path.read_text(encoding="utf-8"))


@router.get("/{name}/samples", response_model=list[SampleInfo])
def list_samples(name: str, user: CurrentUser = Depends(get_current_user)) -> list[SampleInfo]:
    import pandas as pd

    _get_experiment_or_404(name)
    samples_dir = _artifact_dir(name) / "samples"
    csv_paths = sorted(samples_dir.glob("*.csv")) if samples_dir.exists() else []
    return [
        SampleInfo(
            filename=p.name, n_rows=len(pd.read_csv(p)), size_kb=round(p.stat().st_size / 1024, 1)
        )
        for p in csv_paths
    ]


@router.get("/{name}/samples/{filename}")
def download_sample(name: str, filename: str, user: CurrentUser = Depends(get_current_user)) -> Response:
    _get_experiment_or_404(name)
    csv_path = _artifact_dir(name) / "samples" / filename
    if csv_path.suffix != ".csv" or not csv_path.exists():
        raise APIError(404, "not_found", f"Файл '{filename}' не найден")
    return Response(
        content=csv_path.read_bytes(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{name}/samples.zip")
def download_samples_zip(name: str, user: CurrentUser = Depends(get_current_user)) -> StreamingResponse:
    _get_experiment_or_404(name)
    samples_dir = _artifact_dir(name) / "samples"
    csv_paths = sorted(samples_dir.glob("*.csv")) if samples_dir.exists() else []
    if not csv_paths:
        raise APIError(404, "not_found", "Выборки для этого эксперимента не найдены")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for csv_path in csv_paths:
            zf.write(csv_path, arcname=csv_path.name)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}_samples.zip"'},
    )


@router.get("/{name}/results")
def get_results(name: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    from abkit.db.repositories import ResultRepo

    exp = _get_experiment_or_404(name)
    result = ResultRepo().latest_for_experiment(exp.id)
    if result is None:
        raise APIError(404, "not_found", "Результаты анализа для этого эксперимента еще не готовы")
    return result.results


@router.get("/{name}/audit", response_model=PaginatedAudit)
def get_experiment_audit(
    name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedAudit:
    _get_experiment_or_404(name)
    repo = AuditRepo()
    offset = (page - 1) * page_size
    entries = repo.list_recent(limit=page_size, offset=offset, object_name=name)
    total = repo.count(object_name=name)
    items = [
        AuditEntryOut(
            id=e.id, ts=e.ts, user_email=e.user_email, action=e.action,
            object_type=e.object_type, object_id=e.object_id, object_name=e.object_name,
            details=e.details,
        )
        for e in entries
    ]
    return PaginatedAudit(items=items, total=total, page=page, page_size=page_size)
