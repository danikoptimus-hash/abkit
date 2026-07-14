// Item 2 (explicit method selection): mirrors abkit/experiment.py's
// _METHOD_ID_CHAIN_BUILDERS / recommended_method_id — manually kept in sync
// (same duplication pattern as VERDICT_LABELS etc. elsewhere in this
// codebase, noted there too). The display strings below must match
// method_display_name()'s hardcoded per-step labels EXACTLY (e.g. "Welch
// t-test", "CUPED + Welch t-test") — they're not just UI labels, they're
// also how "designed vs manually selected" gets reconstructed later
// (compare a completed result's r.method against the recommended id's
// label) without a separate stored flag that could drift out of sync.
export type MetricType = 'continuous' | 'binary' | 'ratio'

export const METHOD_DISPLAY_NAMES: Record<string, string> = {
  welch: 'Welch t-test',
  cuped_welch: 'CUPED + Welch t-test',
  mann_whitney: 'Mann-Whitney (Hodges-Lehmann)',
  bootstrap_bca: 'Bootstrap (bca)',
  remove_outliers_welch: 'RemoveOutliers + Welch t-test',
  ztest: 'Z-test of proportions',
  chi_square: 'Chi-square test',
  bootstrap_percentile: 'Bootstrap (percentile)',
  delta_method: 'Delta method (ratio)',
}

export interface MethodOption {
  id: string
  label: string
  recommended: boolean
  requiresPreCol: boolean
}

// The type/config-based default — same rule abkit/experiment.py's
// _default_steps_for_metric() encodes as actual Step instances.
export function recommendedMethodId(type: MetricType, hasPreCol: boolean): string {
  if (type === 'binary') return hasPreCol ? 'cuped_welch' : 'ztest'
  if (type === 'ratio') return 'delta_method'
  return hasPreCol ? 'cuped_welch' : 'welch'
}

// Item 2.2: only methods applicable to the metric's type, in the spec's
// stated order; a method that requires a pre-period column is omitted
// entirely (not shown disabled) when the metric has none.
export function methodOptions(type: MetricType, hasPreCol: boolean): MethodOption[] {
  const recommended = recommendedMethodId(type, hasPreCol)
  const opt = (id: string, requiresPreCol = false): MethodOption => ({
    id, label: METHOD_DISPLAY_NAMES[id], recommended: id === recommended, requiresPreCol,
  })
  if (type === 'binary') {
    const opts = [opt('ztest'), opt('chi_square'), opt('bootstrap_percentile')]
    if (hasPreCol) opts.splice(1, 0, opt('cuped_welch', true))
    return opts
  }
  if (type === 'ratio') {
    // No alternatives exist yet (abkit/experiment.py::compare_methods_chains
    // returns [] for ratio too) — a single, always-recommended option.
    return [opt('delta_method')]
  }
  const opts = [opt('welch'), opt('mann_whitney'), opt('bootstrap_bca'), opt('remove_outliers_welch')]
  if (hasPreCol) opts.splice(1, 0, opt('cuped_welch', true))
  return opts
}

// Item 2.3: "designed vs manually selected" is derived, not stored — a
// completed TestResultOut's .method (the pipeline's own display string) is
// compared against the recommended id's label for that metric. Works
// identically right after a run and on a cold page load (Results tab),
// since it only needs data already in results.json + the experiment config.
export function isManuallySelected(actualMethod: string, type: MetricType, hasPreCol: boolean): boolean {
  const recommendedLabel = METHOD_DISPLAY_NAMES[recommendedMethodId(type, hasPreCol)]
  return actualMethod !== recommendedLabel
}
