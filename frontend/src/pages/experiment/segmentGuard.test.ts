import { describe, it, expect } from 'vitest'
import {
  combinationCellCount,
  segmentCardinalityStatus,
  isUnderpowered,
} from './segmentGuard'

describe('segmentCardinalityStatus', () => {
  it('is ok at and below 30', () => {
    expect(segmentCardinalityStatus(29)).toBe('ok')
    expect(segmentCardinalityStatus(30)).toBe('ok')
  })
  it('warns just above 30 through 200', () => {
    expect(segmentCardinalityStatus(31)).toBe('warn')
    expect(segmentCardinalityStatus(199)).toBe('warn')
    expect(segmentCardinalityStatus(200)).toBe('warn')
  })
  it('refuses above 200', () => {
    expect(segmentCardinalityStatus(201)).toBe('refuse')
    expect(segmentCardinalityStatus(5000)).toBe('refuse')
  })
})

describe('combinationCellCount', () => {
  it('multiplies the columns distinct counts', () => {
    expect(combinationCellCount(['a', 'b'], { a: 5, b: 3 })).toBe(15)
    expect(combinationCellCount(['a', 'b', 'c'], { a: 7, b: 3, c: 10 })).toBe(210)
  })
  it('treats an unknown column as 1 (no data yet)', () => {
    expect(combinationCellCount(['a', 'b'], { a: 5 })).toBe(5)
  })
})

describe('isUnderpowered', () => {
  it('flags a group below 100', () => {
    expect(isUnderpowered({ control: 80, treatment: 200 })).toBe(true)
    expect(isUnderpowered({ control: 120, treatment: 150 })).toBe(false)
    expect(isUnderpowered({})).toBe(false)
  })
})
