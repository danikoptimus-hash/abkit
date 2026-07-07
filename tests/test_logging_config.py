"""abkit/logging_config.py — DOCKER.md §6: JSON по умолчанию (ts/level/logger/
msg + произвольные поля), ABKIT_LOG_FORMAT=text для читаемого вывода."""

import json

import pytest

from abkit.logging_config import get_logger, reset_logging


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    reset_logging()
    yield
    reset_logging()


def test_json_format_produces_valid_json_lines(monkeypatch, capsys):
    monkeypatch.setenv("ABKIT_LOG_FORMAT", "json")
    log = get_logger("abkit.test")
    log.info("design.start", user="a@co.com", experiment="exp1", n_rows=100)

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["msg"] == "design.start"
    assert payload["level"] == "info"
    assert payload["logger"] == "abkit.test"
    assert "ts" in payload
    assert payload["user"] == "a@co.com"
    assert payload["experiment"] == "exp1"
    assert payload["n_rows"] == 100


def test_json_format_renders_exception_traceback(monkeypatch, capsys):
    monkeypatch.setenv("ABKIT_LOG_FORMAT", "json")
    log = get_logger("abkit.test")
    try:
        raise ValueError("boom")
    except ValueError:
        log.error("design.failed", experiment="exp1", exc_info=True)

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["level"] == "error"
    assert "ValueError: boom" in payload["exception"]


def test_text_format_does_not_crash_and_is_not_json(monkeypatch, capsys):
    monkeypatch.setenv("ABKIT_LOG_FORMAT", "text")
    log = get_logger("abkit.test")
    log.info("design.start", user="a@co.com")

    out = capsys.readouterr().out.strip()
    assert "design.start" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_log_call_sites_never_reference_secret_variables():
    """Регрессионная защита (DOCKER.md §6.1: "в логи не должны попадать пароли,
    токены, сырые пользовательские данные"): статически проверяем каждый вызов
    log.info/warning/error в jobs.py и auth/service.py — ни один аргумент не
    должен ссылаться на переменные с паролями/токенами."""
    import ast
    import inspect

    import abkit.auth.service as service_module
    import abkit.jobs as jobs_module

    forbidden_substrings = ("password", "token", "secret", "generated")

    for module in (jobs_module, service_module):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("info", "warning", "error", "debug")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "log"
            ):
                continue
            call_src = ast.unparse(node)
            for bad in forbidden_substrings:
                assert bad not in call_src.lower(), (
                    f"{module.__name__}: log-вызов похоже ссылается на секрет "
                    f"('{bad}'): {call_src}"
                )
