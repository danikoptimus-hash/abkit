// TS mirror of abkit/segments.py — the segment-cut cardinality guard, applied
// live at selection time (before running). Kept as pure functions (no DOM) so
// it's unit-tested under vitest, same split as lib/share.ts.

export const SEGMENT_WARN_CELLS = 30
export const SEGMENT_MAX_CELLS = 200
export const UNDERPOWERED_MIN_N_PER_GROUP = 100

export type SegmentCardinalityStatus = 'ok' | 'warn' | 'refuse'

// Cell count of a cut = product of its columns' distinct-value counts.
export function combinationCellCount(cols: string[], cardinalities: Record<string, number>): number {
  return cols.reduce((acc, c) => acc * Math.max(1, cardinalities[c] ?? 1), 1)
}

export function segmentCardinalityStatus(nCells: number): SegmentCardinalityStatus {
  if (nCells > SEGMENT_MAX_CELLS) return 'refuse'
  if (nCells > SEGMENT_WARN_CELLS) return 'warn'
  return 'ok'
}

// Underpowered = fewer than UNDERPOWERED_MIN_N_PER_GROUP users in any group.
export function isUnderpowered(n: Record<string, number>): boolean {
  const counts = Object.values(n)
  return counts.length > 0 && Math.min(...counts) < UNDERPOWERED_MIN_N_PER_GROUP
}
