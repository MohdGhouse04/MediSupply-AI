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

test('Expiry Management search, filters and refresh work correctly', async ({ page }) => {
  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Expiry Management/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Expiry Management' })
  ).toBeVisible()

  const search = page.getByRole('textbox', {
    name: 'Search expiry recommendations',
  })
  const facility = page.getByRole('combobox', {
    name: 'Filter by facility',
  })
  const coverage = page.getByRole('combobox', {
    name: 'Filter forecast coverage',
  })
  const rows = page.locator('.expiry-table tbody tr')

  await expect(rows.first()).toBeVisible()

  const initialCount = await rows.count()
  expect(initialCount).toBeGreaterThan(0)
  console.log('INITIAL EXPIRY ROWS:', initialCount)

  // Search by batch number.
  const batchNumber = (
    await rows.first().locator('td').nth(2).innerText()
  ).trim()

  await search.fill(batchNumber)
  const batchSearchCount = await rows.count()
  expect(batchSearchCount).toBeGreaterThan(0)

  for (let i = 0; i < batchSearchCount; i++) {
    await expect(rows.nth(i).locator('td').nth(2))
      .toContainText(batchNumber)
  }

  console.log('PASS: Batch search:', batchNumber, 'Matching rows:', batchSearchCount)

  // Search empty state.
  await search.fill('NO_MATCH_EXPIRY_987654')
  await expect(rows).toHaveCount(0)
  await expect(
    page.getByText('No batch recommendations match your filters.')
  ).toBeVisible()
  console.log('PASS: Empty search state')

  await search.clear()

  // Facility filter.
  const facilityOptions = await facility.locator('option').allTextContents()
  const selectedFacility = facilityOptions.find(
    name => name.trim() !== 'All facilities'
  )
  expect(selectedFacility).toBeTruthy()

  await facility.selectOption({ label: selectedFacility!.trim() })
  const facilityCount = await rows.count()
  expect(facilityCount).toBeGreaterThan(0)

  for (let i = 0; i < facilityCount; i++) {
    await expect(rows.nth(i).locator('td').nth(1))
      .toHaveText(selectedFacility!.trim())
  }
  console.log('PASS: Facility filter:', selectedFacility)

  await facility.selectOption('ALL')

  // Forecast coverage filters.
  await coverage.selectOption('COVERED')
  const coveredCount = await rows.count()

  for (let i = 0; i < coveredCount; i++) {
    await expect(rows.nth(i).locator('.coverage-badge'))
      .toHaveText('Estimated')
  }
  console.log('PASS: Covered forecast filter:', coveredCount)

  await coverage.selectOption('INSUFFICIENT')
  const insufficientCount = await rows.count()

  for (let i = 0; i < insufficientCount; i++) {
    await expect(rows.nth(i).locator('.coverage-badge'))
      .toHaveText('Insufficient')
  }
  console.log('PASS: Insufficient forecast filter:', insufficientCount)

  expect(coveredCount + insufficientCount).toBe(initialCount)

  // Combined facility and coverage filters.
  await coverage.selectOption('ALL')
  await facility.selectOption({ label: selectedFacility!.trim() })
  await search.fill(batchNumber)

  await expect(rows).toHaveCount(1)
  await expect(rows.first().locator('td').nth(1))
    .toHaveText(selectedFacility!.trim())
  console.log('PASS: Combined filters')

  // Refresh API.
  await search.clear()
  await facility.selectOption('ALL')

  const refreshResponse = page.waitForResponse(response =>
    response.url().includes('/expiry-management/recommendations') &&
    response.request().method() === 'GET'
  )

  await page.getByRole('button', { name: /Refresh data/ }).click()

  const response = await refreshResponse
  expect(response.status()).toBe(200)

  await expect(rows).toHaveCount(initialCount)
  console.log('PASS: Expiry recommendations refresh')
  console.log('FINAL EXPIRY ROWS:', await rows.count())
})

