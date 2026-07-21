"""Single source of truth for building experiment download filenames that
include the design dataset's name: `<experiment>_<dataset>_<suffix>` (or
`<experiment>_<suffix>` when there's no dataset to name).

The dataset NAME is resolved at request time by the backend (see
backend/routers/experiments.py::_download_dataset_segment — it reads the
current design/reference dataset link, so a rename is reflected and a deleted
dataset falls back to the frozen analysis filename). This module only holds the
pure string operations (sanitize + assemble), so they can be unit-tested
without a DB and reused by every download path. A trivial TS mirror
(frontend/src/lib/downloadName.ts) assembles the same pattern for the two
client-side blob downloads, consuming the ALREADY-sanitized segment the backend
exposes on ExperimentDetail — sanitization lives here alone.
"""

from __future__ import annotations

import re

# Filesystem-unsafe characters + whitespace, collapsed to a single "_".
# `\s` matches unicode whitespace; Cyrillic/other unicode LETTERS are left
# as-is (browsers and modern filesystems handle them — no transliteration).
_UNSAFE = re.compile(r'[\s/\\:*?"<>|]+')
# Trailing data-file extensions stripped so the segment is the dataset's NAME,
# not "sales.csv" wedged mid-filename ("exp_sales_report.html", not
# "exp_sales.csv_report.html").
_DATA_EXTENSIONS = (".parquet", ".csv", ".tsv", ".json", ".xlsx", ".xls")
DATASET_SEGMENT_MAX = 60


def sanitize_dataset_segment(name: str | None) -> str | None:
    """Turn a free-text dataset name into a safe filename segment, or None when
    there's nothing usable. Strips a trailing data extension, replaces unsafe
    chars/whitespace with "_", collapses repeats, trims, caps at 60 chars."""
    if not name:
        return None
    stem = name.strip()
    low = stem.lower()
    for ext in _DATA_EXTENSIONS:
        if low.endswith(ext):
            stem = stem[: -len(ext)]
            break
    s = _UNSAFE.sub("_", stem)
    s = re.sub(r"_+", "_", s).strip("_")
    s = s[:DATASET_SEGMENT_MAX].strip("_")
    return s or None


def build_experiment_download_name(
    experiment_name: str, dataset_segment: str | None, suffix: str
) -> str:
    """`<experiment>_<dataset>_<suffix>`, or `<experiment>_<suffix>` when
    dataset_segment is falsy. dataset_segment must already be sanitized
    (sanitize_dataset_segment)."""
    if dataset_segment:
        return f"{experiment_name}_{dataset_segment}_{suffix}"
    return f"{experiment_name}_{suffix}"
