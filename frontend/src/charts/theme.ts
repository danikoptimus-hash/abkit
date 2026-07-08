import { colors } from '../theme/tokens'

// Глобальная палитра ECharts (FRONTEND.md §5.1): значимый эффект — зеленый,
// незначимый — серый, сетка светло-серая. Ни одного оранжевого/красного для
// "обычных" состояний — красный (colors.error) используется ТОЛЬКО для
// значимого отрицательного эффекта, не для generic acccent.
export const chartColors = {
  significantPositive: colors.success,
  significantNegative: colors.error,
  notSignificant: '#999999',
  grid: '#EFEFEF',
  axisLine: colors.border,
  axisLabel: colors.tableHeaderText,
} as const

export const echartsBaseOption = {
  color: [chartColors.notSignificant, chartColors.significantPositive],
  textStyle: { fontFamily: 'Inter, -apple-system, Helvetica, Arial, sans-serif' },
  grid: { borderColor: chartColors.grid },
}
