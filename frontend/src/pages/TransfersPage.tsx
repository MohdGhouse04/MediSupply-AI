import { API_BASE } from '../services/apiBase'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowRightLeft, Check, X, Truck, PackageCheck, RefreshCw,
  AlertTriangle, Plus, Search, Send, RotateCcw
} from 'lucide-react'

const API = API_BASE
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(`${response.status}: ${message}`)
  }
  return response.json() as Promise<T>
}

type Facility = { facility_id: number; facility_name: string }
type InventoryRow = {
  facility_id: number; facility_name: string; batch_id: number
  medicine_id: number; generic_name: string; strength: string
  batch_number: string; expires_on: string; usable_stock: number
  batch_status?: string
}
type Transfer = {
  transfer_id: number; source_facility_id: number; destination_facility_id: number
  batch_id: number; quantity: number; status: string; requested_at: string
  approved_at?: string | null; dispatched_at?: string | null
  received_at?: string | null; remarks?: string | null
}
type Recommendation = {
  recommendation_type: string; medicine_id: number; medicine_name: string
  strength: string; source_facility_id: number; source_facility: string
  destination_facility_id: number; destination_facility: string
  batch_id: number; batch_number: string; batch_expiry: string
  recommended_quantity: number; source_usable_stock: number
  destination_usable_stock: number; destination_shortage_before_allocation: number
  reason: string; approval_required: boolean
}

const statusClass = (status: string) => `status-pill status-${status.toLowerCase().replaceAll('_', '-')}`

