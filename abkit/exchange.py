"""Экспорт/импорт эксперимента одним zip-архивом (пакет export/import).

Здесь — только ЧТЕНИЕ/ЗАПИСЬ самого архива (bytes <-> структуры), без единого
обращения к БД: оркестрация (репозитории, права, audit_log) живет в
`abkit/jobs.py::run_export_experiment`/`run_import_experiment`. Тот же раздел
ответственности, что у `abkit/flow_images.py` (чистая валидация/санитизация) и
jobs.py (БД) — модуль тестируется без testcontainers, а jobs.py против реальной
БД.

Формат архива (`<experiment-name>_export.zip`):

    manifest.json          format_version / app version / exported_at
    experiment.json        config, блоки, теги, статусы, ссылки на датасеты
    assignments.parquet    только для ABSet-сплита (у external-сплита
                           назначений нет по построению — см. ниже)
    analysis_results.json  все прогоны анализа (verdicts, построчные методы)
    reports/               design_report.html, report.html (если сгенерированы)
    datasets/<sha256>.parquet   только с "Include dataset snapshots"

`format_version` — целое, растет при НЕСОВМЕСТИМОМ изменении формата. Импорт
архива с версией НОВЕЕ поддерживаемой — осознанный отказ с внятным текстом
(старый экземпляр не может знать, что за поля появились в новом формате и что
их отсутствие молча испортит), а СТАРЫЕ версии читаются как есть — новые поля
всегда добавляются опциональными.

Ссылки на датасеты: по умолчанию (`include_datasets=False`) в архиве лежат
только имя + `sha256` содержимого, не сами данные — типовой сценарий "перенести
тест между инстансами, смотрящими в одно хранилище" не должен таскать за собой
гигабайты parquet. Снапшоты (`datasets/`) нужны для миграции МЕЖДУ разными
инстансами, где датасета физически нет.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# Растить ТОЛЬКО при несовместимом изменении формата (удаление/переименование
# поля, смена смысла существующего). Добавление нового опционального поля —
# не повод: старый импорт его просто не прочитает.
EXPORT_FORMAT_VERSION = 1

MANIFEST_FILE = "manifest.json"
EXPERIMENT_FILE = "experiment.json"
ASSIGNMENTS_FILE = "assignments.parquet"
ANALYSIS_RESULTS_FILE = "analysis_results.json"
REPORTS_DIR = "reports"
DATASETS_DIR = "datasets"

# Что вообще может лежать в reports/ — белый список, а не "все, что нашлось".
# Импорт пишет эти файлы на диск, поэтому чужое имя в архиве не должно
# приводить к появлению постороннего файла в папке эксперимента, даже
# безобидного: _safe_member ловит traversal, а это — все остальное.
# Совпадает по значению с backend/schemas/experiments.py::REPORT_FILENAMES, но
# это не дубль одной константы: та описывает, что отдает HTTP-роут
# /reports/{report_name}, эта — что признает формат архива. Совпадение
# сегодняшних значений — следствие, а не связь.
REPORT_FILENAMES = ("design_report.html", "report.html")


class ExperimentExchangeError(Exception):
    """Архив нечитаем/не тот. Роутер маппит в 400 (как FlowImageError), а не
    глобальным хендлером — ошибка узкая, к другим эндпоинтам отношения не
    имеет."""


class UnsupportedFormatVersionError(ExperimentExchangeError):
    """format_version новее, чем понимает этот экземпляр ABSet."""


@dataclass
class ArchiveContents:
    """Разобранный архив. `assignments is None` — файла в архиве не было
    (external-сплит либо тест без назначений), это НЕ то же самое, что пустой
    DataFrame."""

    manifest: dict[str, Any]
    experiment: dict[str, Any]
    assignments: pd.DataFrame | None = None
    analysis_results: list[dict[str, Any]] = field(default_factory=list)
    # filename -> байты; только базовые имена, без путей (см. _safe_member).
    reports: dict[str, bytes] = field(default_factory=dict)
    # sha256 -> parquet-байты датасета.
    dataset_snapshots: dict[str, bytes] = field(default_factory=dict)


def dataframe_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _safe_member(name: str) -> str:
    """Имя файла внутри архива -> безопасное базовое имя.

    Архив приходит от пользователя, а его содержимое пишется на диск
    (reports/), поэтому zip-slip (`../../etc/cron.d/x`, абсолютные пути,
    backslash-разделители из Windows-архиваторов) — не гипотетический риск, а
    ровно то, от чего эта функция защищает: `zipfile` СОХРАНЯЕТ такие имена
    как есть (проверено — `namelist()` возвращает `reports/../../../etc/passwd`
    дословно), нормализовать их за нас никто не будет. Полагаться на то, что
    архив создан нашим же экспортом, нельзя: эндпоинт принимает любой
    загруженный файл.

    Traversal — именно ОШИБКА, а не повод молча взять basename: честный
    экспорт таких имен не производит никогда, так что `..` в пути означает
    либо битый, либо враждебный архив, и импортировать из него "то, что
    удалось разобрать" — значит скрыть это от пользователя.
    """
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or any(part == ".." for part in normalized.split("/")):
        raise ExperimentExchangeError(f"Archive contains an unsafe file name: '{name}'")
    base = normalized.rsplit("/", 1)[-1]
    if not base or base == "." or ":" in base:
        raise ExperimentExchangeError(f"Archive contains an unsafe file name: '{name}'")
    return base


def write_archive(
    *,
    manifest: dict[str, Any],
    experiment: dict[str, Any],
    assignments: pd.DataFrame | None = None,
    analysis_results: list[dict[str, Any]] | None = None,
    reports: dict[str, bytes] | None = None,
    dataset_snapshots: dict[str, bytes] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_FILE, json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        zf.writestr(EXPERIMENT_FILE, json.dumps(experiment, indent=2, ensure_ascii=False, default=str))
        # Пустой DataFrame не пишем: "файла нет" — то же самое, что "назначений
        # нет", а лишний parquet с нулем строк только путает при разборе архива
        # руками.
        if assignments is not None and not assignments.empty:
            zf.writestr(ASSIGNMENTS_FILE, dataframe_to_parquet_bytes(assignments))
        zf.writestr(
            ANALYSIS_RESULTS_FILE,
            json.dumps(analysis_results or [], indent=2, ensure_ascii=False, default=str),
        )
        for filename, raw in (reports or {}).items():
            zf.writestr(f"{REPORTS_DIR}/{_safe_member(filename)}", raw)
        for sha256, raw in (dataset_snapshots or {}).items():
            zf.writestr(f"{DATASETS_DIR}/{_safe_member(sha256)}.parquet", raw)
    return buffer.getvalue()


def read_archive(raw: bytes) -> ArchiveContents:
    """Разбирает и ВАЛИДИРУЕТ архив целиком до того, как вызывающий код тронет
    БД: любой отказ (не zip, нет манифеста, версия новее) должен случиться
    раньше, чем будет создана хоть одна строка."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as e:
        raise ExperimentExchangeError("File is not a valid zip archive") from e

    with zf:
        names = set(zf.namelist())

        if MANIFEST_FILE not in names:
            raise ExperimentExchangeError(
                f"Archive has no {MANIFEST_FILE} — this does not look like an "
                f"experiment export produced by ABSet"
            )
        manifest = _read_json(zf, MANIFEST_FILE)
        if not isinstance(manifest, dict):
            raise ExperimentExchangeError(f"{MANIFEST_FILE} must be a JSON object")

        version = manifest.get("format_version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise ExperimentExchangeError(f"{MANIFEST_FILE} has no valid integer format_version")
        if version > EXPORT_FORMAT_VERSION:
            raise UnsupportedFormatVersionError(
                f"This archive uses export format version {version}, but this ABSet "
                f"supports up to version {EXPORT_FORMAT_VERSION}. Upgrade ABSet to import it."
            )

        if EXPERIMENT_FILE not in names:
            raise ExperimentExchangeError(f"Archive has no {EXPERIMENT_FILE}")
        experiment = _read_json(zf, EXPERIMENT_FILE)
        if not isinstance(experiment, dict):
            raise ExperimentExchangeError(f"{EXPERIMENT_FILE} must be a JSON object")

        assignments = None
        if ASSIGNMENTS_FILE in names:
            try:
                assignments = pd.read_parquet(io.BytesIO(zf.read(ASSIGNMENTS_FILE)))
            except Exception as e:
                raise ExperimentExchangeError(f"{ASSIGNMENTS_FILE} is unreadable: {e}") from e

        analysis_results: list[dict[str, Any]] = []
        if ANALYSIS_RESULTS_FILE in names:
            parsed = _read_json(zf, ANALYSIS_RESULTS_FILE)
            if not isinstance(parsed, list):
                raise ExperimentExchangeError(f"{ANALYSIS_RESULTS_FILE} must be a JSON array")
            analysis_results = parsed

        reports: dict[str, bytes] = {}
        dataset_snapshots: dict[str, bytes] = {}
        for name in sorted(names):
            if name.endswith("/"):
                continue
            if name.startswith(f"{REPORTS_DIR}/"):
                member = _safe_member(name)
                if member not in REPORT_FILENAMES:
                    raise ExperimentExchangeError(
                        f"Archive carries an unexpected report file: '{member}'"
                    )
                reports[member] = zf.read(name)
            elif name.startswith(f"{DATASETS_DIR}/") and name.endswith(".parquet"):
                sha256 = _safe_member(name)[: -len(".parquet")]
                dataset_snapshots[sha256] = zf.read(name)

    return ArchiveContents(
        manifest=manifest,
        experiment=experiment,
        assignments=assignments,
        analysis_results=analysis_results,
        reports=reports,
        dataset_snapshots=dataset_snapshots,
    )


def _read_json(zf: zipfile.ZipFile, member: str) -> Any:
    try:
        return json.loads(zf.read(member))
    except json.JSONDecodeError as e:
        raise ExperimentExchangeError(f"{member} is not valid JSON: {e}") from e
