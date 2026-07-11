import { colors } from '../theme/tokens'

// Stage 1 (chart tooltips everywhere): shared base style so every chart's
// hover tooltip looks the same (background/border/font from the theme)
// without each component re-declaring it — spread this into the chart's
// own `tooltip` option, then add a chart-specific `formatter`.
export const tooltipBaseStyle = {
  backgroundColor: '#FFFFFF',
  borderColor: colors.border,
  borderWidth: 1,
  textStyle: {
    color: colors.text,
    fontSize: 12,
    fontFamily: 'Inter, -apple-system, Helvetica, Arial, sans-serif',
  },
  extraCssText: 'box-shadow: 0 2px 8px rgba(0,0,0,0.12); border-radius: 4px; padding: 8px 12px;',
}

// Number formatting matching DetailedResultsTable.tsx's conventions, so a
// value reads the same whether you're looking at the table or hovering the
// chart: percent with a fixed decimal count + "%", plain numbers with
// thousands separators (money/large counts — e.g. a monetary metric's bin
// edges in the thousands).
export function formatPercent(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`
}

// Some chart data is already pre-multiplied to percent scale before it
// reaches the component (e.g. ForestPlotChart's ForestRow.effectRelPct) —
// using formatPercent on those would silently double-multiply (the exact
// bug class the cumulative lift chart had). Use this one instead when the
// number you have is already "5.7" meaning 5.7%, not "0.057".
export function formatPercentValue(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`
}

export function formatCiPercent(lo: number, hi: number, digits = 2): string {
  return `[${formatPercent(lo, digits)}, ${formatPercent(hi, digits)}]`
}

export function formatNumber(value: number, digits = 2): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: digits })
}

export function formatPValue(value: number): string {
  return value.toFixed(4)
}