test('Demand Forecast horizon, filters and refresh work correctly', async ({ page }) => {
  const forecastRequests: string[] = []

  page.on('request', request => {
    if (request.url().includes('/demand-forecasts/')) {
      forecastRequests.push(request.url())
    }
  })

  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Demand Forecast/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Demand Forecast' })
  ).toBeVisible()

  const facility = page.locator('#forecast-facility')
  const medicine = page.locator('#forecast-medicine')
  const refresh = page.getByRole('button', { name: 'Live forecast data' })

  await expect(facility.locator('option').nth(1)).toBeAttached()
  await expect(medicine.locator('option').nth(1)).toBeAttached()

  await expect(page.locator('.forecast-details-grid')).toBeVisible()
  await expect(page.getByText('7-day demand prediction')).toBeVisible()

  // Test forecast horizons.
  for (const days of [14, 30, 60, 7]) {
    const requestCount = forecastRequests.length

    await page.getByRole('button', {
      name: `${days} days`,
      exact: true,
    }).click()

    await expect(page.locator('.forecast-period-label'))
      .toHaveText(`${days}-DAY HORIZON`)

    await expect.poll(() => forecastRequests.length)
      .toBeGreaterThan(requestCount)

    await expect(page.getByText(`${days}-day demand prediction`))
      .toBeVisible()

    console.log(`PASS: ${days}-day forecast horizon`)
  }

  // Test facility filter.
  const facilityOption = await facility.locator('option').nth(1).getAttribute('value')
  const facilityName = (await facility.locator('option').nth(1).innerText()).trim()

  const beforeFacility = forecastRequests.length
  await facility.selectOption(facilityOption!)

  await expect.poll(() => forecastRequests.length)
    .toBeGreaterThan(beforeFacility)

  await expect(page.locator('.forecast-details-grid'))
    .toContainText(facilityName)

  console.log('PASS: Facility filter:', facilityName)

  // Test medicine filter.
  const medicineOption = await medicine.locator('option').nth(1).getAttribute('value')
  const medicineName = (await medicine.locator('option').nth(1).innerText()).trim()

  const beforeMedicine = forecastRequests.length
  await medicine.selectOption(medicineOption!)

  await expect.poll(() => forecastRequests.length)
    .toBeGreaterThan(beforeMedicine)

  await expect(page.locator('.forecast-details-grid'))
    .toContainText(medicineName.split(' · ')[0])

  console.log('PASS: Medicine filter:', medicineName)

  // Test refresh triggers a new API request.
  const beforeRefresh = forecastRequests.length

  await refresh.click()

  await expect.poll(() => forecastRequests.length)
    .toBeGreaterThan(beforeRefresh)

  await expect(refresh).toBeEnabled()
  console.log('PASS: Manual forecast refresh')

  // Reset filters.
  await facility.selectOption('ALL')
  await medicine.selectOption('ALL')

  await expect(page.locator('.forecast-period-label'))
    .toHaveText('7-DAY HORIZON')

  console.log('PASS: Forecast filters reset')
})

