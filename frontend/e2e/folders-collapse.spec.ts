import { test, expect } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { createUserWithTempPassword } from './helpers'

// Панель папок: свернута по умолчанию, выбор запоминается на сервере
// (users.folders_panel_collapsed, миграция 0018).
//
// Свежая учетка на каждый тест — не чистота ради чистоты: настройка per-user и
// ПЕРСИСТЕНТНАЯ, поэтому общий admin@e2e.test, которому один тест развернул
// панель, сломал бы "по умолчанию свернута" в другом. Ровно та зависимость от
// порядка, которую эта фича и создает.
async function loginAsFreshEditor(page: Page, request: APIRequestContext): Promise<string> {
  const email = `_dev_folders_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@e2e.test`
  const tempPassword = await createUserWithTempPassword(request, email, 'editor')

  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(tempPassword)
  await page.getByRole('button', { name: 'Sign In' }).click()

  // Учетка с временным паролем сначала обязана его сменить (/profile).
  await expect(page).toHaveURL(/\/profile$/)
  await page.getByLabel('Current Password').fill(tempPassword)
  await page.getByLabel('New Password').fill('e2epass123')
  await page.getByRole('button', { name: 'Change Password' }).click()
  await expect(page).toHaveURL(/\/experiments$/)
  return email
}

test('A fresh session shows the folders section collapsed', async ({ page, request }) => {
  test.setTimeout(60_000)
  await loginAsFreshEditor(page, request)

  await expect(page.getByRole('button', { name: 'Show folders' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Folders' })).toHaveCount(0)
})

test('Expanding is remembered across navigation and reload', async ({ page, request }) => {
  test.setTimeout(60_000)
  await loginAsFreshEditor(page, request)

  await page.getByRole('button', { name: 'Show folders' }).click()
  const panel = page.getByRole('navigation', { name: 'Folders' })
  await expect(panel).toBeVisible()

  // Уходим на другую страницу и возвращаемся: FolderPanel размонтируется —
  // именно здесь прежний useState терял выбор.
  await page.getByRole('menuitem', { name: 'Datasets' }).click()
  await expect(page).toHaveURL(/\/datasets$/)
  await page.getByRole('menuitem', { name: 'A/B Tests' }).click()
  await expect(page).toHaveURL(/\/experiments$/)
  await expect(panel).toBeVisible()

  // И перезагрузка: значение приезжает с /me, а не из localStorage.
  await page.reload()
  await expect(panel).toBeVisible()

  // Сворачивание запоминается так же, как разворачивание.
  await panel.getByRole('button', { name: 'Hide folders' }).click()
  await expect(page.getByRole('button', { name: 'Show folders' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Show folders' })).toBeVisible()
})

test('The preference is per-user, not global', async ({ page, request }) => {
  test.setTimeout(90_000)
  await loginAsFreshEditor(page, request)

  await page.getByRole('button', { name: 'Show folders' }).click()
  await expect(page.getByRole('navigation', { name: 'Folders' })).toBeVisible()

  await page.getByTestId('user-menu-trigger').click()
  await page.getByText('Logout').click()
  await expect(page).toHaveURL(/\/login$/)

  // Второй пользователь в том же браузере видит СВОЙ дефолт, а не чужой выбор.
  await loginAsFreshEditor(page, request)
  await expect(page.getByRole('button', { name: 'Show folders' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Folders' })).toHaveCount(0)
})
