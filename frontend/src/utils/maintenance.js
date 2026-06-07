// Shared formatting helpers for the maintenance views.

/** Parse a naive-UTC ISO string from the API as a proper UTC Date. */
export function parseUTC(ts) {
  if (!ts) return null
  if (ts.endsWith('Z') || ts.includes('+') || ts.includes('-', 10)) return new Date(ts)
  return new Date(ts + 'Z')
}

export function formatDate(ts) {
  if (!ts) return '—'
  return parseUTC(ts).toLocaleDateString()
}

export function formatInterval(item) {
  const parts = []
  if (item.interval_km) parts.push(`${item.interval_km.toLocaleString()} km`)
  if (item.interval_months) parts.push(`${item.interval_months} mo`)
  return parts.join(' / ') || '—'
}

export function formatLastDone(item) {
  if (item.last_done_date) {
    const d = parseUTC(item.last_done_date)
    return `${d.toLocaleDateString()}${item.last_done_km != null ? ' @ ' + item.last_done_km.toLocaleString() + ' km' : ''}`
  }
  return 'Never'
}

export function formatDue(item) {
  if (!item.last_done_date && item.last_done_km == null) return '—'
  const parts = []
  if (item.last_done_km != null && item.interval_km) {
    parts.push(`${(item.last_done_km + item.interval_km).toLocaleString()} km`)
  }
  if (item.last_done_date && item.interval_months) {
    const due = parseUTC(item.last_done_date)
    due.setMonth(due.getMonth() + item.interval_months)
    parts.push(due.toLocaleDateString())
  }
  return parts.join(' / ') || '—'
}

/** Human summary of how far an alert is from due (km and/or days). */
export function formatRemaining(alert) {
  const parts = []
  if (alert.remaining_km != null) {
    const km = alert.remaining_km
    parts.push(km < 0 ? `${Math.abs(km).toLocaleString()} km over` : `in ${km.toLocaleString()} km`)
  }
  if (alert.remaining_days != null) {
    const d = alert.remaining_days
    parts.push(d < 0 ? `${Math.abs(d)} d over` : `in ${d} d`)
  }
  return parts.join(' · ') || '—'
}
