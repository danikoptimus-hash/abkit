import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment, uploadDataset } from './helpers'

// UX package, Validation п.C: the pre-design dataset is auto-selected so
// Run Validation is ready immediately, no forced manual upload.
test('validation auto-selects the experiment design data', async ({ page, request }) => {
  const name = `val_auto_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)

  await page.goto('/validation')
  await page.getByRole('combobox').first().click()
  await page.getByRole('combobox').first().fill(name)
  await page.getByTitle(name).click()

  await expect(page.getByText('From experiment design')).toBeVisible()
  await expect(page.getByText(/data\.csv/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Validation' })).toBeEnabled()
})

test('"Use different data" reveals upload, and an incompatible file is rejected with the missing columns', async ({
  page,
  request,
}) => {
  const name = `val_incompat_e2e_${Date.now()}`
  await seedExperiment(request, name)

  // Uploaded via the API up front, before any page load: DatasetSelect's
  // query is cached per mount and isn't invalidated by an out-of-band API
  // call made later in the browser context's lifetime.
  const csv = 'some_other_column\n' + Array.from({ length: 50 }, (_, i) => `${i}`).join('\n')
  const incompatibleFilename = `incompatible_${Date.now()}.csv`
  await uploadDataset(request, csv, incompatibleFilename)

  await loginViaUi(page)

  await page.goto('/validation')
  await page.getByRole('combobox').first().click()
  await page.getByRole('combobox').first().fill(name)
  await page.getByTitle(name).click()
  await expect(page.getByText('From experiment design')).toBeVisible()

  await page.getByRole('button', { name: 'Use different data' }).click()

  const datasetSelect = page.getByRole('combobox', { name: 'validation-dataset-select' })
  await datasetSelect.click()
  await datasetSelect.fill(incompatibleFilename)
  await page.getByTitle(incompatibleFilename).click()

  await expect(page.getByText(/missing columns required by the experiment's design/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Validation' })).toBeDisabled()

  await page.getByRole('button', { name: 'Reset to design data' }).click()
  await expect(page.getByText('From experiment design')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Validation' })).toBeEnabled()
})

test('Run Validation is disabled with a tooltip when no experiment is selected', async ({ page, request }) => {
  await seedExperiment(request, `val_notool_e2e_${Date.now()}`)
  await loginViaUi(page)

  await page.goto('/validation')
  const runButton = page.getByRole('button', { name: 'Run Validation' })
  await expect(runButton).toBeDisabled()
  await runButton.hover({ force: true })
  await expect(page.getByText('Select an experiment first')).toBeVisible()
})
