import { API_BASE } from '../services/apiBase'
import { useEffect, useMemo, useState } from 'react'
import {
  Search, RefreshCw, Package, AlertTriangle,
  CalendarClock, Boxes
} from 'lucide-react'

type InventoryItem = {
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

function getExpiryStatus(date: string) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const expiry = new Date(`${date}T00:00:00`)
  const days = Math.ceil((expiry.getTime() - today.getTime()) / 86400000)

  if (days < 0) return { label: 'Expired', className: 'expired' }
  if (days <= 30) return { label: 'Expiring soon', className: 'expiring' }
  return { label: 'Valid', className: 'valid' }
}

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [facility, setFacility] = useState('All facilities')

  async function loadInventory() {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/inventory/`)

      if (!response.ok) {
        throw new Error(`Inventory API returned ${response.status}`)
      }

      const data: InventoryItem[] = await response.json()
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load inventory.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadInventory()
  }, [])

  const facilities = useMemo(
    () => [...new Set(items.map((item) => item.facility_name))].sort(),
    [items]
  )

  const filteredItems = useMemo(() => {
    const query = search.toLowerCase().trim()

    return items.filter((item) => {
      const matchesFacility =
        facility === 'All facilities' || item.facility_name === facility

      const matchesSearch =
        !query ||
        item.generic_name.toLowerCase().includes(query) ||
        item.batch_number.toLowerCase().includes(query) ||
        item.facility_name.toLowerCase().includes(query) ||
        item.strength.toLowerCase().includes(query)

      return matchesFacility && matchesSearch
    })
  }, [items, search, facility])

  const totalUsable = items.reduce((sum, item) => sum + item.usable_stock, 0)
  const totalReserved = items.reduce((sum, item) => sum + item.reserved_quantity, 0)
  const zeroUsable = items.filter((item) => item.usable_stock <= 0).length

  return (
    <div className="page-content inventory-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Package size={13} /> INVENTORY MANAGEMENT</div>
          <h1>Medicine Inventory</h1>
          <p>Monitor medicine batches, available quantities and expiry dates across facilities.</p>
        </div>
        <button className="date-filter" onClick={loadInventory} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
          Refresh data
        </button>
      </div>

      <div className="preview-notice">
        <Package size={16} />
        <span><strong>LIVE INVENTORY</strong> — Batch records loaded from the backend inventory API.</span>
      </div>

      <section className="kpi-grid inventory-kpis">
        <InventoryMetric
          label="BATCH RECORDS"
          value={loading ? '…' : items.length.toString()}
          icon={Boxes}
          color="blue"
          description="Across all facilities"
        />
        <InventoryMetric
          label="USABLE STOCK"
          value={loading ? '…' : totalUsable.toLocaleString()}
          icon={Package}
          color="green"
          description="Available inventory units"
        />
        <InventoryMetric
          label="RESERVED STOCK"
          value={loading ? '…' : totalReserved.toLocaleString()}
          icon={CalendarClock}
          color="purple"
          description="Units reserved"
        />
        <InventoryMetric
          label="ZERO USABLE STOCK"
          value={loading ? '…' : zeroUsable.toString()}
          icon={AlertTriangle}
          color="orange"
          description="Batch records requiring review"
        />
      </section>

      <section className="panel inventory-table-panel">
        <div className="inventory-toolbar">
          <div>
            <h2>Inventory Records</h2>
            <p>{filteredItems.length} records displayed</p>
          </div>

          <div className="inventory-filters">
            <div className="inventory-search">
              <Search size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search medicine, batch or facility..."
                aria-label="Search inventory"
              />
            </div>

            <select
              value={facility}
              onChange={(event) => setFacility(event.target.value)}
              aria-label="Filter by facility"
            >
              <option>All facilities</option>
              {facilities.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </div>
        </div>

        {error && <div className="inventory-error">{error}</div>}

        {loading ? (
          <div className="inventory-empty">Loading inventory records…</div>
        ) : !error && filteredItems.length === 0 ? (
          <div className="inventory-empty">No inventory records match your filters.</div>
        ) : !error ? (
          <div className="inventory-table-wrapper">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>MEDICINE</th>
                  <th>FACILITY</th>
                  <th>BATCH NUMBER</th>
                  <th>EXPIRY DATE</th>
                  <th>ON HAND</th>
                  <th>RESERVED</th>
                  <th>DAMAGED</th>
                  <th>USABLE STOCK</th>
                  <th>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, index) => {
                  const expiry = getExpiryStatus(item.expires_on)

                  return (
                    <tr key={`${item.facility_name}-${item.batch_number}-${index}`}>
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
                          <span>{new Date(`${item.expires_on}T00:00:00`).toLocaleDateString('en-IN', {
                            day: '2-digit', month: 'short', year: 'numeric'
                          })}</span>
                          <span className={`expiry-status ${expiry.className}`}>{expiry.label}</span>
                        </div>
                      </td>
                      <td>{item.quantity_on_hand.toLocaleString()}</td>
                      <td>{item.reserved_quantity.toLocaleString()}</td>
                      <td>{item.damaged_quantity.toLocaleString()}</td>
                      <td>
                        <strong className={item.usable_stock <= 0 ? 'zero-stock' : 'usable-stock'}>
                          {item.usable_stock.toLocaleString()}
                        </strong>
                      </td>
                      <td>
                        <span className={`stock-status ${item.usable_stock <= 0 ? 'stock-empty' : 'stock-available'}`}>
                          {item.usable_stock <= 0 ? 'No usable stock' : 'Available'}
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
          <span>Source: FastAPI · GET /inventory/</span>
          <span>{filteredItems.length} of {items.length} records</span>
        </div>
      </section>
    </div>
  )
}

function InventoryMetric({
  label, value, icon: Icon, color, description
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
