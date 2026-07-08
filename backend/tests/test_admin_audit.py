"""R2 (FRONTEND.md §3.2): admin-only GET /admin/users и GET /audit (глобальный
журнал; фильтр по пользователю — query-параметр `user`, см. §3.2)."""

from __future__ import annotations

from abkit.auth.passwords import hash_password
from abkit.db.repositories import AuditRepo, UserRepo


def _login(app_client, email, role):
    UserRepo().create(email=email, name="U", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})


def test_list_users_requires_admin(app_client):
    _login(app_client, "viewer@co.com", "viewer")
    resp = app_client.get("/api/v1/admin/users")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_list_users_as_admin(app_client):
    _login(app_client, "admin@co.com", "admin")
    UserRepo().create(email="viewer2@co.com", name="V2", password_hash=hash_password("pw12345"), role="viewer")
    resp = app_client.get("/api/v1/admin/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert {"admin@co.com", "viewer2@co.com"} <= emails


def test_global_audit_requires_admin(app_client):
    _login(app_client, "editor@co.com", "editor")
    resp = app_client.get("/api/v1/audit")
    assert resp.status_code == 403


def test_global_audit_filters_by_user(app_client):
    # _login сама пишет запись auth.login (abkit.auth.service.login) — не
    # только явный AuditRepo().log() ниже, поэтому total сравнивается с
    # запасом (>=), а не точным числом.
    _login(app_client, "admin2@co.com", "admin")
    AuditRepo().log(action="delete_experiment", user_email="other@co.com")

    resp_all = app_client.get("/api/v1/audit")
    assert resp_all.json()["total"] >= 2

    resp_filtered = app_client.get("/api/v1/audit", params={"user": "other@co.com"})
    body = resp_filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "delete_experiment"

    resp_unknown = app_client.get("/api/v1/audit", params={"user": "nobody@co.com"})
    assert resp_unknown.json()["total"] == 0


def test_global_audit_filters_by_action(app_client):
    _login(app_client, "admin3@co.com", "admin")
    AuditRepo().log(action="login", user_email="admin3@co.com")
    AuditRepo().log(action="delete_experiment", user_email="admin3@co.com")

    resp = app_client.get("/api/v1/audit", params={"action": "delete_experiment"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "delete_experiment"
