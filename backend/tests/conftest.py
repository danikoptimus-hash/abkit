"""Фикстуры backend-тестов. db_url/postgres_url — из корневого conftest.py
(общие с tests/, testcontainers либо TEST_DATABASE_URL — см. DOCKER.md §12)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(db_url, monkeypatch):
    monkeypatch.setenv("ABKIT_SECRET_KEY", "a-real-generated-secret-for-backend-tests")

    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client
