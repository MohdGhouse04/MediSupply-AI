import { useState } from 'react'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight,
  Bell, Boxes, Building2, CalendarDays, ChevronDown,
  CircleHelp, Clock3, LayoutDashboard, Package,
  Search, Settings, ShieldCheck, Truck, TrendingUp,
  Zap
} from 'lucide-react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts'
import type { LucideIcon } from 'lucide-react'
import './App.css'

type NavItem = {
  label: string
  icon: LucideIcon
}

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

const alerts = [
  {
    medicine: 'Paracetamol 500mg',
    facility: 'Facility 01',
    risk: 'HIGH RISK',
    detail: 'Predicted stockout within 7 days',
  },
  {
    medicine: 'Amoxicillin 250mg',
    facility: 'Facility 02',
    risk: 'HIGH RISK',
    detail: 'Low available inventory',
  },
  {
    medicine: 'Cetirizine 10mg',
    facility: 'Facility 01',
    risk: 'LOW RISK',
    detail: 'Monitor demand trend',
  },
]

function App() {
  const [activePage, setActivePage] = useState('Overview')

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
                {label === 'Stockout Alerts' && <span className="nav-count">2</span>}
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
            <div className="topbar-date"><CalendarDays size={16} /> Nov 22, 2026</div>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><Zap size={13} /> INTELLIGENCE OVERVIEW</div>
              <h1>{activePage === 'Overview' ? 'Supply Chain Overview' : activePage}</h1>
              <p>Monitor inventory health, anticipate demand and make smarter supply decisions.</p>
            </div>
            <button className="date-filter"><CalendarDays size={16} /> Last 30 days <ChevronDown size={15} /></button>
          </div>

          <div className="preview-notice">
            <Activity size={16} />
            <span><strong>UI PREVIEW</strong> — Display values are illustrative. Live backend integration is the next step.</span>
          </div>

          <section className="kpi-grid">
            <KpiCard
              label="TOTAL INVENTORY"
              value="—"
              unit="Units across facilities"
              icon={Package}
              color="blue"
              trend="Live data pending"
              trendUp
            />
            <KpiCard
              label="STOCKOUT ALERTS"
              value="8"
              unit="Current model-generated alerts"
              icon={AlertTriangle}
              color="orange"
              trend="2 high risk"
              trendUp={false}
            />
            <KpiCard
              label="EXPIRY RISK"
              value="—"
              unit="Projected wastage units"
              icon={Clock3}
              color="purple"
              trend="Forecast-based estimate"
              trendUp
            />
            <KpiCard
              label="FACILITIES"
              value="2"
              unit="In the current dataset"
              icon={Building2}
              color="green"
              trend="Connected dataset"
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
                  <p>Application components</p>
                </div>
                <ShieldCheck size={19} className="health-icon" />
              </div>
              <div className="health-list">
                <HealthRow name="FastAPI Backend" status="Connected" />
                <HealthRow name="PostgreSQL Database" status="Connected" />
                <HealthRow name="Kafka Event Pipeline" status="Configured" />
                <HealthRow name="ML Forecast Models" status="Available" />
              </div>
              <div className="health-footer">
                <span className="health-pulse" /> Project components configured
              </div>
            </div>
          </section>

          <section className="bottom-grid">
            <div className="panel alerts-panel">
              <div className="panel-header">
                <div>
                  <h2>Stockout Alerts</h2>
                  <p>Sample alert display based on current project output</p>
                </div>
                <button className="text-action" onClick={() => setActivePage('Stockout Alerts')}>View all <ArrowUpRight size={14} /></button>
              </div>
              <div className="alert-list">
                {alerts.map((alert) => (
                  <div className="alert-row" key={alert.medicine}>
                    <div className={`alert-symbol ${alert.risk === 'HIGH RISK' ? 'high' : 'low'}`}>
                      <AlertTriangle size={17} />
                    </div>
                    <div className="alert-description">
                      <strong>{alert.medicine}</strong>
                      <span>{alert.facility} · {alert.detail}</span>
                    </div>
                    <span className={`risk-label ${alert.risk === 'HIGH RISK' ? 'risk-high' : 'risk-low'}`}>{alert.risk}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel expiry-panel">
              <div className="panel-header">
                <div>
                  <h2>Expiry Management</h2>
                  <p>FEFO recommendation summary</p>
                </div>
                <button className="text-action" onClick={() => setActivePage('Expiry Management')}>Details <ArrowUpRight size={14} /></button>
              </div>
              <div className="expiry-summary">
                <div className="expiry-number">9</div>
                <div>
                  <strong>Batches reviewed</strong>
                  <span>Latest API evaluation</span>
                </div>
              </div>
              <div className="expiry-metrics">
                <div><span>Insufficient forecast</span><strong>7</strong></div>
                <div><span>Estimated wastage</span><strong>0 units</strong></div>
              </div>
              <div className="expiry-note"><Clock3 size={14} /> Forecast estimates require ongoing monitoring.</div>
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
