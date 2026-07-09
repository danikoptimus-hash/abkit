"""DB3 (CLAUDE.md dataset-centric model): design/analyze/validate each
record a use in experiment_datasets, end to end via the real API."""

from __future__ import annotations

import time

from abkit.auth.passwords import hash_password
from abkit.db.repositories import ExperimentDatasetRepo, ExperimentRepo, UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})


def _upload_csv(app_client, csv_text: str, kind: str = "pre_design", experiment_name: str | None = None):
    data = {"kind": kind}
    if experiment_name:
        data["experiment_name"] = experiment_name
    resp = app_client.post(
        "/api/v1/datasets", data=data, files={"file": ("data.csv", csv_text, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _design_csv(n=200) -> str:
    lines = ["user_id,revenue"] + [f"u{i},{100 + i % 10}.5" for i in range(n)]
    return "\n".join(lines)


def _poll_job(app_client, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = app_client.get(f"/api/v1/jobs/{job_id}")
        body = resp.json()
        if body["status"] not in ("pending", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s")


def test_design_analyze_validate_each_record_a_dataset_link(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)

    design_dataset_id = _upload_csv(app_client, _design_csv())
    design_resp = app_client.post(
        "/api/v1/design",
        json={
            "config": {
                "name": "link_exp", "unit_col": "user_id", "groups": {"control": 0.5, "treatment": 0.5},
                "metrics": [{"name": "revenue", "type": "continuous", "role": "primary"}],
                "sample_size": 200, "split_method": "simple", "isolation": "off",
            },
            "dataset_id": design_dataset_id,
        },
    )
    job = _poll_job(app_client, design_resp.json()["job_id"])
    assert job["status"] == "completed", job

    exp = ExperimentRepo().get_by_name("link_exp")
    links = ExperimentDatasetRepo().list_for_experiment(exp.id)
    assert {(str(link.dataset_id), link.kind) for link in links} == {(design_dataset_id, "pre_design")}

    post_dataset_id = _upload_csv(
        app_client, _design_csv(), kind="post_analysis", experiment_name="link_exp",
    )
    analyze_resp = app_client.post(
        "/api/v1/experiments/link_exp/analyze", json={"dataset_id": post_dataset_id},
    )
    analyze_job = _poll_job(app_client, analyze_resp.json()["job_id"])
    assert analyze_job["status"] == "completed", analyze_job

    validate_resp = app_client.post(
        "/api/v1/experiments/link_exp/validate", json={"dataset_id": post_dataset_id, "n_sims": 100},
    )
    validate_job = _poll_job(app_client, validate_resp.json()["job_id"], timeout=30.0)
    assert validate_job["status"] == "completed", validate_job

    links = ExperimentDatasetRepo().list_for_experiment(exp.id)
    kinds_by_dataset = {}
    for link in links:
        kinds_by_dataset.setdefault(str(link.dataset_id), set()).add(link.kind)
    assert kinds_by_dataset[design_dataset_id] == {"pre_design"}
    assert kinds_by_dataset[post_dataset_id] == {"post_analysis", "validation"}


def test_demo_post_data_is_tagged_demo_source_and_linked(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)

    design_dataset_id = _upload_csv(app_client, _design_csv())
    design_resp = app_client.post(
        "/api/v1/design",
        json={
            "config": {
                "name": "demo_link_exp", "unit_col": "user_id", "groups": {"control": 0.5, "treatment": 0.5},
                "metrics": [{"name": "revenue", "type": "continuous", "role": "primary"}],
                "sample_size": 200, "split_method": "simple", "isolation": "off",
            },
            "dataset_id": design_dataset_id,
        },
    )
    _poll_job(app_client, design_resp.json()["job_id"])

    demo_resp = app_client.post(
        "/api/v1/experiments/demo_link_exp/demo-post-data", json={"effect": 0.03},
    )
    assert demo_resp.status_code == 201, demo_resp.text
    demo_dataset = demo_resp.json()
    assert demo_dataset["source"] == "demo"

    exp = ExperimentRepo().get_by_name("demo_link_exp")
    links = ExperimentDatasetRepo().list_for_experiment(exp.id)
    assert (demo_dataset["id"], "post_analysis") in {(str(l.dataset_id), l.kind) for l in links}
