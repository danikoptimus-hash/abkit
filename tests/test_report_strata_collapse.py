"""§3: the analysis-report strata balance table collapses (JS-free
details/summary) when it has > 12 strata; <= 12 renders expanded. The summary
line is always present."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from abkit.config import DesignConfig, MetricConfig
from abkit.experiment import Experiment


def _report_html(tmp_path, n_strata: int) -> str:
    cfg = DesignConfig(
        name=f"collapse_{n_strata}",
        unit_col="",
        groups={"control": 0.5, "treatment": 0.5},
        metrics=[MetricConfig(name="conversion", type="binary", role="primary")],
        split_source="external",
        isolation="off",
        strata=["country"],
    )
    exp = Experiment.design_external(cfg, experiments_dir=Path(tmp_path))
    rng = np.random.default_rng(n_strata)
    rows = []
    for i in range(n_strata):
        country = f"C{i:02d}"
        for _ in range(40):  # >= min_stratum_size so no _other_ collapse
            rows.append({"variant": "A", "conversion": int(rng.binomial(1, 0.2)), "country": country})
            rows.append({"variant": "B", "conversion": int(rng.binomial(1, 0.2)), "country": country})
    data = pd.DataFrame(rows)
    res = exp.analyze(
        data, correction="none", group_column="variant",
        group_mapping={"A": "control", "B": "treatment"},
    )
    return res.report().read_text(encoding="utf-8")


def test_balance_expanded_with_11_strata(tmp_path):
    html = _report_html(tmp_path, 11)
    assert "section-strata-balance" in html
    assert "11 strata · balance chi-square" in html
    assert 'class="strata-balance-details" open>' in html


def test_balance_collapsed_with_13_strata(tmp_path):
    html = _report_html(tmp_path, 13)
    assert "13 strata · balance chi-square" in html
    # Collapsed by default: the details element has no `open` attribute.
    assert 'class="strata-balance-details">' in html
    assert 'class="strata-balance-details" open>' not in html
