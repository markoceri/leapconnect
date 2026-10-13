import { reactive } from 'vue'
import { api } from './useApi'

// Installed software and pending OTA update per VIN, shared by the Details
// card, the Dashboard pill and the FOTA dialog. The backend caches the cloud
// answer for hours; this only avoids duplicate requests between components.
const state = reactive({}) // vin -> { data, loading, error }
const inflight = {}

export function softwareState(vin) {
  if (!state[vin]) state[vin] = { data: null, loading: false, error: '' }
  return state[vin]
}

export async function loadSoftware(vin, { refresh = false } = {}) {
  if (!vin) return null
  const entry = softwareState(vin)
  if (entry.data && !refresh) return entry.data
  if (inflight[vin] && !refresh) return inflight[vin]
  entry.loading = true
  entry.error = ''
  inflight[vin] = api('GET', `/api/vehicles/${vin}/software${refresh ? '?refresh=true' : ''}`)
    .then(data => { entry.data = data; return data })
    .catch(e => { entry.error = e.message || 'Failed to load software info'; return null })
    .finally(() => { entry.loading = false; delete inflight[vin] })
  return inflight[vin]
}

// Download links: plain same-origin GETs (the session cookie authenticates them),
// relative so they work behind the Home Assistant ingress path too.
export function packageDownloadUrl(vin, seq) {
  return `./api/vehicles/${vin}/software/packages/${seq}/download`
}

export function updateDownloadUrl(vin) {
  return `./api/vehicles/${vin}/software/download`
}

// Drop the loaded answers (e.g. the notes language changed).
export function resetSoftware() {
  for (const entry of Object.values(state)) entry.data = null
}

// Decimal units, as the official app shows sizes (1.89 GB).
export function formatBytes(bytes) {
  if (!bytes) return '0 B'
  for (const [unit, factor] of [['GB', 1e9], ['MB', 1e6], ['KB', 1e3]]) {
    if (bytes >= factor) return `${(bytes / factor).toFixed(bytes >= 1e9 ? 2 : 1)} ${unit}`
  }
  return `${bytes} B`
}

export function formatDay(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// Languages the Leapmotor cloud provides release notes in.
export const NOTE_LANGUAGES = [
  ['da-DK', 'Dansk'], ['de-DE', 'Deutsch'], ['el-GR', 'Ελληνικά'], ['en-US', 'English'],
  ['es-ES', 'Español'], ['fr-FR', 'Français'], ['he-IL', 'עברית'], ['it-IT', 'Italiano'],
  ['nl-NL', 'Nederlands'], ['no-NO', 'Norsk'], ['pl-PL', 'Polski'], ['pt-PT', 'Português'],
  ['ro-RO', 'Română'], ['sl-SI', 'Slovenščina'], ['tr-TR', 'Türkçe'], ['zh-CN', '中文'],
]
