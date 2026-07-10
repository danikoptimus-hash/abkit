import { test, expect } from '@playwright/test'
import { loginViaUi, seedExperiment } from './helpers'

// 5-part package pt.3: Redesign for 'designed'-status experiments — the
// wizard opens pre-filled, submitting replaces the split in place (same
// experiment), and the action disappears entirely once running.

test('Redesign replaces the split in place; the Redesign action is gone once running', async ({
  page,
  request,
}) => {
  const name = `redesign_e2e_${Date.now()}`
  await seedExperiment(request, name)
  await loginViaUi(page)
  await page.goto(`/experiments/${name}`)

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByText('Redesign', { exact: true }).click()

  const confirmDialog = page.getByRole('dialog').filter({ hasText: 'Redesign this experiment?' })
  await expect(confirmDialog).toBeVisible()
  await expect(confirmDialog.getByText(/Analyses already run against the old split will be deleted/)).toBeVisible()
  await confirmDialog.getByRole('button', { name: 'Continue' }).click()

  await expect(page).toHaveURL(new RegExp(`/experiments/${name}/redesign$`))
  await expect(page.getByText(`Redesigning "${name}"`)).toBeVisible()

  // Pre-filled — dataset carried over from the existing config, already
  // selected on step 0 (Data).
  await expect(page.getByText('Data loaded:')).toBeVisible()

  // Step 1 (Groups & Metrics) is where the name field lives — pre-filled
  // and locked, since a redesign can't rename the experiment.
  await page.getByRole('button', { name: 'Next' }).click()
  await expect(page.getByPlaceholder('Experiment name')).toHaveValue(name)
  await expect(page.getByPlaceholder('Experiment name')).toBeDisabled()

  await page.getByRole('button', { name: 'Next' }).click()
  await page.getByRole('button', { name: 'Next' }).click()
  await page.getByRole('button', { name: 'Redesign' }).click()

  await expect(page).toHaveURL(new RegExp(`/experiments/${name}$`), { timeout: 15_000 })
  await expect(page.getByRole('heading', { name })).toBeVisible()

  // Move to running — the Redesign menu item must disappear entirely (not
  // merely disabled), per pt.3.4.
  await page.getByText('designed', { exact: true }).click()
  await page.getByText('Move to running').click()
  await expect(page.getByText('running', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'More actions' }).click()
  await expect(page.getByText('Redesign', { exact: true })).not.toBeVisible()
})
