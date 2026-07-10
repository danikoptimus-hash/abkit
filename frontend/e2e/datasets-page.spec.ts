import { test, expect } from '@playwright/test'
import { loginViaUi } from './helpers'

// DB3 (CLAUDE.md dataset-centric model): the Datasets page is now the only
// place a file can be uploaded — design/analyze/validation only select from
// existing datasets (see analyze.spec.ts / validation-datasource.spec.ts).
test('"+ Dataset" modal uploads a file and it appears in the list with an Upload source tag', async ({ page }) => {
  await loginViaUi(page)
  await page.goto('/datasets')

  await page.getByRole('button', { name: 'Dataset' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  const filename = `datasets_page_e2e_${Date.now()}.csv`
  const csv = 'user_id,revenue\nu1,10\nu2,20\n'
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByText('Drag a CSV or parquet file here').click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({ name: filename, mimeType: 'text/csv', buffer: Buffer.from(csv) })

  // Modal closes on success and the new row shows up in the list.
  await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 10_000 })
  const row = page.getByRole('row', { name: new RegExp(filename) })
  await expect(row).toBeVisible()
  await expect(row.getByText('Upload')).toBeVisible()

  // Refresh only makes sense for source=sql — an uploaded file has nothing
  // to re-fetch from (UX package, Datasets п.1.2: absent, not disabled).
  await expect(row.getByRole('button', { name: 'Refresh' })).toHaveCount(0)
})

test('From SQL tab renders a connection picker and SQL editor', async ({ page }) => {
  await loginViaUi(page)
  await page.goto('/datasets')

  await page.getByRole('button', { name: 'Dataset' }).click()
  await page.getByRole('tab', { name: 'From SQL' }).click()

  await expect(page.getByRole('combobox')).toBeVisible()
  await expect(page.getByPlaceholder(/SELECT user_id, revenue FROM/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Preview' })).toBeDisabled()
})
