"""POST /admin/users/bulk-set-active (item 7, audit-details+ package):
bulk Deactivate/Activate on Admin > Users, with self-protection (can't
deactivate your own account or the last active admin)."""

from __future__ import annotations

from abkit.auth.guards import CurrentUser
from abkit.auth.passwords import hash_password
from abkit.db.repositories import AuditRepo, UserRepo


def _login(app_client, email: str, role: str = "admin") -> str:
    user_id = UserRepo().create(email=email, first_name="U", password_hash=hash_password("pw12345"), role=role)
    resp = app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})
    assert resp.status_code == 200
    return str(user_id)


def test_bulk_set_active_requires_admin(app_client):
    _login(app_client, "bulkactive_editor@co.com", role="editor")
    resp = app_client.post("/api/v1/admin/users/bulk-set-active", json={"user_ids": ["whatever"], "is_active": False})
    assert resp.status_code == 403


def test_bulk_deactivate_two_others_succeeds_with_audit(app_client):
    _login(app_client, "bulkactive_admin1@co.com")
    b_id = UserRepo().create(
        email="bulkactive_b@co.com", first_name="B", password_hash=hash_password("pw12345"), role="viewer",
    )
    c_id = UserRepo().create(
        email="bulkactive_c@co.com", first_name="C", password_hash=hash_password("pw12345"), role="viewer",
    )

    resp = app_client.post(
        "/api/v1/admin/users/bulk-set-active",
        json={"user_ids": [str(b_id), str(c_id)], "is_active": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["updated"]) == sorted([str(b_id), str(c_id)])
    assert body["skipped"] == []
    assert UserRepo().get_by_id(b_id).is_active is False
    assert UserRepo().get_by_id(c_id).is_active is False

    audit = AuditRepo().list_recent(limit=10, action="user.active_change")
    audited_ids = {a.object_id for a in audit}
    assert str(b_id) in audited_ids
    assert str(c_id) in audited_ids


def test_bulk_deactivate_skips_self_but_deactivates_the_other(app_client):
    """Mirrors the Playwright test in item 7: select two, deactivate,
    verify self-skip."""
    admin_id = _login(app_client, "bulkactive_self@co.com")
    other_id = UserRepo().create(
        email="bulkactive_other@co.com", first_name="O", password_hash=hash_password("pw12345"), role="viewer",
    )

    resp = app_client.post(
        "/api/v1/admin/users/bulk-set-active",
        json={"user_ids": [admin_id, str(other_id)], "is_active": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated"] == [str(other_id)]
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["user_id"] == admin_id
    assert body["skipped"][0]["reason"] == "cannot deactivate your own account"

    assert UserRepo().get_by_id(UserRepo().get_by_email("bulkactive_self@co.com").id).is_active is True
    assert UserRepo().get_by_id(other_id).is_active is False


def test_bulk_set_active_reports_not_found(app_client):
    _login(app_client, "bulkactive_notfound@co.com")
    resp = app_client.post(
        "/api/v1/admin/users/bulk-set-active",
        json={"user_ids": ["00000000-0000-0000-0000-000000000000"], "is_active": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == []
    assert body["skipped"][0]["reason"] == "not found"


def test_bulk_activate_never_hits_self_or_last_admin_guards(app_client):
    admin_id = _login(app_client, "bulkactive_activate@co.com")
    other_id = UserRepo().create(
        email="bulkactive_activate_other@co.com", first_name="O", password_hash=hash_password("pw12345"),
        role="viewer",
    )
    UserRepo().set_active(other_id, False)

    resp = app_client.post(
        "/api/v1/admin/users/bulk-set-active",
        json={"user_ids": [admin_id, str(other_id)], "is_active": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["updated"]) == sorted([admin_id, str(other_id)])
    assert body["skipped"] == []


def test_admin_bulk_set_active_skips_the_last_active_admin(app_client):
    """Direct service-level test (app_client only configures the DB env —
    ABKIT_MODE=db, ABKIT_SECRET_KEY — no HTTP calls below): the
    last-active-admin guard defends a race the API itself can never
    reproduce, since abkit.auth.service.current_user_from_token re-checks
    is_active from the DB on EVERY request (a deactivated admin's session
    stops authenticating immediately, before they could submit a bulk
    request as themselves). This exercises admin_bulk_set_active() directly
    with a CurrentUser constructed independently of a live session, so the
    guard itself — not just its unreachability via HTTP — is verified."""
    from abkit.auth.service import admin_bulk_set_active

    admin_a = UserRepo().create(
        email="bulkactive_race_a@co.com", first_name="A", password_hash=hash_password("pw12345"), role="admin",
    )
    admin_b = UserRepo().create(
        email="bulkactive_race_b@co.com", first_name="B", password_hash=hash_password("pw12345"), role="admin",
    )
    # Simulates A's account being deactivated out-of-band (e.g. by another
    # admin) after A's CurrentUser was already resolved for this request —
    # B is now the ONLY active admin in the DB.
    UserRepo().set_active(admin_a, False)

    acting_as_a = CurrentUser(id=str(admin_a), email="bulkactive_race_a@co.com", name="A", role="admin")
    updated, skipped = admin_bulk_set_active(acting_as_a, user_ids=[str(admin_b)], is_active=False)

    assert updated == []
    assert skipped == [(str(admin_b), "cannot deactivate the last active admin")]
    assert UserRepo().get_by_id(admin_b).is_active is True
