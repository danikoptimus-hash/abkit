"""Feature (dataset name in downloads): the pure filename-builder — sanitizing
free-text dataset names into safe filename segments and assembling
<experiment>_<dataset>_<suffix>."""

from __future__ import annotations

from abkit.download_names import (
    DATASET_SEGMENT_MAX,
    build_experiment_download_name,
    sanitize_dataset_segment,
)


def test_strips_known_data_extension():
    assert sanitize_dataset_segment("sales.csv") == "sales"
    assert sanitize_dataset_segment("q3_report.parquet") == "q3_report"
    assert sanitize_dataset_segment("data.tsv") == "data"


def test_replaces_spaces_and_unsafe_chars_with_underscore():
    assert sanitize_dataset_segment("monthly report.csv") == "monthly_report"
    assert sanitize_dataset_segment('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_collapses_repeats_and_trims():
    assert sanitize_dataset_segment("a   b//c") == "a_b_c"
    assert sanitize_dataset_segment("__weird__name__") == "weird_name"
    assert sanitize_dataset_segment("  spaced  ") == "spaced"


def test_caps_at_60_chars():
    seg = sanitize_dataset_segment("x" * 100)
    assert seg is not None
    assert len(seg) == DATASET_SEGMENT_MAX == 60


def test_cyrillic_and_unicode_letters_kept_as_is():
    # No transliteration — letters preserved, only spaces/unsafe replaced.
    assert sanitize_dataset_segment("Тест данные.csv") == "Тест_данные"
    assert sanitize_dataset_segment("ventes françaises") == "ventes_françaises"


def test_empty_or_all_unsafe_returns_none():
    assert sanitize_dataset_segment("") is None
    assert sanitize_dataset_segment(None) is None
    assert sanitize_dataset_segment("///") is None
    assert sanitize_dataset_segment("   .csv") is None


def test_build_with_and_without_segment():
    assert build_experiment_download_name("exp", "sales", "design_report.html") == "exp_sales_design_report.html"
    assert build_experiment_download_name("exp", None, "design_report.html") == "exp_design_report.html"
    assert build_experiment_download_name("exp", "", "report.html") == "exp_report.html"
    assert build_experiment_download_name("Тест", "данные", "export.zip") == "Тест_данные_export.zip"
