"""Plotly-графики для отчетов: forest plot, распределения, кумулятивный лифт."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.stats.proportion import proportion_confint

from abkit.analysis.results import TestResult

_DESIGNED_COLOR = "#2E7D32"
_OTHER_COLOR = "#90A4AE"


def fig_to_html_div(fig: go.Figure, include_js: bool = False) -> str:
    """Рендерит figure в HTML-фрагмент. include_js=True встраивает plotly.js целиком
    (используется один раз на страницу для полностью офлайн-отчета)."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs="inline" if include_js else False,
        config={"displaylogo": False},
    )


def _forest_traces(
    labels: list[str],
    effects: list[float],
    lo: list[float],
    hi: list[float],
    designed: list[bool],
    extra_lines: list[str],
    is_pct: bool,
) -> go.Scatter:
    """extra_lines: one HTML-safe hover line per point beyond effect/CI —
    the p-value for the main forest plot, n per group for segment
    breakdowns (same "extra lines, caller decides what" design as the
    frontend's ForestRow.extraTooltipLines, for the same reason: what's
    relevant differs by caller, and there's no third field both need)."""
    colors = [_DESIGNED_COLOR if d else _OTHER_COLOR for d in designed]
    err_plus = [h - e for h, e in zip(hi, effects)]
    err_minus = [e - l for l, e in zip(lo, effects)]
    unit = "%" if is_pct else ""
    return go.Scatter(
        x=effects,
        y=labels,
        mode="markers",
        marker=dict(color=colors, size=11, symbol="diamond"),
        error_x=dict(type="data", symmetric=False, array=err_plus, arrayminus=err_minus),
        showlegend=False,
        customdata=list(zip(lo, hi, extra_lines)),
        hovertemplate=(
            "<b>%{y}</b><br>"
            f"Effect: %{{x:.2f}}{unit}<br>"
            f"95% CI: [%{{customdata[0]:.2f}}{unit}, %{{customdata[1]:.2f}}{unit}]<br>"
            "%{customdata[2]}"
            "<extra></extra>"
        ),
    )


def forest_plot(results: list[TestResult], value: str = "rel", title: str = "") -> go.Figure:
    """Forest plot по цепочкам методов: designed-цепочка выделена цветом, ноль — вертикаль."""
    labels = [f"{r.method} ({r.treatment_group})" for r in results]
    if value == "rel":
        effects = [r.effect_rel * 100 for r in results]
        lo = [r.ci_rel[0] * 100 for r in results]
        hi = [r.ci_rel[1] * 100 for r in results]
        x_title = "Effect, %"
    else:
        effects = [r.effect_abs for r in results]
        lo = [r.ci_abs[0] for r in results]
        hi = [r.ci_abs[1] for r in results]
        x_title = "Effect (abs.)"

    designed = [r.is_designed_method for r in results]
    extra_lines = [f"p-value: {r.p_value:.4f}" if r.p_value is not None else "p-value: —" for r in results]
    fig = go.Figure()
    fig.add_trace(_forest_traces(labels, effects, lo, hi, designed, extra_lines, is_pct=value == "rel"))
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        height=max(250, 70 * len(results) + 100),
        margin=dict(l=200),
    )
    return fig


def segment_forest_plot(segment_results: list[tuple[str, TestResult]], title: str = "") -> go.Figure:
    """Forest plot эффекта в разрезе страт (segment_results: [(stratum_name, TestResult)])."""
    labels = [f"{name}" for name, _r in segment_results]
    results = [r for _name, r in segment_results]
    designed = [False] * len(results)  # сегменты всегда exploratory
    effects = [r.effect_rel * 100 for r in results]
    lo = [r.ci_rel[0] * 100 for r in results]
    hi = [r.ci_rel[1] * 100 for r in results]
    extra_lines = [f"n: {', '.join(f'{k}={v}' for k, v in r.n.items())}" for r in results]

    fig = go.Figure()
    fig.add_trace(_forest_traces(labels, effects, lo, hi, designed, extra_lines, is_pct=True))
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=title,
        xaxis_title="Effect, %",
        height=max(250, 70 * len(results) + 100),
        margin=dict(l=200),
    )
    return fig


