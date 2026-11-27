// Charging points of the charging providers: labels, status colours, popups.

const PLUGS = {
  'Type 2 Outlet': 'Type 2',
  'Type 2 Connector (Cable Attached)': 'Type 2 cable',
  'CCS Combo 2 Plug (Cable Attached)': 'CCS2',
  'CHAdeMO': 'CHAdeMO',
  'Type F Schuko': 'Schuko',
}

export const plugLabel = p => PLUGS[p] || p

// available | busy | down | unknown
export function statusClass(status) {
  const s = (status || '').toLowerCase()
  if (s === 'available') return 'available'
  if (['occupied', 'reserved', 'charging'].includes(s)) return 'busy'
  if (['outofservice', 'faulted', 'inoperative', 'offline'].includes(s)) return 'down'
  return 'unknown'
}

export const STATUS_COLORS = { available: '#22c55e', busy: '#f59e0b', down: '#ef4444', unknown: '#94a3b8' }

const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// Where to draw a charging point: some provider records have latitude and
// longitude swapped; next to a known position, the closer reading wins.
export function stationLatLng(st, near = null) {
  if (st?.latitude == null || st?.longitude == null) return null
  const a = [st.latitude, st.longitude]
  const b = [st.longitude, st.latitude]
  if (!near) return Math.abs(st.latitude) <= 90 ? a : b
  const d = p => (p[0] - near[0]) ** 2 + (p[1] - near[1]) ** 2
  return d(b) < d(a) ? b : a
}

// One line per connector of a station (an EVSE is one connector)
function connectorLine(st) {
  const parts = []
  if (st.max_power_kw) parts.push(`${st.max_power_kw} kW ${st.is_dc == null ? '' : st.is_dc ? 'DC' : 'AC'}`.trim())
  if (st.plugs?.length) parts.push(st.plugs.map(plugLabel).join(', '))
  if (st.price != null) parts.push(`€${st.price.toFixed(2)}/${st.price_unit || 'kWh'}`)
  const status = st.status ? ` <span style="color:${STATUS_COLORS[statusClass(st.status)]}">● ${escapeHtml(st.status)}</span>` : ''
  return `<div>${escapeHtml(parts.join(' · ') || st.evse_id)}${status}</div>`
}

// Popup of the connectors at one place (same name/position)
export function stationPopupHtml(connectors, extra = '') {
  const first = connectors[0]
  const title = escapeHtml(first.name || first.operator || 'Charging point')
  const sub = [first.name ? first.operator : null, first.address].filter(Boolean).map(escapeHtml).join('<br>')
  const by = escapeHtml(first.provider_label || '')
  return `<div class="station-popup"><strong>${title}</strong>${by ? ` <small>· ${by}</small>` : ''}`
    + `${sub ? `<div style="opacity:.75">${sub}</div>` : ''}`
    + `<div style="margin-top:4px">${connectors.map(connectorLine).join('')}</div>${extra}</div>`
}

// Group connectors standing at the same place (one marker per station)
export function groupByPlace(stations) {
  const groups = new Map()
  for (const st of stations) {
    const pos = stationLatLng(st)
    if (!pos) continue
    const key = `${st.provider}:${pos[0].toFixed(5)},${pos[1].toFixed(5)}`
    if (!groups.has(key)) groups.set(key, { pos, connectors: [] })
    groups.get(key).connectors.push(st)
  }
  return [...groups.values()]
}

// The best status of a station's connectors (for the marker colour)
export function placeStatus(connectors) {
  const classes = connectors.map(c => statusClass(c.status))
  for (const c of ['available', 'busy', 'down']) if (classes.includes(c)) return c
  return 'unknown'
}
