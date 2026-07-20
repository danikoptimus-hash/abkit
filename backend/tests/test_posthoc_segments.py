"""Segment-combinations package §1/§2 at the HTTP layer: combinations accepted
+ computed in the analyze run, the cardinality guard refuses an oversized cut,
and post-hoc cuts are appended to / removed from a finished run (external-split
included) without touching the verdict."""

from __future__ import annotations

import time

from abkit.auth.passwords import hash_password
from abkit.db.repositories import UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})


def _poll_job(app_client, job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = app_client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s")


def _design_external(app_client, name: str, **overrides) -> None:
    config = {
        "name": name, "unit_col": "",
        "groups": {"control": 0.5, "treatment": 0.5},
        "metrics": [{"name": "conversion", "type": "binary", "role": "primary"}],
        "split_source": "external", "isolation": "off",
    }
    config.update(overrides)
    resp = app_client.post("/api/v1/design", json={"config": config})
    assert resp.status_code == 202, resp.text
    assert _poll_job(app_client, resp.json()["job_id"])["status"] == "completed"


def _upload(app_client, filename: str, csv_text: str) -> str:
    up = app_client.post(
        "/api/v1/datasets", data={"kind": "post_analysis"},
        files={"file": (filename, csv_text, "text/csv")},
    )
    assert up.status_code == 201, up.text
    return up.json()["id"]


def _strata_csv() -> str:
    rows = ["variant,conversion,country,platform"]
    for country in ("US", "UK"):
        for platform in ("ios", "android"):
            for _ in range(40):
                rows += [f"A,0,{country},{platform}", f"B,1,{country},{platform}"]
    return "\n".join(rows) + "\n"


def _analyze(app_client, name, dataset_id, **body_extra):
    body = {
        "dataset_id": dataset_id, "correction": "none",
        "group_column": "variant", "group_mapping": {"A": "control", "B": "treatment"},
    }
    body.update(body_extra)
    resp = app_client.post(f"/api/v1/experiments/{name}/analyze", json=body)
    assert resp.status_code == 202, resp.text
    assert _poll_job(app_client, resp.json()["job_id"])["status"] == "completed"


def test_combination_computed_in_the_run(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    _design_external(app_client, "combo_run", strata=["country"])
    ds = _upload(app_client, "post.csv", _strata_csv())
    _analyze(app_client, "combo_run", ds,
             segment_columns=["country"], segment_combinations=[["country", "platform"]])

    chart = app_client.get("/api/v1/experiments/combo_run/results").json()["chart_data"]
    seg = chart["metrics"]["conversion"]["segments_by_dimension"]
    assert "country × platform" in seg
    assert chart["combination_dimensions"] == ["country × platform"]


def test_cardinality_guard_refuses_oversized_combination(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    _design_external(app_client, "combo_refuse")
    # colA has 21 distinct values, colB has 10 -> 210 cells > 200 -> refuse.
    rows = ["variant,conversion,colA,colB"]
    for i in range(42):
        rows.append(f"{'A' if i % 2 == 0 else 'B'},{i % 2},a{i % 21},b{i % 10}")
    ds = _upload(app_client, "wide.csv", "\n".join(rows) + "\n")
    resp = app_client.post(
        "/api/v1/experiments/combo_refuse/analyze",
        json={
            "dataset_id": ds, "correction": "none",
            "group_column": "variant", "group_mapping": {"A": "control", "B": "treatment"},
            "segment_combinations": [["colA", "colB"]],
        },
    )
    assert resp.status_code == 422, resp.text
    assert "noise, not analysis" in resp.text


def test_posthoc_add_dedup_remove_and_verdict_unchanged(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    _design_external(app_client, "posthoc", strata=["country"])
    ds = _upload(app_client, "post.csv", _strata_csv())
    _analyze(app_client, "posthoc", ds, segment_columns=["country"])

    before = app_client.get("/api/v1/experiments/posthoc/results").json()
    verdict_before = before["results"]
    assert "country × platform" not in before["chart_data"]["metrics"]["conversion"]["segments_by_dimension"]

    # Add a post-hoc combination.
    resp = app_client.post(
        "/api/v1/experiments/posthoc/results/segments",
        json={"segment_combinations": [["country", "platform"]]},
    )
    assert resp.status_code == 202, resp.text
    assert _poll_job(app_client, resp.json()["job_id"])["status"] == "completed"

    after = app_client.get("/api/v1/experiments/posthoc/results").json()
    chart = after["chart_data"]
    assert "country × platform" in chart["metrics"]["conversion"]["segments_by_dimension"]
    assert chart["post_hoc_dimensions"] == ["country × platform"]
    # Verdict / primary results are byte-identical — post-hoc never re-runs metrics.
    assert after["results"] == verdict_before

    # Dedup: the same cut in the other column order adds nothing.
    resp = app_client.post(
        "/api/v1/experiments/posthoc/results/segments",
        json={"segment_combinations": [["platform", "country"]]},
    )
    assert _poll_job(app_client, resp.json()["job_id"])["status"] == "completed"
    chart2 = app_client.get("/api/v1/experiments/posthoc/results").json()["chart_data"]
    assert chart2["post_hoc_dimensions"] == ["country × platform"]

    # Remove it.
    rm = app_client.delete(
        "/api/v1/experiments/posthoc/results/segments", params={"label": "country × platform"}
    )
    assert rm.status_code == 200, rm.text
    chart3 = app_client.get("/api/v1/experiments/posthoc/results").json()["chart_data"]
    assert "country × platform" not in chart3["metrics"]["conversion"]["segments_by_dimension"]
    assert chart3["post_hoc_dimensions"] == []


def test_posthoc_remove_rejects_non_posthoc_dimension(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    _design_external(app_client, "posthoc_guard", strata=["country"])
    ds = _upload(app_client, "post.csv", _strata_csv())
    _analyze(app_client, "posthoc_guard", ds, segment_columns=["country"])
    # "country" is a declared/pre-run cut, not post-hoc — can't be removed.
    rm = app_client.delete(
        "/api/v1/experiments/posthoc_guard/results/segments", params={"label": "country"}
    )
    assert rm.status_code == 400, rm.text
