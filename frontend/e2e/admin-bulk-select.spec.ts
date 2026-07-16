import { test, expect } from '@playwright/test'
import { loginViaUi, createUserWithTempPassword } from './helpers'

// Item 7 (audit-details+ package): bulk select on Admin > Users — matches
// the explicit test spec: select two (including yourself), deactivate,
// verify self-skip.
test('Bulk select two users, deactivate: self is skipped, the other is deactivated', async ({ page, request }) => {
  const email = `admin_bulk_target_${Date.now()}@e2e.test`
  await createUserWithTempPassword(request, email, 'viewer')

  await loginViaUi(page, 'admin@e2e.test', 'e2epass123')
  await page.goto('/admin')

  await page.getByRole('button', { name: 'Bulk select' }).click()

  const selfRow = page.getByRole('row', { name: /admin@e2e\.test/ })
  const targetRow = page.getByRole('row', { name: new RegExp(email) })
  await selfRow.getByRole('checkbox').check()
  await targetRow.getByRole('checkbox').check()
  await expect(page.getByText('2 selected')).toBeVisible()

  await page.getByRole('button', { name: 'Deactivate' }).click()

  // Mixed outcome (one skipped) shows the summary modal — the self-skip
  // reason names exactly what happened, not a generic failure.
  const modal = page.getByRole('dialog')
  await expect(modal.getByText(/Deactivated 1, skipped 1/)).toBeVisible()
  await expect(modal.getByText(/admin@e2e\.test.*cannot deactivate your own account/)).toBeVisible()
  await page.getByRole('button', { name: 'OK' }).click()

  // admin@e2e.test itself must still be active (self-protection held) —
  // its row is unaffected and still shows without opting into "Show
  // inactive". The target user became inactive and drops out of the
  // default (active-only) view.
  await expect(page.getByRole('row', { name: /admin@e2e\.test/ })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(email) })).not.toBeVisible()

  await page.getByRole('switch', { name: 'Show inactive' }).click()
  const deactivatedRow = page.getByRole('row', { name: new RegExp(email) })
  await expect(deactivatedRow).toBeVisible()
  await expect(deactivatedRow.getByText('no', { exact: true })).toBeVisible()
})

test('Bulk activate: reactivating a deactivated user works with no self-skip involved', async ({ page, request }) => {
  const email = `admin_bulk_reactivate_${Date.now()}@e2e.test`
  await createUserWithTempPassword(request, email, 'viewer')

  await loginViaUi(page, 'admin@e2e.test', 'e2epass123')
  await page.goto('/admin')

  // Deactivate first (single-user Edit modal, existing path) so there is
  // something to reactivate in bulk.
  const row = page.getByRole('row', { name: new RegExp(email) })
  await row.getByRole('button', { name: 'Edit' }).click()
  const editModal = page.getByRole('dialog')
  await editModal.getByRole('switch').click()
  await editModal.getByRole('button', { name: 'OK' }).click()
  await expect(editModal).not.toBeVisible()

  await page.getByRole('switch', { name: 'Show inactive' }).click()
  await page.getByRole('button', { name: 'Bulk select' }).click()
  await page.getByRole('row', { name: new RegExp(email) }).getByRole('checkbox').check()
  await expect(page.getByText('1 selected')).toBeVisible()

  await page.getByRole('button', { name: 'Activate', exact: true }).click()
  await expect(page.getByText('Activated 1 user')).toBeVisible()

  const reactivatedRow = page.getByRole('row', { name: new RegExp(email) })
  await expect(reactivatedRow.getByText('yes', { exact: true })).toBeVisible()
})
