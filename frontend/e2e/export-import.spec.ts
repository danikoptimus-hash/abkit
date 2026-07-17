import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment } from './helpers'

// Пакет export/import + глобальная "+".
//
// Экспортный zip тут НЕ разбирается на части (это дело backend/tests/
// test_experiment_export_import.py, там же и round-trip с глубоким
// сравнением) — здесь проверяется ровно то, чего backend-тест увидеть не
// может: что кнопка есть, что браузер реально получает файл, и что
// загруженный обратно через UI архив дает новый тест в списке.

test('Export a test from the list, then import the archive back through the UI', async ({
  page,
  request,
}) => {
  test.setTimeout(90_000)
  const suffix = Date.now()
  const name = `_dev_export_e2e_${suffix}`

  await seedExperiment(request, name)
  await loginViaUi(page)
  await page.goto('/experiments')
  await page.getByPlaceholder('Search by name or tag...').fill(name)

  const row = page.getByRole('row', { name: new RegExp(name) })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Export' }).click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'Export' })
  await expect(dialog.getByTestId('include-dataset-snapshots')).toBeVisible()
  // Со снапшотом: импорт ниже должен пройти без предупреждений даже если бы
  // датасета не было — и заодно это проверяет ветку include_datasets=true.
  await dialog.getByTestId('include-dataset-snapshots').click()

  const downloadPromise = page.waitForEvent('download')
  await dialog.getByRole('button', { name: 'Export' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(`${name}_export.zip`)

  const archivePath = await download.path()
  expect(archivePath).toBeTruthy()

  // Импорт того же архива обратно: имя занято -> копия с суффиксом.
  await page.getByRole('button', { name: 'Import' }).click()
  const importDialog = page.getByRole('dialog').filter({ hasText: 'Import A/B test' })
  await importDialog.locator('input[type="file"]').setInputFiles(archivePath!)
  await importDialog.getByRole('button', { name: 'Import' }).click()

  const doneDialog = page.getByRole('dialog').filter({ hasText: 'Import complete' })
  await expect(doneDialog).toBeVisible({ timeout: 30_000 })
  await expect(doneDialog.getByText(`${name} (imported)`)).toBeVisible()

  await doneDialog.getByRole('button', { name: 'Open test' }).click()
  // Через page.url(), а не toHaveURL(RegExp): имя содержит "(imported)", и в
  // регулярке эти скобки — группа захвата, а не литерал (тест из-за этого
  // "не находил" URL, который на самом деле был правильным).
  await expect.poll(() => page.url()).toContain(encodeURIComponent(`${name} (imported)`))
  // Импортированный тест — всегда черновик, чей бы он ни был в архиве.
  await expect(page.getByText('draft', { exact: true })).toBeVisible()
})

test('Export is available from the experiment page ⋯ menu', async ({ page, request }) => {
  test.setTimeout(60_000)
  const name = `_dev_export_menu_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)
  await page.goto(`/experiments/${encodeURIComponent(name)}`)

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Export' }).click()
  await expect(page.getByRole('dialog').filter({ hasText: 'Export' })).toBeVisible()
})

test('Export and Import are absent for a viewer', async ({ page }) => {
  await loginViaUi(page, 'viewer@e2e.test', 'e2epass123')
  await page.goto('/experiments')
  // Ждем, что список реально отрисовался (у страницы нет заголовка, за
  // который можно зацепиться) — иначе "кнопки нет" прошло бы и на пустой,
  // еще не смонтированной странице.
  await expect(page.getByPlaceholder('Search by name or tag...')).toBeVisible()

  await expect(page.getByRole('button', { name: 'Import' })).toHaveCount(0)
  // Export — тоже Editor+, viewer его не видит даже на видимом тесте.
  await expect(page.getByRole('button', { name: 'Export' })).toHaveCount(0)
})
