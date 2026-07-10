import { test, expect } from '@playwright/test'
import { loginViaUi } from './helpers'

const API_BASE = process.env.E2E_API_BASE ?? 'http://localhost:8000/api/v1'

// UX-fix: deactivated e2e/dev test accounts shouldn't clutter the Admin
// Users list by default — "Show inactive" is opt-in (CLAUDE.md's "_dev_
// prefix + self-cleanup" rule leaves accounts deactivated, not deleted).
test('deactivated users are hidden by default and shown with "Show inactive"', async ({ page, request }) => {
  const email = `admin_users_e2e_${Date.now()}@e2e.test`

  const loginResp = await request.post(`${API_BASE}/auth/login`, {
    data: { email: 'admin@e2e.test', password: 'e2epass123' },
  })
  if (!loginResp.ok()) throw new Error(`login failed: ${loginResp.status()}`)

  const createResp = await request.post(`${API_BASE}/admin/users`, {
    data: { email, first_name: 'Admin', last_name: 'UsersE2E', role: 'viewer' },
  })
  if (!createResp.ok()) throw new Error(`create user failed: ${createResp.status()}`)
  const userId = (await createResp.json()).user.id as string

  const deactivateResp = await request.patch(`${API_BASE}/admin/users/${userId}`, {
    data: { is_active: false },
  })
  if (!deactivateResp.ok()) throw new Error(`deactivate failed: ${deactivateResp.status()}`)

  await loginViaUi(page)
  await page.goto('/admin')

  await expect(page.getByRole('row', { name: new RegExp(email) })).not.toBeVisible()

  await page.getByRole('switch', { name: 'Show inactive' }).click()
  await expect(page.getByRole('row', { name: new RegExp(email) })).toBeVisible()

  await page.getByRole('switch', { name: 'Show inactive' }).click()
  await expect(page.getByRole('row', { name: new RegExp(email) })).not.toBeVisible()
})