test('Facilities selection, filtering, clearing and refresh work correctly', async ({ page }) => {
  const facilityRequests: string[] = []

  page.on('request', request => {
    const url = request.url()

    if (
      url.includes('/facilities/') ||
      url.includes('/inventory/') ||
      url.includes('/transactions/summary/facilities')
    ) {
      facilityRequests.push(url)
    }
  })

  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Facilities/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Facilities' })
  ).toBeVisible()

  const cards = page.locator('.facility-card')
  const tableRows = page.locator('.facility-inventory-panel tbody tr')
  const activityRows = page.locator('.facility-activity-row')

  await expect(cards.first()).toBeVisible()
  await expect(tableRows.first()).toBeVisible()

  const initialCardCount = await cards.count()
  const initialTableCount = await tableRows.count()

  expect(initialCardCount).toBeGreaterThan(0)
  expect(initialTableCount).toBeGreaterThan(0)

  console.log('INITIAL FACILITY CARDS:', initialCardCount)
  console.log('INITIAL INVENTORY ROWS:', initialTableCount)

  // Select the first facility.
  const firstCard = cards.first()
  const facilityName = (await firstCard.locator('h2').innerText()).trim()

  await firstCard.click()

  await expect(firstCard).toHaveClass(/selected/)
  await expect(page.getByRole('button', {
    name: 'Clear facility filter',
  })).toBeVisible()

  await expect(activityRows).toHaveCount(1)
  await expect(tableRows.first().locator('td').first())
    .toHaveText(facilityName)

  await expect(tableRows).toHaveCount(
    await tableRows.count()
  )

  for (const row of await tableRows.all()) {
    await expect(row.locator('td').first()).toHaveText(facilityName)
  }

  console.log('PASS: Facility selection filters inventory and activity:', facilityName)

  // Select the same card again to toggle the filter off.
  await firstCard.click()

  await expect(firstCard).not.toHaveClass(/selected/)
  await expect(page.getByRole('button', {
    name: 'Clear facility filter',
  })).toHaveCount(0)

  await expect(cards).toHaveCount(initialCardCount)
  await expect(tableRows).toHaveCount(initialTableCount)

  console.log('PASS: Clicking selected facility clears filter')

  // Select again and use the explicit clear button.
  await firstCard.click()

  await expect(page.getByRole('button', {
    name: 'Clear facility filter',
  })).toBeVisible()

  await page.getByRole('button', {
    name: 'Clear facility filter',
  }).click()

  await expect(firstCard).not.toHaveClass(/selected/)
  await expect(tableRows).toHaveCount(initialTableCount)

  console.log('PASS: Clear facility filter restores all inventory')

  // Verify refresh calls all three APIs.
  const beforeRefresh = facilityRequests.length

  await page.getByRole('button', {
    name: 'Refresh data',
  }).click()

  await expect.poll(() =>
    facilityRequests.length - beforeRefresh
  ).toBeGreaterThanOrEqual(3)

  await expect(page.getByRole('button', {
    name: 'Refresh data',
  })).toBeEnabled()

  expect(facilityRequests.slice(beforeRefresh)).toEqual(
    expect.arrayContaining([
      expect.stringContaining('/facilities/'),
      expect.stringContaining('/inventory/'),
      expect.stringContaining('/transactions/summary/facilities'),
    ])
  )

  await expect(tableRows).toHaveCount(initialTableCount)

  console.log('PASS: Refresh reloads all three facility APIs')
  console.log('FINAL INVENTORY ROWS:', await tableRows.count())
})


