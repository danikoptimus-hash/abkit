import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { loginViaUi, seedExperiment } from './helpers'

// Tag management page (/settings/tags, admin-only): rename, merge, delete,
// plus the case-insensitive get-or-create dedup guard on the Properties
// modal's "create on the fly" path.

async function tagExperimentViaProperties(page: Page, experimentName: string, tagName: string) {
  await page.goto(`/experiments/${experimentName}`)
  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByText('Edit Properties').click()
  const modal = page.getByRole('dialog')
  const tagsSelect = modal.getByRole('combobox', { name: 'Tags' })
  await tagsSelect.click()
  await tagsSelect.fill(tagName)
  await page.keyboard.press('Enter')
  await modal.getByRole('button', { name: 'Save' }).click()
  await expect(modal).not.toBeVisible()
}

test('renaming a tag on the management page updates its badge on the experiment page and list', async ({
  page,
  request,
}) => {
  const expName = `tagmgmt_rename_e2e_${Date.now()}`
  const oldName = `rename-src-${Date.now()}`
  const newName = `renamed-target-${Date.now()}`
  await seedExperiment(request, expName)
  await loginViaUi(page)
  await tagExperimentViaProperties(page, expName, oldName)

  await page.goto('/settings/tags')
  const search = page.getByPlaceholder('Search tags...')
  await search.fill(oldName)
  const row = page.getByRole('row', { name: new RegExp(oldName) })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Rename' }).click()

  const renameDialog = page.getByRole('dialog').filter({ hasText: 'Rename' })
  await renameDialog.getByRole('textbox').fill(newName)
  await renameDialog.getByRole('button', { name: 'Rename' }).click()
  await expect(renameDialog).not.toBeVisible()

  // No reload anywhere above — the management page's own list, the
  // experiment page's badge, and the experiments list row all read from
  // caches this rename must invalidate (query-key-registry contract).
  await page.goto(`/experiments/${expName}`)
  await expect(page.getByText(newName, { exact: true })).toBeVisible()
  await expect(page.getByText(oldName, { exact: true })).not.toBeVisible()

  await page.goto('/experiments')
  await expect(page.getByRole('row', { name: new RegExp(expName) }).getByText(newName)).toBeVisible()
})

test('merging a tag reassigns its experiments to the target and removes the source', async ({ page, request }) => {
  const expB = `tagmgmt_merge_b_e2e_${Date.now()}`
  const expC = `tagmgmt_merge_c_e2e_${Date.now()}`
  const sourceName = `merge-src-${Date.now()}`
  const targetName = `merge-dst-${Date.now()}`
  await seedExperiment(request, expB)
  await seedExperiment(request, expC)
  await loginViaUi(page)
  await tagExperimentViaProperties(page, expB, sourceName)
  await tagExperimentViaProperties(page, expC, targetName)

  await page.goto('/settings/tags')
  const search = page.getByPlaceholder('Search tags...')
  await search.fill(sourceName)
  const row = page.getByRole('row', { name: new RegExp(sourceName) })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Merge' }).click()

  const mergeDialog = page.getByRole('dialog').filter({ hasText: 'Merge' })
  const targetSelect = mergeDialog.getByRole('combobox', { name: 'merge-target-select' })
  await targetSelect.click()
  await targetSelect.fill(targetName)
  await page.getByTitle(targetName, { exact: true }).click()
  // Narrower than /will be re-tagged/, which also matches the modal's
  // static explanatory paragraph above the target picker.
  await expect(mergeDialog.getByText(/experiment.*will be re-tagged\./)).toBeVisible()
  await mergeDialog.getByRole('button', { name: 'Merge', exact: true }).click()
  await expect(mergeDialog).not.toBeVisible()

  await page.goto(`/experiments/${expB}`)
  await expect(page.getByText(targetName, { exact: true })).toBeVisible()
  await expect(page.getByText(sourceName, { exact: true })).not.toBeVisible()

  await page.goto(`/experiments/${expC}`)
  await expect(page.getByText(targetName, { exact: true })).toBeVisible()

  await page.goto('/settings/tags')
  await page.getByPlaceholder('Search tags...').fill(sourceName)
  await expect(page.getByRole('row', { name: new RegExp(sourceName) })).not.toBeVisible()
})

test('deleting a tag from the management page removes it from tagged experiments', async ({ page, request }) => {
  const expName = `tagmgmt_delete_e2e_${Date.now()}`
  const tagName = `delete-mgmt-${Date.now()}`
  await seedExperiment(request, expName)
  await loginViaUi(page)
  await tagExperimentViaProperties(page, expName, tagName)

  await page.goto('/settings/tags')
  await page.getByPlaceholder('Search tags...').fill(tagName)
  const row = page.getByRole('row', { name: new RegExp(tagName) })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Delete' }).click()

  await expect(page.locator('.ant-modal-confirm-title', { hasText: `Delete tag "${tagName}"?` })).toBeVisible()
  // Scoped to .ant-modal-confirm — the row's own Delete icon button
  // (aria-label="Delete") is still present underneath and would otherwise
  // collide with the confirm dialog's "Delete" OK button in strict mode.
  await page.locator('.ant-modal-confirm').getByRole('button', { name: 'Delete', exact: true }).click()
  await expect(page.getByRole('row', { name: new RegExp(tagName) })).not.toBeVisible()

  await page.goto(`/experiments/${expName}`)
  await expect(page.getByText(tagName, { exact: true })).not.toBeVisible()
})

test('creating a tag with a different case reuses the existing tag instead of creating a duplicate', async ({
  page,
  request,
}) => {
  const expE = `tagmgmt_dup_e_e2e_${Date.now()}`
  const expF = `tagmgmt_dup_f_e2e_${Date.now()}`
  const ts = Date.now()
  const upperName = `DupCase-${ts}`
  const lowerName = `dupcase-${ts}`
  await seedExperiment(request, expE)
  await seedExperiment(request, expF)
  await loginViaUi(page)
  await tagExperimentViaProperties(page, expE, upperName)
  await tagExperimentViaProperties(page, expF, lowerName)

  await page.goto('/settings/tags')
  await page.getByPlaceholder('Search tags...').fill(`dupcase-${ts}`)
  const rows = page.getByRole('row', { name: new RegExp(`dupcase-${ts}`, 'i') })
  await expect(rows).toHaveCount(1)
  // A plain getByText('2') would also match the "e2e.test" substring in the
  // Created-by email cell — the Experiments count renders as a link once
  // its count is > 0, so scope to that instead.
  await expect(rows.getByRole('link', { name: '2', exact: true })).toBeVisible()
})
