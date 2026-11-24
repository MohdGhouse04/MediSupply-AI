import { test, expect } from '@playwright/test'

const pages = [
  { name: 'Overview', heading: 'Supply Chain Overview' },
  { name: 'Inventory', heading: 'Medicine Inventory' },
  { name: 'Stockout Alerts', heading: 'Stockout Alerts' },
  { name: 'Expiry Management', heading: 'Expiry Management' },
  { name: 'Demand Forecast', heading: 'Demand Forecast' },
  { name: 'Facilities', heading: 'Facilities' },
  { name: 'Transfers', heading: 'Inter-facility Transfers' },
  { name: 'Procurement', heading: 'Procurement Management' },
]

test('diagnose Recharts container dimensions', async ({ page }) => {
  let currentPage = 'Initial load'
  const chartWarnings: string[] = []

  page.on('console', message => {
    if (
      message.type() === 'warning' &&
      message.text().toLowerCase().includes('width')
    ) {
      chartWarnings.push(`[${currentPage}] ${message.text()}`)
    }
  })

  await page.goto('/')

  for (const item of pages) {
    currentPage = item.name

    if (item.name !== 'Overview') {
      await page.locator('.sidebar').getByRole('button', {
        name: new RegExp(`^${item.name}`),
      }).click()
    }

    await expect(
      page.getByRole('heading', { name: item.heading, exact: true })
    ).toBeVisible()

    await page.waitForTimeout(800)

    const dimensions = await page.locator('.recharts-responsive-container').evaluateAll(
      elements => elements.map(element => {
        const rect = element.getBoundingClientRect()
        const parent = element.parentElement?.getBoundingClientRect()

        return {
          chart: {
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          },
          parent: parent ? {
            width: Math.round(parent.width),
            height: Math.round(parent.height),
          } : null,
          visible: rect.width > 0 && rect.height > 0,
        }
      })
    )

    console.log(`${item.name} CHART DIMENSIONS:`, JSON.stringify(dimensions))
  }

  console.log('RECHARTS WARNINGS:', JSON.stringify(chartWarnings, null, 2))
})

test('Inventory search, facility filter and refresh work correctly', async ({ page }) => {
  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Inventory/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Medicine Inventory' })
  ).toBeVisible()

  const search = page.getByRole('textbox', { name: 'Search inventory' })
  const facility = page.getByRole('combobox', { name: 'Filter by facility' })
  const rows = page.locator('.inventory-table tbody tr')

  await expect(rows.first()).toBeVisible()

  const initialCount = await rows.count()
  expect(initialCount).toBeGreaterThan(0)
  console.log('INITIAL INVENTORY ROWS:', initialCount)

  // Search by the first medicine name.
  const medicineName = (
    await rows.first().locator('td').nth(0).locator('strong').innerText()
  ).trim()

  await search.fill(medicineName)

  await expect(rows.first()).toBeVisible()

  const searchCount = await rows.count()
  expect(searchCount).toBeGreaterThan(0)

  for (let i = 0; i < searchCount; i++) {
    const rowText = await rows.nth(i).innerText()
    expect(rowText.toLowerCase()).toContain(medicineName.toLowerCase())
  }

  console.log('PASS: Medicine search:', medicineName)

  // Search for a value that should not exist.
  await search.fill('NO_MATCH_MEDICINE_987654')

  await expect(
    page.getByText('No inventory records match your filters.')
  ).toBeVisible()

  expect(await rows.count()).toBe(0)
  console.log('PASS: Empty search state')

  // Reset search and select an actual facility.
  await search.clear()

  const facilityOptions = await facility.locator('option').allTextContents()
  const selectedFacility = facilityOptions.find(
    name => name.trim() !== 'All facilities'
  )

  expect(selectedFacility).toBeTruthy()

  await facility.selectOption({ label: selectedFacility!.trim() })

  await expect(rows.first()).toBeVisible()

  const facilityCount = await rows.count()
  expect(facilityCount).toBeGreaterThan(0)

  for (let i = 0; i < facilityCount; i++) {
    await expect(rows.nth(i).locator('td').nth(1))
      .toHaveText(selectedFacility!.trim())
  }

  console.log('PASS: Facility filter:', selectedFacility)

  // Reset filters and verify refresh.
  await facility.selectOption({ label: 'All facilities' })

  const refreshResponse = page.waitForResponse(response =>
    response.url().includes('/api/inventory/') &&
    response.request().method() === 'GET'
  )

  await page.getByRole('button', { name: /Refresh data/ }).click()

  const response = await refreshResponse
  expect(response.status()).toBe(200)

  await expect(rows.first()).toBeVisible()
  expect(await rows.count()).toBe(initialCount)

  console.log('PASS: Inventory refresh')
  console.log('FINAL INVENTORY ROWS:', await rows.count())
})