export default function TransfersPage() {
  const [transfers, setTransfers] = useState<Transfer[]>([])
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [inventory, setInventory] = useState<InventoryRow[]>([])
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [showForm, setShowForm] = useState(false)
  const [sourceId, setSourceId] = useState('')
  const [destinationId, setDestinationId] = useState('')
  const [batchId, setBatchId] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [remarks, setRemarks] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [transferData, facilityData, inventoryData, recommendationData] = await Promise.all([
        request<Transfer[]>('/stock-transfers/?limit=100'),
        request<Facility[]>('/facilities/'),
        request<InventoryRow[]>('/inventory/'),
        request<{ recommendations: Recommendation[] }>('/stock-transfers/recommendations?safety_days=3'),
      ])
      setTransfers(transferData)
      setFacilities(facilityData)
      setInventory(inventoryData)
      setRecommendations(recommendationData.recommendations ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load transfer data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const sourceBatches = useMemo(() => inventory.filter(row =>
    row.facility_id === Number(sourceId) &&
    row.usable_stock > 0 &&
    (!row.batch_status || row.batch_status === 'AVAILABLE')
  ), [inventory, sourceId])

  const selectedBatch = sourceBatches.find(row => row.batch_id === Number(batchId))
  const filtered = transfers.filter(item => {
    const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter
    const matchesSearch = `${item.transfer_id} ${item.batch_id} ${item.remarks ?? ''}`.toLowerCase().includes(search.toLowerCase())
    return matchesStatus && matchesSearch
  })

  const counts = {
    total: transfers.length,
    pending: transfers.filter(t => t.status === 'PENDING').length,
    transit: transfers.filter(t => t.status === 'DISPATCHED').length,
    received: transfers.filter(t => t.status === 'RECEIVED').length,
  }

  const facilityName = (id: number) =>
    facilities.find(f => f.facility_id === id)?.facility_name ?? `Facility ${id}`
  const batchInfo = (id: number) => inventory.find(row => row.batch_id === id)

  async function createTransfer(event: React.FormEvent) {
    event.preventDefault()
    if (!sourceId || !destinationId || !batchId || Number(quantity) <= 0) {
      setError('Complete all required transfer fields.')
      return
    }
    if (sourceId === destinationId) {
      setError('Source and destination facilities must be different.')
      return
    }
    if (!selectedBatch || Number(quantity) > selectedBatch.usable_stock) {
      setError('Requested quantity exceeds available usable stock.')
      return
    }
    setBusy(true); setError(''); setNotice('')
    try {
      await request('/stock-transfers/', {
        method: 'POST',
        body: JSON.stringify({
          source_facility_id: Number(sourceId),
          destination_facility_id: Number(destinationId),
          batch_id: Number(batchId),
          quantity: Number(quantity),
          remarks: remarks || null,
        }),
      })
      setNotice('Transfer request created. It is awaiting approval.')
      setShowForm(false); setQuantity('1'); setRemarks('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create transfer.')
    } finally { setBusy(false) }
  }

  async function runAction(id: number, action: 'approve' | 'reject' | 'cancel' | 'dispatch' | 'receive') {
    setBusy(true); setError(''); setNotice('')
    try {
      if (action === 'approve' || action === 'reject' || action === 'cancel') {
        const status = action === 'approve' ? 'APPROVED' : action === 'reject' ? 'REJECTED' : 'CANCELLED'
        await request(`/stock-transfers/${id}/status`, {
          method: 'PATCH', body: JSON.stringify({ status }),
        })
      } else {
        await request(`/stock-transfers/${id}/${action}`, { method: 'POST' })
      }
      setNotice(`Transfer #${id}: ${action} action completed.`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : `Could not ${action} transfer.`)
    } finally { setBusy(false) }
  }

  async function createRecommendedTransfer(rec: Recommendation) {
    setBusy(true); setError(''); setNotice('')
    try {
      await request('/stock-transfers/', {
        method: 'POST',
        body: JSON.stringify({
          source_facility_id: rec.source_facility_id,
          destination_facility_id: rec.destination_facility_id,
          batch_id: rec.batch_id,
          quantity: rec.recommended_quantity,
          remarks: `Created from AI transfer recommendation. ${rec.reason}`,
        }),
      })
      setNotice('Recommended transfer request created and awaiting approval.')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create recommended transfer.')
    } finally { setBusy(false) }
  }

  return (
    <div className="page-content operations-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><ArrowRightLeft size={13} /> INVENTORY MOVEMENT</div>
          <h1>Inter-facility Transfers</h1>
          <p>Redistribute eligible medicine stock between facilities with approval and receipt tracking.</p>
        </div>
        <div className="operations-heading-actions">
          <button className="secondary-action" onClick={() => void load()} disabled={loading}>
            <RefreshCw size={15} /> Refresh
          </button>
          <button className="primary-action" onClick={() => setShowForm(!showForm)}>
            <Plus size={16} /> New transfer
          </button>
        </div>
      </div>

      {error && <div className="operations-alert error"><AlertTriangle size={17} />{error}</div>}
      {notice && <div className="operations-alert success"><Check size={17} />{notice}</div>}

      <section className="kpi-grid">
        <div className="kpi-card"><div className="kpi-top"><span>TOTAL TRANSFERS</span><ArrowRightLeft size={18} /></div><div className="kpi-value">{loading ? '…' : counts.total}</div><div className="kpi-unit">Recorded transfer requests</div></div>
        <div className="kpi-card"><div className="kpi-top"><span>PENDING APPROVAL</span><AlertTriangle size={18} /></div><div className="kpi-value">{loading ? '…' : counts.pending}</div><div className="kpi-unit">Awaiting a decision</div></div>
        <div className="kpi-card"><div className="kpi-top"><span>IN TRANSIT</span><Truck size={18} /></div><div className="kpi-value">{loading ? '…' : counts.transit}</div><div className="kpi-unit">Dispatched, not yet received</div></div>
        <div className="kpi-card"><div className="kpi-top"><span>RECEIVED</span><PackageCheck size={18} /></div><div className="kpi-value">{loading ? '…' : counts.received}</div><div className="kpi-unit">Completed transfers</div></div>
      </section>

      {showForm && <section className="panel operations-form-panel">
        <div className="panel-heading"><div><h2>Create transfer request</h2><p>Stock is deducted only after dispatch.</p></div></div>
        <form className="operations-form" onSubmit={createTransfer}>
          <label>Source facility<select value={sourceId} onChange={e => { setSourceId(e.target.value); setBatchId('') }} required><option value="">Select source</option>{facilities.map(f => <option key={f.facility_id} value={f.facility_id}>{f.facility_name}</option>)}</select></label>
          <label>Destination facility<select value={destinationId} onChange={e => setDestinationId(e.target.value)} required><option value="">Select destination</option>{facilities.filter(f => String(f.facility_id) !== sourceId).map(f => <option key={f.facility_id} value={f.facility_id}>{f.facility_name}</option>)}</select></label>
          <label className="form-span-2">Source batch<select value={batchId} onChange={e => setBatchId(e.target.value)} required><option value="">Select available batch</option>{sourceBatches.map(row => <option key={row.batch_id} value={row.batch_id}>{row.generic_name} {row.strength} · {row.batch_number} · usable {row.usable_stock}</option>)}</select></label>
          {selectedBatch && <div className="form-hint form-span-2">Available usable stock: <strong>{selectedBatch.usable_stock.toLocaleString()}</strong> units · Expires {selectedBatch.expires_on}</div>}
          <label>Quantity<input type="number" min="1" max={selectedBatch?.usable_stock ?? undefined} value={quantity} onChange={e => setQuantity(e.target.value)} required /></label>
          <label>Remarks<input value={remarks} onChange={e => setRemarks(e.target.value)} maxLength={500} placeholder="Optional reason for transfer" /></label>
          <div className="form-actions form-span-2"><button type="button" className="secondary-action" onClick={() => setShowForm(false)}>Cancel</button><button className="primary-action" disabled={busy}>{busy ? 'Submitting…' : 'Submit request'}</button></div>
        </form>
      </section>}

      <section className="panel">
        <div className="panel-heading"><div><h2>AI transfer recommendations</h2><p>Suggested transfers based on forecast demand, safety stock and FEFO batch eligibility. Approval is required.</p></div><span className="panel-count">{recommendations.length} suggestions</span></div>
        {recommendations.length === 0 ? <div className="operations-empty">{loading ? 'Loading recommendations…' : 'No eligible transfer recommendations are currently available.'}</div> :
          <div className="recommendation-grid">{recommendations.map((rec, index) => <article className="recommendation-card" key={`${rec.batch_id}-${rec.destination_facility_id}-${index}`}>
            <div className="recommendation-top"><span className="recommendation-tag">TRANSFER SUGGESTED</span><span className="recommendation-quantity">{rec.recommended_quantity} units</span></div>
            <h3>{rec.medicine_name} <small>{rec.strength}</small></h3>
            <div className="transfer-route"><div><span>FROM</span><strong>{rec.source_facility}</strong></div><ArrowRightLeft size={17} /><div><span>TO</span><strong>{rec.destination_facility}</strong></div></div>
            <div className="recommendation-meta"><span>Batch {rec.batch_number}</span><span>Expiry {rec.batch_expiry}</span></div>
            <p>{rec.reason}</p>
            <button className="secondary-action recommendation-button" disabled={busy} onClick={() => void createRecommendedTransfer(rec)}><Plus size={15} /> Create transfer request</button>
          </article>)}</div>}
      </section>

      <section className="panel">
        <div className="panel-heading"><div><h2>Transfer register</h2><p>Track approval, dispatch and receiving status.</p></div></div>
        <div className="table-toolbar"><div className="table-search"><Search size={16} /><input placeholder="Search transfer ID, batch or remarks" value={search} onChange={e => setSearch(e.target.value)} /></div><select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="ALL">All statuses</option>{['PENDING','APPROVED','DISPATCHED','RECEIVED','REJECTED','CANCELLED'].map(s => <option key={s}>{s}</option>)}</select></div>
        <div className="inventory-table-wrapper"><table className="inventory-table"><thead><tr><th>TRANSFER</th><th>ROUTE</th><th>BATCH / MEDICINE</th><th>QUANTITY</th><th>REQUESTED</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>
          {filtered.map(item => {
            const batch = batchInfo(item.batch_id)
            return <tr key={item.transfer_id}>
              <td><strong>TR-{item.transfer_id}</strong></td>
              <td><div className="route-cell">{facilityName(item.source_facility_id)}<span>to</span>{facilityName(item.destination_facility_id)}</div></td>
              <td><strong>{batch?.generic_name ?? `Batch ${item.batch_id}`}</strong><small className="table-subtext">{batch?.batch_number ?? 'Batch details unavailable'} {batch?.strength ?? ''}</small></td>
              <td>{item.quantity.toLocaleString()}</td><td>{new Date(item.requested_at).toLocaleDateString()}</td>
              <td><span className={statusClass(item.status)}>{item.status.replaceAll('_', ' ')}</span></td>
              <td><div className="row-actions">
                {item.status === 'PENDING' && <><button title="Approve" disabled={busy} onClick={() => void runAction(item.transfer_id, 'approve')}><Check size={15}/></button><button title="Reject" disabled={busy} onClick={() => void runAction(item.transfer_id, 'reject')}><X size={15}/></button></>}
                {item.status === 'APPROVED' && <><button title="Dispatch" disabled={busy} onClick={() => void runAction(item.transfer_id, 'dispatch')}><Send size={15}/></button><button title="Cancel" disabled={busy} onClick={() => void runAction(item.transfer_id, 'cancel')}><X size={15}/></button></>}
                {item.status === 'DISPATCHED' && <button title="Confirm receipt" disabled={busy} onClick={() => void runAction(item.transfer_id, 'receive')}><PackageCheck size={15}/></button>}
                {['RECEIVED','REJECTED','CANCELLED'].includes(item.status) && <span className="muted-action">—</span>}
              </div></td>
            </tr>
          })}
          {!loading && filtered.length === 0 && <tr><td colSpan={7}><div className="operations-empty">No transfer records match these filters.</div></td></tr>}
        </tbody></table></div>
        <div className="table-footnote"><RotateCcw size={13}/> Dispatch deducts stock from the source. Receiving adds it to the destination inventory.</div>
      </section>
    </div>
  )
}