test('Transfers search, status filter, refresh and form controls work correctly', async ({ page }) => {
  const transferRequests: string[] = []

  page.on('request', request => {
    const url = request.url()

    if (
      url.includes('/stock-transfers/') ||
      url.includes('/facilities/') ||
      url.includes('/inventory/')
    ) {
      transferRequests.push(url)
    }
  })

  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Transfers/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Inter-facility Transfers' })
  ).toBeVisible()

  const rows = page.locator('.inventory-table tbody tr')
  const search = page.getByPlaceholder('Search transfer ID, batch or remarks')
  const status = page.locator('.table-toolbar select')

  await expect(page.getByText('TOTAL TRANSFERS', { exact: true })).toBeVisible()

  await expect.poll(() => rows.count(), {
    timeout: 15000,
  }).toBeGreaterThan(0)

  const initialRows = await rows.count()
  expect(initialRows).toBeGreaterThan(0)

  console.log('INITIAL TRANSFER ROWS:', initialRows)

  // Search by the first transfer ID.
  const firstTransferId = (
    await rows.first().locator('td').first().innerText()
  ).trim()

  await search.fill(firstTransferId.replace('TR-', ''))

  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText(firstTransferId)

  console.log('PASS: Transfer ID search:', firstTransferId)

  // Verify empty search results.
  await search.fill('NO-MATCH-TRANSFER-99999')

  await expect(
    page.getByText('No transfer records match these filters.')
  ).toBeVisible()

  console.log('PASS: Empty search state')

  // Reset search and test status filtering.
  await search.clear()
  await status.selectOption('PENDING')

  for (const row of await rows.all()) {
    await expect(row.locator('td').nth(5)).toContainText('PENDING')
  }

  console.log('PASS: Pending status filter')

  await status.selectOption('ALL')
  await expect(rows).toHaveCount(initialRows)

  console.log('PASS: Status filter reset')

  // Verify refresh reloads transfer, facility, inventory and recommendation data.
  const beforeRefresh = transferRequests.length

  await page.getByRole('button', { name: 'Refresh' }).click()

  await expect.poll(() =>
    transferRequests.length - beforeRefresh
  ).toBeGreaterThanOrEqual(4)

  expect(transferRequests.slice(beforeRefresh)).toEqual(
    expect.arrayContaining([
      expect.stringContaining('/stock-transfers/?'),
      expect.stringContaining('/facilities/'),
      expect.stringContaining('/inventory/'),
      expect.stringContaining('/stock-transfers/recommendations'),
    ])
  )

  await expect(rows).toHaveCount(initialRows)

  console.log('PASS: Refresh reloads all four API requests')

  // Open the new transfer form.
  await page.getByRole('button', { name: 'New transfer' }).click()

  await expect(
    page.getByRole('heading', { name: 'Create transfer request' })
  ).toBeVisible()

  const source = page.getByLabel('Source facility')
  const destination = page.getByLabel('Destination facility')
  const batch = page.getByLabel('Source batch')
  const quantity = page.getByLabel('Quantity')
  const remarks = page.getByLabel('Remarks')

  const sourceOptions = await source.locator('option').count()
  expect(sourceOptions).toBeGreaterThan(1)

  const sourceValue = await source.locator('option').nth(1).getAttribute('value')
  expect(sourceValue).toBeTruthy()

  await source.selectOption(sourceValue!)

  // Destination must not include the selected source facility.
  const destinationValues = await destination.locator('option').evaluateAll(
    options => options.map(option => (option as HTMLOptionElement).value)
  )

  expect(destinationValues).not.toContain(sourceValue)

  console.log('PASS: Destination excludes selected source facility')

  // Verify available batches are loaded for the selected source.
  const batchOptions = await batch.locator('option').count()
  expect(batchOptions).toBeGreaterThan(1)

  console.log('PASS: Available source batches loaded:', batchOptions - 1)

  await quantity.fill('2')
  await remarks.fill('Playwright read-only form test')

  await expect(quantity).toHaveValue('2')
  await expect(remarks).toHaveValue('Playwright read-only form test')

  console.log('PASS: Quantity and remarks inputs')

  // Cancel without submitting; no backend mutation.
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()

  await expect(
    page.getByRole('heading', { name: 'Create transfer request' })
  ).toHaveCount(0)

  console.log('PASS: Form cancellation without submission')
})

