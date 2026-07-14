from abkit.analysis.results import AnalysisResults, TestResult


def _make_result(p_value, effect_abs=5.0, **overrides):
    defaults = dict(
        metric="revenue",
        method="WelchTTest",
        effect_abs=effect_abs,
        effect_rel=0.05,
        ci_abs=(1.0, 9.0),
        ci_rel=(0.01, 0.09),
        p_value=p_value,
        p_value_adjusted=None,
        n={"control": 100, "treatment": 100},
        n_removed={},
        variance_reduction=None,
        warnings=[],
        is_designed_method=True,
        treatment_group="treatment",
    )
    defaults.update(overrides)
    return TestResult(**defaults)


# Item 2.4: a design with alpha=0.01 and a p-value of 0.03 must verdict "no
# effect" — 0.03 < 0.05 (the old hardcoded default every verdict/
# detailed-rows call used before this package) would have shown
# significant, but 0.03 > 0.01 (the experiment's actual configured alpha)
# correctly does not. These are unit-level checks on AnalysisResults
# itself; abkit/viz/report.py and the frontend's analyzeTypes.ts::verdict()
# now both pass config.alpha through to these same methods (see
# tests/test_viz_report.py for the report-level wiring).
def test_verdict_respects_configured_alpha_not_hardcoded_005():
    results = AnalysisResults([_make_result(p_value=0.03)])
    assert results.verdict("revenue", alpha=0.01) == "no_effect_detected"
    assert results.verdict("revenue", alpha=0.05) == "significant_positive"


def test_verdicts_bulk_respects_alpha():
    results = AnalysisResults([_make_result(p_value=0.03)])
    assert results.verdicts(alpha=0.01)[("revenue", "treatment")] == "no_effect_detected"
    assert results.verdicts(alpha=0.05)[("revenue", "treatment")] == "significant_positive"


def test_detailed_rows_verdict_respects_alpha():
    results = AnalysisResults([_make_result(p_value=0.03)])
    rows_strict = results.detailed_rows("control", alpha=0.01)
    rows_loose = results.detailed_rows("control", alpha=0.05)
    assert rows_strict[0]["verdict"] == "no_effect_detected"
    assert rows_loose[0]["verdict"] == "significant_positive"


def test_detailed_display_rows_verdict_respects_alpha():
    results = AnalysisResults([_make_result(p_value=0.03)])
    display_strict = results.detailed_display_rows("control", alpha=0.01)
    display_loose = results.detailed_display_rows("control", alpha=0.05)
    assert display_strict[0]["Verdict"] == "no_effect_detected"
    assert display_loose[0]["Verdict"] == "significant_positive"


# Item 3.4: a row with no variance-reduction mechanic (variance_reduction is
# None) keeps the "—" placeholder rather than a misleading 0%/blank value.
def test_detailed_rows_variance_reduction_placeholder_when_none():
    results = AnalysisResults([_make_result(p_value=0.03, method="Welch t-test", variance_reduction=None)])
    row = results.detailed_rows("control")[0]
    assert row["variance_reduction"] == "—"


# Item 3 (variance reduction technique labels): each variance-reduction
# mechanic gets its own label, inferred from the method's display string
# (method_display_name()'s prefix chain) — a regression guard for the
# "PostStratification" (raw class name) vs "Post-stratification" (actual
# display string) mismatch found while wiring this up.
def test_detailed_rows_variance_reduction_technique_labels():
    results = AnalysisResults(
        [
            _make_result(p_value=0.03, method="CUPED + Welch t-test", variance_reduction=0.142),
            _make_result(p_value=0.03, method="Post-stratification", variance_reduction=0.2),
            _make_result(p_value=0.03, method="RemoveOutliers + Welch t-test", variance_reduction=0.37),
        ]
    )
    rows = {r["method"]: r["variance_reduction"] for r in results.detailed_rows("control")}
    assert rows["CUPED + Welch t-test"] == "CUPED (14.2%)"
    assert rows["Post-stratification"] == "PostStrat (20.0%)"
    assert rows["RemoveOutliers + Welch t-test"] == "Outlier removal (37.0%)"
