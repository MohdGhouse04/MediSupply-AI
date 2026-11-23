import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Boxes, RefreshCw, Plus, Search, AlertTriangle, Check,
  ClipboardList, Truck, PackageCheck, X
} from 'lucide-react'

const API = '/api'
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
type Supplier = { supplier_id: number; supplier_name: string; city?: string | null; state?: string | null }
type Medicine = { medicine_id: number; generic_name: string; strength: string; dosage_form?: string; unit?: string }
type PO = {
  purchase_order_id: number; facility_id: number; supplier_id: number; status: string
  order_date: string; expected_delivery_date?: string | null; total_amount: number | string
  remarks?: string | null
}
type POItem = {
  purchase_order_item_id: number; purchase_order_id: number; medicine_id: number
  ordered_quantity: number; received_quantity: number; unit_cost: number | string
}
type PODetail = { purchase_order: PO; items: POItem[] }
type Recommendation = Record<string, unknown>
type Summary = {
  total_recommendations: number; medicines_requiring_procurement: number
  urgency_breakdown: Record<string, number>; total_usable_stock: number
  total_gross_procurement_quantity: number; total_provisional_procurement_quantity: number
  total_pending_inbound: number; total_approved_inbound: number
  total_dispatched_inbound: number; safety_days: number
  forecast_is_synthetic: boolean; approval_required: boolean
}
type DraftItem = { medicine_id: string; ordered_quantity: string; unit_cost: string }
type ReceiptDraft = { received_quantity: string; batch_number: string; manufactured_on: string; expires_on: string }

