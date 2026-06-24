// Resolve the active accent colour for non-CSS contexts (canvas charts,
// Leaflet vector layers, dynamically-built marker HTML) where a `var(--accent)`
// string cannot be used. Reads the computed CSS custom properties so it always
// reflects the current theme + selected vehicle colour.

const FALLBACK_HEX = '#00d4ff'
const FALLBACK_RGB = '0, 212, 255'

function readVar(name, fallback) {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

// Current accent as a hex string, e.g. "#79cfae".
export function accentHex() {
  return readVar('--accent', FALLBACK_HEX)
}

// Current accent as an "r, g, b" triplet string.
export function accentRgb() {
  return readVar('--accent-rgb', FALLBACK_RGB)
}

// Current accent as an rgba() string with the given alpha.
export function accentRgba(alpha) {
  return `rgba(${accentRgb()}, ${alpha})`
}
