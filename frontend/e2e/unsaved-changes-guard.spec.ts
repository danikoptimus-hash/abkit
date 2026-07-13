import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment, uploadDataset } from './helpers'

// Item 1: editing the experiment page's markdown blocks/name and then
// navigating away (tabs, the Discard button itself) without saving must
// confirm first — "Keep editing" cancels the navigation and preserves the
// draft, "Discard" throws it away and proceeds.
test('editing a block then switching tabs prompts to discard; Keep editing preserves the draft, Discard loses it', async ({
  page,
  request,
}) => {
  test.setTimeout(30_000)
  const name = `unsaved_guard_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)
  await page.goto(`/experiments/${name}`)

  await page.getByRole('button', { name: 'Edit' }).click()
  const hypothesisBox = page.locator('.ant-card', { hasText: 'Hypothesis' }).getByRole('textbox').first()
  await hypothesisBox.fill('If we change X, Y will improve.')

  // Switching tabs while dirty prompts — "Keep editing" cancels the
  // navigation and the draft (and edit mode) survive.
  await page.getByRole('tab', { name: 'Analysis' }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Keep editing' }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).not.toBeVisible()
  await expect(hypothesisBox).toHaveValue('If we change X, Y will improve.')
  await expect(page.getByRole('button', { name: 'Save' })).toBeVisible() // still in edit mode

  // Discard confirms, throws away the draft, and completes the navigation.
  await page.getByRole('tab', { name: 'Analysis' }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Discard', exact: true }).click()
  await expect(page.locator('.ant-modal-confirm-title')).not.toBeVisible()
  await expect(page.getByRole('tab', { name: 'Analysis', selected: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Edit' })).toBeVisible() // back to view mode

  await page.getByRole('tab', { name: 'Design' }).click()
  await expect(page.getByText('If we change X, Y will improve.')).not.toBeVisible()
})

// Item 1.3: Edit dataset modal — closing (X/mask/Esc/Cancel all route
// through the same onCancel) while the name has been changed prompts the
// same way.
test('Edit dataset modal prompts to discard when closed with unsaved changes', async ({ page, request }) => {
  test.setTimeout(30_000)
  const filename = `guard_dataset_${Date.now()}.csv`
  await uploadDataset(request, 'user_id,revenue\nu1,10\nu2,20\n', filename)
  await loginViaUi(page)

  await page.goto('/datasets')
  const row = page.getByRole('row', { name: new RegExp(filename) })
  await row.hover()
  await row.getByRole('button', { name: 'Edit' }).click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'Edit dataset' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('textbox').first().fill(`renamed_${filename}`)

  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Keep editing' }).click()
  await expect(dialog).toBeVisible()

  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await page.getByRole('button', { name: 'Discard', exact: true }).click()
  await expect(dialog).not.toBeVisible()
})

// Item A.4: unfinished SQL in dataset creation — previously had NO guard at
// all (onCancel={onClose} direct passthrough); FromSqlTab now reports its
// own dirty state up to CreateDatasetModal.
test('Create dataset modal (From SQL) prompts to discard unsaved SQL', async ({ page }) => {
  test.setTimeout(30_000)
  await loginViaUi(page)
  await page.goto('/datasets')

  await page.getByRole('button', { name: 'Dataset' }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: 'New dataset' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('tab', { name: 'From SQL' }).click()
  await dialog.locator('textarea').fill('SELECT * FROM users')

  // X/mask/Esc all route through the same onCancel as the Cancel button in
  // the other modals — closing via the X icon here covers that path instead.
  await dialog.locator('.ant-modal-close').click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Keep editing' }).click()
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('textarea')).toHaveValue('SELECT * FROM users')

  await dialog.locator('.ant-modal-close').click()
  await page.getByRole('button', { name: 'Discard', exact: true }).click()
  await expect(dialog).not.toBeVisible()
})

// Item A.3: route-level navigation (a top-nav <Link>, not the in-page tab
// switch already covered above) must be caught too — this specifically
// exercises the data-router migration's useBlocker, a capability that
// didn't exist at all before (plain <BrowserRouter> can't intercept route
// changes).
test('clicking a top-nav link while editing the experiment page prompts to discard', async ({ page, request }) => {
  test.setTimeout(30_000)
  const name = `unsaved_guard_nav_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)
  await page.goto(`/experiments/${name}`)

  await page.getByRole('button', { name: 'Edit' }).click()
  const hypothesisBox = page.locator('.ant-card', { hasText: 'Hypothesis' }).getByRole('textbox').first()
  await hypothesisBox.fill('Route-nav guard check.')

  await page.getByRole('link', { name: 'Datasets' }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Keep editing' }).click()
  await expect(page).toHaveURL(new RegExp(`/experiments/${name}$`))
  await expect(hypothesisBox).toHaveValue('Route-nav guard check.')

  await page.getByRole('link', { name: 'Datasets' }).click()
  await page.getByRole('button', { name: 'Discard', exact: true }).click()
  await expect(page).toHaveURL(/\/datasets$/)
})

// Item A.3/A.4: the design wizard has multi-step, multi-field state with no
// pristine tracking at all before this package — leaving mid-wizard (via a
// top-nav link, a real route change) must warn.
test('leaving the design wizard mid-flow via a nav link prompts to discard', async ({ page }) => {
  test.setTimeout(30_000)
  await loginViaUi(page)
  await page.goto('/experiments/new')

  // Demo Data already changes state away from INITIAL_STATE (datasetId,
  // columns, groups/metrics suggestions) — dirty from step 0 onward, before
  // ever reaching the Experiment name field (that's step 1).
  await page.getByRole('button', { name: 'Demo Data' }).click()
  await expect(page.getByText(/Data loaded: 5000 rows/)).toBeVisible({ timeout: 15_000 })

  await page.getByRole('link', { name: 'A/B Tests' }).click()
  await expect(page.locator('.ant-modal-confirm-title', { hasText: 'You have unsaved changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Keep editing' }).click()
  await expect(page).toHaveURL(/\/experiments\/new$/)
  await expect(page.getByText(/Data loaded: 5000 rows/)).toBeVisible()

  await page.getByRole('link', { name: 'A/B Tests' }).click()
  await page.getByRole('button', { name: 'Discard', exact: true }).click()
  await expect(page).toHaveURL(/\/experiments$/)
})
