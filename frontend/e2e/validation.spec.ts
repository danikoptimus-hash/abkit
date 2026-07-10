import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment } from './helpers'

// UX package, Validation п.C: auto-datasource means no manual upload is
// needed anymore when the experiment already has its design data stored.
test('validation page runs A/A + A/B and shows FPR and power tables', async ({ page, request }) => {
  test.setTimeout(60_000)
  const name = `validation_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)

  await page.goto('/validation')
  await page.getByRole('combobox', { name: 'validation-experiment-select' }).click()
  // showSearch на Select (Validation.tsx) — печатаем имя, чтобы найти опцию
  // среди всех экспериментов в БД без опоры на виртуализированный список
  // (иначе на большом количестве экспериментов свежесозданная опция может
  // не попасть в изначально отрендеренное окно rc-virtual-list).
  await page.getByRole('combobox', { name: 'validation-experiment-select' }).fill(name)
  await page.getByTitle(name).click()
  await expect(page.getByText('From experiment design')).toBeVisible()

  // Дефолт компонента (2000) статистически осмыслен, но слишком медленный для
  // e2e — 100 (минимум по InputNumber) достаточно для проверки самого потока.
  await page.getByRole('spinbutton').first().fill('100')
  await page.getByRole('button', { name: 'Run Validation' }).click()

  await expect(page.getByText('A/A: empirical FPR')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('A/B: empirical vs analytical power')).toBeVisible()
  await expect(page.getByText(/honest|lying/).first()).toBeVisible()
  await expect(page.getByText(/Validated with data\.csv/)).toBeVisible()
})

// 6-part package pt.11: Validation moved out of the main nav into
// Settings > Tools — reachable at /settings/validation, gone from the top
// menu, and the old /validation URL still redirects there (bookmarks keep
// working).
test('Validation is reachable from Settings > Tools, absent from the main nav, and /validation redirects', async ({
  page,
  request,
}) => {
  test.setTimeout(60_000)
  const name = `validation_settings_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)

  await expect(page.getByRole('menuitem', { name: 'Validation' })).not.toBeVisible()

  await page.getByTestId('user-menu-trigger').click()
  await page.getByRole('menuitem', { name: 'Validation (A/A, A/B)' }).click()
  await expect(page).toHaveURL(/\/settings\/validation$/)

  await page.getByRole('combobox', { name: 'validation-experiment-select' }).click()
  await page.getByRole('combobox', { name: 'validation-experiment-select' }).fill(name)
  await page.getByTitle(name).click()
  await expect(page.getByText('From experiment design')).toBeVisible()
  await page.getByRole('spinbutton').first().fill('100')
  await page.getByRole('button', { name: 'Run Validation' }).click()
  await expect(page.getByText('A/A: empirical FPR')).toBeVisible({ timeout: 30_000 })

  await page.goto('/validation')
  await expect(page).toHaveURL(/\/settings\/validation$/)
})

test('viewer does not see Validation in Settings', async ({ page }) => {
  await loginViaUi(page, 'viewer@e2e.test', 'e2epass123')
  await page.getByTestId('user-menu-trigger').click()
  await expect(page.getByRole('menuitem', { name: 'Validation (A/A, A/B)' })).not.toBeVisible()
})
