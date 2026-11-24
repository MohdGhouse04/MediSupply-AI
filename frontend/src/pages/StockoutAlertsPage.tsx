import { API_BASE } from '../services/apiBase'
import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, Clock3, RefreshCw,
  Search, ShieldAlert, ShieldCheck
} from 'lucide-react'

type StockoutAlert = {
  alert_id: number
  date: string
  facility_id: number
  facility_name: string
  medicine_id: number
  medicine: string
  strength: string
  dosage_form: string
  stockout_probability: number
  risk_threshold: number
  risk_status: string
  alert_action: string
  previous_stock: number
  previous_unmet_demand: number
  average_demand_7_days: number
  average_demand_14_days: number
  average_demand_30_days: number
  acknowledged: boolean
  acknowledged_by: string | null
  acknowledged_at: string | null
  source_age_days: number
  freshness_status: string
  is_stale: boolean
}

type AlertResponse = {
  total_alerts: number
  high_risk_count: number
  low_risk_count: number
  acknowledged_count: number
  unacknowledged_count: number
  source_date: string | null
  source_age_days: number
  max_allowed_age_days: number
  freshness_status: string
  is_stale: boolean
  alerts: StockoutAlert[]
}

const API = API_BASE

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

function formatTimestamp(value: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function StockoutAlertsPage() {
  const [data, setData] = useState<AlertResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [ackFilter, setAckFilter] = useState('ALL')
  const [operator, setOperator] = useState('Inventory Manager')
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadAlerts() {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API}/stockout-alerts/`, {
        headers: { Accept: 'application/json' },
      })
      if (!response.ok) {
        throw new Error(`Stockout API returned ${response.status}: ${await response.text()}`)
      }
      setData(await response.json() as AlertResponse)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load stockout alerts.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAlerts()
  }, [])

  async function acknowledgeAlert(alertId: number) {
    const acknowledgedBy = operator.trim()

    if (!acknowledgedBy) {
      setActionMessage('Enter the operator name before acknowledging an alert.')
      return
    }

    setAcknowledgingId(alertId)
    setActionMessage(null)

    try {
      const response = await fetch(`${API}/stockout-alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
      })

      if (!response.ok) {
        throw new Error(`Acknowledgement failed (${response.status}): ${await response.text()}`)
      }

      setActionMessage(`Alert #${alertId} acknowledged successfully.`)
      await loadAlerts()
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : 'Unable to acknowledge alert.')
    } finally {
      setAcknowledgingId(null)
    }
  }

  const filteredAlerts = useMemo(() => {
    const query = search.toLowerCase().trim()

    return [...(data?.alerts ?? [])]
      .filter((alert) => {
        const matchesSearch =
          !query ||
          alert.medicine.toLowerCase().includes(query) ||
          alert.strength.toLowerCase().includes(query) ||
          alert.facility_name.toLowerCase().includes(query)

        const matchesRisk = riskFilter === 'ALL' || alert.risk_status === riskFilter
        const matchesAck =
          ackFilter === 'ALL' ||
          (ackFilter === 'ACKNOWLEDGED' && alert.acknowledged) ||
          (ackFilter === 'PENDING' && !alert.acknowledged)

        return matchesSearch && matchesRisk && matchesAck
      })
      .sort((a, b) => b.stockout_probability - a.stockout_probability)
  }, [data, search, riskFilter, ackFilter])

  return (
    <div className="page-content stockout-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><ShieldAlert size={13} /> PREDICTIVE RISK MONITORING</div>
          <h1>Stockout Alerts</h1>
          <p>Review model-generated stockout risks and record operational acknowledgement.</p>
        </div>
        <button className="date-filter" onClick={loadAlerts} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
          Refresh alerts
        </button>
      </div>

      {data?.is_stale && (
        <div className="stockout-freshness-warning">
          <AlertTriangle size={19} />
          <div>
            <strong>Stockout data is stale — review before acting</strong>
            <span>
              Source date: {formatDate(data.source_date)} · {data.source_age_days} days old.
              Maximum allowed age: {data.max_allowed_age_days} days.
              These predictions may not reflect current inventory.
            </span>
          </div>
          <span className="freshness-badge stale">STALE DATA</span>
        </div>
      )}

      {data && !data.is_stale && (
        <div className="stockout-freshness-ok">
          <CheckCircle2 size={17} />
          <span>Alert data is {data.freshness_status.toLowerCase()} · Source date: {formatDate(data.source_date)}</span>
        </div>
      )}

      <section className="kpi-grid stockout-kpis">
        <AlertMetric
          label="TOTAL ALERTS"
          value={loading ? '…' : String(data?.total_alerts ?? '—')}
          icon={AlertTriangle}
          color="blue"
          description="Current model-generated records"
        />
        <AlertMetric
          label="HIGH RISK"
          value={loading ? '…' : String(data?.high_risk_count ?? '—')}
          icon={ShieldAlert}
          color="orange"
          description="Above the configured risk threshold"
        />
        <AlertMetric
          label="LOW RISK"
          value={loading ? '…' : String(data?.low_risk_count ?? '—')}
          icon={ShieldCheck}
          color="green"
          description="Below the configured risk threshold"
        />
        <AlertMetric
          label="PENDING REVIEW"
          value={loading ? '…' : String(data?.unacknowledged_count ?? '—')}
          icon={Clock3}
          color="purple"
          description={`${data?.acknowledged_count ?? 0} acknowledged`}
        />
      </section>

      <section className="panel stockout-table-panel">
        <div className="inventory-toolbar stockout-toolbar">
          <div>
            <h2>Alert Register</h2>
            <p>{filteredAlerts.length} of {data?.total_alerts ?? 0} alerts displayed</p>
          </div>
          <div className="inventory-filters">
            <div className="inventory-search">
              <Search size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search medicine or facility..."
                aria-label="Search stockout alerts"
              />
            </div>
            <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value)} aria-label="Filter by risk">
              <option value="ALL">All risk levels</option>
              <option value="HIGH_RISK">High risk</option>
              <option value="LOW_RISK">Low risk</option>
            </select>
            <select value={ackFilter} onChange={(event) => setAckFilter(event.target.value)} aria-label="Filter by acknowledgement">
              <option value="ALL">All statuses</option>
              <option value="PENDING">Pending review</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
            </select>
          </div>
        </div>

        <div className="stockout-operator">
          <label htmlFor="operator-name">Acknowledging operator</label>
          <input
            id="operator-name"
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            maxLength={150}
            placeholder="Enter operator name"
          />
          <span>Recorded by the backend when an alert is acknowledged.</span>
        </div>

        {actionMessage && (
          <div className="stockout-action-message" role="status">{actionMessage}</div>
        )}
        {error && <div className="inventory-error">{error}</div>}

        {loading ? (
          <div className="inventory-empty">Loading stockout alerts…</div>
        ) : !error && filteredAlerts.length === 0 ? (
          <div className="inventory-empty">No alerts match your filters.</div>
        ) : !error ? (
          <div className="inventory-table-wrapper">
            <table className="inventory-table stockout-table">
              <thead>
                <tr>
                  <th>MEDICINE</th>
                  <th>FACILITY</th>
                  <th>RISK PROBABILITY</th>
                  <th>RISK LEVEL</th>
                  <th>STOCK</th>
                  <th>AVG. DEMAND / DAY</th>
                  <th>REVIEW STATUS</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((alert) => {
                  const high = alert.risk_status === 'HIGH_RISK'
                  return (
                    <tr key={alert.alert_id}>
                      <td>
                        <div className="medicine-cell">
                          <strong>{alert.medicine}</strong>
                          <span>{alert.strength} · {alert.dosage_form}</span>
                          <small>Alert #{alert.alert_id}</small>
                        </div>
                      </td>
                      <td>{alert.facility_name}</td>
                      <td>
                        <div className="probability-cell">
                          <strong>{(alert.stockout_probability * 100).toFixed(2)}%</strong>
                          <div className="probability-track">
                            <span
                              className={high ? 'probability-high' : 'probability-low'}
                              style={{ width: `${Math.min(alert.stockout_probability * 100, 100)}%` }}
                            />
                          </div>
                          <small>Threshold: {(alert.risk_threshold * 100).toFixed(0)}%</small>
                        </div>
                      </td>
                      <td>
                        <span className={`risk-label ${high ? 'risk-high' : 'risk-low'}`}>
                          {alert.risk_status.replace('_', ' ')}
                        </span>
                      </td>
                      <td>
                        <strong>{alert.previous_stock.toLocaleString()}</strong>
                        <div className="stockout-subtext">Unmet: {alert.previous_unmet_demand}</div>
                      </td>
                      <td>
                        <strong>{alert.average_demand_7_days.toFixed(1)}</strong>
                        <div className="stockout-subtext">7-day average</div>
                      </td>
                      <td>
                        {alert.acknowledged ? (
                          <div className="acknowledged-cell">
                            <span className="acknowledged-badge"><CheckCircle2 size={13} /> Acknowledged</span>
                            <small>{alert.acknowledged_by}</small>
                            <small>{formatTimestamp(alert.acknowledged_at)}</small>
                          </div>
                        ) : (
                          <span className="pending-badge">Pending review</span>
                        )}
                      </td>
                      <td>
                        {alert.acknowledged ? (
                          <span className="stockout-subtext">Recorded</span>
                        ) : (
                          <button
                            className="acknowledge-button"
                            onClick={() => acknowledgeAlert(alert.alert_id)}
                            disabled={acknowledgingId !== null || !operator.trim()}
                          >
                            {acknowledgingId === alert.alert_id ? 'Saving…' : 'Acknowledge'}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        <div className="inventory-table-footer">
          <span>Source: FastAPI · GET /stockout-alerts/</span>
          <span>Generated: {formatDate(data?.source_date ?? null)}</span>
        </div>
      </section>

      <div className="stockout-method-note">
        <AlertTriangle size={15} />
        <span>
          Risk probabilities are model estimates, not confirmed stockouts.
          Acknowledgement records that an operator reviewed an alert; it does not resolve the underlying inventory risk.
        </span>
      </div>
    </div>
  )
}

function AlertMetric({
  label, value, icon: Icon, color, description,
}: {
  label: string
  value: string
  icon: typeof AlertTriangle
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
