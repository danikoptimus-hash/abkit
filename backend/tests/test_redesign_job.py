"""5-part package pt.3: POST /experiments/{name}/redesign — in-place replace
of an existing 'designed' experiment's split/config, unlike POST /design's
always-create. Mirrors backend/tests/test_design_job.py's fixtures/helpers."""

from __future__ import annotations

import time

from abkit.auth.passwords import hash_password
from abkit.db.repositories import AssignmentRepo, ExperimentRepo, ResultRepo, UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})


def _upload_csv(app_client, csv_text: str, kind: str = "pre_design"):
    resp = app_client.post(
        "/api/v1/datasets", data={"kind": kind}, files={"file": ("data.csv", csv_text, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _design_csv(n=200) -> str:
    lines = ["user_id,revenue"] + [f"u{i},{100 + i % 10}" for i in range(n)]
    return "\n".join(lines)


def _design_config(name: str, sample_size: int = 200) -> dict:
    return {
        "name": name,
        "unit_col": "user_id",
        "groups": {"control": 0.5, "treatment": 0.5},
        "metrics": [{"name": "revenue", "type": "continuous", "role": "primary"}],
        "sample_size": sample_size,
        "split_method": "simple",
        "isolation": "off",
        "exclude_experiments": "all_active",
    }


def _poll_job(app_client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = app_client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s")


def _design(app_client, name: str, dataset_id: str, sample_size: int = 200) -> dict:
    resp = app_client.post(
        "/api/v1/design", json={"config": _design_config(name, sample_size), "dataset_id": dataset_id},
    )
    assert resp.status_code == 202, resp.text
    job = _poll_job(app_client, resp.json()["job_id"])
    assert job["status"] == "completed", job
    return job


def test_redesign_replaces_split_and_config_in_place(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "redesign_target", dataset_id, sample_size=200)

    exp = ExperimentRepo().get_by_name("redesign_target")
    assert exp is not None
    original_id = exp.id
    original_assignments = AssignmentRepo().load(exp.id)

    # Different dataset (fewer candidate rows) — the actual split always
    # covers every candidate row, so a smaller pool is the reliable way to
    # prove the split changed (config.sample_size only feeds the power
    # calculation, it doesn't subsample candidates).
    dataset_id_2 = _upload_csv(app_client, _design_csv(n=120))
    resp = app_client.post(
        "/api/v1/experiments/redesign_target/redesign",
        json={"config": _design_config("redesign_target", sample_size=100), "dataset_id": dataset_id_2},
    )
    assert resp.status_code == 202, resp.text
    job = _poll_job(app_client, resp.json()["job_id"])
    assert job["status"] == "completed", job

    exp_after = ExperimentRepo().get_by_name("redesign_target")
    assert exp_after.id == original_id  # same row, not a new experiment
    assert exp_after.status == "designed"
    assert exp_after.config["sample_size"] == 100

    new_assignments = AssignmentRepo().load(exp_after.id)
    assert len(new_assignments) == 120
    assert len(new_assignments) != len(original_assignments)


def test_redesign_deletes_analysis_results_from_old_split(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "redesign_with_results", dataset_id)
    exp = ExperimentRepo().get_by_name("redesign_with_results")

    post_dataset_id = _upload_csv(app_client, _design_csv(), kind="post_analysis")
    analyze_resp = app_client.post(
        "/api/v1/experiments/redesign_with_results/analyze",
        json={"dataset_id": post_dataset_id, "correction": "none", "compare_methods": False},
    )
    assert analyze_resp.status_code == 202, analyze_resp.text
    analyze_job = _poll_job(app_client, analyze_resp.json()["job_id"])
    assert analyze_job["status"] == "completed", analyze_job
    assert ResultRepo().count_for_experiment(exp.id) > 0

    dataset_id_2 = _upload_csv(app_client, _design_csv())
    resp = app_client.post(
        "/api/v1/experiments/redesign_with_results/redesign",
        json={"config": _design_config("redesign_with_results"), "dataset_id": dataset_id_2},
    )
    job = _poll_job(app_client, resp.json()["job_id"])
    assert job["status"] == "completed", job

    assert ResultRepo().count_for_experiment(exp.id) == 0

    results_resp = app_client.get("/api/v1/experiments/redesign_with_results/results")
    assert results_resp.status_code == 404


def test_redesign_unavailable_once_running(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "redesign_running_guard", dataset_id)

    status_resp = app_client.post(
        "/api/v1/experiments/redesign_running_guard/status", json={"to": "running"},
    )
    assert status_resp.status_code == 200, status_resp.text

    dataset_id_2 = _upload_csv(app_client, _design_csv())
    resp = app_client.post(
        "/api/v1/experiments/redesign_running_guard/redesign",
        json={"config": _design_config("redesign_running_guard"), "dataset_id": dataset_id_2},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_status"


def test_redesign_cannot_rename(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "redesign_no_rename", dataset_id)

    dataset_id_2 = _upload_csv(app_client, _design_csv())
    resp = app_client.post(
        "/api/v1/experiments/redesign_no_rename/redesign",
        json={"config": _design_config("a_different_name"), "dataset_id": dataset_id_2},
    )
    assert resp.status_code == 422


def test_redesign_isolation_self_exclusion(app_client, tmp_path, monkeypatch):
    """abkit/design/isolation.py already self-excludes an experiment's own
    OLD assignments from the isolation occupied-units check (via
    current_experiment_name=config.name) — redesigning with isolation=off
    and the SAME users the experiment already occupies must not be blocked
    by the experiment's own prior split."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "redesign_self_exclusion", dataset_id)

    # Same unit pool, isolation="exclude" this time — would exclude every
    # unit as "already occupied" if self-exclusion didn't work, since this
    # experiment itself holds all of them from the first design.
    config = _design_config("redesign_self_exclusion")
    config["isolation"] = "exclude"
    resp = app_client.post(
        "/api/v1/experiments/redesign_self_exclusion/redesign",
        json={"config": config, "dataset_id": dataset_id},
    )
    job = _poll_job(app_client, resp.json()["job_id"])
    assert job["status"] == "completed", job

    exp = ExperimentRepo().get_by_name("redesign_self_exclusion")
    assert len(AssignmentRepo().load(exp.id)) == 200


def test_redesign_requires_edit_access(app_client, tmp_path, monkeypatch):
    """Any editor can create (run_design), but redesign needs owner/access-
    editor/admin (require_experiment_edit_access) — a plain editor on
    someone else's experiment is blocked, unlike run_design/run_analyze."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client, email="owner@co.com", role="editor")
    dataset_id = _upload_csv(app_client, _design_csv())
    _design(app_client, "redesign_access_guard", dataset_id)
    app_client.post("/api/v1/auth/logout")

    _login(app_client, email="other_editor@co.com", role="editor")
    dataset_id_2 = _upload_csv(app_client, _design_csv())
    resp = app_client.post(
        "/api/v1/experiments/redesign_access_guard/redesign",
        json={"config": _design_config("redesign_access_guard"), "dataset_id": dataset_id_2},
    )
    assert resp.status_code == 403
