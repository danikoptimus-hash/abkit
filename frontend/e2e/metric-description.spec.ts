import { test, expect } from '@playwright/test'
import { loginViaUi } from './helpers'

// Part 1: a metric description entered in the wizard shows on the Design tab
// and, on the Results tab, behind an info popover next to the metric name.
test('metric description flows from the wizard to the Design tab and the Results info popover', async ({
  page,
}) => {
  test.setTimeout(90_000)
  const desc = 'Total revenue per user in the test window (sum of order totals).'

  await loginViaUi(page)
  await page.getByRole('button', { name: 'Create A/B Test' }).click()

  // Step 1: demo data.
  await page.getByRole('button', { name: 'Demo Data' }).click()
  await expect(page.getByText(/Data loaded: 5000 rows/)).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Next' }).click()

  // Step 2: name + fill the first metric's description.
  const expName = `metric_desc_e2e_${Date.now()}`
  await page.getByPlaceholder('Experiment name').fill(expName)
  await page
    .getByPlaceholder('What does this metric measure and how is it computed? (optional)')
    .first()
    .fill(desc)
  await page.getByRole('button', { name: 'Next' }).click()

  // Step 3: isolation off + calculate.
  await page.getByText(/exclude — exclude participants/).click()
  await page.getByText(/off — exclude no one/).click()
  await page.getByRole('button', { name: 'Calculate sample size' }).click()
  await expect(page.getByText(/Required per group:|No MDE target set/)).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Next' }).click()

  // Step 4: design.
  await page.getByRole('button', { name: 'Design' }).click()
  await expect(page).toHaveURL(new RegExp(`/experiments/${expName}$`), { timeout: 20_000 })

  // Design tab: the description is shown inline under the metric.
  await expect(page.getByText(desc)).toBeVisible()

  // Analyze via demo post-period data.
  await page.getByRole('tab', { name: 'Analysis' }).click()
  await page.getByRole('button', { name: /Generate demo post-period data/ }).click()
  await page.getByRole('button', { name: 'Run analysis' }).click()
  await expect(
    page.getByText(/significant positive|significant negative|no effect detected/).first(),
  ).toBeVisible({ timeout: 30_000 })

  // Results tab: the description is NOT inlined — it's behind an info popover.
  await page.getByRole('tab', { name: 'Results' }).click()
  await page.getByLabel(/^metric-info-/).first().hover()
  const popover = page.getByRole('tooltip')
  await expect(popover.getByText('Metric definition')).toBeVisible()
  await expect(popover.getByText(desc)).toBeVisible()
})
