import { useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight,
  Bell, Boxes, Building2, CalendarDays, ChevronDown,
  CircleHelp, Clock3, LayoutDashboard, Package,
  Search, Settings, ShieldCheck, Truck, TrendingUp, Zap
} from 'lucide-react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts'
import type { LucideIcon } from 'lucide-react'
import { fetchOverviewData } from './services/api'
import type { OverviewData } from './services/api'
import InventoryPage from './pages/InventoryPage'
import StockoutAlertsPage from './pages/StockoutAlertsPage'
import ExpiryManagementPage from './pages/ExpiryManagementPage'
import DemandForecastPage from './pages/DemandForecastPage'
import FacilitiesPage from './pages/FacilitiesPage'
import TransfersPage from './pages/TransfersPage'
import ProcurementPage from './pages/ProcurementPage'
import './App.css'

type NavItem = { label: string; icon: LucideIcon }

const navigation: { heading: string; items: NavItem[] }[] = [
  {
    heading: 'WORKSPACE',
    items: [
      { label: 'Overview', icon: LayoutDashboard },
      { label: 'Inventory', icon: Package },
      { label: 'Stockout Alerts', icon: AlertTriangle },
      { label: 'Expiry Management', icon: Clock3 },
      { label: 'Demand Forecast', icon: TrendingUp },
    ],
  },
  {
    heading: 'OPERATIONS',
    items: [
      { label: 'Facilities', icon: Building2 },
      { label: 'Transfers', icon: Truck },
      { label: 'Procurement', icon: Boxes },
    ],
  },
]

const forecastData = [
  { day: 'Nov 21', actual: 42, forecast: 44 },
  { day: 'Nov 22', actual: 48, forecast: 46 },
  { day: 'Nov 23', actual: 45, forecast: 47 },
  { day: 'Nov 24', actual: 53, forecast: 50 },
  { day: 'Nov 25', actual: 49, forecast: 52 },
  { day: 'Nov 26', actual: 57, forecast: 54 },
  { day: 'Nov 27', actual: 55, forecast: 58 },
  { day: 'Nov 28', actual: null, forecast: 56 },
  { day: 'Nov 29', actual: null, forecast: 61 },
  { day: 'Nov 30', actual: null, forecast: 63 },
  { day: 'Dec 01', actual: null, forecast: 60 },
  { day: 'Dec 02', actual: null, forecast: 66 },
]

