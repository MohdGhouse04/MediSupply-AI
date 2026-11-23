import { useEffect, useMemo, useState } from 'react'
import {
  Activity, CalendarDays, RefreshCw, TrendingUp, Package,
  Building2, BarChart3
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts'

type Facility = {
  facility_id: number
  facility_name: string
}

type Medicine = {
  medicine_id: number
  generic_name: string
  strength: string
  unit: string
}

type ForecastRecord = {
  date: string
  facility_id: number
  medicine_id: number
  forecast_day: number
  predicted_demand: number
  horizon: number
}

type ForecastResponse = {
  horizon_days: number
  total_records: number
  total_predicted_demand: number
  average_daily_demand: number
  forecast_start_date: string | null
  forecast_end_date: string | null
  filters: {
    facility_id: number | null
    medicine_id: number | null
  }
  facility_totals: {
    facility_id: number
    predicted_demand: number
  }[]
  medicine_totals: {
    medicine_id: number
    predicted_demand: number
  }[]
  forecasts: ForecastRecord[]
}

const API = '/api'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${await response.text()}`)
  }
  return response.json() as Promise<T>
}

function formatNumber(value: number) {
  return value.toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

export default function DemandForecastPage() {
  const [horizon, setHorizon] = useState(7)
  const [facilityId, setFacilityId] = useState('ALL')
  const [medicineId, setMedicineId] = useState('ALL')
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [medicines, setMedicines] = useState<Medicine[]>([])
  const [data, setData] = useState<ForecastResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      getJson<Facility[]>('/facilities/'),
      getJson<Medicine[]>('/medicines/'),
    ])
      .then(([facilityData, medicineData]) => {
        setFacilities(facilityData)
        setMedicines(medicineData)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Unable to load filter options.')
      })
  }, [])

  useEffect(() => {
    let active = true

    async function loadForecast() {
      setLoading(true)
      setError(null)

      const params = new URLSearchParams({ horizon: String(horizon) })
      if (facilityId !== 'ALL') params.set('facility_id', facilityId)
      if (medicineId !== 'ALL') params.set('medicine_id', medicineId)

      try {
        const result = await getJson<ForecastResponse>(
          `/demand-forecasts/?${params.toString()}`
        )
        if (active) setData(result)
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unable to load demand forecasts.')
          setData(null)
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    loadForecast()
    return () => { active = false }
  }, [horizon, facilityId, medicineId])

  const dailyData = useMemo(() => {
    const grouped = new Map<string, number>()

    for (const item of data?.forecasts ?? []) {
      grouped.set(
        item.date,
        (grouped.get(item.date) ?? 0) + item.predicted_demand
      )
    }

    return [...grouped.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, demand]) => ({
        date,
        label: new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', {
          day: '2-digit', month: 'short',
        }),
        demand: Number(demand.toFixed(2)),
      }))
  }, [data])

  const medicineChartData = useMemo(() => {
    return (data?.medicine_totals ?? []).map((item) => {
      const medicine = medicines.find((m) => m.medicine_id === item.medicine_id)
      return {
        name: medicine ? `${medicine.generic_name} ${medicine.strength}` : `Medicine ${item.medicine_id}`,
        demand: item.predicted_demand,
      }
    })
  }, [data, medicines])

  const facilityChartData = useMemo(() => {
    return (data?.facility_totals ?? []).map((item) => {
      const facility = facilities.find((f) => f.facility_id === item.facility_id)
      return {
        name: facility?.facility_name ?? `Facility ${item.facility_id}`,
        demand: item.predicted_demand,
      }
    })
  }, [data, facilities])

  const selectedFacility = facilities.find((item) => String(item.facility_id) === facilityId)
  const selectedMedicine = medicines.find((item) => String(item.medicine_id) === medicineId)

  return (
    <div className="page-content demand-forecast-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><TrendingUp size={13} /> PREDICTIVE ANALYTICS</div>
          <h1>Demand Forecast</h1>
          <p>Explore predicted medicine demand across facilities and forecast horizons.</p>
        </div>
        <button
          className="date-filter"
          onClick={() => {
            setHorizon((current) => current)
            setFacilityId((current) => current)
          }}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
          {loading ? 'Loading…' : 'Live forecast data'}
        </button>
      </div>

      <div className="forecast-disclosure">
        <Activity size={17} />
        <span>
          <strong>Experimental demand forecast</strong>
          Predictions are generated from simulated historical demand using a trained
          machine-learning model. Longer recursive horizons have not been independently
          validated for forecast accuracy.
        </span>
      </div>

      <section className="forecast-filter-panel panel">
        <div className="forecast-filter-heading">
          <div>
            <h2>Forecast configuration</h2>
            <p>Change the horizon or narrow the forecast to a facility or medicine.</p>
          </div>
          <BarChart3 size={19} />
        </div>

        <div className="forecast-controls">
          <div className="forecast-control horizon-control">
            <label>FORECAST HORIZON</label>
            <div className="horizon-options">
              {[7, 14, 30, 60].map((days) => (
                <button
                  key={days}
                  className={horizon === days ? 'horizon-option active' : 'horizon-option'}
                  onClick={() => setHorizon(days)}
                >
                  {days} days
                </button>
              ))}
            </div>
          </div>

          <div className="forecast-control">
            <label htmlFor="forecast-facility">FACILITY</label>
            <select
              id="forecast-facility"
              value={facilityId}
              onChange={(event) => setFacilityId(event.target.value)}
            >
              <option value="ALL">All facilities</option>
              {facilities.map((item) => (
                <option key={item.facility_id} value={item.facility_id}>
                  {item.facility_name}
                </option>
              ))}
            </select>
          </div>

          <div className="forecast-control">
            <label htmlFor="forecast-medicine">MEDICINE</label>
            <select
              id="forecast-medicine"
              value={medicineId}
              onChange={(event) => setMedicineId(event.target.value)}
            >
              <option value="ALL">All medicines</option>
              {medicines.map((item) => (
                <option key={item.medicine_id} value={item.medicine_id}>
                  {item.generic_name} · {item.strength}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {error && <div className="inventory-error">{error}</div>}

      <section className="kpi-grid forecast-kpis">
        <ForecastMetric
          label="TOTAL PREDICTED DEMAND"
          value={loading ? '…' : formatNumber(data?.total_predicted_demand ?? 0)}
          suffix="units"
          icon={Package}
          description={`${horizon}-day forecast period`}
        />
        <ForecastMetric
          label="AVERAGE DAILY DEMAND"
          value={loading ? '…' : formatNumber(data?.average_daily_demand ?? 0)}
          suffix="units / day"
          icon={Activity}
          description="Average across selected records"
        />
        <ForecastMetric
          label="FORECAST RECORDS"
          value={loading ? '…' : String(data?.total_records ?? 0)}
          suffix="daily predictions"
          icon={CalendarDays}
          description="Facility-medicine-date records"
        />
        <ForecastMetric
          label="FACILITIES INCLUDED"
          value={loading ? '…' : String(data?.facility_totals.length ?? 0)}
          suffix="facilities"
          icon={Building2}
          description="Matching selected filters"
        />
      </section>

      <section className="panel forecast-chart-panel">
        <div className="forecast-panel-heading">
          <div>
            <h2>Daily Predicted Demand</h2>
            <p>
              {selectedFacility?.facility_name ?? 'All facilities'}
              {' · '}
              {selectedMedicine
                ? `${selectedMedicine.generic_name} ${selectedMedicine.strength}`
                : 'All medicines'}
            </p>
          </div>
          <span className="forecast-period-label">{horizon}-DAY HORIZON</span>
        </div>

        {loading ? (
          <div className="inventory-empty">Loading daily forecast…</div>
        ) : dailyData.length === 0 ? (
          <div className="inventory-empty">No forecast records are available for these filters.</div>
        ) : (
          <div className="forecast-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dailyData} margin={{ top: 12, right: 18, left: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#263449" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#8998ad', fontSize: 11 }}
                  axisLine={{ stroke: '#344158' }}
                  tickLine={false}
                  minTickGap={24}
                />
                <YAxis
                  tick={{ fill: '#8998ad', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={48}
                />
                <Tooltip
                  contentStyle={{
                    background: '#111d30',
                    border: '1px solid #344158',
                    borderRadius: 8,
                    color: '#e8eef8',
                    fontSize: 12,
                  }}
                  formatter={(value) => [`${formatNumber(Number(value))} units`, 'Predicted demand']}
                  labelStyle={{ color: '#aab8ca' }}
                />
                <Line
                  type="monotone"
                  dataKey="demand"
                  name="Predicted demand"
                  stroke="#5b9df8"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5, fill: '#5b9df8', stroke: '#dceaff', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="forecast-chart-footnote">
          Daily values are aggregated across the selected facilities and medicines.
        </div>
      </section>

      <div className="forecast-comparison-grid">
        <section className="panel forecast-chart-panel">
          <div className="forecast-panel-heading">
            <div>
              <h2>Demand by Medicine</h2>
              <p>Predicted units over the selected horizon</p>
            </div>
          </div>
          {medicineChartData.length === 0 ? (
            <div className="inventory-empty">No medicine breakdown available.</div>
          ) : (
            <div className="forecast-small-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={medicineChartData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#263449" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#8998ad', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8998ad', fontSize: 10 }} axisLine={false} tickLine={false} width={42} />
                  <Tooltip
                    contentStyle={{ background: '#111d30', border: '1px solid #344158', borderRadius: 8, fontSize: 12 }}
                    formatter={(value) => [`${formatNumber(Number(value))} units`, 'Predicted demand']}
                  />
                  <Bar dataKey="demand" fill="#5b9df8" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        <section className="panel forecast-chart-panel">
          <div className="forecast-panel-heading">
            <div>
              <h2>Demand by Facility</h2>
              <p>Predicted units over the selected horizon</p>
            </div>
          </div>
          {facilityChartData.length === 0 ? (
            <div className="inventory-empty">No facility breakdown available.</div>
          ) : (
            <div className="forecast-small-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={facilityChartData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#263449" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#8998ad', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8998ad', fontSize: 10 }} axisLine={false} tickLine={false} width={42} />
                  <Tooltip
                    contentStyle={{ background: '#111d30', border: '1px solid #344158', borderRadius: 8, fontSize: 12 }}
                    formatter={(value) => [`${formatNumber(Number(value))} units`, 'Predicted demand']}
                  />
                  <Bar dataKey="demand" fill="#35c5a0" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      </div>

      <section className="panel forecast-details-panel">
        <div className="forecast-panel-heading">
          <div>
            <h2>Forecast Details</h2>
            <p>Selected forecast scope and date coverage</p>
          </div>
        </div>
        <div className="forecast-details-grid">
          <div><span>Forecast model output</span><strong>{horizon}-day demand prediction</strong></div>
          <div><span>Start date</span><strong>{formatDate(data?.forecast_start_date ?? null)}</strong></div>
          <div><span>End date</span><strong>{formatDate(data?.forecast_end_date ?? null)}</strong></div>
          <div><span>Facility filter</span><strong>{selectedFacility?.facility_name ?? 'All facilities'}</strong></div>
          <div><span>Medicine filter</span><strong>{selectedMedicine ? `${selectedMedicine.generic_name} ${selectedMedicine.strength}` : 'All medicines'}</strong></div>
          <div><span>Source</span><strong>multi_horizon_forecasts.csv</strong></div>
        </div>
      </section>

      <div className="stockout-method-note">
        <Activity size={15} />
        <span>
          Forecasts represent predicted demand, not guaranteed consumption or available stock.
          Future receipts, stock transfers and unmet demand are not simulated in these demand projections.
        </span>
      </div>
    </div>
  )
}

function ForecastMetric({
  label, value, suffix, icon: Icon, description,
}: {
  label: string
  value: string
  suffix: string
  icon: typeof Package
  description: string
}) {
  return (
    <div className="panel kpi-card">
      <div className="kpi-top">
        <span>{label}</span>
        <div className="kpi-icon blue"><Icon size={19} /></div>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-unit">{suffix} · {description}</div>
    </div>
  )
}
