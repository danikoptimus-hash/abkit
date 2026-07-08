"""Печатает OpenAPI-схему backend'а в stdout — источник для
openapi-typescript (frontend/package.json, скрипт gen:api). Не требует
поднятого сервера/БД: create_app() строит роуты, ABKIT_SECRET_KEY нужен
только для прохождения lifespan при реальном старте, не для схемы."""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    # Windows: stdout по умолчанию в cp1252, схема содержит русские docstring'и
    # (UnicodeEncodeError без этого) — тот же класс проблемы, что и с rich-
    # консолью в cli.py (см. память проекта: legacy_windows=False + utf-8).
    sys.stdout.reconfigure(encoding="utf-8")

    os.environ.setdefault("ABKIT_SECRET_KEY", "dummy-for-schema-export")
    from backend.main import create_app

    json.dump(create_app().openapi(), sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