test('Stockout Alerts search and filters work correctly', async ({ page }) => {
  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Stockout Alerts/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Stockout Alerts' })
  ).toBeVisible()

  const search = page.getByRole('textbox', {
    name: 'Search stockout alerts',
  })
  const risk = page.getByRole('combobox', {
    name: 'Filter by risk',
  })
  const acknowledgement = page.getByRole('combobox', {
    name: 'Filter by acknowledgement',
  })
  const rows = page.locator('.stockout-table tbody tr')

  await expect(rows).toHaveCount(8)

  // High-risk filter
  await risk.selectOption('HIGH_RISK')
  await expect(rows).toHaveCount(2)
  await expect(rows.locator('.risk-label')).toHaveText([
    'HIGH RISK',
    'HIGH RISK',
  ])
  console.log('PASS: High-risk filter')

  // Low-risk filter
  await risk.selectOption('LOW_RISK')
  await expect(rows).toHaveCount(6)
  console.log('PASS: Low-risk filter')

  // Pending acknowledgement filter
  await risk.selectOption('ALL')
  await acknowledgement.selectOption('PENDING')
  await expect(rows).toHaveCount(6)
  await expect(rows.locator('.pending-badge')).toHaveCount(6)
  console.log('PASS: Pending acknowledgement filter')

  // Acknowledged filter
  await acknowledgement.selectOption('ACKNOWLEDGED')
  await expect(rows).toHaveCount(2)
  await expect(rows.locator('.acknowledged-badge')).toHaveCount(2)
  console.log('PASS: Acknowledged filter')

  // Combined filters
  await risk.selectOption('HIGH_RISK')
  await acknowledgement.selectOption('ACKNOWLEDGED')
  await expect(rows).toHaveCount(2)
  console.log('PASS: Combined filters')

  // Search by medicine
  await risk.selectOption('ALL')
  await acknowledgement.selectOption('ALL')
  await search.fill('Amoxicillin')
  await expect(rows).toHaveCount(2)

  for (let i = 0; i < await rows.count(); i++) {
    await expect(rows.nth(i).locator('.medicine-cell strong'))
      .toHaveText('Amoxicillin')
  }
  console.log('PASS: Medicine search')

  // Search by facility
  await search.fill('Sangareddy')
  await expect(rows).toHaveCount(4)

  for (let i = 0; i < await rows.count(); i++) {
    await expect(rows.nth(i).locator('td').nth(1))
      .toHaveText('Sangareddy Community Pharmacy')
  }
  console.log('PASS: Facility search')

  // Empty search state
  await search.fill('NO_MATCH_ALERT_987654')
  await expect(rows).toHaveCount(0)
  await expect(
    page.getByText('No alerts match your filters.')
  ).toBeVisible()
  console.log('PASS: Empty search state')

  // Refresh
  await search.clear()

  const refreshResponse = page.waitForResponse(response =>
    response.url().includes('/stockout-alerts/') &&
    response.request().method() === 'GET'
  )

  await page.getByRole('button', { name: /Refresh alerts/ }).click()

  const response = await refreshResponse
  expect(response.status()).toBe(200)
  await expect(rows).toHaveCount(8)

  console.log('PASS: Stockout Alerts refresh')
})
