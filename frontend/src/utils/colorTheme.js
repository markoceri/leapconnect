// Generate a full, standalone UI theme built around a single base colour — the
// vehicle's factory colour. This is NOT a tinted variant of dark/light: it is a
// third theme option ("car colour") whose brightness and saturation adapt to
// the colour itself. Light paints (e.g. Light White) yield a light theme, dark
// paints (e.g. Starry Night Blue) yield a dark theme; vivid paints colour the
// whole interface strongly, near-greys stay tastefully neutral.

function hexToHsl(hex) {
  const h = hex.replace('#', '')
  const f = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const r = parseInt(f.slice(0, 2), 16) / 255
  const g = parseInt(f.slice(2, 4), 16) / 255
  const b = parseInt(f.slice(4, 6), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  let s = 0
  let hue = 0
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) hue = ((g - b) / d + (g < b ? 6 : 0)) / 6
    else if (max === g) hue = ((b - r) / d + 2) / 6
    else hue = ((r - g) / d + 4) / 6
  }
  return { h: hue * 360, s: s * 100, l: l * 100 }
}

function hslToHex(h, s, l) {
  s = Math.max(0, Math.min(100, s)) / 100
  l = Math.max(0, Math.min(100, l)) / 100
  const k = (n) => (n + h / 30) % 12
  const a = s * Math.min(l, 1 - l)
  const f = (n) => {
    const v = l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
    return Math.round(255 * v)
      .toString(16)
      .padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

function hexToRgbStr(hex) {
  const h = hex.replace('#', '')
  const f = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  return `${parseInt(f.slice(0, 2), 16)}, ${parseInt(f.slice(2, 4), 16)}, ${parseInt(f.slice(4, 6), 16)}`
}

// Dark theme: [cssVar, saturation-factor, lightness%]. actual S = chroma*factor.
const DARK_TOKENS = [
  ['--bg', 1.0, 8],
  ['--bg2', 0.95, 10],
  ['--card', 0.85, 13],
  ['--input', 0.95, 9],
  ['--elevated', 0.75, 17],
  ['--border', 0.7, 23],
  ['--border2', 0.7, 19],
  ['--divider', 0.7, 16],
  ['--btn-bg', 0.9, 21],
  ['--btn-border', 0.8, 29],
  ['--btn-hover', 0.9, 27],
  ['--toggle-bg', 0.9, 21],
  ['--toggle-border', 0.8, 29],
  ['--toggle-knob', 0.5, 40],
  ['--tooltip-bg', 0.8, 15],
  ['--tooltip-border', 0.7, 21],
  ['--heatmap-empty', 0.7, 15],
  ['--chart-grid', 0.6, 23],
  ['--text', 0.18, 92],
  ['--heading', 0.18, 85],
  ['--sub', 0.22, 64],
  ['--label', 0.22, 52],
  ['--muted3', 0.22, 45],
  ['--muted', 0.2, 38],
  ['--muted2', 0.2, 31],
  ['--chart-tick', 0.2, 38],
]

const LIGHT_TOKENS = [
  ['--bg', 0.55, 96],
  ['--bg2', 0.5, 98],
  ['--card', 0.0, 100],
  ['--input', 0.5, 95],
  ['--elevated', 0.55, 94],
  ['--border', 0.55, 89],
  ['--border2', 0.5, 92],
  ['--divider', 0.55, 89],
  ['--btn-bg', 0.6, 93],
  ['--btn-border', 0.6, 86],
  ['--btn-hover', 0.6, 90],
  ['--toggle-bg', 0.6, 86],
  ['--toggle-border', 0.6, 82],
  ['--toggle-knob', 0.4, 64],
  ['--tooltip-bg', 0.0, 100],
  ['--tooltip-border', 0.6, 86],
  ['--heatmap-empty', 0.55, 94],
  ['--chart-grid', 0.55, 89],
  ['--text', 0.5, 14],
  ['--heading', 0.5, 14],
  ['--sub', 0.4, 34],
  ['--label', 0.4, 34],
  ['--muted3', 0.4, 34],
  ['--muted', 0.35, 40],
  ['--muted2', 0.3, 52],
  ['--chart-tick', 0.35, 40],
]

// Generate a full theme around baseHex.
// Returns { vars: { cssVar: value }, base: 'dark' | 'light' }.
export function generateVehicleTheme(baseHex) {
  const c = hexToHsl(baseHex)
  // Light paints -> light theme; everything else -> dark theme.
  const isLight = c.l >= 62
  const tokens = isLight ? LIGHT_TOKENS : DARK_TOKENS
  // Theme saturation derives from the paint: greys stay near-neutral, vivid
  // paints colour strongly. Capped so it never looks garish.
  const chroma = isLight ? clamp(c.s, 14, 52) : clamp(c.s, 12, 48)

  const out = {}
  for (const [name, factor, light] of tokens) {
    out[name] = hslToHex(c.h, chroma * factor, light)
  }

  // Accent: a readable rendition of the *actual* paint colour. We keep the
  // paint's own saturation (so muted paints like Canopy Grey stay grey rather
  // than turning vivid) and only adjust lightness for contrast on the theme.
  const accentS = clamp(c.s, 0, 90)
  const accentL = isLight ? clamp(c.l, 30, 46) : clamp(c.l < 40 ? c.l + 22 : c.l, 50, 72)
  const accent = hslToHex(c.h, accentS, accentL)
  out['--accent'] = accent
  out['--accent-rgb'] = hexToRgbStr(accent)

  if (isLight) {
    out['--hero-bg'] = `linear-gradient(160deg, ${hslToHex(c.h, chroma * 0.6, 95)}, ${hslToHex(c.h, chroma * 0.5, 97)})`
    out['--skeleton'] = `linear-gradient(90deg, ${out['--border']} 25%, ${hslToHex(c.h, chroma * 0.5, 95)} 50%, ${out['--border']} 75%)`
    out['--shadow-card'] = '0 2px 8px #1a24200a, 0 1px 3px #1a242006'
    out['--shadow-menu'] = '0 8px 24px #1a242018, 0 2px 8px #1a242010'
  } else {
    out['--hero-bg'] = `linear-gradient(160deg, ${hslToHex(c.h, chroma, 9)}, ${hslToHex(c.h, chroma * 0.85, 13)})`
    out['--skeleton'] = `linear-gradient(90deg, ${out['--btn-bg']} 25%, ${hslToHex(c.h, chroma * 0.9, 28)} 50%, ${out['--btn-bg']} 75%)`
    out['--shadow-card'] = 'none'
    out['--shadow-menu'] = '0 12px 32px #000a, 0 2px 8px #0004'
  }
  return { vars: out, base: isLight ? 'light' : 'dark' }
}

// The set of variables generateVehicleTheme can set — used to clear overrides.
export const THEME_VARS = [
  ...new Set([
    ...DARK_TOKENS.map((t) => t[0]),
    ...LIGHT_TOKENS.map((t) => t[0]),
    '--accent',
    '--accent-rgb',
    '--hero-bg',
    '--skeleton',
    '--shadow-card',
    '--shadow-menu',
  ]),
]
