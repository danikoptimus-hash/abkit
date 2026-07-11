import ReactECharts from 'echarts-for-react'
import { chartColors } from './theme'
import { formatPercentValue, tooltipBaseStyle } from './tooltip'
import type { DailyLiftPoint } from '../pages/experiment/analyzeTypes'

export function CumulativeLiftChart({ points }: { points: DailyLiftPoint[] }) {
  const dates = points.map((p) => p.date)
  const lift = points.map((p) => p.effect_rel * 100)
  const ciLower = points.map((p) => p.ci_lower * 100)
  const ciUpper = points.map((p) => p.ci_upper * 100)
  const band = ciUpper.map((hi, i) => hi - ciLower[i])

  const option = {
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    // Stage 1: no tooltip at all previously — the CI band series are
    // `silent: true` (so dragging/hover doesn't fight the fill), which
    // also excludes them from an axis-trigger tooltip's params on their
    // own; only the visible "Cumulative lift, %" line shows up, and its
    // own dataIndex is enough to pull the matching CI bounds back out of
    // the closures above (cleaner than reconstructing them from the
    // stacked/invisible series' values).
    tooltip: {
      trigger: 'axis',
      ...tooltipBaseStyle,
      formatter: (params: { seriesName: string; dataIndex: number }[]) => {
        const liftParam = params.find((p) => p.seriesName === 'Cumulative lift, %')
        if (!liftParam) return ''
        const i = liftParam.dataIndex
        return (
          `<b>${dates[i]}</b><br/>` +
          `Lift: ${formatPercentValue(lift[i])}<br/>` +
          `95% CI: [${formatPercentValue(ciLower[i])}, ${formatPercentValue(ciUpper[i])}]`
        )
      },
    },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: chartColors.axisLine } } },
    yAxis: {
      type: 'value', name: 'Lift, %',
      axisLine: { lineStyle: { color: chartColors.axisLine } },
      splitLine: { lineStyle: { color: chartColors.grid } },
    },
    series: [
      {
        name: 'CI (lower bound)', type: 'line', data: ciLower, showSymbol: false,
        lineStyle: { opacity: 0 }, stack: 'ci', silent: true,
      },
      {
        name: 'CI', type: 'line', data: band, showSymbol: false,
        lineStyle: { opacity: 0 }, areaStyle: { color: chartColors.significantPositive, opacity: 0.15 },
        stack: 'ci', silent: true,
      },
      {
        name: 'Cumulative lift, %', type: 'line', data: lift, showSymbol: true,
        lineStyle: { color: chartColors.significantPositive }, itemStyle: { color: chartColors.significantPositive },
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { type: 'dashed', color: chartColors.axisLine },
          data: [{ yAxis: 0 }],
          label: { show: false },
        },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height: 320 }} />
}
