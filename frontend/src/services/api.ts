import { API_BASE } from './apiBase'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(`${path} returned ${response.status}: ${message}`)
  }

  return response.json() as Promise<T>
}

export type OverviewData = {
  health: { status: string; service: string }
  inventory: {
    medicine_id: number
    generic_name: string
    strength: string
    total_usable_stock: number
  }[]
  facilities: {
    facility_id: number
    facility_name: string
    facility_type: string
    city: string
    state: string
  }[]
  stockout: {
    total_alerts: number
    high_risk_count: number
    low_risk_count: number
    acknowledged_count: number
    unacknowledged_count: number
    source_date: string | null
    freshness_status: string
    is_stale: boolean
    alerts: {
      alert_id: number
      medicine: string
      strength: string
      facility_name: string
      stockout_probability: number
      risk_status: string
      acknowledged: boolean
    }[]
  }
  expiry: {
    forecast_horizon_days: number
    total_batches_reviewed: number
    batches_with_insufficient_forecast: number
    estimated_wastage_units: number
    estimated_wastage_value: number
  }
}

export async function fetchOverviewData(): Promise<OverviewData> {
  const [health, inventory, facilities, stockout, expiry] = await Promise.all([
    getJson<OverviewData['health']>('/health'),
    getJson<OverviewData['inventory']>('/inventory/summary/medicines'),
    getJson<OverviewData['facilities']>('/facilities/'),
    getJson<OverviewData['stockout']>('/stockout-alerts/'),
    getJson<OverviewData['expiry']>('/expiry-management/recommendations'),
  ])

  return { health, inventory, facilities, stockout, expiry }
}
