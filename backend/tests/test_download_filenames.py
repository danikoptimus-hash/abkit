"""Feature (dataset name in downloads): every experiment-page download's
Content-Disposition carries the design dataset's name — <experiment>_<dataset>_
<suffix>. Covers ABSet (design dataset), external (reference / none), rename,
and the deleted-dataset frozen fallback."""

from __future__ import annotations

import time

from abkit.auth.passwords import hash_password
from abkit.db.repositories import UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})


def _poll(app_client, job_id, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = app_client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _upload(app_client, filename, csv_text, kind="pre_design"):
    up = app_client.post(
        "/api/v1/datasets", data={"kind": kind},
        files={"file": (filename, csv_text, "text/csv")},
    )
    assert up.status_code == 201, up.text
    return up.json()


def _design_csv(n=120):
    rows = ["user_id,revenue"]
    for i in range(n):
        rows.append(f"u{i},{100 + i % 9}")
    return "\n".join(rows) + "\n"


def _design_absplit(app_client, name, dataset_id):
    resp = app_client.post(
        "/api/v1/design",
        json={
            "config": {
                "name": name, "unit_col": "user_id",
                "groups": {"control": 0.5, "treatment": 0.5},
                "metrics": [{"name": "revenue", "type": "continuous", "role": "primary"}],
                "sample_size": 100, "split_method": "simple", "isolation": "off",
            },
            "dataset_id": dataset_id,
        },
    )
    assert resp.status_code == 202, resp.text
    assert _poll(app_client, resp.json()["job_id"])["status"] == "completed"


def _design_external(app_client, name, reference_dataset_id=None):
    config = {
        "name": name, "unit_col": "",
        "groups": {"control": 0.5, "treatment": 0.5},
        "metrics": [{"name": "conversion", "type": "binary", "role": "primary"}],
        "split_source": "external", "isolation": "off",
    }
    if reference_dataset_id:
        config["reference_dataset_id"] = reference_dataset_id
    resp = app_client.post("/api/v1/design", json={"config": config})
    assert resp.status_code == 202, resp.text
    assert _poll(app_client, resp.json()["job_id"])["status"] == "completed"


def _disposition(app_client, url, method="get", **kw):
    resp = getattr(app_client, method)(url, **kw)
    assert resp.status_code == 200, resp.text
    return resp.headers.get("content-disposition", "")


def test_absplit_downloads_carry_design_dataset_name(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    ds = _upload(app_client, "sales quarterly.csv", _design_csv())  # → segment "sales_quarterly"
    _design_absplit(app_client, "abx", ds["id"])

    seg = "sales_quarterly"
    # design report
    assert seg in _disposition(app_client, "/api/v1/experiments/abx/reports/design_report.html?download=1")
    # samples zip + per-group csv
    assert seg in _disposition(app_client, "/api/v1/experiments/abx/samples.zip")
    csv_disp = _disposition(app_client, "/api/v1/experiments/abx/samples/control.csv")
    assert seg in csv_disp and "control.csv" in csv_disp
    # export zip
    export_disp = _disposition(app_client, "/api/v1/experiments/abx/export")
    assert seg in export_disp and "export.zip" in export_disp

    # Analysis report (after a run).
    post = _upload(app_client, "march results.csv", _design_csv(), kind="post_analysis")
    ar = app_client.post(
        "/api/v1/experiments/abx/analyze",
        json={"dataset_id": post["id"], "correction": "none"},
    )
    assert _poll(app_client, ar.json()["job_id"])["status"] == "completed"
    assert seg in _disposition(app_client, "/api/v1/experiments/abx/reports/report.html?download=1")

    # ExperimentDetail exposes the same segment for client-side blob downloads.
    detail = app_client.get("/api/v1/experiments/abx").json()
    assert detail["download_dataset_segment"] == seg


def test_rename_is_reflected_at_download_time(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    ds = _upload(app_client, "old_name.csv", _design_csv())
    _design_absplit(app_client, "abrn", ds["id"])
    app_client.patch(f"/api/v1/datasets/{ds['id']}", json={"name": "new_name.csv"})
    disp = _disposition(app_client, "/api/v1/experiments/abrn/reports/design_report.html?download=1")
    assert "new_name" in disp
    assert "old_name" not in disp


def test_external_without_reference_keeps_plain_name(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    _design_external(app_client, "extnone")
    # External has no design report/samples — test via export (always available).
    disp = _disposition(app_client, "/api/v1/experiments/extnone/export")
    # No dataset segment — plain <name>_export.zip.
    assert "extnone_export.zip" in disp
    assert app_client.get("/api/v1/experiments/extnone").json()["download_dataset_segment"] is None


def test_external_with_reference_uses_reference_name(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    ref = _upload(app_client, "firebase export.csv", _design_csv())  # → "firebase_export"
    _design_external(app_client, "extref", reference_dataset_id=ref["id"])
    disp = _disposition(app_client, "/api/v1/experiments/extref/export")
    assert "firebase_export" in disp


def test_deleted_design_dataset_falls_back_to_frozen_analysis_filename(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    ds = _upload(app_client, "design_data.csv", _design_csv())
    _design_absplit(app_client, "abdel", ds["id"])
    # Run analysis so a frozen dataset_filename exists on the result.
    post = _upload(app_client, "frozen results.csv", _design_csv(), kind="post_analysis")
    ar = app_client.post(
        "/api/v1/experiments/abdel/analyze",
        json={"dataset_id": post["id"], "correction": "none"},
    )
    assert _poll(app_client, ar.json()["job_id"])["status"] == "completed"

    # Delete the design dataset (in use → requires confirm).
    rm = app_client.request(
        "DELETE", f"/api/v1/datasets/{ds['id']}", json={"confirm": "DELETE"}
    )
    assert rm.status_code in (200, 204), rm.text

    disp = _disposition(app_client, "/api/v1/experiments/abdel/reports/design_report.html?download=1")
    assert "frozen_results" in disp
    assert "design_data" not in disp
