import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment, uploadDataset } from './helpers'

// UX package, Datasets §2/§3: Edit/Delete actions and live search — all
// against plain source=upload datasets (no live external DB needed, unlike
// database-connections.spec.ts's schema/table/edit-sql coverage).

test('Edit dataset renames it, upload source only exposes the name field', async ({ page, request }) => {
  const originalName = `edit_original_${Date.now()}.csv`
  await uploadDataset(request, 'a,b\n1,2\n', originalName)
  await loginViaUi(page)
  await page.goto('/datasets')

  const row = page.getByRole('row', { name: new RegExp(originalName) })
  await row.hover()
  await row.getByRole('button', { name: 'Edit' }).click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'Edit dataset' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('To change data, upload a new dataset.')).toBeVisible()

  // §2.3 — upload source still gets a read-only snapshot preview (useful
  // when renaming), just no connection/SQL/schema-table controls.
  await expect(dialog.getByText('Data preview')).toBeVisible()
  await expect(dialog.getByText(/Stored snapshot: \d+ rows, fetched/)).toBeVisible()
  await expect(dialog.getByRole('columnheader', { name: 'a' })).toBeVisible()
  await expect(dialog.getByRole('tab', { name: 'Query result' })).not.toBeVisible()

  const nameInput = dialog.getByRole('textbox')
  const newName = `edited_${Date.now()}.csv`
  await nameInput.fill(newName)
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog).not.toBeVisible()

  await expect(page.getByRole('row', { name: new RegExp(newName) })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(originalName) })).not.toBeVisible()
})

test('Delete an unused dataset requires typed DELETE; canceling does not delete it', async ({ page, request }) => {
  const filename = `delete_unused_${Date.now()}.csv`
  await uploadDataset(request, 'a,b\n1,2\n', filename)
  await loginViaUi(page)
  await page.goto('/datasets')

  const row = page.getByRole('row', { name: new RegExp(filename) })
  await row.hover()
  await row.getByRole('button', { name: 'Delete' }).click()

  const confirmDialog = page.getByRole('dialog').filter({ hasText: `Delete dataset ${filename}?` })
  await expect(confirmDialog).toBeVisible()
  await expect(confirmDialog.getByText(/Type DELETE to confirm/)).toBeVisible()
  const okButton = confirmDialog.getByRole('button', { name: 'Delete' })
  await expect(okButton).toBeDisabled()

  // Canceling does not delete it.
  await confirmDialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(confirmDialog).not.toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(filename) })).toBeVisible()

  await row.hover()
  await row.getByRole('button', { name: 'Delete' }).click()
  await expect(confirmDialog).toBeVisible()
  await confirmDialog.getByPlaceholder('DELETE').fill('DELETE')
  await expect(okButton).toBeEnabled()
  await okButton.click()

  await expect(page.getByRole('row', { name: new RegExp(filename) })).not.toBeVisible()
})

test('Delete a dataset used by an experiment requires typed DELETE and lists the experiment', async ({
  page,
  request,
}) => {
  const name = `used_dataset_exp_${Date.now()}`
  await seedExperiment(request, name) // creates + designs on a pre_design dataset ("data.csv")
  await loginViaUi(page)
  await page.goto('/datasets')

  const row = page.getByRole('row', { name: /^data\.csv/ }).filter({ has: page.getByRole('link', { name }) })
  await row.hover()
  await row.getByRole('button', { name: 'Delete' }).click()

  const confirmDialog = page.getByRole('dialog').filter({ hasText: 'Used by experiments' })
  await expect(confirmDialog).toBeVisible()
  await expect(confirmDialog.getByText(name, { exact: false })).toBeVisible()

  const deleteButton = confirmDialog.getByRole('button', { name: 'Delete' })
  await expect(deleteButton).toBeDisabled()
  await confirmDialog.getByPlaceholder('DELETE').fill('DELETE')
  await expect(deleteButton).toBeEnabled()
  await deleteButton.click()
  await expect(confirmDialog).not.toBeVisible()

  // The experiment itself and its (frozen) results context survive —
  // only the live dataset row is gone.
  await page.goto(`/experiments/${name}`)
  await expect(page.getByText(name)).toBeVisible()
})

test('Live search filters the Datasets table without pressing Enter, Source filter narrows further', async ({
  page,
  request,
}) => {
  const uniqueToken = `search_probe_${Date.now()}`
  const matchName = `${uniqueToken}_match.csv`
  const otherName = `unrelated_${Date.now()}.csv`
  await uploadDataset(request, 'a,b\n1,2\n', matchName)
  await uploadDataset(request, 'a,b\n1,2\n', otherName)

  await loginViaUi(page)
  await page.goto('/datasets')
  await expect(page.getByRole('row', { name: new RegExp(otherName) })).toBeVisible()

  await page.getByPlaceholder('Search datasets...').fill(uniqueToken)
  // No Enter pressed — the debounced filter must apply on its own.
  await expect(page.getByRole('row', { name: new RegExp(matchName) })).toBeVisible({ timeout: 3_000 })
  await expect(page.getByRole('row', { name: new RegExp(otherName) })).not.toBeVisible()

  await page.getByPlaceholder('Search datasets...').fill('')
  await expect(page.getByRole('row', { name: new RegExp(otherName) })).toBeVisible()

  // Source filter (All/Upload/SQL/Demo) — both probes are source=upload.
  await page.getByRole('combobox', { name: 'Source' }).click()
  await page.getByTitle('SQL', { exact: true }).click()
  await expect(page.getByRole('row', { name: new RegExp(otherName) })).not.toBeVisible()
})
