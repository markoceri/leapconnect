export function doorState(val) {
  if (val === true) return { text: 'Open', cls: 'bad' }
  if (val === false) return { text: 'Closed', cls: 'good' }
  return { text: '—', cls: '' }
}

export function climateMode(val) {
  const modes = { 0: 'Off', 1: 'Cooling', 2: 'Heating', 3: 'Auto' }
  return modes[val] || `Mode ${val}`
}

export function gearLabel(val) {
  const gears = { 0: 'P', 1: 'R', 2: 'N', 3: 'D' }
  return gears[val] || `Gear ${val}`
}

export function formatTime(isoStr) {
  try {
    return new Date(isoStr).toLocaleString()
  } catch {
    return isoStr
  }
}

export function formatNumber(val) {
  return typeof val === 'number' ? val.toLocaleString() : val
}
