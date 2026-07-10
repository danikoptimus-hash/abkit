import { test, expect } from '@playwright/test'
import { loginViaUi } from './helpers'

// DB4 (CLAUDE.md, Database Connections feature): full round trip through
// the admin UI — create a connection, test it, then use it from the
// Datasets page's "From SQL" tab (preview + create), and finally design an
// experiment on the resulting dataset. Self-references the same postgres
// the docker compose stack already runs (reachable as "postgres" from
// INSIDE the backend container, which is what actually executes the SQL —
// not from this test runner). Skipped when E2E_POSTGRES_* isn't set (local
// dev without a matching .env-generated password) — see .github/workflows/ci.yml.
const PG = {
  host: process.env.E2E_POSTGRES_HOST,
  port: process.env.E2E_POSTGRES_PORT,
  user: process.env.E2E_POSTGRES_USER,
  password: process.env.E2E_POSTGRES_PASSWORD,
  db: process.env.E2E_POSTGRES_DB,
}

test('create a database connection, test it, preview SQL, create a dataset, and design on it', async ({ page }) => {
  test.skip(!PG.host || !PG.password, 'E2E_POSTGRES_* not set — see .github/workflows/ci.yml')
  test.setTimeout(60_000)
  // Regression guard: an uncaught render error anywhere in this flow (e.g.
  // the react-simple-code-editor/Prism crash this test caught during
  // development — see CreateDatasetModal.tsx's plain-textarea choice)
  // blanks the whole page instead of failing one assertion; fail loudly.
  const pageErrors: string[] = []
  page.on('pageerror', (err) => pageErrors.push(err.message))

  await loginViaUi(page)
  await page.goto('/admin/db-connections')

  const connectionName = `e2e_pg_${Date.now()}`
  await page.getByRole('button', { name: 'Database' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()

  await dialog.getByLabel('Host').fill(PG.host!)
  await dialog.getByLabel('Port').fill(PG.port!)
  await dialog.getByLabel('Database Name').fill(PG.db!)
  await dialog.getByLabel('Username').fill(PG.user!)
  await dialog.getByLabel('Password').fill(PG.password!)
  await dialog.getByLabel('Display Name').fill(connectionName)

  await dialog.getByRole('button', { name: 'Test connection' }).click()
  await expect(dialog.getByText('Connection successful')).toBeVisible({ timeout: 10_000 })

  await dialog.getByRole('button', { name: 'OK' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(connectionName) })).toBeVisible()

  // From SQL: select the connection, preview, create a dataset off the
  // app's own `users` table (guaranteed to exist and be non-empty — this
  // test itself just logged in as one).
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Dataset' }).click()
  await page.getByRole('tab', { name: 'From SQL' }).click()

  await page.getByRole('combobox', { name: 'from-sql-connection-select' }).click()
  await page.getByTitle(new RegExp(connectionName)).click()

  // Schema/table pickers (UX package, Datasets п.1.1/1.3): selecting a
  // table autofills the SQL box with "SELECT * FROM schema.table" — but
  // once the user edits it by hand, further table selections stop
  // clobbering that edit ("SQL is the source of truth").
  const schemaSelect = page.getByRole('combobox', { name: 'from-sql-schema-select' })
  await schemaSelect.click()
  await schemaSelect.fill('public')
  await page.getByTitle('public').click()

  const tableSelect = page.getByRole('combobox', { name: 'from-sql-table-select' })
  await tableSelect.click()
  await tableSelect.fill('users')
  await page.getByTitle('users', { exact: true }).click()

  const sqlBox = page.getByPlaceholder('SELECT user_id, revenue FROM events WHERE ...')
  await expect(sqlBox).toHaveValue('SELECT * FROM "public"."users"')

  // Manually edit — selecting a DIFFERENT table afterward must NOT
  // overwrite this (the app's own "experiments" table also always exists).
  await sqlBox.fill('SELECT * FROM "public"."users" LIMIT 1')
  await tableSelect.click()
  await tableSelect.fill('experiments')
  await page.getByTitle('experiments', { exact: true }).click()
  await expect(sqlBox).toHaveValue('SELECT * FROM "public"."users" LIMIT 1')

  await sqlBox.fill('SELECT id, email, role FROM users')
  await page.getByRole('button', { name: 'Preview' }).click()
  await expect(page.getByRole('columnheader', { name: 'email' })).toBeVisible({ timeout: 10_000 })

  const datasetName = `e2e_sql_dataset_${Date.now()}`
  await page.getByPlaceholder('e.g. active_users_30d').fill(datasetName)
  await page.getByRole('button', { name: 'Create dataset' }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 20_000 })

  const row = page.getByRole('row', { name: new RegExp(datasetName) })
  await expect(row).toBeVisible()
  // exact: the dataset's own filename contains "sql" as a substring too
  // (e2e_sql_dataset_...), and getByText matches case-insensitively.
  await expect(row.getByText('SQL', { exact: true })).toBeVisible()
  // Refresh icon present for source=sql (UX package, Datasets п.1.1a/1.5) —
  // hover-reveal like the rest of the app's row actions.
  await row.hover()
  await expect(row.getByRole('button', { name: 'Refresh' })).toBeVisible()

  // Preview drawer explains the snapshot semantics (UX package, Datasets
  // п.4.1) — deleting the source table doesn't touch the stored dataset.
  await row.click()
  await expect(page.getByText(/Snapshot stored in ABKit/)).toBeVisible()
  await page.keyboard.press('Escape')

  // Change the SQL's source table (a real, live change — insert a new user
  // via the admin API) before refreshing, then confirm Refresh actually
  // re-fetches: n_rows must reflect the new row count, not just show a
  // generic success toast (UX package, Datasets п.1.5).
  const datasetsBefore = await page.request.get('/api/v1/datasets?page_size=200')
  const beforeEntry = (await datasetsBefore.json()).items.find((d: { filename: string }) =>
    d.filename.startsWith(datasetName),
  )
  expect(beforeEntry).toBeTruthy()

  const newUserEmail = `e2e_refresh_probe_${Date.now()}@e2e.test`
  const createUserResp = await page.request.post('/api/v1/admin/users', {
    data: { email: newUserEmail, first_name: 'Refresh', last_name: 'Probe', role: 'viewer' },
  })
  expect(createUserResp.ok()).toBeTruthy()

  // Refresh re-runs the SQL against the live connection — requires
  // confirming a Modal first, doesn't fire immediately on click (UX
  // package, Datasets п.1.3).
  await row.hover()
  await row.getByRole('button', { name: 'Refresh' }).click()
  const confirmDialog = page.getByRole('dialog').filter({ hasText: 'Refresh dataset from source?' })
  await expect(confirmDialog).toBeVisible()
  await expect(confirmDialog.getByText(/replace the stored snapshot/)).toBeVisible()
  await confirmDialog.getByRole('button', { name: 'Refresh' }).click()
  await expect(page.getByText(/Refreshed:/)).toBeVisible({ timeout: 15_000 })

  const datasetsAfter = await page.request.get('/api/v1/datasets?page_size=200')
  const afterEntry = (await datasetsAfter.json()).items.find((d: { filename: string }) =>
    d.filename.startsWith(datasetName),
  )
  expect(afterEntry.n_rows).toBe(beforeEntry.n_rows + 1)

  // Design an experiment picking this dataset — proves it round-trips
  // through the exact same path a file upload would (DB3).
  await page.goto('/experiments/new')
  await page.getByRole('combobox', { name: 'design-dataset-select' }).click()
  await page.getByRole('combobox', { name: 'design-dataset-select' }).fill(datasetName)
  await page.getByTitle(new RegExp(datasetName)).click()
  await expect(page.getByText(/Data loaded:/)).toBeVisible({ timeout: 10_000 })

  expect(pageErrors).toEqual([])
})
