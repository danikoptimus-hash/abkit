"""Структурированное логирование в stdout (DOCKER.md §6). Формат по умолчанию —
JSON: {"ts", "level", "logger", "msg", ...произвольные поля}. ABKIT_LOG_FORMAT=
text — человекочитаемый вывод для отладки. ABKIT_LOG_LEVEL — INFO по умолчанию.

INFO — старт/финиш/длительность ключевых операций (design/analyze/validate),
WARNING — деградации (SRM-провалы и т.п., пишутся вызывающей стороной),
ERROR — исключения (exc_info=True добавляет traceback). Пароли/токены/сырые
пользовательские данные никогда не передаются в лог-вызовы (см. abkit/jobs.py,
abkit/auth/service.py — логируются email и метаданные, не содержимое)."""

from __future__ import annotations

import os
import sys

import structlog

_configured = False


def configure_logging() -> None:
    """Идемпотентно (кроме явного сброса) настраивает structlog. Безопасно
    вызывать многократно (например, на каждый Streamlit rerun) — no-op после
    первого вызова в рамках процесса."""
    global _configured
    if _configured:
        return

    level_name = os.environ.get("ABKIT_LOG_LEVEL", "INFO").upper()
    level = getattr(__import__("logging"), level_name, 20)
    fmt = os.environ.get("ABKIT_LOG_FORMAT", "json").lower()

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.EventRenamer("msg"),
    ]
    if fmt == "text":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str = "abkit"):
    configure_logging()
    return structlog.get_logger(name).bind(logger=name)


def reset_logging() -> None:
    """Только для тестов — позволяет перенастроить логирование при смене
    ABKIT_LOG_FORMAT/ABKIT_LOG_LEVEL между тест-кейсами."""
    global _configured
    _configured = False