def _wilson_proportion_plot(
    control: pd.Series, treatment: pd.Series, metric_name: str, control_name: str, treat_name: str
) -> go.Figure:
    """Bar-chart долей с усами Wilson score interval — гистограмма непригодна для 0/1."""
    names = [control_name, treat_name]
    series_by_name = {control_name: control, treat_name: treatment}
    colors = {control_name: _OTHER_COLOR, treat_name: _DESIGNED_COLOR}

    props, err_plus, err_minus, texts, customdata = [], [], [], [], []
    for name in names:
        values = series_by_name[name].dropna()
        n = len(values)
        count = int(values.sum())
        p = count / n if n else 0.0
        lo, hi = proportion_confint(count, n, alpha=0.05, method="wilson") if n else (0.0, 0.0)
        props.append(p * 100)
        err_plus.append((hi - p) * 100)
        err_minus.append((p - lo) * 100)
        texts.append(f"{p * 100:.1f}% ± {(hi - lo) / 2 * 100:.1f}%")
        customdata.append((lo * 100, hi * 100, n))

    fig = go.Figure(
        go.Bar(
            x=names,
            y=props,
            error_y=dict(type="data", symmetric=False, array=err_plus, arrayminus=err_minus),
            text=texts,
            textposition="outside",
            marker_color=[colors[n] for n in names],
            customdata=customdata,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Rate: %{y:.2f}%<br>"
                "95% CI: [%{customdata[0]:.2f}%, %{customdata[1]:.2f}%]<br>"
                "n: %{customdata[2]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"Rate of {metric_name} (binary): {control_name} vs {treat_name}" if metric_name else "Rate (binary)",
        yaxis_title="Rate, %",
        showlegend=False,
        height=450,
    )
    return fig


def p99_clip_stats(combined: pd.Series) -> tuple[float, int, float]:
    """(P99-порог, число наблюдений выше него, их доля в %) — используется и
    distribution_plot(clip_to_p99=True) для сужения оси, и вызывающей стороной
    (app.py/report.py) для подписи под графиком "N наблюдений (X%) выше
    порога..."."""
    n = len(combined)
    if n == 0:
        return 0.0, 0, 0.0
    threshold = float(combined.quantile(0.99))
    n_above = int((combined > threshold).sum())
    return threshold, n_above, n_above / n * 100


def distribution_plot(
    control: pd.Series,
    treatment: pd.Series,
    metric_name: str = "",
    metric_type: str = "continuous",
    control_name: str = "control",
    treat_name: str = "treatment",
    trim_threshold: float | None = None,
    clip_to_p99: bool = True,
) -> go.Figure:
    """Распределение метрики по группам — вид зависит от типа метрики:
    binary -> bar-chart долей с Wilson-ДИ (гистограмма непригодна для 0/1);
    continuous/ratio -> наложенные гистограммы + ECDF (для ratio исключаются
    юзеры с нулевым знаменателем — они уже NaN в values на этот момент).

    clip_to_p99: визуальное ограничение оси X 99-м перцентилем объединенных
    данных (сам расчет/анализ эту опцию не видит и не меняется — только вид
    графика). Наблюдения выше P99 попадают в последний бин гистограммы
    (clip(upper=...) перед построением); ECDF считается по ПОЛНЫМ данным, но
    ось X визуально обрезается тем же порогом. Подпись под графиком с числом
    отсеченных наблюдений строится вызывающей стороной через p99_clip_stats()
    на тех же исходных (control_clean+treatment_clean) данных."""
    if metric_type == "binary":
        return _wilson_proportion_plot(control, treatment, metric_name, control_name, treat_name)

    control_clean = control.dropna()
    treatment_clean = treatment.dropna()
    n_excluded = (len(control) - len(control_clean)) + (len(treatment) - len(treatment_clean))
    n = len(control_clean) + len(treatment_clean)
    nbins = max(5, min(50, int(np.sqrt(max(n, 1)))))

    all_values = pd.concat([control_clean, treatment_clean]) if n else pd.Series(dtype=float)

    p99_threshold: float | None = None
    if clip_to_p99 and n:
        threshold, n_above, _pct_above = p99_clip_stats(all_values)
        if n_above > 0:
            p99_threshold = threshold

    hist_control = control_clean.clip(upper=p99_threshold) if p99_threshold is not None else control_clean
    hist_treatment = (
        treatment_clean.clip(upper=p99_threshold) if p99_threshold is not None else treatment_clean
    )

    fig = make_subplots(rows=2, cols=1, subplot_titles=["Distribution", "ECDF"])

    # go.Histogram bins client-side from raw x-values, so per-bin
    # customdata/hovertemplate can't be attached — pre-compute shared bin
    # edges via np.histogram (mirrors backend/chart_data.py::_histogram_pair)
    # and render as go.Bar instead, giving hover exact control over bin
    # range/count/% share, matching the frontend chart's tooltip content.
    hist_all = pd.concat([hist_control, hist_treatment]) if n else pd.Series(dtype=float)
    if len(hist_all):
        bin_edges = np.histogram_bin_edges(hist_all.to_numpy(), bins=nbins)
    else:
        bin_edges = np.linspace(0.0, 1.0, nbins + 1)
    bin_labels = [f"{bin_edges[i]:.4g}–{bin_edges[i + 1]:.4g}" for i in range(len(bin_edges) - 1)]

    for name, series in ((control_name, hist_control), (treat_name, hist_treatment)):
        values = series.to_numpy()
        counts, _ = np.histogram(values, bins=bin_edges)
        total = len(values)
        pct = counts / total * 100 if total else np.zeros_like(counts, dtype=float)
        bin_width = np.diff(bin_edges)
        density = counts / (total * bin_width) if total else np.zeros_like(counts, dtype=float)
        fig.add_trace(
            go.Bar(
                x=bin_labels,
                y=density,
                name=name,
                opacity=0.55,
                customdata=np.stack([counts, pct], axis=-1),
                hovertemplate=(
                    f"<b>%{{x}}</b><br>{name}: %{{customdata[0]:.0f}} (%{{customdata[1]:.1f}}%)<extra></extra>"
                ),
            ),
            row=1, col=1,
        )
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(type="category", row=1, col=1)

    for name, series in ((control_name, control_clean), (treat_name, treatment_clean)):
        values = np.sort(series.to_numpy())
        if len(values) == 0:
            continue
        ecdf = np.arange(1, len(values) + 1) / len(values)
        fig.add_trace(
            go.Scatter(
                x=values,
                y=ecdf,
                mode="lines",
                name=f"{name} ECDF",
                hovertemplate=(
                    f"<b>{name}</b><br>Value: %{{x:,.2f}}<br>Cumulative: %{{y:.1%}}<extra></extra>"
                ),
            ),
            row=2, col=1,
        )

    if p99_threshold is not None:
        # Row 1 is now a category axis over pre-clipped bin labels (bins were
        # built from hist_control/hist_treatment, already clipped above) —
        # no numeric range to set there. Row 2 (ECDF) is still numeric over
        # the full unclipped data, so it still needs the explicit range.
        x_min = float(all_values.min())
        fig.update_xaxes(range=[x_min, p99_threshold], row=2, col=1)

    if trim_threshold is not None:
        # Row 1 switched to a category axis (bin labels) above — a numeric
        # vline position no longer lands correctly, so mark the bin the
        # threshold falls into by its category label instead.
        bin_idx = min(int(np.searchsorted(bin_edges, trim_threshold, side="right")) - 1, len(bin_labels) - 1)
        if 0 <= bin_idx < len(bin_labels):
            fig.add_vline(x=bin_labels[bin_idx], line_dash="dot", line_color="red", row=1, col=1)

    title = f"Distribution of {metric_name} ({metric_type})" if metric_name else "Distribution"
    if metric_type == "ratio" and n_excluded > 0:
        title += f" — {n_excluded} users excluded (zero denominator)"

    skew = float(all_values.skew()) if len(all_values) > 2 else 0.0
    if skew > 3 and len(all_values) and all_values.min() > 0:
        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    x=1.0, y=1.15, xanchor="right",
                    buttons=[
                        dict(label="Linear X scale", method="relayout", args=[{"xaxis.type": "linear"}]),
                        dict(label="Log X scale (skewed)", method="relayout", args=[{"xaxis.type": "log"}]),
                    ],
                )
            ]
        )

    fig.update_layout(title=title, height=650)
    return fig


