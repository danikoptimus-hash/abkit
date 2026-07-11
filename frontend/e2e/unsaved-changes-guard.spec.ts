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
