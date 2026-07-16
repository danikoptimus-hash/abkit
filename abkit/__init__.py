"""abkit — фреймворк для дизайна и анализа A/B тестов."""

import os
from pathlib import Path

from abkit.config import DesignConfig, MetricConfig
from abkit.experiment import DesignError, Experiment

__all__ = ["DesignConfig", "MetricConfig", "Experiment", "DesignError", "PRODUCT_NAME"]


def _read_version(*, env: dict | None = None, sha_file: Path | None = None) -> str:
    """Single source of truth = the release git tag (item 8, audit-details+
    package — CLAUDE.md "Правило: релизный процесс"). `ABKIT_VERSION` is set
    by docker/Dockerfile's ARG->ENV on a tagged CI build (build-and-push job,
    .github/workflows/ci.yml — derives it from the pushed `vX.Y.Z` tag, so
    the value here is already the plain "X.Y.Z" the tag names, no further
    parsing needed). A LOCAL build (no explicit --build-arg, the Dockerfile's
    own default) leaves ABKIT_VERSION at its literal "dev" default — falls
    through to /app/GIT_SHA, computed automatically at image-build time by
    the Dockerfile's `version` stage (git rev-parse --short HEAD against the
    build context's own .git — no developer action needed, this Just Works
    on plain `docker compose up -d --build`). A bare non-Docker run (pytest,
    local editable install) has neither — "dev" plain, since it's not what
    gets shown to real users (only the Docker-built About page/report header
    are). env/sha_file are injectable purely for tests/test_version.py —
    real callers (module load below) always use the real environ/path."""
    env = env if env is not None else os.environ
    sha_file = sha_file if sha_file is not None else Path(__file__).resolve().parent.parent / "GIT_SHA"

    env_version = env.get("ABKIT_VERSION", "dev")
    if env_version != "dev":
        return env_version.lstrip("v")

    if sha_file.exists():
        sha = sha_file.read_text().strip()
        if sha and sha != "unknown":
            return f"dev ({sha})"

    return "dev"


__version__ = _read_version()

# Единый источник имени продукта (UX-пакет, ребрендинг) — README.md, HTML-отчеты
# (abkit/viz/report.py), CLI (cli.py/cli_admin.py --help), backend (Settings >
# About, FastAPI app title), frontend (frontend/src/branding.ts — TS не может
# импортировать Python, синхронизировать вручную при изменении). "abkit" (в
# нижнем регистре) остается техническим идентификатором пакета/репозитория/
# путей — не переименовывается.
PRODUCT_NAME = "ABSet"
