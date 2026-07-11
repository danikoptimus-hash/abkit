"""Stage 4 (CLAUDE.md, variant flow images): upload/list/serve/delete/reorder
API, permission gate (same as Redesign — owner/access-editor/admin), and
cascade-delete-with-files on experiment deletion (unlike datasets)."""

from __future__ import annotations

import io
import time
import uuid as uuid_mod
from pathlib import Path

from PIL import Image

from abkit.auth.passwords import hash_password
from abkit.db.repositories import ExperimentRepo, FlowImageRepo, UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    user_id = UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})
    return user_id


def _make_experiment(name="flow_exp", owner_id=None):
    return ExperimentRepo().create(name=name, owner_id=owner_id, status="designed", config={"name": name})


def _png_file(color=(255, 0, 0)):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_upload_list_and_serve_flow_image(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    owner_id = _login(app_client)
    _make_experiment("flow_exp1", owner_id=owner_id)

    resp = app_client.post(
        "/api/v1/experiments/flow_exp1/flow-images",
        data={"group_name": "control", "flow_title": "Existing checkout"},
        files={"file": ("shot.png", _png_file(), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["group_name"] == "control"
    assert body["flow_title"] == "Existing checkout"
    assert body["position"] == 0

    listed = app_client.get("/api/v1/experiments/flow_exp1/flow-images")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    file_resp = app_client.get(f"/api/v1/experiments/flow_exp1/flow-images/{body['id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "image/png"
    assert len(file_resp.content) > 0


def test_upload_rejects_non_image_content(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    owner_id = _login(app_client)
    _make_experiment("flow_exp2", owner_id=owner_id)

    resp = app_client.post(
        "/api/v1/experiments/flow_exp2/flow-images",
        data={"group_name": "control", "flow_title": ""},
        files={"file": ("fake.png", io.BytesIO(b"not an image"), "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_flow_image"


def test_upload_enforces_max_per_group(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    owner_id = _login(app_client)
    _make_experiment("flow_exp3", owner_id=owner_id)

    for i in range(10):
        resp = app_client.post(
            "/api/v1/experiments/flow_exp3/flow-images",
            data={"group_name": "control", "flow_title": ""},
            files={"file": (f"shot{i}.png", _png_file(), "image/png")},
        )
        assert resp.status_code == 201, resp.text

    resp = app_client.post(
        "/api/v1/experiments/flow_exp3/flow-images",
        data={"group_name": "control", "flow_title": ""},
        files={"file": ("shot_over.png", _png_file(), "image/png")},
    )
    assert resp.status_code == 400
    assert "maximum" in resp.json()["error"]["message"]


def test_delete_flow_image_removes_row_and_file(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    owner_id = _login(app_client)
    _make_experiment("flow_exp4", owner_id=owner_id)

    resp = app_client.post(
        "/api/v1/experiments/flow_exp4/flow-images",
        data={"group_name": "control", "flow_title": ""},
        files={"file": ("shot.png", _png_file(), "image/png")},
    )
    image_id = resp.json()["id"]
    stored_path = Path(FlowImageRepo().get_by_id(uuid_mod.UUID(image_id)).file_path)
    assert stored_path.exists()

    del_resp = app_client.delete(f"/api/v1/experiments/flow_exp4/flow-images/{image_id}")
    assert del_resp.status_code == 204
    assert not stored_path.exists()

    listed = app_client.get("/api/v1/experiments/flow_exp4/flow-images")
    assert listed.json() == []


def test_set_group_order_updates_title_position_and_deletes_missing(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    owner_id = _login(app_client)
    _make_experiment("flow_exp5", owner_id=owner_id)

    ids = []
    for i in range(3):
        resp = app_client.post(
            "/api/v1/experiments/flow_exp5/flow-images",
            data={"group_name": "treatment", "flow_title": "old title"},
            files={"file": (f"shot{i}.png", _png_file(), "image/png")},
        )
        ids.append(resp.json()["id"])
    dropped_path = Path(FlowImageRepo().get_by_id(uuid_mod.UUID(ids[1])).file_path)

    # keep ids[2], ids[0], reversed; drop ids[1] (deferred delete, applied here).
    resp = app_client.put(
        "/api/v1/experiments/flow_exp5/flow-images/order",
        json={"group_name": "treatment", "flow_title": "new title", "image_ids": [ids[2], ids[0]]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    by_id = {b["id"]: b for b in body}
    assert by_id[ids[2]]["position"] == 0
    assert by_id[ids[0]]["position"] == 1
    assert all(b["flow_title"] == "new title" for b in body)
    assert not dropped_path.exists()

    listed = app_client.get("/api/v1/experiments/flow_exp5/flow-images").json()
    assert {img["id"] for img in listed} == {ids[2], ids[0]}


def test_upload_forbidden_for_non_owner_editor(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    other_owner = UserRepo().create(
        email="owner_flow@co.com", first_name="O", password_hash=hash_password("pw12345"), role="editor"
    )
    _make_experiment("flow_exp6", owner_id=other_owner)

    _login(app_client, email="not_owner_flow@co.com", role="editor")
    resp = app_client.post(
        "/api/v1/experiments/flow_exp6/flow-images",
        data={"group_name": "control", "flow_title": ""},
        files={"file": ("shot.png", _png_file(), "image/png")},
    )
    assert resp.status_code == 403


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


def test_set_group_order_regenerates_design_report_with_embedded_image(app_client, tmp_path, monkeypatch):
    """Stage 4 item 4.4 (report side): design_report.html is written by the
    real design job BEFORE any flow image exists — this confirms the final
    order call patches the already-saved file in place (see
    abkit/jobs.py::_regenerate_design_report)."""
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    _login(app_client)

    csv_text = "\n".join(["user_id,revenue"] + [f"u{i},{100 + i % 10}" for i in range(200)])
    up = app_client.post(
        "/api/v1/datasets", data={"kind": "pre_design"}, files={"file": ("data.csv", csv_text, "text/csv")},
    )
    dataset_id = up.json()["id"]

    design_resp = app_client.post(
        "/api/v1/design",
        json={
            "config": {
                "name": "flow_exp_report",
                "unit_col": "user_id",
                "groups": {"control": 0.5, "treatment": 0.5},
                "metrics": [{"name": "revenue", "type": "continuous", "role": "primary"}],
                "sample_size": 200,
                "split_method": "simple",
                "isolation": "off",
            },
            "dataset_id": dataset_id,
        },
    )
    job = _poll_job(app_client, design_resp.json()["job_id"])
    assert job["status"] == "completed", job

    report_path = Path(tmp_path) / "flow_exp_report" / "design_report.html"
    before_html = report_path.read_text(encoding="utf-8")
    assert 'id="section-flows"' not in before_html

    upload_resp = app_client.post(
        "/api/v1/experiments/flow_exp_report/flow-images",
        data={"group_name": "control", "flow_title": "Existing checkout"},
        files={"file": ("shot.png", _png_file(), "image/png")},
    )
    image_id = upload_resp.json()["id"]

    order_resp = app_client.put(
        "/api/v1/experiments/flow_exp_report/flow-images/order",
        json={"group_name": "control", "flow_title": "Existing checkout", "image_ids": [image_id]},
    )
    assert order_resp.status_code == 200, order_resp.text

    after_html = report_path.read_text(encoding="utf-8")
    assert 'id="section-flows"' in after_html
    assert "Existing checkout" in after_html
    assert "data:image/jpeg;base64," in after_html
    # The rest of the report (written by the design job) is untouched.
    assert "flow_exp_report" in after_html


def test_delete_experiment_cascades_flow_images_and_files(app_client, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    owner_id = _login(app_client)
    _make_experiment("flow_exp7", owner_id=owner_id)

    resp = app_client.post(
        "/api/v1/experiments/flow_exp7/flow-images",
        data={"group_name": "control", "flow_title": ""},
        files={"file": ("shot.png", _png_file(), "image/png")},
    )
    image_id = resp.json()["id"]
    stored_path = Path(FlowImageRepo().get_by_id(uuid_mod.UUID(image_id)).file_path)
    assert stored_path.exists()

    del_resp = app_client.request("DELETE", "/api/v1/experiments/flow_exp7", json={"confirm": "DELETE"})
    assert del_resp.status_code == 200, del_resp.text

    assert FlowImageRepo().get_by_id(uuid_mod.UUID(image_id)) is None
    assert not stored_path.exists()
