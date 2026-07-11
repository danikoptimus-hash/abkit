import ReactECharts from 'echarts-for-react'
import type { EChartsInstance } from 'echarts-for-react'
import type { CustomSeriesRenderItemAPI, CustomSeriesRenderItemParams, CustomSeriesRenderItemReturn } from 'echarts'
import { chartColors } from './theme'
import { formatPercentValue, tooltipBaseStyle } from './tooltip'

export interface ForestRow {
  label: string
  effectRelPct: number
  ciLoPct: number
  ciHiPct: number
  highlighted: boolean
  // Stage 1 (tooltips): extra "label: value" lines appended to the hover
  // tooltip below Effect/95% CI — neither is part of the visual encoding
  // (the error bar only draws effect + CI), and what's relevant differs by
  // caller: the main forest plot shows p-value, segment breakdowns show n
  // per group instead. A flexible list beats hardcoding one specific
  // field two different callers would use for two different things.
  extraTooltipLines?: string[]
}

function renderErrorBar(
  _params: CustomSeriesRenderItemParams,
  api: CustomSeriesRenderItemAPI,
): CustomSeriesRenderItemReturn {
  const categoryIndex = api.value(0) as number
  const lo = api.value(1) as number
  const hi = api.value(2) as number
  const point = api.value(3) as number
  const highlighted = api.value(4) === 1
  const color = highlighted ? chartColors.significantPositive : chartColors.notSignificant

  const loCoord = api.coord([lo, categoryIndex])
  const hiCoord = api.coord([hi, categoryIndex])
  const midCoord = api.coord([point, categoryIndex])
  const capHalf = 5

  return {
    type: 'group',
    children: [
      { type: 'line', shape: { x1: loCoord[0], y1: loCoord[1], x2: hiCoord[0], y2: hiCoord[1] }, style: { stroke: color, lineWidth: 2 } },
      { type: 'line', shape: { x1: loCoord[0], y1: loCoord[1] - capHalf, x2: loCoord[0], y2: loCoord[1] + capHalf }, style: { stroke: color, lineWidth: 2 } },
      { type: 'line', shape: { x1: hiCoord[0], y1: hiCoord[1] - capHalf, x2: hiCoord[0], y2: hiCoord[1] + capHalf }, style: { stroke: color, lineWidth: 2 } },
      { type: 'circle', shape: { cx: midCoord[0], cy: midCoord[1], r: 5 }, style: { fill: color } },
    ],
  }
}

export function ForestPlotChart({
  rows,
  title,
  onChartReady,
}: {
  rows: ForestRow[]
  title?: string
  // Stage 1 e2e coverage (item 1.4): lets a caller expose the live echarts
  // instance (e.g. on window, mirroring DistributionChart's
  // __abkitDistributionChart) — kept as a caller-supplied callback instead
  // of a hardcoded window global here, since this component is reused for
  // both the main forest plot and per-segment breakdowns and only the
  // former needs to be addressable from a test.
  onChartReady?: (instance: EChartsInstance) => void
}) {
  const labels = rows.map((r) => r.label)
  const data = rows.map((r, i) => [i, r.ciLoPct, r.ciHiPct, r.effectRelPct, r.highlighted ? 1 : 0])
  const height = Math.max(200, 60 * rows.length + 80)

  const option = {
    title: title ? { text: title, textStyle: { fontSize: 13 } } : undefined,
    // Stage 1: custom-series charts (this one draws its own error-bar
    // shapes via renderItem) get NO tooltip at all unless one is
    // explicitly wired up — bar/line series have a sane ECharts default,
    // custom ones don't. dataIndex maps straight back to `rows` (same
    // order data[] was built in), so the formatter just reads from there
    // instead of re-deriving anything from the plotted coordinates.
    tooltip: {
      trigger: 'item',
      ...tooltipBaseStyle,
      formatter: (params: { dataIndex: number }) => {
        const row = rows[params.dataIndex]
        if (!row) return ''
        const extra = (row.extraTooltipLines ?? []).map((line) => `${line}<br/>`).join('')
        return (
          `<b>${row.label}</b><br/>` +
          `Effect: ${formatPercentValue(row.effectRelPct)}<br/>` +
          `95% CI: [${formatPercentValue(row.ciLoPct)}, ${formatPercentValue(row.ciHiPct)}]<br/>` +
          extra
        )
      },
    },
    grid: { left: 220, right: 40, top: title ? 48 : 20, bottom: 32 },
    xAxis: {
      type: 'value',
      name: 'Effect, %',
      axisLine: { lineStyle: { color: chartColors.axisLine } },
      splitLine: { lineStyle: { color: chartColors.grid } },
    },
    yAxis: { type: 'category', data: labels, inverse: true, axisLine: { lineStyle: { color: chartColors.axisLine } } },
    series: [
      {
        type: 'custom',
        renderItem: renderErrorBar,
        encode: { x: [1, 2, 3], y: 0 },
        data,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: chartColors.axisLine },
          data: [{ xAxis: 0 }],
          label: { show: false },
        },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height }} onChartReady={onChartReady} />
}
