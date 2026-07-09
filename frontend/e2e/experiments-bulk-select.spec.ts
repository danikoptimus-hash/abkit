import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment } from './helpers'

const API_BASE = process.env.E2E_API_BASE ?? 'http://localhost:8000/api/v1'

test('bulk select: toggling the mode shows checkboxes, selecting rows shows the action bar', async ({
  page,
  request,
}) => {
  const nameA = `bulk_toggle_a_${Date.now()}`
  const nameB = `bulk_toggle_b_${Date.now()}`
  await seedExperiment(request, nameA)
  await seedExperiment(request, nameB)
  await loginViaUi(page)
  await page.goto('/experiments')

  await expect(page.locator('.ant-checkbox')).toHaveCount(0)
  await page.getByRole('button', { name: 'Bulk select' }).click()
  await expect(page.locator('.ant-checkbox').first()).toBeVisible()

  const rowA = page.getByRole('row', { name: new RegExp(nameA) })
  const rowB = page.getByRole('row', { name: new RegExp(nameB) })
  await rowA.getByRole('checkbox').check()
  await rowB.getByRole('checkbox').check()

  await expect(page.getByText('2 selected')).toBeVisible()

  await page.getByRole('button', { name: 'Deselect all' }).click()
  await expect(page.getByText('2 selected')).not.toBeVisible()
  await expect(page.locator('.ant-checkbox')).toHaveCount(0)
})

test('bulk delete removes the selected experiments after typing DELETE', async ({ page, request }) => {
  const nameA = `bulk_del_a_e2e_${Date.now()}`
  const nameB = `bulk_del_b_e2e_${Date.now()}`
  await seedExperiment(request, nameA)
  await seedExperiment(request, nameB)
  await loginViaUi(page)
  await page.goto('/experiments')

  await page.getByRole('button', { name: 'Bulk select' }).click()
  await page.getByRole('row', { name: new RegExp(nameA) }).getByRole('checkbox').check()
  await page.getByRole('row', { name: new RegExp(nameB) }).getByRole('checkbox').check()
  await expect(page.getByText('2 selected')).toBeVisible()

  await page.getByRole('button', { name: 'Delete selected' }).click()
  const modal = page.getByRole('dialog')
  await expect(modal.getByText(nameA, { exact: true })).toBeVisible()
  await expect(modal.getByText(nameB, { exact: true })).toBeVisible()

  const okButton = modal.getByRole('button', { name: 'Delete' })
  await expect(okButton).toBeDisabled()
  await modal.getByRole('textbox').fill('DELETE')
  await expect(okButton).toBeEnabled()
  await okButton.click()

  await expect(page.getByRole('link', { name: nameA, exact: true })).not.toBeVisible()
  await expect(page.getByRole('link', { name: nameB, exact: true })).not.toBeVisible()
})

test('bulk delete skips an experiment without permission and reports it', async ({ page, request }) => {
  const ownName = `bulk_perm_own_${Date.now()}`
  const othersName = `bulk_perm_others_${Date.now()}`
  const editorEmail = `bulk_editor_${Date.now()}@e2e.test`
  const editorPassword = 'e2epass123'

  // Someone else's experiment, published so a different editor can at least
  // see (and select) it, but not delete it.
  await seedExperiment(request, othersName)
  const publishResp = await request.patch(`${API_BASE}/experiments/${othersName}`, {
    data: { publication_status: 'published' },
  })
  expect(publishResp.ok()).toBeTruthy()

  const createResp = await request.post(`${API_BASE}/admin/users`, {
    data: { email: editorEmail, first_name: 'Bulk', last_name: 'Editor', role: 'editor', password: editorPassword },
  })
  expect(createResp.ok()).toBeTruthy()

  await seedExperiment(request, ownName, { email: editorEmail, password: editorPassword })

  await loginViaUi(page, editorEmail, editorPassword)
  await page.goto('/experiments')

  await page.getByRole('button', { name: 'Bulk select' }).click()
  await page.getByRole('row', { name: new RegExp(ownName) }).getByRole('checkbox').check()
  await page.getByRole('row', { name: new RegExp(othersName) }).getByRole('checkbox').check()
  await expect(page.getByText('2 selected')).toBeVisible()

  await page.getByRole('button', { name: 'Delete selected' }).click()
  const modal = page.getByRole('dialog')
  await modal.getByRole('textbox').fill('DELETE')
  await modal.getByRole('button', { name: 'Delete' }).click()

  // The name is interpolated into one sentence (not its own element), so
  // match the whole line rather than the bare name — which would otherwise
  // ambiguously also match the (still-closing) confirm modal's file list.
  await expect(page.getByText(new RegExp(`Deleted 1, skipped 1.*${othersName}`))).toBeVisible()

  await page.getByRole('button', { name: 'OK' }).click()
  await expect(page.getByRole('link', { name: ownName, exact: true })).not.toBeVisible()
  await expect(page.getByRole('link', { name: othersName, exact: true })).toBeVisible()
})