def cumulative_lift_plot(daily: pd.DataFrame, title: str = "") -> go.Figure:
    """Кумулятивный лифт с ДИ по дням. daily: колонки date, effect_rel, ci_lower,
    ci_upper — все как ДОЛИ (0.02 = 2%), тот же конвеншн, что и everywhere else
    (TestResult.effect_rel, effects на строках 45/73 выше) — *100 только здесь,
    на границе отрисовки."""
    fig = go.Figure()
    dates = list(daily["date"])
    ci_upper_pct = [v * 100 for v in daily["ci_upper"]]
    ci_lower_pct = [v * 100 for v in daily["ci_lower"]]
    effect_rel_pct = [v * 100 for v in daily["effect_rel"]]
    fig.add_trace(
        go.Scatter(
            x=dates + dates[::-1],
            y=ci_upper_pct + ci_lower_pct[::-1],
            fill="toself",
            fillcolor="rgba(46,125,50,0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="CI",
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=effect_rel_pct,
            mode="lines+markers",
            name="Cumulative lift, %",
            customdata=list(zip(ci_lower_pct, ci_upper_pct)),
            hovertemplate=(
                "<b>%{x}</b><br>Lift: %{y:.1f}%<br>"
                "95% CI: [%{customdata[0]:.1f}%, %{customdata[1]:.1f}%]<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Lift, %")
    return fig
