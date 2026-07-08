"""R2 (FRONTEND.md §3.2, §5.2): список и предпросмотр загруженных датасетов
(Dataset.storage_path — CSV, как и все текущие загрузки в app.py через
st.file_uploader + pd.read_csv; DatasetRepo.create() пока нигде не
вызывается на проде — таблица datasets заполнится только в R3 при переносе
загрузки на HTTP)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from abkit.auth.guards import CurrentUser
from abkit.db.repositories import DatasetRepo, ExperimentRepo, UserRepo
from backend.deps import get_current_user
from backend.errors import APIError
from backend.schemas.datasets import DatasetOut, DatasetPreview, PaginatedDatasets

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=PaginatedDatasets)
def list_datasets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedDatasets:
    all_datasets = DatasetRepo().list_all()
    total = len(all_datasets)
    start = (page - 1) * page_size
    page_items = all_datasets[start : start + page_size]

    exp_name_by_id = {e.id: e.name for e in ExperimentRepo().list_all()}
    email_by_id = {u.id: u.email for u in UserRepo().list_all()}

    items = [
        DatasetOut(
            id=str(d.id), experiment_id=str(d.experiment_id),
            experiment_name=exp_name_by_id.get(d.experiment_id),
            kind=d.kind, filename=d.filename, n_rows=d.n_rows, columns=d.columns,
            uploaded_by_email=email_by_id.get(d.uploaded_by) if d.uploaded_by else None,
            uploaded_at=d.uploaded_at,
        )
        for d in page_items
    ]
    return PaginatedDatasets(items=items, total=total, page=page, page_size=page_size)


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
def preview_dataset(
    dataset_id: str,
    rows: int = Query(default=20, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
) -> DatasetPreview:
    import uuid as uuid_mod

    import pandas as pd

    try:
        parsed_id = uuid_mod.UUID(dataset_id)
    except ValueError as e:
        raise APIError(422, "validation_error", "Некорректный идентификатор датасета") from e

    ds = DatasetRepo().get_by_id(parsed_id)
    if ds is None:
        raise APIError(404, "not_found", f"Датасет '{dataset_id}' не найден")
    try:
        preview_df = pd.read_csv(ds.storage_path, nrows=rows)
    except OSError as e:
        raise APIError(404, "not_found", "Файл датасета недоступен на диске") from e

    # NaN не валиден в JSON (json.dumps с allow_nan=True пишет литерал NaN,
    # который не парсится стандартными JS/JSON-клиентами) — заменяем на None.
    preview_df = preview_df.where(pd.notnull(preview_df), None)
    return DatasetPreview(
        filename=ds.filename, n_rows=ds.n_rows, columns=ds.columns,
        rows=preview_df.to_dict(orient="records"),
    )
