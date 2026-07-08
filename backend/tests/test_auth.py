"""R1 (REACT.md): логин/logout/me/change-password через HTTP + cookie, и
проверка, что роль ниже требуемой отклоняется (аналог
tests/test_jobs_permission_matrix.py, но на уровне backend.deps)."""

from __future__ import annotations

import pytest

from abkit.auth.passwords import hash_password
from abkit.db.repositories import UserRepo


def test_login_success_sets_cookie_and_returns_user(app_client):
    UserRepo().create(
        email="editor@co.com", name="Editor", password_hash=hash_password("pw12345"), role="editor"
    )
    resp = app_client.post("/api/v1/auth/login", json={"email": "editor@co.com", "password": "pw12345"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "editor@co.com"
    assert body["role"] == "editor"
    assert "abkit_session" in resp.cookies


def test_login_wrong_password_returns_401_unified_error_shape(app_client):
    UserRepo().create(
        email="viewer@co.com", name="V", password_hash=hash_password("pw12345"), role="viewer"
    )
    resp = app_client.post("/api/v1/auth/login", json={"email": "viewer@co.com", "password": "wrong"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "invalid_credentials"
    assert "message" in body["error"]


def test_me_without_cookie_is_401(app_client):
    resp = app_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_me_with_valid_session_returns_user(app_client):
    UserRepo().create(
        email="admin@co.com", name="A", password_hash=hash_password("pw12345"), role="admin"
    )
    app_client.post("/api/v1/auth/login", json={"email": "admin@co.com", "password": "pw12345"})
    resp = app_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_logout_clears_session(app_client):
    UserRepo().create(
        email="editor2@co.com", name="E", password_hash=hash_password("pw12345"), role="editor"
    )
    app_client.post("/api/v1/auth/login", json={"email": "editor2@co.com", "password": "pw12345"})
    resp = app_client.post("/api/v1/auth/logout")
    assert resp.status_code == 200

    me_resp = app_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401


def test_change_password_then_old_password_rejected_new_accepted(app_client):
    UserRepo().create(
        email="pw@co.com", name="P", password_hash=hash_password("oldpass123"), role="editor"
    )
    app_client.post("/api/v1/auth/login", json={"email": "pw@co.com", "password": "oldpass123"})
    resp = app_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "oldpass123", "new_password": "newpass456"},
    )
    assert resp.status_code == 200

    app_client.post("/api/v1/auth/logout")
    old_login = app_client.post("/api/v1/auth/login", json={"email": "pw@co.com", "password": "oldpass123"})
    assert old_login.status_code == 401
    new_login = app_client.post("/api/v1/auth/login", json={"email": "pw@co.com", "password": "newpass456"})
    assert new_login.status_code == 200


def test_change_password_wrong_old_password_400(app_client):
    UserRepo().create(
        email="pw2@co.com", name="P2", password_hash=hash_password("realpass123"), role="editor"
    )
    app_client.post("/api/v1/auth/login", json={"email": "pw2@co.com", "password": "realpass123"})
    resp = app_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrongpass", "new_password": "newpass456"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_password"


def test_openapi_schema_is_served(app_client):
    resp = app_client.get("/api/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "abkit API"


def test_health_endpoint_does_not_require_auth(app_client):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_require_min_role_blocks_below_threshold():
    from abkit.auth.guards import CurrentUser
    from backend.deps import require_min_role
    from backend.errors import APIError

    viewer = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="v@co.com", name="V", role="viewer")
    dep = require_min_role("editor")
    with pytest.raises(APIError) as exc_info:
        dep(viewer)
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "forbidden"


def test_require_min_role_allows_at_or_above_threshold():
    from abkit.auth.guards import CurrentUser
    from backend.deps import require_min_role

    editor = CurrentUser(id="22222222-2222-2222-2222-222222222222", email="e@co.com", name="E", role="editor")
    admin = CurrentUser(id="33333333-3333-3333-3333-333333333333", email="a@co.com", name="A", role="admin")
    dep = require_min_role("editor")
    assert dep(editor) is editor
    assert dep(admin) is admin
