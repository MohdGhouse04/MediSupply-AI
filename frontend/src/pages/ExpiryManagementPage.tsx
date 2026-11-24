import { API_BASE } from '../services/apiBase'
import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, CalendarClock, CheckCircle2,
  Clock3, Package, RefreshCw, Search
} from 'lucide-react'

type Recommendation = {
  facility_id: number
  facility_name: string
  medicine_id: number
  generic_name: string
  strength: string
  batch_id: number
  batch_number: string
  expires_on: string
  usable_stock: number
  projected_wastage_units: number | null
  estimated_wastage_value: number | null
  forecast_status: string
  recommendation: string
}

type ExpiryResponse = {
  forecast_model: string
  forecast_horizon_days: number
  forecast_file: string
  total_batches_reviewed: number
  batches_with_insufficient_forecast: number
  estimated_wastage_units: number
  estimated_wastage_value: number
  recommendations: Recommendation[]
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

function formatCurrency(value: number | null) {
  if (value === null) return 'Not estimated'
  return value.toLocaleString('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  })
}

function expiryDays(value: string) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const expiry = new Date(`${value}T00:00:00`)
  return Math.ceil((expiry.getTime() - today.getTime()) / 86400000)
}

export default function ExpiryManagementPage() {
  const [data, setData] = useState<ExpiryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [facility, setFacility] = useState('ALL')
  const [coverage, setCoverage] = useState('ALL')

  async function loadRecommendations() {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/expiry-management/recommendations`, {
        headers: { Accept: 'application/json' },
      })

      if (!response.ok) {
        throw new Error(`Expiry API returned ${response.status}: ${await response.text()}`)
      }

      setData(await response.json() as ExpiryResponse)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load expiry recommendations.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRecommendations()
  }, [])

  const facilities = useMemo(
    () => [...new Set((data?.recommendations ?? []).map((item) => item.facility_name))].sort(),
    [data]
  )

  const filtered = useMemo(() => {
    const query = search.toLowerCase().trim()

    return (data?.recommendations ?? []).filter((item) => {
      const matchesSearch =
        !query ||
        item.generic_name.toLowerCase().includes(query) ||
        item.batch_number.toLowerCase().includes(query) ||
        item.facility_name.toLowerCase().includes(query)

      const matchesFacility = facility === 'ALL' || item.facility_name === facility

      const matchesCoverage =
        coverage === 'ALL' ||
        (coverage === 'COVERED' && item.forecast_status === 'ESTIMATED_WITHIN_60_DAY_FORECAST') ||
        (coverage === 'INSUFFICIENT' && item.forecast_status === 'INSUFFICIENT_FORECAST_HORIZON')

      return matchesSearch && matchesFacility && matchesCoverage
    })
  }, [data, search, facility, coverage])

  const coveredCount = (data?.recommendations ?? []).filter(
    (item) => item.forecast_status === 'ESTIMATED_WITHIN_60_DAY_FORECAST'
  ).length

  const reviewCount = data?.batches_with_insufficient_forecast ?? 0

  return (
    <div className="page-content expiry-management-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><CalendarClock size={13} /> EXPIRY RISK MANAGEMENT</div>
          <h1>Expiry Management</h1>
          <p>Review batch-level wastage estimates and FEFO recommendations across facilities.</p>
        </div>
        <button className="date-filter" onClick={loadRecommendations} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
          Refresh data
        </button>
      </div>

      <div className="preview-notice expiry-model-notice">
        <Clock3 size={16} />
        <span>
          <strong>EXPERIMENTAL FORECAST</strong> — {data?.forecast_horizon_days ?? 60}-day demand forecast.
          Estimates are limited to the available forecast coverage.
        </span>
      </div>

      {data && reviewCount > 0 && (
        <div className="expiry-coverage-warning">
          <AlertTriangle size={19} />
          <div>
            <strong>{reviewCount} batches have insufficient forecast coverage</strong>
            <span>
              Their expiry dates extend beyond the {data.forecast_horizon_days}-day forecast horizon.
              Wastage is unknown, not zero. Review FEFO issuing and monitor these batches.
            </span>
          </div>
          <span className="coverage-count">{reviewCount} BATCHES</span>
        </div>
      )}

      <section className="kpi-grid expiry-kpis">
        <ExpiryMetric
          label="BATCHES REVIEWED"
          value={loading ? '…' : String(data?.total_batches_reviewed ?? '—')}
          icon={Package}
          color="blue"
          description="Active batch recommendations"
        />
        <ExpiryMetric
          label="ESTIMATED WASTAGE"
          value={loading ? '…' : `${(data?.estimated_wastage_units ?? 0).toLocaleString()} units`}
          icon={AlertTriangle}
          color="orange"
          description="Only within forecast coverage"
        />
        <ExpiryMetric
          label="ESTIMATED VALUE"
          value={loading ? '…' : formatCurrency(data?.estimated_wastage_value ?? 0)}
          icon={CalendarClock}
          color="purple"
          description="Projected wastage value"
        />
        <ExpiryMetric
          label="INSUFFICIENT COVERAGE"
          value={loading ? '…' : String(reviewCount)}
          icon={Clock3}
          color="green"
          description={`${coveredCount} batches covered by forecast`}
        />
      </section>

      <section className="panel expiry-table-panel">
        <div className="inventory-toolbar">
          <div>
            <h2>Batch Expiry Recommendations</h2>
            <p>{filtered.length} of {data?.total_batches_reviewed ?? 0} batches displayed</p>
          </div>

          <div className="inventory-filters">
            <div className="inventory-search">
              <Search size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search medicine, batch or facility..."
                aria-label="Search expiry recommendations"
              />
            </div>

            <select value={facility} onChange={(event) => setFacility(event.target.value)} aria-label="Filter by facility">
              <option value="ALL">All facilities</option>
              {facilities.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>

            <select value={coverage} onChange={(event) => setCoverage(event.target.value)} aria-label="Filter forecast coverage">
              <option value="ALL">All coverage statuses</option>
              <option value="COVERED">Within forecast</option>
              <option value="INSUFFICIENT">Insufficient coverage</option>
            </select>
          </div>
        </div>

        {error && <div className="inventory-error">{error}</div>}

        {loading ? (
          <div className="inventory-empty">Loading expiry recommendations…</div>
        ) : !error && filtered.length === 0 ? (
          <div className="inventory-empty">No batch recommendations match your filters.</div>
        ) : !error ? (
          <div className="inventory-table-wrapper">
            <table className="inventory-table expiry-table">
              <thead>
                <tr>
                  <th>MEDICINE</th>
                  <th>FACILITY</th>
                  <th>BATCH</th>
                  <th>EXPIRY DATE</th>
                  <th>USABLE STOCK</th>
                  <th>PROJECTED WASTAGE</th>
                  <th>ESTIMATED VALUE</th>
                  <th>FORECAST COVERAGE</th>
                  <th>RECOMMENDATION</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const insufficient = item.forecast_status === 'INSUFFICIENT_FORECAST_HORIZON'
                  const days = expiryDays(item.expires_on)

                  return (
                    <tr key={`${item.facility_id}-${item.batch_id}`}>
                      <td>
                        <div className="medicine-cell">
                          <strong>{item.generic_name}</strong>
                          <span>{item.strength}</span>
                        </div>
                      </td>
                      <td>{item.facility_name}</td>
                      <td><span className="batch-code">{item.batch_number}</span></td>
                      <td>
                        <div className="expiry-cell">
                          <strong>{formatDate(item.expires_on)}</strong>
                          <span className="expiry-date-remaining">
                            {days < 0 ? 'Expired' : `${days} days remaining`}
                          </span>
                        </div>
                      </td>
                      <td><strong>{item.usable_stock.toLocaleString()}</strong></td>
                      <td>
                        {insufficient ? (
                          <span className="unknown-estimate">Not estimated</span>
                        ) : (
                          <strong className={item.projected_wastage_units && item.projected_wastage_units > 0 ? 'zero-stock' : 'usable-stock'}>
                            {item.projected_wastage_units?.toLocaleString() ?? '—'} units
                          </strong>
                        )}
                      </td>
                      <td>{formatCurrency(item.estimated_wastage_value)}</td>
                      <td>
                        <span className={`coverage-badge ${insufficient ? 'coverage-insufficient' : 'coverage-valid'}`}>
                          {insufficient ? <AlertTriangle size={12} /> : <CheckCircle2 size={12} />}
                          {insufficient ? 'Insufficient' : 'Estimated'}
                        </span>
                      </td>
                      <td>
                        <span className={`expiry-recommendation ${insufficient ? 'recommend-review' : 'recommend-normal'}`}>
                          {item.recommendation === 'NORMAL_FEFO_ISSUING'
                            ? 'Normal FEFO'
                            : 'Review & monitor'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        <div className="inventory-table-footer">
          <span>Source: FastAPI · GET /expiry-management/recommendations</span>
          <span>{filtered.length} of {data?.total_batches_reviewed ?? 0} records</span>
        </div>
      </section>

      <div className="expiry-explanation">
        <div>
          <CheckCircle2 size={16} />
          <span><strong>Within forecast:</strong> projected wastage is estimated using demand and FEFO batch consumption.</span>
        </div>
        <div>
          <AlertTriangle size={16} />
          <span><strong>Insufficient coverage:</strong> expiry is beyond the forecast horizon. No wastage estimate is available.</span>
        </div>
      </div>

      <div className="stockout-method-note">
        <Clock3 size={15} />
        <span>
          Forecast model: {data?.forecast_model ?? '60-day demand forecast (experimental)'}.
          These are simulated-data planning estimates, not guaranteed future outcomes.
        </span>
      </div>
    </div>
  )
}

function ExpiryMetric({
  label, value, icon: Icon, color, description,
}: {
  label: string
  value: string
  icon: typeof Package
  color: string
  description: string
}) {
  return (
    <div className="panel kpi-card">
      <div className="kpi-top">
        <span>{label}</span>
        <div className={`kpi-icon ${color}`}><Icon size={19} /></div>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-unit">{description}</div>
    </div>
  )
}