function App() {
  const [activePage, setActivePage] = useState('Overview')
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    fetchOverviewData()
      .then((data) => {
        if (isMounted) setOverview(data)
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setApiError(error instanceof Error ? error.message : 'Unable to load dashboard data.')
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => { isMounted = false }
  }, [])

  const totalUsableStock = overview?.inventory.reduce(
    (total, medicine) => total + medicine.total_usable_stock, 0
  ) ?? 0

  const displayedAlerts = [...(overview?.stockout.alerts ?? [])]
    .sort((a, b) => b.stockout_probability - a.stockout_probability)
    .slice(0, 3)

  const formatValue = (value: number | undefined) =>
    value === undefined ? '—' : value.toLocaleString()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Activity size={22} /></div>
          <div>
            <div className="brand-name">MediSupply<span>AI</span></div>
            <div className="brand-caption">INTELLIGENT SUPPLY CHAIN</div>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-switch">
          <div className="workspace-avatar">M</div>
          <div className="workspace-text">
            <strong>Medical Network</strong>
            <span>Organization</span>
          </div>
          <ChevronDown size={15} />
        </button>

        {navigation.map((group) => (
          <div className="nav-group" key={group.heading}>
            <div className="nav-heading">{group.heading}</div>
            {group.items.map(({ label, icon: Icon }) => (
              <button
                key={label}
                className={`nav-item ${activePage === label ? 'active' : ''}`}
                onClick={() => setActivePage(label)}
              >
                <Icon size={18} strokeWidth={1.8} />
                <span>{label}</span>
                {label === 'Stockout Alerts' && (
                  <span className="nav-count">{overview?.stockout.high_risk_count ?? '—'}</span>
                )}
              </button>
            ))}
          </div>
        ))}

        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setActivePage('Settings')}>
            <Settings size={18} /><span>Settings</span>
          </button>
          <button className="nav-item" onClick={() => setActivePage('Help & Support')}>
            <CircleHelp size={18} /><span>Help & Support</span>
          </button>
          <div className="sidebar-profile">
            <div className="profile-avatar">IM</div>
            <div className="profile-info">
              <strong>Inventory Manager</strong>
              <span>Administrator</span>
            </div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{activePage}</strong>
          </div>
          <div className="topbar-actions">
            <div className="environment-tag"><span /> DEVELOPMENT</div>
            <button className="icon-button" aria-label="Search"><Search size={19} /></button>
            <button className="icon-button notification-button" aria-label="Notifications">
              <Bell size={19} /><i />
            </button>
            <div className="topbar-divider" />
            <div className="topbar-date"><CalendarDays size={16} /> Nov 23, 2026</div>
          </div>
        </header>

        {activePage === "Inventory" && <InventoryPage />}
        {activePage === "Stockout Alerts" && <StockoutAlertsPage />}
        {activePage === "Expiry Management" && <ExpiryManagementPage />}
        {activePage === "Demand Forecast" && <DemandForecastPage />}
        {activePage === "Facilities" && <FacilitiesPage />}
        {activePage === "Transfers" && <TransfersPage />}
        {activePage === "Procurement" && <ProcurementPage />}
        <div className="page-content" hidden={["Inventory", "Stockout Alerts", "Expiry Management", "Demand Forecast", "Facilities", "Transfers", "Procurement"].includes(activePage)}>
          <div className="page-heading">
            <div>
              <div className="eyebrow"><Zap size={13} /> INTELLIGENCE OVERVIEW</div>
              <h1>{activePage === 'Overview' ? 'Supply Chain Overview' : activePage}</h1>
              <p>Monitor inventory health, anticipate demand and make smarter supply decisions.</p>
            </div>
            <button className="date-filter">
              <CalendarDays size={16} /> Last 30 days <ChevronDown size={15} />
            </button>
          </div>

          <div className={`preview-notice ${apiError ? 'api-error' : ''}`}>
            <Activity size={16} />
            {loading ? (
              <span><strong>CONNECTING</strong> — Loading live backend data.</span>
            ) : apiError ? (
              <span><strong>API CONNECTION ISSUE</strong> — {apiError}</span>
            ) : (
              <span><strong>LIVE BACKEND DATA</strong> — Metrics are loaded from FastAPI. The demand chart remains illustrative.</span>
            )}
          </div>

          <section className="kpi-grid">
            <KpiCard
              label="TOTAL INVENTORY"
              value={loading ? '…' : apiError ? '—' : formatValue(totalUsableStock)}
              unit="Usable units across facilities"
              icon={Package}
              color="blue"
              trend="Combined usable stock"
              trendUp
            />
            <KpiCard
              label="STOCKOUT ALERTS"
              value={loading ? '…' : apiError ? '—' : formatValue(overview?.stockout.total_alerts)}
              unit="Current model-generated alerts"
              icon={AlertTriangle}
              color="orange"
              trend={loading ? 'Loading risk levels' : `${overview?.stockout.high_risk_count ?? 0} high risk`}
              trendUp={false}
            />
            <KpiCard
              label="EXPIRY RISK"
              value={loading ? '…' : apiError ? '—' : formatValue(overview?.expiry.estimated_wastage_units)}
              unit="Estimated wastage units"
              icon={Clock3}
              color="purple"
              trend={overview ? `${overview.expiry.batches_with_insufficient_forecast} batches lack forecast coverage` : 'Forecast-based estimate'}
              trendUp
            />
            <KpiCard
              label="FACILITIES"
              value={loading ? '…' : apiError ? '—' : formatValue(overview?.facilities.length)}
              unit="Facilities in dataset"
              icon={Building2}
              color="green"
              trend="Backend facility records"
              trendUp
            />
          </section>

          <section className="analytics-grid">
            <div className="panel forecast-panel">
              <div className="panel-header">
                <div>
                  <h2>Demand Forecast</h2>
                  <p>Illustrative daily demand trend</p>
                </div>
                <button className="select-filter">7 days <ChevronDown size={14} /></button>
              </div>
              <div className="chart-legend">
                <span><i className="legend-dot actual" /> Historical demand</span>
                <span><i className="legend-dot forecast" /> Predicted demand</span>
              </div>
              <div className="chart-area">
                {activePage === 'Overview' && (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastData} margin={{ top: 12, right: 10, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#293449" strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="day" tick={{ fill: '#8290a5', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#8290a5', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: '#182235', border: '1px solid #344158', borderRadius: 9, color: '#f1f5f9' }}
                      labelStyle={{ color: '#aebbd0' }}
                    />
                    <Line type="monotone" dataKey="actual" name="Historical" stroke="#4F9CF9" strokeWidth={2.5} dot={false} connectNulls={false} />
                    <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#26C6A0" strokeWidth={2.5} strokeDasharray="6 5" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
                )}
              </div>
              <div className="chart-footer">
                <span>Preview visualization — not live model output</span>
                <span>Demand units / day</span>
              </div>
            </div>

            <div className="panel health-panel">
              <div className="panel-header">
                <div>
                  <h2>System Health</h2>
                  <p>API connectivity checks</p>
                </div>
                <ShieldCheck size={19} className="health-icon" />
              </div>
              <div className="health-list">
                <HealthRow
                  name="FastAPI Backend"
                  status={loading ? 'Checking' : overview?.health.status === 'healthy' ? 'Healthy' : 'Unavailable'}
                />
                <HealthRow
                  name="Inventory API"
                  status={loading ? 'Checking' : overview ? 'Connected' : 'Unavailable'}
                />
                <HealthRow
                  name="Stockout Alert Data"
                  status={loading ? 'Checking' : overview?.stockout.freshness_status ?? 'Unavailable'}
                />
                <HealthRow
                  name="Expiry Forecast"
                  status={loading ? 'Checking' : overview ? `${overview.expiry.forecast_horizon_days}-day horizon` : 'Unavailable'}
                />
              </div>
              <div className="health-footer">
                <span className="health-pulse" />
                {loading ? 'Checking backend services' : apiError ? 'Some data could not be loaded' : 'Backend data successfully loaded'}
              </div>
            </div>
          </section>

          <section className="bottom-grid">
            <div className="panel alerts-panel">
              <div className="panel-header">
                <div>
                  <h2>Stockout Alerts</h2>
                  <p>Latest model-generated alerts from the backend</p>
                </div>
                <button className="text-action" onClick={() => setActivePage('Stockout Alerts')}>
                  View all <ArrowUpRight size={14} />
                </button>
              </div>
              <div className="alert-list">
                {loading ? (
                  <div className="alert-row">
                    <div className="alert-description"><strong>Loading alerts…</strong></div>
                  </div>
                ) : apiError ? (
                  <div className="alert-row">
                    <div className="alert-description"><strong>Alerts unavailable</strong><span>Check the backend connection</span></div>
                  </div>
                ) : displayedAlerts.map((alert) => {
                  const isHighRisk = alert.risk_status === 'HIGH_RISK'
                  return (
                    <div className="alert-row" key={alert.alert_id}>
                      <div className={`alert-symbol ${isHighRisk ? 'high' : 'low'}`}>
                        <AlertTriangle size={17} />
                      </div>
                      <div className="alert-description">
                        <strong>{alert.medicine} {alert.strength}</strong>
                        <span>
                          {alert.facility_name} · Stockout probability {(alert.stockout_probability * 100).toFixed(1)}%
                        </span>
                      </div>
                      <span className={`risk-label ${isHighRisk ? 'risk-high' : 'risk-low'}`}>
                        {alert.risk_status.replace('_', ' ')}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="panel expiry-panel">
              <div className="panel-header">
                <div>
                  <h2>Expiry Management</h2>
                  <p>FEFO recommendation summary</p>
                </div>
                <button className="text-action" onClick={() => setActivePage('Expiry Management')}>
                  Details <ArrowUpRight size={14} />
                </button>
              </div>
              <div className="expiry-summary">
                <div className="expiry-number">
                  {loading ? '…' : overview?.expiry.total_batches_reviewed ?? '—'}
                </div>
                <div>
                  <strong>Batches reviewed</strong>
                  <span>Latest API evaluation</span>
                </div>
              </div>
              <div className="expiry-metrics">
                <div>
                  <span>Insufficient forecast</span>
                  <strong>{loading ? '…' : overview?.expiry.batches_with_insufficient_forecast ?? '—'}</strong>
                </div>
                <div>
                  <span>Estimated wastage</span>
                  <strong>{loading ? '…' : `${overview?.expiry.estimated_wastage_units ?? '—'} units`}</strong>
                </div>
              </div>
              <div className="expiry-note">
                <Clock3 size={14} /> Estimates apply only within the available forecast horizon.
              </div>
            </div>
          </section>

          <footer className="page-footer">
            <span>© 2026 MediSupply AI</span>
            <span>Predictive intelligence for smarter medicine supply chains</span>
            <span className="footer-version">Development preview</span>
          </footer>
        </div>
      </main>
    </div>
  )
}

function KpiCard({
  label, value, unit, icon: Icon, color, trend, trendUp,
}: {
  label: string
  value: string
  unit: string
  icon: LucideIcon
  color: string
  trend: string
  trendUp: boolean
}) {
  return (
    <div className="panel kpi-card">
      <div className="kpi-top">
        <span>{label}</span>
        <div className={`kpi-icon ${color}`}><Icon size={19} /></div>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-unit">{unit}</div>
      <div className={`kpi-trend ${trendUp ? 'positive' : 'attention'}`}>
        {trendUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
        {trend}
      </div>
    </div>
  )
}

function HealthRow({ name, status }: { name: string; status: string }) {
  return (
    <div className="health-row">
      <div className="health-row-name"><span className="status-dot" />{name}</div>
      <span className="health-status">{status}</span>
    </div>
  )
}

export default App
