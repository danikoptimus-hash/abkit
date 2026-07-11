import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from abkit.viz.plots import distribution_plot, p99_clip_stats


def _trace_types(fig: go.Figure) -> list[str]:
    return [trace.type for trace in fig.data]


def test_binary_metric_uses_bar_chart_not_histogram(tmp_path=None):
    rng = np.random.default_rng(1)
    control = pd.Series(rng.binomial(1, 0.10, size=2000))
    treatment = pd.Series(rng.binomial(1, 0.13, size=2000))

    fig = distribution_plot(
        control, treatment, metric_name="clicks", metric_type="binary",
        control_name="control", treat_name="treatment",
    )

    assert _trace_types(fig) == ["bar"]
    assert "(binary)" in fig.layout.title.text
    # ECDF не должен фигурировать в легенде для binary (его тут просто нет)
    assert not any("ECDF" in (name or "") for name in [t.name for t in fig.data])


def test_binary_bar_has_wilson_error_bars_and_percentage_labels():
    control = pd.Series([1] * 124 + [0] * 876)  # 12.4%
    treatment = pd.Series([1] * 150 + [0] * 850)  # 15%

    fig = distribution_plot(
        control, treatment, metric_name="clicks", metric_type="binary",
        control_name="control", treat_name="treatment",
    )
    bar = fig.data[0]
    assert bar.error_y is not None
    assert bar.error_y.array is not None
    assert "%" in bar.text[0]
    assert "±" in bar.text[0]
    assert bar.y[0] == pytest.approx(12.4, abs=0.05)


def test_continuous_metric_uses_histogram_and_ecdf():
    rng = np.random.default_rng(2)
    control = pd.Series(rng.normal(100, 20, size=1000))
    treatment = pd.Series(rng.normal(105, 20, size=1000))

    fig = distribution_plot(
        control, treatment, metric_name="revenue", metric_type="continuous",
        control_name="control", treat_name="treatment",
    )

    types = _trace_types(fig)
    # Histogram switched to precomputed go.Bar traces (Stage 1: per-bin
    # tooltips need customdata, which go.Histogram's client-side auto-binning
    # can't attach) — two bars (control/treatment) + two ECDF scatter lines.
    assert types.count("bar") == 2
    assert types.count("scatter") == 2
    assert "(continuous)" in fig.layout.title.text
    names = [t.name for t in fig.data]
    assert any("ECDF" in n for n in names)


def test_continuous_auto_bins_scale_with_sqrt_n():
    rng = np.random.default_rng(3)
    small = pd.Series(rng.normal(0, 1, size=25))
    large = pd.Series(rng.normal(0, 1, size=1000))

    fig_small = distribution_plot(small, small, metric_type="continuous")
    fig_large = distribution_plot(large, large, metric_type="continuous")

    # Bin count == number of category labels on the (now bar-based) histogram trace
    nbins_small = len(fig_small.data[0].x)
    nbins_large = len(fig_large.data[0].x)
    assert nbins_small < nbins_large
    assert nbins_large <= 50


def test_skewed_continuous_offers_log_scale_toggle():
    rng = np.random.default_rng(4)
    # сильно перекошенное вправо распределение (лог-нормальное)
    skewed = pd.Series(rng.lognormal(mean=0, sigma=2.0, size=2000))

    fig = distribution_plot(skewed, skewed, metric_type="continuous")
    assert fig.layout.updatemenus is not None and len(fig.layout.updatemenus) > 0


def test_non_skewed_continuous_has_no_log_scale_toggle():
    rng = np.random.default_rng(5)
    normal = pd.Series(rng.normal(100, 20, size=2000))

    fig = distribution_plot(normal, normal, metric_type="continuous")
    assert not fig.layout.updatemenus


