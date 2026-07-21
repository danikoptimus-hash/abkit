import { describe, it, expect } from 'vitest'
import { experimentDownloadName } from './downloadName'

describe('experimentDownloadName', () => {
  it('inserts the dataset segment when present', () => {
    expect(experimentDownloadName('exp', 'sales', 'export.zip')).toBe('exp_sales_export.zip')
    expect(experimentDownloadName('exp', 'sales', 'detailed_results.csv')).toBe('exp_sales_detailed_results.csv')
  })
  it('omits the segment when null/undefined/empty', () => {
    expect(experimentDownloadName('exp', null, 'export.zip')).toBe('exp_export.zip')
    expect(experimentDownloadName('exp', undefined, 'export.zip')).toBe('exp_export.zip')
    expect(experimentDownloadName('exp', '', 'export.zip')).toBe('exp_export.zip')
  })
  it('joins the parts verbatim (no sanitization here — the segment is pre-sanitized)', () => {
    expect(experimentDownloadName('my exp', 'my ds', 'export.zip')).toBe('my exp_my ds_export.zip')
  })
})
