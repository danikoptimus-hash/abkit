"""Folders for A/B tests (item 5, folders package): GET/POST /folders,
PATCH/DELETE /folders/{id}, PUT /experiments/{name}/folder,
POST /experiments/bulk-move-folder, plus folder_id/folder_name showing up on
the experiments list and the `folder` filter composing with the rest."""

from __future__ import annotations

from abkit.auth.passwords import hash_password
from abkit.db.repositories import AuditRepo, ExperimentRepo, UserRepo


def _make_user(email: str, role: str = "editor") -> str:
    return str(UserRepo().create(email=email, first_name="U", password_hash=hash_password("pw12345"), role=role))


def _login(app_client, email: str, role: str = "editor") -> str:
    user_id = _make_user(email, role=role)
    resp = app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})
    assert resp.status_code == 200
    return user_id


def _make_experiment(name: str, owner_id: str) -> None:
    ExperimentRepo().create(name=name, owner_id=owner_id, status="designed", config={"name": name})


def test_create_folder_requires_editor(app_client):
    _login(app_client, "folders_viewer@co.com", role="viewer")
    resp = app_client.post("/api/v1/folders", json={"name": "Q3 tests"})
    assert resp.status_code == 403


def test_create_and_list_folders_with_counts(app_client):
    owner_id = _login(app_client, "folders_owner@co.com")
    _make_experiment("folders_exp_a", owner_id)
    _make_experiment("folders_exp_b", owner_id)

    create_resp = app_client.post("/api/v1/folders", json={"name": "Growth"})
    assert create_resp.status_code == 201, create_resp.text
    folder_id = create_resp.json()["id"]

    move_resp = app_client.put("/api/v1/experiments/folders_exp_a/folder", json={"folder_id": folder_id})
    assert move_resp.status_code == 200, move_resp.text

    listing = app_client.get("/api/v1/folders").json()
    row = next(f for f in listing["items"] if f["id"] == folder_id)
    assert row["count"] == 1
    assert row["created_by_email"] == "folders_owner@co.com"
    assert listing["uncategorized_count"] == 1
    assert listing["all_count"] == 2


def test_create_folder_duplicate_name_is_rejected(app_client):
    _login(app_client, "folders_dup@co.com")
    first = app_client.post("/api/v1/folders", json={"name": "Checkout"})
    assert first.status_code == 201
    second = app_client.post("/api/v1/folders", json={"name": "Checkout"})
    assert second.status_code == 400


def test_move_experiment_to_folder_writes_audit_with_names(app_client):
    owner_id = _login(app_client, "folders_move@co.com")
    _make_experiment("folders_move_exp", owner_id)
    folder_id = app_client.post("/api/v1/folders", json={"name": "Onboarding"}).json()["id"]

    resp = app_client.put("/api/v1/experiments/folders_move_exp/folder", json={"folder_id": folder_id})
    assert resp.status_code == 200
    assert resp.json()["folder_id"] == folder_id

    audit = AuditRepo().list_recent(limit=10, action="experiment.folder_change")
    entry = next(a for a in audit if a.object_name == "folders_move_exp")
    assert entry.details == {"from": None, "to": "Onboarding"}

    back_resp = app_client.put("/api/v1/experiments/folders_move_exp/folder", json={"folder_id": None})
    assert back_resp.status_code == 200
    assert back_resp.json()["folder_id"] is None


def test_move_experiment_to_folder_forbidden_for_unrelated_editor(app_client):
    other_owner = _make_user("folders_other_owner@co.com")
    _make_experiment("folders_forbidden_exp", other_owner)
    _login(app_client, "folders_unrelated@co.com")
    folder_id = app_client.post("/api/v1/folders", json={"name": "Someone else's"}).json()["id"]

    resp = app_client.put("/api/v1/experiments/folders_forbidden_exp/folder", json={"folder_id": folder_id})
    assert resp.status_code == 403


