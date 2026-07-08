import { test, expect } from '@playwright/test'
import { loginViaUi } from './helpers'

test('viewer does not see "Создать A/B тест" button', async ({ page }) => {
  await loginViaUi(page, 'viewer@e2e.test', 'e2epass123')
  await expect(page.getByRole('button', { name: 'Создать A/B тест' })).not.toBeVisible()
})

test('viewer cannot open /admin (redirected away)', async ({ page }) => {
  await loginViaUi(page, 'viewer@e2e.test', 'e2epass123')
  await page.goto('/admin')
  await expect(page).toHaveURL(/\/experiments$/)
})

test('admin sees "Создать A/B тест" and can open /admin', async ({ page }) => {
  await loginViaUi(page, 'admin@e2e.test', 'e2epass123')
  await expect(page.getByRole('button', { name: 'Создать A/B тест' })).toBeVisible()

  await page.goto('/admin')
  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByText('Пользователи')).toBeVisible()
})