const statusClass = (status: string) => `status-pill status-${status.toLowerCase().replaceAll('_', '-')}`
const money = (value: number | string | undefined) => `₹${Number(value ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

export default function ProcurementPage() {
  const [orders, setOrders] = useState<PO[]>([])
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [medicines, setMedicines] = useState<Medicine[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [showForm, setShowForm] = useState(false)
  const [facilityId, setFacilityId] = useState('')
  const [supplierId, setSupplierId] = useState('')
  const [deliveryDate, setDeliveryDate] = useState('')
  const [remarks, setRemarks] = useState('')
  const [draftItems, setDraftItems] = useState<DraftItem[]>([{ medicine_id: '', ordered_quantity: '', unit_cost: '' }])
  const [selectedOrder, setSelectedOrder] = useState<PODetail | null>(null)
  const [receiptDrafts, setReceiptDrafts] = useState<Record<number, ReceiptDraft>>({})
  const [receiptRemarks, setReceiptRemarks] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [po, f, s, m, sum, rec] = await Promise.all([
        request<PO[]>('/purchase-orders/?limit=100'),
        request<Facility[]>('/facilities/'),
        request<Supplier[]>('/suppliers/'),
        request<Medicine[]>('/medicines/'),
        request<Summary>('/procurement/summary?safety_days=3'),
        request<{ recommendations: Recommendation[] }>('/procurement/recommendations?safety_days=3'),
      ])
      setOrders(po); setFacilities(f); setSuppliers(s); setMedicines(m)
      setSummary(sum); setRecommendations(rec.recommendations ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load procurement data.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  const filteredOrders = useMemo(() => orders.filter(order => {
    const matchesStatus = statusFilter === 'ALL' || order.status === statusFilter
    const matchesSearch = `PO-${order.purchase_order_id} ${order.status} ${order.remarks ?? ''}`.toLowerCase().includes(search.toLowerCase())
    return matchesStatus && matchesSearch
  }), [orders, search, statusFilter])

  const facilityName = (id: number) => facilities.find(f => f.facility_id === id)?.facility_name ?? `Facility ${id}`
  const supplierName = (id: number) => suppliers.find(s => s.supplier_id === id)?.supplier_name ?? `Supplier ${id}`
  const medicineName = (id: number) => {
    const m = medicines.find(item => item.medicine_id === id)
    return m ? `${m.generic_name} ${m.strength}` : `Medicine ${id}`
  }

  function updateDraft(index: number, field: keyof DraftItem, value: string) {
    setDraftItems(items => items.map((item, i) => i === index ? { ...item, [field]: value } : item))
  }

  async function createOrder(event: React.FormEvent) {
    event.preventDefault()
    if (!facilityId || !supplierId || draftItems.some(item => !item.medicine_id || Number(item.ordered_quantity) <= 0 || Number(item.unit_cost) < 0 || item.unit_cost === '')) {
      setError('Select a facility and supplier, then complete every medicine line with a valid quantity and unit cost.')
      return
    }
    const ids = draftItems.map(item => item.medicine_id)
    if (new Set(ids).size !== ids.length) {
      setError('Each medicine can appear only once in a purchase order.')
      return
    }
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await request<{ purchase_order_id: number; status: string }>('/purchase-orders/', {
        method: 'POST',
        body: JSON.stringify({
          facility_id: Number(facilityId),
          supplier_id: Number(supplierId),
          expected_delivery_date: deliveryDate ? `${deliveryDate}T00:00:00` : null,
          remarks: remarks || null,
          items: draftItems.map(item => ({
            medicine_id: Number(item.medicine_id),
            ordered_quantity: Number(item.ordered_quantity),
            unit_cost: Number(item.unit_cost),
          })),
        }),
      })
      setNotice(`Purchase order PO-${result.purchase_order_id} created as ${result.status}.`)
      setShowForm(false); setDraftItems([{ medicine_id: '', ordered_quantity: '', unit_cost: '' }])
      setRemarks(''); setDeliveryDate('')
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create purchase order.') }
    finally { setBusy(false) }
  }

  async function changeStatus(order: PO, status: string) {
    setBusy(true); setError(''); setNotice('')
    try {
      await request(`/purchase-orders/${order.purchase_order_id}/status`, {
        method: 'PATCH', body: JSON.stringify({ status }),
      })
      setNotice(`PO-${order.purchase_order_id} updated to ${status}.`)
      await load()
      if (selectedOrder?.purchase_order.purchase_order_id === order.purchase_order_id) await openOrder(order.purchase_order_id)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update purchase order.') }
    finally { setBusy(false) }
  }

  async function openOrder(id: number) {
    setError('')
    try {
      const detail = await request<PODetail>(`/purchase-orders/${id}`)
      setSelectedOrder(detail)
      const drafts: Record<number, ReceiptDraft> = {}
      detail.items.forEach(item => {
        drafts[item.purchase_order_item_id] = {
          received_quantity: String(Math.max(0, item.ordered_quantity - item.received_quantity)),
          batch_number: '', manufactured_on: '', expires_on: '',
        }
      })
      setReceiptDrafts(drafts)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load purchase order details.') }
  }

  function updateReceipt(id: number, field: keyof ReceiptDraft, value: string) {
    setReceiptDrafts(current => ({ ...current, [id]: { ...current[id], [field]: value } }))
  }

  async function receiveGoods(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedOrder) return
    const outstanding = selectedOrder.items.filter(item => item.ordered_quantity > item.received_quantity)
    const receiptItems = outstanding.map(item => {
      const draft = receiptDrafts[item.purchase_order_item_id]
      return { item, draft }
    }).filter(({ draft }) => Number(draft?.received_quantity) > 0)

    if (!receiptItems.length || receiptItems.some(({ draft }) => !draft.batch_number || !draft.expires_on)) {
      setError('Enter a received quantity, batch number and expiry date for at least one outstanding item.')
      return
    }
    setBusy(true); setError(''); setNotice('')
    try {
      const payload = {
        remarks: receiptRemarks || null,
        items: receiptItems.map(({ item, draft }) => ({
          purchase_order_item_id: item.purchase_order_item_id,
          received_quantity: Number(draft.received_quantity),
          batch_number: draft.batch_number,
          manufactured_on: draft.manufactured_on || null,
          expires_on: draft.expires_on,
        })),
      }
      const result = await request<{ purchase_order_status: string }>(`/purchase-orders/${selectedOrder.purchase_order.purchase_order_id}/receive`, {
        method: 'POST', body: JSON.stringify(payload),
      })
      setNotice(`Goods recorded successfully. Purchase order is now ${result.purchase_order_status}.`)
      setReceiptRemarks('')
      await load()
      await openOrder(selectedOrder.purchase_order.purchase_order_id)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not record goods receipt.') }
    finally { setBusy(false) }
  }

  const totalDraft = draftItems.reduce((sum, item) => sum + Number(item.ordered_quantity || 0) * Number(item.unit_cost || 0), 0)
  const canReceive = selectedOrder && ['ORDERED', 'PARTIALLY_RECEIVED'].includes(selectedOrder.purchase_order.status)

  return (
    <div className="page-content operations-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Boxes size={13} /> SUPPLIER & REPLENISHMENT</div>
          <h1>Procurement Management</h1>
          <p>Review replenishment needs, create purchase orders and track supplier deliveries.</p>
        </div>
        <div className="operations-heading-actions">
          <button className="secondary-action" onClick={() => void load()} disabled={loading}><RefreshCw size={15}/> Refresh</button>
          <button className="primary-action" onClick={() => setShowForm(!showForm)}><Plus size={16}/> New purchase order</button>
        </div>
      </div>

      {error && <div className="operations-alert error"><AlertTriangle size={17}/>{error}</div>}
      {notice && <div className="operations-alert success"><Check size={17}/>{notice}</div>}

      <section className="kpi-grid">
        <div className="kpi-card"><div className="kpi-top"><span>PROCUREMENT NEEDS</span><ClipboardList size={18}/></div><div className="kpi-value">{loading ? '…' : summary?.medicines_requiring_procurement ?? '—'}</div><div className="kpi-unit">Medicines requiring procurement</div></div>
        <div className="kpi-card"><div className="kpi-top"><span>GROSS QUANTITY GAP</span><AlertTriangle size={18}/></div><div className="kpi-value">{loading ? '…' : (summary?.total_gross_procurement_quantity ?? 0).toLocaleString()}</div><div className="kpi-unit">Before inbound stock adjustments</div></div>
        <div className="kpi-card"><div className="kpi-top"><span>PROVISIONAL QUANTITY</span><Boxes size={18}/></div><div className="kpi-value">{loading ? '…' : (summary?.total_provisional_procurement_quantity ?? 0).toLocaleString()}</div><div className="kpi-unit">After inbound stock adjustments</div></div>
        <div className="kpi-card"><div className="kpi-top"><span>INBOUND DISPATCHED</span><Truck size={18}/></div><div className="kpi-value">{loading ? '…' : (summary?.total_dispatched_inbound ?? 0).toLocaleString()}</div><div className="kpi-unit">Units in transit from transfers</div></div>
      </section>

      {summary && <div className="procurement-context">
        <span><strong>Usable stock:</strong> {summary.total_usable_stock.toLocaleString()} units</span>
        <span><strong>Pending inbound:</strong> {summary.total_pending_inbound.toLocaleString()}</span>
        <span><strong>Approved inbound:</strong> {summary.total_approved_inbound.toLocaleString()}</span>
        <span><strong>Safety buffer:</strong> {summary.safety_days} days</span>
      </div>}

      {summary?.forecast_is_synthetic && <div className="operations-alert warning"><AlertTriangle size={17}/> Procurement recommendations use simulated demand data and are decision support, not automatic orders. Human approval is required.</div>}

      {showForm && <section className="panel operations-form-panel">
        <div className="panel-heading"><div><h2>Create purchase order</h2><p>New orders start as DRAFT and must pass the approval workflow.</p></div></div>
        <form className="operations-form" onSubmit={createOrder}>
          <label>Receiving facility<select value={facilityId} onChange={e => setFacilityId(e.target.value)} required><option value="">Select facility</option>{facilities.map(f => <option key={f.facility_id} value={f.facility_id}>{f.facility_name}</option>)}</select></label>
          <label>Supplier<select value={supplierId} onChange={e => setSupplierId(e.target.value)} required><option value="">Select supplier</option>{suppliers.map(s => <option key={s.supplier_id} value={s.supplier_id}>{s.supplier_name}{s.city ? ` · ${s.city}` : ''}</option>)}</select></label>
          <label>Expected delivery date<input type="date" value={deliveryDate} onChange={e => setDeliveryDate(e.target.value)} /></label>
          <label>Remarks<input value={remarks} onChange={e => setRemarks(e.target.value)} maxLength={500} placeholder="Optional order notes" /></label>
          <div className="form-span-2 line-items-heading"><h3>Order items</h3><button type="button" className="secondary-action" onClick={() => setDraftItems(items => [...items, { medicine_id: '', ordered_quantity: '', unit_cost: '' }])}><Plus size={14}/> Add medicine</button></div>
          {draftItems.map((item, index) => <div className="po-line-item form-span-2" key={index}>
            <label>Medicine<select value={item.medicine_id} onChange={e => updateDraft(index, 'medicine_id', e.target.value)} required><option value="">Select medicine</option>{medicines.filter(m => !draftItems.some((other, i) => i !== index && other.medicine_id === String(m.medicine_id))).map(m => <option key={m.medicine_id} value={m.medicine_id}>{m.generic_name} · {m.strength}</option>)}</select></label>
            <label>Quantity<input type="number" min="1" value={item.ordered_quantity} onChange={e => updateDraft(index, 'ordered_quantity', e.target.value)} required /></label>
            <label>Unit cost (₹)<input type="number" min="0" step="0.01" value={item.unit_cost} onChange={e => updateDraft(index, 'unit_cost', e.target.value)} required /></label>
            <button type="button" className="remove-line" title="Remove item" disabled={draftItems.length === 1} onClick={() => setDraftItems(items => items.filter((_, i) => i !== index))}><X size={16}/></button>
          </div>)}
          <div className="po-total form-span-2">Estimated order total <strong>{money(totalDraft)}</strong></div>
          <div className="form-actions form-span-2"><button type="button" className="secondary-action" onClick={() => setShowForm(false)}>Cancel</button><button className="primary-action" disabled={busy}>{busy ? 'Creating…' : 'Create draft order'}</button></div>
        </form>
      </section>}

      <section className="panel">
        <div className="panel-heading"><div><h2>Replenishment recommendations</h2><p>Forecast-based procurement gaps with urgency and inbound stock context.</p></div><span className="panel-count">{recommendations.length} recommendations</span></div>
        {recommendations.length === 0 ? <div className="operations-empty">{loading ? 'Loading recommendations…' : 'No procurement recommendations returned by the API.'}</div> :
          <div className="inventory-table-wrapper"><table className="inventory-table"><thead><tr><th>MEDICINE</th><th>FACILITY</th><th>USABLE STOCK</th><th>DEMAND / GAP</th><th>RECOMMENDATION</th></tr></thead><tbody>
            {recommendations.map((rec, index) => {
              const medicine = String(rec.medicine_name ?? rec.generic_name ?? `Medicine ${rec.medicine_id ?? ''}`)
              const facility = String(rec.facility_name ?? rec.facility ?? `Facility ${rec.facility_id ?? ''}`)
              const urgency = String(rec.urgency ?? rec.urgency_level ?? rec.priority ?? 'REVIEW')
              const qty = rec.provisional_procurement_quantity ?? rec.recommended_quantity ?? rec.procurement_quantity ?? rec.gross_procurement_quantity
              return <tr key={String(rec.medicine_id ?? index) + '-' + String(rec.facility_id ?? '')}>
                <td><strong>{medicine}</strong><small className="table-subtext">{String(rec.strength ?? '')}</small></td>
                <td>{facility}</td>
                <td>{String(rec.usable_stock ?? rec.current_usable_stock ?? '—')}</td>
                <td><strong>{qty === undefined ? '—' : Number(qty).toLocaleString()}</strong><small className="table-subtext">Provisional / recommended qty</small></td>
                <td><span className={statusClass(urgency)}>{urgency.replaceAll('_', ' ')}</span><small className="table-subtext">{String(rec.action ?? rec.recommendation_type ?? 'Review recommendation')}</small></td>
              </tr>
            })}
          </tbody></table></div>}
      </section>

      <section className="panel">
        <div className="panel-heading"><div><h2>Purchase order register</h2><p>Manage draft, approval, ordering and goods receipt lifecycle.</p></div></div>
        <div className="table-toolbar"><div className="table-search"><Search size={16}/><input placeholder="Search PO number or remarks" value={search} onChange={e => setSearch(e.target.value)}/></div><select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="ALL">All statuses</option>{['DRAFT','PENDING_APPROVAL','APPROVED','ORDERED','PARTIALLY_RECEIVED','RECEIVED','REJECTED','CANCELLED'].map(s => <option key={s}>{s}</option>)}</select></div>
        <div className="inventory-table-wrapper"><table className="inventory-table"><thead><tr><th>ORDER</th><th>FACILITY</th><th>SUPPLIER</th><th>ORDER DATE</th><th>EXPECTED</th><th>AMOUNT</th><th>STATUS</th><th>WORKFLOW</th></tr></thead><tbody>
          {filteredOrders.map(order => <tr key={order.purchase_order_id}>
            <td><button className="text-link" onClick={() => void openOrder(order.purchase_order_id)}>PO-{order.purchase_order_id}</button></td>
            <td>{facilityName(order.facility_id)}</td><td>{supplierName(order.supplier_id)}</td>
            <td>{new Date(order.order_date).toLocaleDateString()}</td><td>{order.expected_delivery_date ? new Date(order.expected_delivery_date).toLocaleDateString() : '—'}</td>
            <td>{money(order.total_amount)}</td><td><span className={statusClass(order.status)}>{order.status.replaceAll('_', ' ')}</span></td>
            <td><div className="row-actions">
              {order.status === 'DRAFT' && <button title="Submit for approval" disabled={busy} onClick={() => void changeStatus(order, 'PENDING_APPROVAL')}><Check size={15}/></button>}
              {order.status === 'PENDING_APPROVAL' && <><button title="Approve" disabled={busy} onClick={() => void changeStatus(order, 'APPROVED')}><Check size={15}/></button><button title="Reject" disabled={busy} onClick={() => void changeStatus(order, 'REJECTED')}><X size={15}/></button></>}
              {order.status === 'APPROVED' && <button title="Mark as ordered" disabled={busy} onClick={() => void changeStatus(order, 'ORDERED')}><Truck size={15}/></button>}
              {['ORDERED','PARTIALLY_RECEIVED'].includes(order.status) && <button title="Record goods receipt" onClick={() => void openOrder(order.purchase_order_id)}><PackageCheck size={15}/></button>}
              {['DRAFT','PENDING_APPROVAL','APPROVED'].includes(order.status) && <button title="Cancel order" disabled={busy} onClick={() => void changeStatus(order, 'CANCELLED')}><X size={15}/></button>}
              {['RECEIVED','REJECTED','CANCELLED'].includes(order.status) && <button title="View details" onClick={() => void openOrder(order.purchase_order_id)}><Search size={15}/></button>}
            </div></td>
          </tr>)}
          {!loading && filteredOrders.length === 0 && <tr><td colSpan={8}><div className="operations-empty">No purchase orders match these filters.</div></td></tr>}
        </tbody></table></div>
      </section>

      {selectedOrder && <div className="modal-backdrop" onClick={() => setSelectedOrder(null)}>
        <section className="panel po-detail-modal" onClick={e => e.stopPropagation()}>
          <div className="panel-heading"><div><div className="eyebrow">PURCHASE ORDER DETAILS</div><h2>PO-{selectedOrder.purchase_order.purchase_order_id}</h2><p>{facilityName(selectedOrder.purchase_order.facility_id)} · {supplierName(selectedOrder.purchase_order.supplier_id)}</p></div><button className="modal-close" onClick={() => setSelectedOrder(null)}><X size={18}/></button></div>
          <div className="po-detail-summary"><span>Status <strong className={statusClass(selectedOrder.purchase_order.status)}>{selectedOrder.purchase_order.status.replaceAll('_', ' ')}</strong></span><span>Total <strong>{money(selectedOrder.purchase_order.total_amount)}</strong></span></div>
          <div className="inventory-table-wrapper"><table className="inventory-table"><thead><tr><th>MEDICINE</th><th>ORDERED</th><th>RECEIVED</th><th>OUTSTANDING</th><th>UNIT COST</th></tr></thead><tbody>
            {selectedOrder.items.map(item => <tr key={item.purchase_order_item_id}><td>{medicineName(item.medicine_id)}</td><td>{item.ordered_quantity}</td><td>{item.received_quantity}</td><td>{item.ordered_quantity - item.received_quantity}</td><td>{money(item.unit_cost)}</td></tr>)}
          </tbody></table></div>
          {canReceive && <form className="receipt-form" onSubmit={receiveGoods}>
            <h3>Record goods received</h3>
            <p>Enter the delivery batch details for each item being received. You can record partial quantities.</p>
            {selectedOrder.items.filter(item => item.ordered_quantity > item.received_quantity).map(item => {
              const draft = receiptDrafts[item.purchase_order_item_id]
              const outstanding = item.ordered_quantity - item.received_quantity
              return <div className="receipt-item" key={item.purchase_order_item_id}>
                <strong>{medicineName(item.medicine_id)}</strong><span className="table-subtext">{outstanding} units outstanding</span>
                <div className="receipt-fields">
                  <label>Received qty<input type="number" min="0" max={outstanding} value={draft?.received_quantity ?? ''} onChange={e => updateReceipt(item.purchase_order_item_id, 'received_quantity', e.target.value)}/></label>
                  <label>Batch number<input value={draft?.batch_number ?? ''} onChange={e => updateReceipt(item.purchase_order_item_id, 'batch_number', e.target.value)} /></label>
                  <label>Manufactured on<input type="date" value={draft?.manufactured_on ?? ''} onChange={e => updateReceipt(item.purchase_order_item_id, 'manufactured_on', e.target.value)}/></label>
                  <label>Expires on<input type="date" value={draft?.expires_on ?? ''} onChange={e => updateReceipt(item.purchase_order_item_id, 'expires_on', e.target.value)} required={Number(draft?.received_quantity) > 0}/></label>
                </div>
              </div>
            })}
            <label className="receipt-remarks">Receipt remarks<input value={receiptRemarks} onChange={e => setReceiptRemarks(e.target.value)} placeholder="Optional delivery notes"/></label>
            <button className="primary-action" disabled={busy}>{busy ? 'Saving receipt…' : 'Confirm goods receipt'}</button>
          </form>}
          {!canReceive && <div className="form-hint">Goods receipt is available when the purchase order reaches ORDERED or PARTIALLY RECEIVED.</div>}
        </section>
      </div>}
    </div>
  )
}
