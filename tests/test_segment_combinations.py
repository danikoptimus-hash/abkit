"""Segment combinations (segment-combinations package §1) — crossing 2+
columns into one cut, dedup by column-set, underpowered cells, and the
invariant that declaring segments never touches the verdict/primary results.
Core-level (Experiment.analyze) coverage — file store, no testcontainers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from abkit.config import DesignConfig, MetricConfig
from abkit.experiment import Experiment


def _cfg(name="seg_combo", **overrides) -> DesignConfig:
    fields = dict(
        name=name,
        unit_col="",
        groups={"control": 0.5, "treatment": 0.5},
        metrics=[MetricConfig(name="conversion", type="binary", role="primary")],
        split_source="external",
        isolation="off",
    )
    fields.update(overrides)
    return DesignConfig(**fields)


def _data(rng, *, per_cell=80):
    rows = []
    combos = [
        ("US", "ios", 0.10, 0.30), ("US", "android", 0.10, 0.28),
        ("UK", "ios", 0.10, 0.11), ("UK", "android", 0.10, 0.12),
    ]
    for country, plat, cp, tp in combos:
        for _ in range(per_cell):
            rows.append({"variant": "A", "conversion": int(rng.binomial(1, cp)),
                         "country": country, "platform": plat})
            rows.append({"variant": "B", "conversion": int(rng.binomial(1, tp)),
                         "country": country, "platform": plat})
    return pd.DataFrame(rows)


def _analyze(tmp_path, data, **kwargs):
    exp = Experiment.design_external(_cfg(), experiments_dir=Path(tmp_path))
    return exp.analyze(
        data, correction="none", group_column="variant",
        group_mapping={"A": "control", "B": "treatment"}, **kwargs,
    )


def test_two_column_combination_computed(tmp_path):
    rng = np.random.default_rng(0)
    res = _analyze(tmp_path, _data(rng), segment_combinations=[["country", "platform"]])
    by = res.context["segment_results_by_dimension"]
    assert "country × platform" in by
    assert res.context["combination_segment_dimensions"] == ["country × platform"]
    cells = {name for name, _ in by["country × platform"]["conversion"]["treatment"]}
    assert cells == {"US|ios", "US|android", "UK|ios", "UK|android"}


def test_three_column_combination_computed(tmp_path):
    rng = np.random.default_rng(1)
    df = _data(rng)
    # Random (group-independent) so the 3-way cells aren't confounded with the
    # A/B alternation — otherwise each cell holds only one group.
    df["device"] = rng.choice(["new", "old"], size=len(df))
    res = _analyze(tmp_path, df, segment_combinations=[["country", "platform", "device"]])
    by = res.context["segment_results_by_dimension"]
    assert "country × platform × device" in by


def test_single_column_via_segment_columns(tmp_path):
    rng = np.random.default_rng(2)
    res = _analyze(tmp_path, _data(rng), segment_columns=["country"])
    assert "country" in res.context["segment_results_by_dimension"]


def test_combination_dedup_by_column_set(tmp_path):
    rng = np.random.default_rng(3)
    # country × platform and platform × country are the SAME cut.
    res = _analyze(tmp_path, _data(rng),
                   segment_combinations=[["country", "platform"], ["platform", "country"]])
    combos = res.context["combination_segment_dimensions"]
    assert len(combos) == 1


def test_underpowered_cells_flagged_in_chart_data(tmp_path):
    from backend.chart_data import build_chart_data

    rng = np.random.default_rng(4)
    # 80 users/group per cell < 100 → every cell underpowered.
    res = _analyze(tmp_path, _data(rng, per_cell=80), segment_combinations=[["country", "platform"]])
    cd = build_chart_data(res)
    cells = cd["metrics"]["conversion"]["segments_by_dimension"]["country × platform"]["treatment"]
    assert all(c["underpowered"] for c in cells)
    assert cd["combination_dimensions"] == ["country × platform"]


def test_powered_cells_not_flagged(tmp_path):
    from backend.chart_data import build_chart_data

    rng = np.random.default_rng(5)
    # 150 users/group per cell (>= 100) → not underpowered.
    res = _analyze(tmp_path, _data(rng, per_cell=150), segment_combinations=[["country", "platform"]])
    cd = build_chart_data(res)
    cells = cd["metrics"]["conversion"]["segments_by_dimension"]["country × platform"]["treatment"]
    assert not any(c["underpowered"] for c in cells)


def test_declaring_segments_does_not_change_verdict_or_primary_results(tmp_path):
    """Segments must never touch the decision path — the primary designed-method
    result is byte-identical with and without a declared combination."""
    rng = np.random.default_rng(6)
    data = _data(rng)

    def primary(res):
        r = next(r for r in res.results if r.is_designed_method and r.role == "primary")
        return (r.effect_abs, r.effect_rel, r.p_value, tuple(r.ci_rel))

    baseline = _analyze(tmp_path / "a", data)
    with_segments = _analyze(
        tmp_path / "b", data,
        segment_columns=["country"], segment_combinations=[["country", "platform"]],
    )
    assert primary(baseline) == primary(with_segments)


def test_combination_missing_column_degrades(tmp_path):
    rng = np.random.default_rng(7)
    res = _analyze(tmp_path, _data(rng), segment_combinations=[["country", "nonexistent"]])
    assert "country × nonexistent" not in res.context["segment_results_by_dimension"]
    assert any("nonexistent" in w for w in res.global_warnings)
