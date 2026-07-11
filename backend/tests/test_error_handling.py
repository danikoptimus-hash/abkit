"""Samples-download follow-up: internal_error without any way to correlate
it to a log line was useless for diagnosis (see backend/errors.py's
_handle_unexpected_error) — this locks in the error_id contract: present in
both the user-facing message (so it's visible in a UI toast without the
frontend needing to read `details`) and in `details.error_id` (for anything
that does want structured access)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from abkit.auth.passwords import hash_password
from abkit.db.repositories import ExperimentRepo, UserRepo


def _login(app_client, email="editor@co.com", role="editor"):
    UserRepo().create(email=email, first_name="E", password_hash=hash_password("pw12345"), role=role)
    app_client.post("/api/v1/auth/login", json={"email": email, "password": "pw12345"})


@pytest.fixture
def lenient_app_client(db_url, monkeypatch):
    """Same as the shared app_client fixture (backend/tests/conftest.py),
    except raise_server_exceptions=False — needed ONLY here: Starlette's
    TestClient re-raises an unhandled exception into the test process by
    default even though the server already sent a real 500 response (our
    registered Exception handler runs either way), which is exactly the
    response this test needs to inspect rather than have raised at it."""
    monkeypatch.setenv("ABKIT_SECRET_KEY", "a-real-generated-secret-for-backend-tests")
    monkeypatch.setenv("ABKIT_MODE", "db")

    from backend.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_unhandled_exception_returns_error_id_in_message_and_details(lenient_app_client, monkeypatch):
    app_client = lenient_app_client

    def _boom(self, name):
        raise RuntimeError("deliberately broken for this test")

    monkeypatch.setattr(ExperimentRepo, "get_by_name", _boom)
    _login(app_client)

    resp = app_client.get("/api/v1/experiments/anything")
    assert resp.status_code == 500
    body = resp.json()["error"]
    assert body["code"] == "internal_error"

    match = re.search(r"\(ref: ([0-9a-f]{8})\)", body["message"])
    assert match, f"expected a (ref: <8 hex chars>) suffix in {body['message']!r}"
    assert body["details"]["error_id"] == match.group(1)
