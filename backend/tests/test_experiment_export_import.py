"""Экспорт/импорт эксперимента zip-архивом (пакет export/import) — против
реальной БД через реальное API.

Основной тест — round-trip: design -> analyze -> export -> import -> глубокое
сравнение config/assignments/results. Остальное — ветки, которые ТЗ называет
явно: конфликт имени, отказ по format_version, предупреждение о ненайденном
датасете, права (Viewer).
"""

from __future__ import annotations

import io
import json
import time
import zipfile

from abkit.auth.passwords import hash_password
from abkit.db.repositories import ExperimentRepo, ResultRepo, UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    resp = app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})
    assert resp.status_code == 200, resp.text


def _design_csv(n=200) -> str:
    lines = ["user_id,revenue"] + [f"u{i},{100 + i % 10}.5" for i in range(n)]
    return "\n".join(lines)


def _post_csv(n=200) -> str:
    lines = ["user_id,revenue"] + [f"u{i},{110 + i % 7}.5" for i in range(n)]
    return "\n".join(lines)


def _upload_csv(app_client, csv_text: str, filename: str = "data.csv", kind: str = "pre_design") -> str:
    resp = app_client.post(
        "/api/v1/datasets",
        data={"kind": kind},
        files={"file": (filename, csv_text, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _poll_job(app_client, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = app_client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s")


def _design(app_client, name: str, dataset_id: str) -> dict:
    resp = app_client.post(
        "/api/v1/design",
        json={
            "config": {
                "name": name,
                "unit_col": "user_id",
                "groups": {"control": 0.5, "treatment": 0.5},
                "metrics": [{
                    "name": "revenue", "type": "continuous", "role": "primary",
                    # Part 1: metric description must survive the export→import
                    # round trip (the config deep-compare below asserts it).
                    "description": "Total revenue per user in the test window.",
                }],
                "sample_size": 200,
                "split_method": "simple",
                "isolation": "off",
            },
            "dataset_id": dataset_id,
        },
    )
    assert resp.status_code == 202, resp.text
    job = _poll_job(app_client, resp.json()["job_id"])
    assert job["status"] == "completed", job
    return job


def _export(app_client, name: str, *, include_datasets: bool = False) -> bytes:
    resp = app_client.get(
        f"/api/v1/experiments/{name}/export", params={"include_datasets": str(include_datasets).lower()}
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    return resp.content


def _import(app_client, raw: bytes, *, confirm: bool = False):
    return app_client.post(
        "/api/v1/experiments/import",
        data={"confirm_dataset_names": str(confirm).lower()},
        files={"file": ("export.zip", raw, "application/zip")},
    )


def _rezip(raw: bytes, *, manifest_patch: dict) -> bytes:
    """Пересобирает архив с подмененным manifest.json — так тестируется отказ
    по версии, не подделывая при этом остальной архив."""
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            data = src.read(item)
            if item == "manifest.json":
                manifest = json.loads(data)
                manifest.update(manifest_patch)
                data = json.dumps(manifest).encode()
            dst.writestr(item, data)
    return out.getvalue()


def test_export_import_round_trip_preserves_config_assignments_results(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)

    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "rt_exp", dataset_id)

    post_id = _upload_csv(app_client, _post_csv(), filename="post.csv", kind="post_analysis")
    analyze = app_client.post(
        "/api/v1/experiments/rt_exp/analyze", json={"dataset_id": post_id, "correction": "holm"}
    )
    assert analyze.status_code == 202, analyze.text
    assert _poll_job(app_client, analyze.json()["job_id"])["status"] == "completed"

    # PUT /blocks принимает голый список и различает обновление/создание по
    # id — без него upsert_many создал бы ВТОРОЙ hypothesis-блок.
    existing_blocks = app_client.get("/api/v1/experiments/rt_exp/blocks").json()
    hypothesis_block = next(b for b in existing_blocks if b["kind"] == "hypothesis")
    put_blocks = app_client.put(
        "/api/v1/experiments/rt_exp/blocks",
        json=[
            {
                "id": hypothesis_block["id"],
                "kind": "hypothesis",
                "title": "Hypothesis",
                "content_md": "H0: nothing",
                "position": 0,
            }
        ],
    )
    assert put_blocks.status_code == 200, put_blocks.text

    original = app_client.get("/api/v1/experiments/rt_exp").json()
    original_results = app_client.get("/api/v1/experiments/rt_exp/results").json()
    original_row = ExperimentRepo().get_by_name("rt_exp")
    from abkit.db.repositories import AssignmentRepo

    original_assignments = AssignmentRepo().load(original_row.id)

    raw = _export(app_client, "rt_exp")

    # Архив содержит ровно то, что обещает ТЗ.
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "experiment.json" in names
        assert "assignments.parquet" in names
        assert "analysis_results.json" in names
        assert "reports/design_report.html" in names
        assert "reports/report.html" in names
        # Датасеты — по ссылке, не вложены (дефолт).
        assert not [n for n in names if n.startswith("datasets/")]
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["format_version"] == 1
        assert manifest["exported_by"] == "editor@co.com"
        payload = json.loads(zf.read("experiment.json"))
        assert payload["datasets"], "dataset references must be carried even without snapshots"

    resp = _import(app_client, raw)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Имя занято исходным тестом -> суффикс.
    assert body["experiment_name"] == "rt_exp (imported)"
    assert body["renamed"] is True
    assert body["original_name"] == "rt_exp"
    # Датасеты те же самые (совпали по sha256) — предупреждений быть не должно.
    assert body["warnings"] == []

    imported = app_client.get("/api/v1/experiments/rt_exp (imported)").json()
    assert imported["config"] == original["config"]
    assert imported["publication_status"] == "draft"
    assert imported["owner_email"] == "editor@co.com"

    imported_row = ExperimentRepo().get_by_name("rt_exp (imported)")
    imported_assignments = AssignmentRepo().load(imported_row.id)
    assert len(imported_assignments) == len(original_assignments)
    assert sorted(imported_assignments["unit_id"]) == sorted(original_assignments["unit_id"])
    assert (
        imported_assignments.sort_values("unit_id")["group"].tolist()
        == original_assignments.sort_values("unit_id")["group"].tolist()
    )

    imported_results = app_client.get("/api/v1/experiments/rt_exp (imported)/results").json()
    # results — ядровой JSON (verdicts, построчные методы); run_meta несет
    # created_at/run_number, которые у копии свои по построению.
    assert {k: v for k, v in imported_results.items() if k != "run_meta"} == {
        k: v for k, v in original_results.items() if k != "run_meta"
    }
    assert ResultRepo().count_for_experiment(imported_row.id) == 1

    blocks = app_client.get("/api/v1/experiments/rt_exp (imported)/blocks").json()
    hypothesis = [b for b in blocks if b["kind"] == "hypothesis"]
    assert len(hypothesis) == 1, "default blocks must be updated, not duplicated"
    assert hypothesis[0]["content_md"] == "H0: nothing"

    reports = app_client.get("/api/v1/experiments/rt_exp (imported)/reports/design_report.html")
    assert reports.status_code == 200


def test_import_twice_keeps_appending_a_distinct_suffix(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "dup_exp", dataset_id)
    raw = _export(app_client, "dup_exp")

    first = _import(app_client, raw)
    second = _import(app_client, raw)
    assert first.json()["experiment_name"] == "dup_exp (imported)"
    assert second.json()["experiment_name"] == "dup_exp (imported 2)"


def test_import_rejects_newer_format_version_with_a_clear_message(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "ver_exp", dataset_id)
    raw = _export(app_client, "ver_exp")

    resp = _import(app_client, _rezip(raw, manifest_patch={"format_version": 99}))
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert error["code"] == "unsupported_format_version"
    assert "99" in error["message"]
    assert "Upgrade ABSet" in error["message"]
    # Отказ не должен оставлять за собой эксперимент.
    assert ExperimentRepo().get_by_name("ver_exp (imported)") is None


def test_import_rejects_a_non_archive(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    resp = _import(app_client, b"this is not a zip at all")
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "invalid_archive"


def test_import_warns_when_dataset_is_missing_and_still_succeeds(app_client, tmp_path, monkeypatch):
    """Датасет не найден ни по sha256, ни по имени, снапшота в архиве нет ->
    импорт УДАЕТСЯ с предупреждением (ТЗ), а не падает."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv(), filename="vanishing.csv")
    _design(app_client, "warn_exp", dataset_id)
    raw = _export(app_client, "warn_exp")

    # Убираем датасет из инстанса -> ссылке нечего резолвить.
    app_client.request(
        "DELETE", f"/api/v1/datasets/{dataset_id}", json={"confirm": "DELETE"}
    )

    resp = _import(app_client, raw)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["warnings"], "a missing dataset must surface as a warning"
    assert "vanishing.csv" in body["warnings"][0]
    assert "re-analysis is unavailable" in body["warnings"][0]
    assert ExperimentRepo().get_by_name("warn_exp (imported)") is not None


def test_import_asks_confirmation_on_name_match_then_links(app_client, tmp_path, monkeypatch):
    """Тот же ИМЯ, другое содержимое -> сначала 400 confirmation_required,
    затем, с confirm, импорт проходит и линкует по имени."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv(), filename="shared.csv")
    _design(app_client, "conf_exp", dataset_id)
    raw = _export(app_client, "conf_exp")

    # Подменяем содержимое датасета под тем же именем: sha не совпадет, имя —
    # совпадет.
    app_client.request("DELETE", f"/api/v1/datasets/{dataset_id}", json={"confirm": "DELETE"})
    _upload_csv(app_client, _design_csv(n=150), filename="shared.csv")

    first = _import(app_client, raw)
    assert first.status_code == 400, first.text
    error = first.json()["error"]
    assert error["code"] == "confirmation_required"
    assert error["details"]["datasets"] == ["shared.csv"]
    # Ничего не создано до подтверждения.
    assert ExperimentRepo().get_by_name("conf_exp (imported)") is None

    second = _import(app_client, raw, confirm=True)
    assert second.status_code == 201, second.text
    assert ExperimentRepo().get_by_name("conf_exp (imported)") is not None
    assert any("linked by name" in w for w in second.json()["warnings"])


def test_export_with_snapshots_lets_import_recreate_the_dataset(app_client, tmp_path, monkeypatch):
    """Cross-instance-миграция: снапшот в архиве -> датасет пересоздается,
    владелец — импортирующий, и он реально читается с диска."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv(), filename="snap.csv")
    _design(app_client, "snap_exp", dataset_id)

    raw = _export(app_client, "snap_exp", include_datasets=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert [n for n in zf.namelist() if n.startswith("datasets/")], "snapshot must be embedded"

    app_client.request("DELETE", f"/api/v1/datasets/{dataset_id}", json={"confirm": "DELETE"})

    resp = _import(app_client, raw)
    assert resp.status_code == 201, resp.text
    assert resp.json()["warnings"] == [], "a carried snapshot must not warn"

    listing = app_client.get("/api/v1/datasets", params={"q": "snap.csv"}).json()
    assert listing["total"] == 1
    recreated = listing["items"][0]
    assert recreated["filename"] == "snap.csv"
    assert recreated["n_rows"] == 200
    # Снапшот пишется как .parquet, даже если отображаемое имя .csv —
    # read_dataset_file выбирает парсер по расширению storage_path, так что
    # превью здесь и есть проверка, что файл реально читается.
    preview = app_client.get(f"/api/v1/datasets/{recreated['id']}/preview")
    assert preview.status_code == 200, preview.text
    assert preview.json()["n_rows"] == 200


def test_export_is_denied_for_viewer(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "perm_exp", dataset_id)
    raw = _export(app_client, "perm_exp")
    app_client.post("/api/v1/auth/logout")

    _login(app_client, email="viewer@co.com", role="viewer")
    resp = app_client.get("/api/v1/experiments/perm_exp/export")
    assert resp.status_code == 403, resp.text

    imported = _import(app_client, raw)
    assert imported.status_code == 403, imported.text


def test_export_of_invisible_draft_is_404_for_another_editor(app_client, tmp_path, monkeypatch):
    """Editor+ может экспортировать любой ВИДИМЫЙ тест — чужой черновик
    невидим, значит и не экспортируется (тот же гейт, что у Analyze)."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "hidden_exp", dataset_id)
    app_client.post("/api/v1/auth/logout")

    _login(app_client, email="other@co.com", role="editor")
    resp = app_client.get("/api/v1/experiments/hidden_exp/export")
    assert resp.status_code == 404, resp.text


def test_export_and_import_are_audited(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "audit_exp", dataset_id)
    raw = _export(app_client, "audit_exp")
    _import(app_client, raw)

    from abkit.db.repositories import AuditRepo

    actions = [e.action for e in AuditRepo().list_recent(limit=100)]
    assert "experiment.export" in actions
    assert "experiment.import" in actions