test('Procurement search, filters, refresh and purchase order form work correctly', async ({ page }) => {
  const procurementRequests: string[] = []

  page.on('request', request => {
    const url = request.url()

    if (
      url.includes('/purchase-orders/') ||
      url.includes('/facilities/') ||
      url.includes('/suppliers/') ||
      url.includes('/medicines/') ||
      url.includes('/procurement/summary') ||
      url.includes('/procurement/recommendations')
    ) {
      procurementRequests.push(url)
    }
  })

  await page.goto('/')

  await page.locator('.sidebar').getByRole('button', {
    name: /^Procurement/,
  }).click()

  await expect(
    page.getByRole('heading', { name: 'Procurement Management' })
  ).toBeVisible()

  const search = page.getByPlaceholder('Search PO number or remarks')
  const status = page.locator('.table-toolbar select')
  const rows = page.locator('.inventory-table tbody tr').last()

  await expect(
    page.getByText('PROCUREMENT NEEDS', { exact: true })
  ).toBeVisible()

  await expect.poll(async () =>
    page.locator('h2').filter({ hasText: 'Purchase order register' }).count()
  ).toBe(1)

  await expect.poll(async () =>
    procurementRequests.filter(url => url.includes('/purchase-orders/?')).length
  ).toBeGreaterThan(0)

  const register = page.locator('.panel').filter({
    has: page.getByRole('heading', { name: 'Purchase order register' }),
  })

  await expect.poll(() => register.locator('tbody tr').count(), {
    timeout: 15000,
  }).toBeGreaterThan(0)

  const initialRows = await register.locator('tbody tr').count()
  expect(initialRows).toBeGreaterThan(0)

  console.log('INITIAL PURCHASE ORDER ROWS:', initialRows)

  // Search by purchase order number.
  const registerRows = register.locator('tbody tr')
  const firstOrderId = (
    await registerRows.first().locator('td').first().innerText()
  ).trim()

  await search.fill(firstOrderId.replace('PO-', ''))

  await expect(registerRows).toHaveCount(1)
  await expect(registerRows.first()).toContainText(firstOrderId)

  console.log('PASS: Purchase order search:', firstOrderId)

  // Empty search.
  await search.fill('NO-MATCH-PO-99999')

  await expect(
    page.getByText('No purchase orders match these filters.')
  ).toBeVisible()

  console.log('PASS: Empty search state')

  // Status filtering.
  await search.clear()
  await status.selectOption('DRAFT')

  for (const row of await registerRows.all()) {
    await expect(row.locator('td').nth(6)).toContainText('DRAFT')
  }

  console.log('PASS: Draft status filter')

  await status.selectOption('ALL')
  await expect(registerRows).toHaveCount(initialRows)

  console.log('PASS: Status filter reset')

  // Refresh all six Procurement APIs.
  const beforeRefresh = procurementRequests.length

  await page.getByRole('button', { name: 'Refresh' }).click()

  await expect.poll(() =>
    procurementRequests.length - beforeRefresh
  ).toBeGreaterThanOrEqual(6)

  expect(procurementRequests.slice(beforeRefresh)).toEqual(
    expect.arrayContaining([
      expect.stringContaining('/purchase-orders/?'),
      expect.stringContaining('/facilities/'),
      expect.stringContaining('/suppliers/'),
      expect.stringContaining('/medicines/'),
      expect.stringContaining('/procurement/summary'),
      expect.stringContaining('/procurement/recommendations'),
    ])
  )

  await expect(registerRows).toHaveCount(initialRows)

  console.log('PASS: Refresh reloads all six APIs')

  // Open purchase-order form.
  await page.getByRole('button', { name: 'New purchase order' }).click()

  await expect(
    page.getByRole('heading', { name: 'Create purchase order' })
  ).toBeVisible()

  const facility = page.getByLabel('Receiving facility')
  const supplier = page.getByLabel('Supplier')
  const deliveryDate = page.getByLabel('Expected delivery date')
  const remarks = page.getByPlaceholder('Optional order notes')

  expect(await facility.locator('option').count()).toBeGreaterThan(1)
  expect(await supplier.locator('option').count()).toBeGreaterThan(1)

  console.log('PASS: Facility and supplier options loaded')

  await facility.selectOption({ index: 1 })
  await supplier.selectOption({ index: 1 })

  await deliveryDate.fill('2026-12-15')
  await remarks.fill('Playwright read-only procurement form test')

  const lineItems = page.locator('.po-line-item')

  await expect(lineItems).toHaveCount(1)

  // Add a second medicine line.
  await page.getByRole('button', { name: 'Add medicine' }).click()

  await expect(lineItems).toHaveCount(2)

  console.log('PASS: Add medicine line')

  // Remove the second line without submitting.
  await lineItems.nth(1).getByRole('button', { name: 'Remove item' }).click()

  await expect(lineItems).toHaveCount(1)

  console.log('PASS: Remove medicine line')

  // Fill the first medicine line.
  const medicine = lineItems.nth(0).getByLabel('Medicine')
  const quantity = lineItems.nth(0).getByLabel('Quantity')
  const unitCost = lineItems.nth(0).getByLabel('Unit cost (₹)')

  expect(await medicine.locator('option').count()).toBeGreaterThan(1)

  await medicine.selectOption({ index: 1 })
  await quantity.fill('10')
  await unitCost.fill('25')

  await expect(quantity).toHaveValue('10')
  await expect(unitCost).toHaveValue('25')

  await expect(page.locator('.po-total')).toContainText('₹250')

  console.log('PASS: Medicine, quantity, unit cost and estimated total')

  await expect(remarks).toHaveValue('Playwright read-only procurement form test')

  // Cancel without creating a purchase order.
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()

  await expect(
    page.getByRole('heading', { name: 'Create purchase order' })
  ).toHaveCount(0)

  console.log('PASS: Form cancellation without submission')
})