def test_ratio_metric_excludes_zero_denominator_users_and_notes_it():
    rng = np.random.default_rng(6)
    n = 500
    values = rng.normal(2, 0.5, size=n)
    # первые 50 - "исключенные" (эмулируем NaN, как это делает build_metric_context
    # для den=0 через values.replace(0, np.nan))
    values[:50] = np.nan
    control = pd.Series(values)
    treatment = pd.Series(rng.normal(2.2, 0.5, size=n))

    fig = distribution_plot(
        control, treatment, metric_name="revenue_per_session", metric_type="ratio",
        control_name="control", treat_name="treatment",
    )

    assert "users excluded" in fig.layout.title.text
    assert "50" in fig.layout.title.text


def test_ratio_metric_no_footnote_when_no_zero_denominator():
    rng = np.random.default_rng(7)
    control = pd.Series(rng.normal(2, 0.5, size=200))
    treatment = pd.Series(rng.normal(2.1, 0.5, size=200))

    fig = distribution_plot(
        control, treatment, metric_name="revenue_per_session", metric_type="ratio",
    )
    assert "excluded" not in fig.layout.title.text


def test_p99_clip_stats_computes_threshold_and_share_above():
    combined = pd.Series(list(range(1, 101)))  # 1..100, P99 = 99.01-ish
    threshold, n_above, pct_above = p99_clip_stats(combined)
    assert threshold == pytest.approx(combined.quantile(0.99))
    assert n_above == int((combined > threshold).sum())
    assert pct_above == pytest.approx(n_above / 100 * 100)


def test_p99_clip_stats_empty_series_returns_zeros():
    assert p99_clip_stats(pd.Series(dtype=float)) == (0.0, 0, 0.0)


def test_distribution_plot_clips_x_axis_to_p99_by_default():
    rng = np.random.default_rng(8)
    # нормальные данные + жирный выброс-хвост, чтобы P99 был заметно ниже максимума
    control = pd.Series(np.concatenate([rng.normal(100, 10, size=950), rng.uniform(500, 1000, size=50)]))
    treatment = pd.Series(np.concatenate([rng.normal(100, 10, size=950), rng.uniform(500, 1000, size=50)]))

    fig = distribution_plot(control, treatment, metric_type="continuous")

    combined = pd.concat([control, treatment])
    threshold, n_above, _pct = p99_clip_stats(combined)
    assert n_above > 0
    # Row 1 (histogram) is now a category axis over bin labels built from
    # already-clip()-ped data — no numeric xaxis.range to assert on there
    # (see abkit/viz/plots.py::distribution_plot comment); only row 2
    # (ECDF, still numeric) keeps the explicit range.
    ecdf_range = fig.layout.xaxis2.range
    assert ecdf_range[1] == pytest.approx(threshold)
    # гистограмма при этом строится по clip()-нутым данным (выбросы собраны в
    # последний бин, а не обрублены совсем) — верхняя граница последнего бина == threshold
    last_bin_upper = float(fig.data[0].x[-1].split("–")[1])
    assert last_bin_upper == pytest.approx(threshold, rel=1e-3)
    # ни одно наблюдение не потеряно — просто зажато в последний бин
    total_control = sum(c for c, _pct in fig.data[0].customdata)
    assert total_control == len(control)
    # ECDF же считается по ПОЛНЫМ данным (только ось обрезана визуально)
    ecdf_trace = next(t for t in fig.data if t.type == "scatter")
    assert max(ecdf_trace.x) > threshold


def test_distribution_plot_clip_to_p99_false_shows_full_range():
    rng = np.random.default_rng(9)
    control = pd.Series(np.concatenate([rng.normal(100, 10, size=950), rng.uniform(500, 1000, size=50)]))
    treatment = pd.Series(np.concatenate([rng.normal(100, 10, size=950), rng.uniform(500, 1000, size=50)]))

    fig = distribution_plot(control, treatment, metric_type="continuous", clip_to_p99=False)

    assert fig.layout.xaxis.range is None
    last_bin_upper = float(fig.data[0].x[-1].split("–")[1])
    assert last_bin_upper > 400  # исходные выбросы не обрезаны
