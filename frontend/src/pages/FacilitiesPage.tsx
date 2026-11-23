import { useEffect, useMemo, useState } from 'react'
import {
  Building2, Package, Activity, RefreshCw, MapPin,
  Boxes, ArrowLeftRight, ShieldCheck
} from 'lucide-react'
import {
  BarChart, Bar, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts'

type Facility = {
  facility_id: number
  facility_name: string
  facility_type: string
  city: string
  state: string
}

type InventoryRecord = {
  facility_name: string
  generic_name: string
  strength: string
  batch_number: string
  expires_on: string
  quantity_on_hand: number
  reserved_quantity: number
  damaged_quantity: number
  usable_stock: number
}

type TransactionSummary = {
  facility_id: number
  facility_name: string
  total_transactions: number
  total_quantity: number | null
}

type FacilityMetrics = {
  facility: Facility
  batches: number
  medicines: number
  onHand: number
  reserved: number
  damaged: number
  usable: number
  transactions: number
  transactionQuantity: number
}

const API = '/api'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`)
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${await response.text()}`)
  }
  return response.json() as Promise<T>
}

const numberFormat = (value: number) =>
  value.toLocaleString('en-IN', { maximumFractionDigits: 0 })

export default function FacilitiesPage() {
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [inventory, setInventory] = useState<InventoryRecord[]>([])
  const [transactions, setTransactions] = useState<TransactionSummary[]>([])
  const [selectedFacility, setSelectedFacility] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function loadData() {
    setLoading(true)
    setError(null)

    try {
      const [facilityData, inventoryData, transactionData] = await Promise.all([
        getJson<Facility[]>('/facilities/'),
        getJson<InventoryRecord[]>('/inventory/'),
        getJson<TransactionSummary[]>('/transactions/summary/facilities'),
      ])

      setFacilities(facilityData)
      setInventory(inventoryData)
      setTransactions(transactionData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load facility data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const facilityMetrics = useMemo<FacilityMetrics[]>(() => {
    return facilities.map((facility) => {
      const records = inventory.filter(
        (item) => item.facility_name === facility.facility_name
      )

      const activity = transactions.find(
        (item) => item.facility_id === facility.facility_id
      )

      return {
        facility,
        batches: records.length,
        medicines: new Set(records.map((item) => `${item.generic_name}|${item.strength}`)).size,
        onHand: records.reduce((sum, item) => sum + item.quantity_on_hand, 0),
        reserved: records.reduce((sum, item) => sum + item.reserved_quantity, 0),
        damaged: records.reduce((sum, item) => sum + item.damaged_quantity, 0),
        usable: records.reduce((sum, item) => sum + item.usable_stock, 0),
        transactions: activity?.total_transactions ?? 0,
        transactionQuantity: activity?.total_quantity ?? 0,
      }
    })
  }, [facilities, inventory, transactions])

  const visibleFacilities = selectedFacility === null
    ? facilityMetrics
    : facilityMetrics.filter((item) => item.facility.facility_id === selectedFacility)

  const visibleInventory = selectedFacility === null
    ? inventory
    : inventory.filter((item) =>
        facilityMetrics.find((metric) =>
          metric.facility.facility_id === selectedFacility
        )?.facility.facility_name === item.facility_name
      )

  const totals = useMemo(() => ({
    facilities: facilities.length,
    batches: inventory.length,
    onHand: visibleInventory.reduce((sum, item) => sum + item.quantity_on_hand, 0),
    reserved: visibleInventory.reduce((sum, item) => sum + item.reserved_quantity, 0),
    damaged: visibleInventory.reduce((sum, item) => sum + item.damaged_quantity, 0),
    usable: visibleInventory.reduce((sum, item) => sum + item.usable_stock, 0),
  }), [facilities, inventory, visibleInventory])

  const medicineData = useMemo(() => {
    const grouped = new Map<string, {
      name: string
      facility: string
      usable: number
      onHand: number
      reserved: number
      damaged: number
      batches: number
    }>()

    for (const item of visibleInventory) {
      const key = `${item.facility_name}|${item.generic_name}|${item.strength}`
      const existing = grouped.get(key) ?? {
        name: `${item.generic_name} ${item.strength}`,
        facility: item.facility_name,
        usable: 0,
        onHand: 0,
        reserved: 0,
        damaged: 0,
        batches: 0,
      }

      existing.usable += item.usable_stock
      existing.onHand += item.quantity_on_hand
      existing.reserved += item.reserved_quantity
      existing.damaged += item.damaged_quantity
      existing.batches += 1
      grouped.set(key, existing)
    }

    return [...grouped.values()].sort((a, b) => b.usable - a.usable)
  }, [visibleInventory])

  const chartData = visibleFacilities.map((item) => ({
    name: item.facility.facility_name.replace(' Community Pharmacy', '').replace(' General Hospital', ''),
    usable: item.usable,
    reserved: item.reserved,
    damaged: item.damaged,
  }))

  return (
    <div className="page-content facilities-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Building2 size={13} /> NETWORK OPERATIONS</div>
          <h1>Facilities</h1>
          <p>Monitor medicine inventory, availability and transaction activity across facilities.</p>
        </div>
        <button className="date-filter" onClick={loadData} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
          {loading ? 'Loading…' : 'Refresh data'}
        </button>
      </div>

      <div className="facility-data-note">
        <ShieldCheck size={17} />
        <span>Facility inventory is calculated from live batch-level records. Transaction activity is displayed separately from stock balances.</span>
      </div>

      {error && <div className="inventory-error">{error}</div>}

      <section className="kpi-grid facility-kpis">
        <FacilityMetric
          label="TOTAL FACILITIES"
          value={loading ? '…' : String(totals.facilities)}
          suffix="registered locations"
          icon={Building2}
        />
        <FacilityMetric
          label="USABLE STOCK"
          value={loading ? '…' : numberFormat(totals.usable)}
          suffix="available units"
          icon={Package}
        />
        <FacilityMetric
          label="RESERVED STOCK"
          value={loading ? '…' : numberFormat(totals.reserved)}
          suffix="reserved units"
          icon={Boxes}
        />
        <FacilityMetric
          label="DAMAGED STOCK"
          value={loading ? '…' : numberFormat(totals.damaged)}
          suffix="damaged units"
          icon={Activity}
        />
      </section>

      <section className="facility-cards-grid">
        {facilityMetrics.map((item) => (
          <button
            key={item.facility.facility_id}
            className={`panel facility-card ${selectedFacility === item.facility.facility_id ? 'selected' : ''}`}
            onClick={() => setSelectedFacility(
              selectedFacility === item.facility.facility_id
                ? null
                : item.facility.facility_id
            )}
          >
            <div className="facility-card-top">
              <div className="facility-card-icon"><Building2 size={20} /></div>
              <span className="facility-type">{item.facility.facility_type}</span>
            </div>
            <h2>{item.facility.facility_name}</h2>
            <div className="facility-location"><MapPin size={13} /> {item.facility.city}, {item.facility.state}</div>
            <div className="facility-card-stock">
              <div>
                <span>USABLE STOCK</span>
                <strong>{numberFormat(item.usable)}</strong>
              </div>
              <div>
                <span>MEDICINES</span>
                <strong>{item.medicines}</strong>
              </div>
              <div>
                <span>BATCHES</span>
                <strong>{item.batches}</strong>
              </div>
            </div>
            <div className="facility-card-footer">
              <span>{item.transactions} transactions recorded</span>
              <span>{selectedFacility === item.facility.facility_id ? 'Selected ✓' : 'View details →'}</span>
            </div>
          </button>
        ))}
      </section>

      <div className="facility-section-heading">
        <div>
          <h2>Inventory Distribution</h2>
          <p>{selectedFacility === null ? 'Compare stock across all facilities' : 'Stock breakdown for selected facility'}</p>
        </div>
        {selectedFacility !== null && (
          <button className="facility-clear-filter" onClick={() => setSelectedFacility(null)}>
            Clear facility filter
          </button>
        )}
      </div>

      <section className="facility-analytics-grid">
        <div className="panel facility-chart-panel">
          <div className="forecast-panel-heading">
            <div>
              <h2>Stock by Facility</h2>
              <p>Usable, reserved and damaged units</p>
            </div>
          </div>
          <div className="facility-chart">
            {chartData.length === 0 ? (
              <div className="inventory-empty">No facility inventory data available.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 15, right: 12, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#263449" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#8998ad', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8998ad', fontSize: 10 }} axisLine={false} tickLine={false} width={42} />
                  <Tooltip
                    contentStyle={{ background: '#111d30', border: '1px solid #344158', borderRadius: 8, fontSize: 12 }}
                    formatter={(value) => [`${numberFormat(Number(value))} units`]}
                  />
                  <Bar dataKey="usable" name="Usable" fill="#35c5a0" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="reserved" name="Reserved" fill="#5b9df8" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="damaged" name="Damaged" fill="#e6a34a" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="facility-chart-legend">
            <span><i className="usable-dot" /> Usable</span>
            <span><i className="reserved-dot" /> Reserved</span>
            <span><i className="damaged-dot" /> Damaged</span>
          </div>
        </div>

        <div className="panel facility-activity-panel">
          <div className="forecast-panel-heading">
            <div>
              <h2>Transaction Activity</h2>
              <p>Recorded inventory transactions</p>
            </div>
            <ArrowLeftRight size={18} />
          </div>
          {visibleFacilities.map((item) => (
            <div className="facility-activity-row" key={item.facility.facility_id}>
              <div className="facility-activity-name">
                <strong>{item.facility.facility_name}</strong>
                <span>{item.transactions} transactions</span>
              </div>
              <div className="facility-activity-value">
                <strong>{numberFormat(item.transactionQuantity)}</strong>
                <span>transaction quantity</span>
              </div>
            </div>
          ))}
          <div className="facility-activity-note">
            Transaction quantity is the sum of quantities recorded in transaction history. It is not current inventory stock.
          </div>
        </div>
      </section>

      <section className="panel facility-inventory-panel">
        <div className="forecast-panel-heading">
          <div>
            <h2>Medicine Availability by Facility</h2>
            <p>{medicineData.length} facility-medicine combinations · Live inventory</p>
          </div>
        </div>

        {medicineData.length === 0 ? (
          <div className="inventory-empty">No inventory records available for this facility.</div>
        ) : (
          <div className="inventory-table-wrapper">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>FACILITY</th>
                  <th>MEDICINE</th>
                  <th>BATCHES</th>
                  <th>ON HAND</th>
                  <th>RESERVED</th>
                  <th>DAMAGED</th>
                  <th>USABLE STOCK</th>
                </tr>
              </thead>
              <tbody>
                {medicineData.map((item) => (
                  <tr key={`${item.facility}|${item.name}`}>
                    <td>{item.facility}</td>
                    <td>{item.name}</td>
                    <td>{item.batches}</td>
                    <td>{numberFormat(item.onHand)}</td>
                    <td>{numberFormat(item.reserved)}</td>
                    <td>{numberFormat(item.damaged)}</td>
                    <td><strong className="facility-usable-value">{numberFormat(item.usable)}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="facility-table-footer">
          Showing {medicineData.length} facility-medicine combinations from {visibleInventory.length} inventory records.
        </div>
      </section>

      <div className="stockout-method-note">
        <Activity size={15} />
        <span>
          Usable stock excludes reserved and damaged quantities and excludes expired or unavailable batches, as calculated by the backend inventory API.
          Facility metrics are aggregated from batch-level inventory records.
        </span>
      </div>
    </div>
  )
}

function FacilityMetric({
  label, value, suffix, icon: Icon,
}: {
  label: string
  value: string
  suffix: string
  icon: typeof Package
}) {
  return (
    <div className="panel kpi-card">
      <div className="kpi-top">
        <span>{label}</span>
        <div className="kpi-icon blue"><Icon size={19} /></div>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-unit">{suffix}</div>
    </div>
  )
}