def test_experiments_list_filters_by_folder_and_uncategorized(app_client):
    owner_id = _login(app_client, "folders_filter@co.com")
    _make_experiment("folders_filter_in", owner_id)
    _make_experiment("folders_filter_out", owner_id)
    folder_id = app_client.post("/api/v1/folders", json={"name": "Filtered"}).json()["id"]
    app_client.put("/api/v1/experiments/folders_filter_in/folder", json={"folder_id": folder_id})

    in_folder = app_client.get("/api/v1/experiments", params={"folder": folder_id}).json()
    assert [e["name"] for e in in_folder["items"]] == ["folders_filter_in"]
    assert in_folder["items"][0]["folder_name"] == "Filtered"

    uncategorized = app_client.get("/api/v1/experiments", params={"folder": "none"}).json()
    names = {e["name"] for e in uncategorized["items"]}
    assert "folders_filter_out" in names
    assert "folders_filter_in" not in names


def test_rename_folder_requires_creator_or_admin(app_client):
    creator_id = _login(app_client, "folders_rename_creator@co.com")
    folder_id = app_client.post("/api/v1/folders", json={"name": "Original"}).json()["id"]

    _login(app_client, "folders_rename_other@co.com")
    forbidden = app_client.patch(f"/api/v1/folders/{folder_id}", json={"name": "Hijacked"})
    assert forbidden.status_code == 403

    admin_id = UserRepo().create(
        email="folders_rename_admin@co.com", first_name="A", password_hash=hash_password("pw12345"), role="admin",
    )
    app_client.post("/api/v1/auth/login", json={"email": "folders_rename_admin@co.com", "password": "pw12345"})
    admin_resp = app_client.patch(f"/api/v1/folders/{folder_id}", json={"name": "Renamed by admin"})
    assert admin_resp.status_code == 200
    assert admin_resp.json()["name"] == "Renamed by admin"
    assert creator_id and admin_id


def test_delete_folder_moves_experiments_to_uncategorized_and_requires_creator_or_admin(app_client):
    owner_id = _login(app_client, "folders_delete_owner@co.com")
    folder_id = app_client.post("/api/v1/folders", json={"name": "To delete"}).json()["id"]
    _make_experiment("folders_delete_exp", owner_id)
    app_client.put("/api/v1/experiments/folders_delete_exp/folder", json={"folder_id": folder_id})

    _login(app_client, "folders_delete_other@co.com")
    forbidden = app_client.delete(f"/api/v1/folders/{folder_id}")
    assert forbidden.status_code == 403

    app_client.post("/api/v1/auth/login", json={"email": "folders_delete_owner@co.com", "password": "pw12345"})
    resp = app_client.delete(f"/api/v1/folders/{folder_id}")
    assert resp.status_code == 200
    assert resp.json()["affected_experiments"] == 1

    detail = app_client.get("/api/v1/experiments/folders_delete_exp").json()
    assert detail["folder_id"] is None


def test_bulk_move_folder_skips_no_permission(app_client):
    owner_id = _login(app_client, "folders_bulk_owner@co.com")
    other_owner = _make_user("folders_bulk_other_owner@co.com")
    _make_experiment("folders_bulk_own", owner_id)
    _make_experiment("folders_bulk_others", other_owner)
    folder_id = app_client.post("/api/v1/folders", json={"name": "Bulk target"}).json()["id"]

    resp = app_client.post(
        "/api/v1/experiments/bulk-move-folder",
        json={"names": ["folders_bulk_own", "folders_bulk_others", "folders_bulk_missing"], "folder_id": folder_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["moved"] == ["folders_bulk_own"]
    skipped_by_name = {s["name"]: s["reason"] for s in body["skipped"]}
    assert skipped_by_name["folders_bulk_others"] == "no permission"
    assert skipped_by_name["folders_bulk_missing"] == "not found"

    assert ExperimentRepo().get_by_name("folders_bulk_own").folder_id is not None
    assert ExperimentRepo().get_by_name("folders_bulk_others").folder_id is None
