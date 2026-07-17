"""abkit/exchange.py — чтение/запись архива без БД (модуль по построению
чистый, testcontainers здесь не нужен, в отличие от backend/tests/
test_experiment_export_import.py, где тот же формат гоняется через API)."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from abkit.exchange import (
    EXPORT_FORMAT_VERSION,
    ExperimentExchangeError,
    UnsupportedFormatVersionError,
    read_archive,
    write_archive,
)


def _manifest(**overrides):
    base = {"format_version": EXPORT_FORMAT_VERSION, "app_version": "v9.9.9"}
    base.update(overrides)
    return base


def _archive(**overrides) -> bytes:
    kwargs = {
        "manifest": _manifest(),
        "experiment": {"name": "exp", "config": {"unit_col": "user_id"}},
    }
    kwargs.update(overrides)
    return write_archive(**kwargs)


def test_round_trip_preserves_every_section():
    assignments = pd.DataFrame(
        {
            "unit_id": ["u1", "u2"],
            "group": ["control", "treatment"],
            "stratum": ["a", "b"],
            "assigned_at": pd.to_datetime(["2026-01-01", "2026-01-02"]),
        }
    )
    raw = _archive(
        assignments=assignments,
        analysis_results=[{"results": {"verdict": "ship"}}],
        reports={"design_report.html": b"<html>design</html>"},
        dataset_snapshots={"abc123": b"not-really-parquet"},
    )

    contents = read_archive(raw)
    assert contents.manifest["format_version"] == EXPORT_FORMAT_VERSION
    assert contents.experiment["name"] == "exp"
    assert contents.analysis_results == [{"results": {"verdict": "ship"}}]
    assert contents.reports == {"design_report.html": b"<html>design</html>"}
    assert contents.dataset_snapshots == {"abc123": b"not-really-parquet"}
    assert contents.assignments is not None
    assert contents.assignments["unit_id"].tolist() == ["u1", "u2"]
    assert contents.assignments["group"].tolist() == ["control", "treatment"]


def test_empty_assignments_are_omitted_rather_than_written_empty():
    """external-сплит: назначений нет по построению. "Файла нет" и "файл с
    нулем строк" не должны быть двумя разными состояниями."""
    raw = _archive(assignments=pd.DataFrame(columns=["unit_id", "group"]))
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "assignments.parquet" not in zf.namelist()
    assert read_archive(raw).assignments is None


def test_newer_format_version_is_rejected():
    raw = _archive(manifest=_manifest(format_version=EXPORT_FORMAT_VERSION + 1))
    with pytest.raises(UnsupportedFormatVersionError) as e:
        read_archive(raw)
    assert "Upgrade ABSet" in str(e.value)


def test_same_or_older_format_version_is_accepted():
    """Старые архивы читаются как есть — новые поля всегда опциональны."""
    assert read_archive(_archive(manifest=_manifest(format_version=EXPORT_FORMAT_VERSION))) is not None


@pytest.mark.parametrize("bad", [None, "1", 1.5, True])
def test_non_integer_format_version_is_rejected(bad):
    raw = _archive(manifest=_manifest(format_version=bad))
    with pytest.raises(ExperimentExchangeError, match="format_version"):
        read_archive(raw)


def test_not_a_zip_is_rejected():
    with pytest.raises(ExperimentExchangeError, match="not a valid zip"):
        read_archive(b"plain bytes")


def test_missing_manifest_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("experiment.json", json.dumps({"name": "x"}))
    with pytest.raises(ExperimentExchangeError, match="manifest.json"):
        read_archive(buffer.getvalue())


def test_missing_experiment_json_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(_manifest()))
    with pytest.raises(ExperimentExchangeError, match="experiment.json"):
        read_archive(buffer.getvalue())


def test_malformed_json_is_rejected_as_a_bad_archive_not_a_crash():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", "{not json")
    with pytest.raises(ExperimentExchangeError, match="not valid JSON"):
        read_archive(buffer.getvalue())


@pytest.mark.parametrize(
    "evil",
    [
        "reports/../../../etc/passwd",
        "reports/..\\..\\evil.html",
    ],
)
def test_zip_slip_member_is_rejected(evil):
    """Архив приходит от пользователя, а reports/ пишутся на диск — путь с ../
    обязан отлетать при РАЗБОРЕ, а не при записи. zipfile такие имена не
    нормализует (namelist() отдает их дословно), так что это единственное
    место, где они ловятся."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(_manifest()))
        zf.writestr("experiment.json", json.dumps({"name": "x"}))
        zf.writestr(evil, b"pwned")
    with pytest.raises(ExperimentExchangeError, match="unsafe file name"):
        read_archive(buffer.getvalue())


def test_unexpected_report_file_is_rejected():
    """Не traversal, но и не наш файл: импорт пишет reports/ на диск, так что
    посторонним именам там взяться неоткуда."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(_manifest()))
        zf.writestr("experiment.json", json.dumps({"name": "x"}))
        zf.writestr("reports/evil.html", b"<script>")
    with pytest.raises(ExperimentExchangeError, match="unexpected report file"):
        read_archive(buffer.getvalue())


def test_unrecognized_members_are_ignored_not_fatal():
    """Посторонние записи (README архиватора, абсолютный путь, не попадающий в
    наш префикс) — просто не наши: игнорируем, а не валим импорт. Записать на
    диск их все равно нечему: пишутся только reports/ из белого списка."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(_manifest()))
        zf.writestr("experiment.json", json.dumps({"name": "x"}))
        zf.writestr("README.txt", b"created by some archiver")
        zf.writestr("/reports/design_report.html", b"absolute, not our namespace")

    contents = read_archive(buffer.getvalue())
    assert contents.experiment["name"] == "x"
    assert contents.reports == {}


def test_report_members_are_flattened_to_base_names():
    raw = _archive(reports={"design_report.html": b"x"})
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "reports/design_report.html" in zf.namelist()
    assert list(read_archive(raw).reports) == ["design_report.html"]
