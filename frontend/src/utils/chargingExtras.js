// Extra costs of a charging session — the live preview of the session dialog.
// Same rules as the backend (leapconnect/domain/charging/extras.py), which
// computes the saved amounts.

export const EXTRA_KINDS = [
  { id: 'fixed', label: 'Fixed amount' },
  { id: 'time', label: 'Time-based' },
  { id: 'per_kwh', label: 'Per kWh' },
  { id: 'percent', label: '% of energy cost' },
]

export const START_REFS = [
  { id: 'charge_start', label: 'charge start' },
  { id: 'charge_end', label: 'charge end' },
]

export const END_REFS = [
  { id: 'charge_end', label: 'charge end' },
  { id: 'unplug', label: 'unplug' },
  { id: 'departure', label: 'departure' },
  { id: 'manual', label: 'a set duration' },
]

const UNIT_MINUTES = { minute: 1, hour: 60 }

function blank(kind) {
  return {
    kind,
    label: '',
    included: true,
    amount: null,
    rate: null,
    time_unit: 'hour',
    billing: 'exact',
    start_ref: 'charge_end',
    start_offset_min: 0,
    end_ref: 'unplug',
    duration_min: null,
    cap: null,
  }
}

// Common extras, prefilled: the user only types the amount or the rate
export const EXTRA_PRESETS = [
  { id: 'session', label: 'Session fee', make: () => ({ ...blank('fixed'), label: 'Session fee' }) },
  {
    id: 'idle',
    label: 'Idle fee (after the charge)',
    make: () => ({ ...blank('time'), label: 'Idle fee', time_unit: 'minute', start_offset_min: 0, end_ref: 'unplug' }),
  },
  {
    id: 'parking',
    label: 'Parking',
    make: () => ({ ...blank('time'), label: 'Parking', start_ref: 'charge_start', end_ref: 'departure', billing: 'started' }),
  },
  {
    id: 'time_fee',
    label: 'Per-minute charging fee',
    make: () => ({ ...blank('time'), label: 'Charging time fee', time_unit: 'minute', start_ref: 'charge_start', end_ref: 'charge_end' }),
  },
  { id: 'roaming', label: 'Roaming surcharge (per kWh)', make: () => ({ ...blank('per_kwh'), label: 'Roaming surcharge' }) },
  { id: 'payment', label: 'Payment fee (%)', make: () => ({ ...blank('percent'), label: 'Payment fee' }) },
  { id: 'discount', label: 'Discount', make: () => ({ ...blank('fixed'), label: 'Discount' }) },
  { id: 'custom', label: 'Custom…', make: () => blank('fixed') },
]

const num = v => (v === '' || v == null || Number.isNaN(Number(v)) ? null : Number(v))

// { begin, finish, minutes } of a time-based extra; finish/minutes are null
// while the end isn't known (e.g. still plugged in)
export function extraWindow(extra, ctx) {
  if (extra.end_ref === 'manual') {
    return { begin: null, finish: null, minutes: num(extra.duration_min) }
  }
  let begin = extra.start_ref === 'charge_start' ? ctx.startTs : ctx.endTs
  const finish = { charge_end: ctx.endTs, unplug: ctx.unplugTs, departure: ctx.departureTs }[extra.end_ref] || null
  if (!begin) return { begin: null, finish, minutes: null }
  begin = new Date(begin.getTime() + (num(extra.start_offset_min) || 0) * 60000)
  if (!finish) return { begin, finish: null, minutes: null }
  return { begin, finish, minutes: Math.max(0, Math.floor((finish - begin) / 60000)) }
}

// Amount of one extra; null when it can't be computed
export function extraCost(extra, ctx) {
  if (extra.kind === 'fixed') return num(extra.amount)
  const rate = num(extra.rate)
  if (rate == null) return null
  if (extra.kind === 'per_kwh') return ctx.energyKwh == null ? null : rate * ctx.energyKwh
  if (extra.kind === 'percent') return ctx.energyCost == null ? null : (rate * ctx.energyCost) / 100
  const { minutes } = extraWindow(extra, ctx)
  if (minutes == null) return null
  let units = minutes / (UNIT_MINUTES[extra.time_unit] || 60)
  if (extra.billing === 'started') units = Math.ceil(units)
  let cost = rate * units
  const cap = num(extra.cap)
  if (cap != null) cost = Math.min(cost, cap)
  return cost
}

// The fields the API takes (no id, no computed values)
export function extraPayload(extra) {
  const { kind, label, included, time_unit, billing, start_ref, end_ref } = extra
  return {
    kind,
    label: label || '',
    included: included !== false,
    amount: num(extra.amount),
    rate: num(extra.rate),
    time_unit,
    billing,
    start_ref,
    start_offset_min: num(extra.start_offset_min) || 0,
    end_ref,
    duration_min: num(extra.duration_min),
    cap: num(extra.cap),
  }
}

// Total cost of a session (energy + extras counted in it), for the summaries
export function sessionTotal(s) {
  return s.total_cost ?? s.cost ?? 0
}
