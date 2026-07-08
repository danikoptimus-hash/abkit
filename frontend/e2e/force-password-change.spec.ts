import { test, expect } from '@playwright/test'
import { createUserWithTempPassword } from './helpers'

test('user with temp password is forced to change it before accessing the app', async ({
  page,
  request,
}) => {
  const email = `forcepw_${Date.now()}@e2e.test`
  const tempPassword = await createUserWithTempPassword(request, email)

  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Пароль').fill(tempPassword)
  await page.getByRole('button', { name: 'Войти' }).click()

  // Любой переход (не только прямой заход) заворачивает на /profile.
  await expect(page).toHaveURL(/\/profile$/)
  await expect(page.getByText('Смена пароля')).toBeVisible()

  await page.goto('/experiments')
  await expect(page).toHaveURL(/\/profile$/)

  await page.getByLabel('Текущий пароль').fill(tempPassword)
  await page.getByLabel('Новый пароль').fill('newpassword456')
  await page.getByRole('button', { name: 'Сменить пароль' }).click()

  await expect(page).toHaveURL(/\/experiments$/)

  // После смены доступ открыт, повторный логин со старым паролем не проходит.
  await page.getByTestId('user-menu-trigger').click()
  await page.getByText('Выйти').click()
  await expect(page).toHaveURL(/\/login$/)

  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Пароль').fill('newpassword456')
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page).toHaveURL(/\/experiments$/)
})
