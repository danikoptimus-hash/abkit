import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment } from './helpers'

// FRONTEND.md §7 R6: "Playwright: демо пост-данные -> анализ -> вердикты и
// forest plot видны -> экспорт таблицы."
test('analyze with demo post-data shows verdicts and forest plot, then exports the table', async ({
  page,
  request,
}) => {
  test.setTimeout(60_000)
  const name = `analyze_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)

  await page.goto(`/experiments/${name}`)
  await page.getByRole('tab', { name: 'Analysis' }).click()

  await page.getByRole('button', { name: /Generate demo post-period data/ }).click()
  await expect(
    page.getByText(/significant positive|significant negative|no effect detected/).first(),
  ).toBeVisible({ timeout: 20_000 })

  await expect(page.getByRole('heading', { name: 'Forest plot' })).toBeVisible()
  // ECharts renders into a canvas — the chart itself can't be checked with a
  // text locator, but the container must exist and be visible.
  await expect(page.locator('canvas').first()).toBeVisible()

  // Detailed table and CSV export live on the Results tab (UX package,
  // section 2: Analysis has verdicts+charts, Results has the table).
  await page.getByRole('tab', { name: 'Results' }).click()
  await expect(page.getByText('Detailed Results Table')).toBeVisible()

  // No "Designed" column (UX package, 5.1) — the designed method is bolded
  // instead.
  await expect(page.getByRole('columnheader', { name: 'Designed' })).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: 'Effect (abs.)' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Lift %' })).toBeVisible()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toContain('detailed_results.csv')
})

// UX package, п.3: after a first analysis, "Re-run analysis" reopens the
// options+upload panel and a second run (with a different dataset) replaces
// what Results shows — history isn't lost (run_meta.run_number counts up),
// but only the latest run is displayed.
test('re-run analysis with a new dataset updates the results and run count', async ({ page, request }) => {
  test.setTimeout(60_000)
  const name = `analyze_rerun_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)

  await page.goto(`/experiments/${name}`)
  await page.getByRole('tab', { name: 'Analysis' }).click()
  await page.getByRole('button', { name: /Generate demo post-period data/ }).click()
  await expect(
    page.getByText(/significant positive|significant negative|no effect detected/).first(),
  ).toBeVisible({ timeout: 20_000 })

  await page.getByRole('tab', { name: 'Results' }).click()
  await expect(page.getByText(/demo data \(run #1\)/)).toBeVisible()

  await page.getByRole('tab', { name: 'Analysis' }).click()
  await page.getByRole('button', { name: 'Re-run analysis' }).click()
  await expect(page.getByRole('button', { name: 'Run Analysis' })).not.toBeVisible()

  const csv =
    'user_id,revenue\n' + Array.from({ length: 200 }, (_, i) => `u_${name}_${i},${100 + (i % 10)}.5`).join('\n')
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByText('Upload post-period data (CSV)').click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({ name: 'rerun.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })

  await page.getByRole('button', { name: 'Run Analysis' }).click()
  await expect(
    page.getByText(/significant positive|significant negative|no effect detected/).first(),
  ).toBeVisible({ timeout: 20_000 })

  await page.getByRole('tab', { name: 'Results' }).click()
  await expect(page.getByText(/rerun\.csv \(run #2\)/)).toBeVisible()
})
