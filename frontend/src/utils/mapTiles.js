// Map base layers: one place for every dashboard map's tile provider.
//
// The provider is chosen in Settings → General → Map (GET/PUT /api/map-tiles)
// and defaults to OpenStreetMap, which needs no API key. Providers without a
// dark style get one from a CSS filter (`.map-tiles-dark-filter`, main.css).

import { reactive, watch } from 'vue'
import L from 'leaflet'
import { api } from '../composables/useApi'
import { useAppStore } from '../stores/appStore'

const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'

// `dark`: a URL template, null to invert the light tiles with the CSS filter,
// or 'same' to keep the light tiles as they are (satellite imagery).
// `key`: 'required' | 'optional' | false — appended as `keyParam`.
export const MAP_PROVIDERS = [
  {
    id: 'osm',
    label: 'OpenStreetMap',
    description: 'Free, no API key. Dark mode is an inverted version of the standard map.',
    key: false,
    light: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    dark: null,
    maxZoom: 19,
    attribution: OSM_ATTRIBUTION,
  },
  {
    id: 'carto',
    label: 'CARTO',
    description: 'Positron / Dark Matter styles. Free personal key (5M requests/month).',
    key: 'required',
    keyParam: 'key',
    keyUrl: 'https://carto.com/basemaps/apikey',
    light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    subdomains: 'abcd',
    maxZoom: 19,
    attribution: `${OSM_ATTRIBUTION} &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>`,
  },
  {
    id: 'maptiler',
    label: 'MapTiler',
    description: 'Streets light / dark styles. Free key with a monthly quota.',
    key: 'required',
    keyParam: 'key',
    keyUrl: 'https://cloud.maptiler.com/account/keys/',
    light: 'https://api.maptiler.com/maps/streets-v2/256/{z}/{x}/{y}{r}.png',
    dark: 'https://api.maptiler.com/maps/streets-v2-dark/256/{z}/{x}/{y}{r}.png',
    maxZoom: 20,
    attribution: `&copy; <a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener">MapTiler</a> ${OSM_ATTRIBUTION}`,
  },
  {
    id: 'stadia',
    label: 'Stadia Maps',
    description: 'Alidade Smooth light / dark styles. Use an API key, or leave it empty if your domain is registered with Stadia.',
    key: 'optional',
    keyParam: 'api_key',
    keyUrl: 'https://client.stadiamaps.com/',
    light: 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png',
    dark: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
    maxZoom: 20,
    attribution: `&copy; <a href="https://stadiamaps.com/" target="_blank" rel="noopener">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> ${OSM_ATTRIBUTION}`,
  },
  {
    id: 'esri_imagery',
    label: 'Esri satellite',
    description: 'Satellite imagery, no API key. Handy for drawing zones.',
    key: false,
    light: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    dark: 'same',
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics, and the GIS User Community',
  },
  {
    id: 'custom',
    label: 'Custom URL',
    description: 'Any XYZ raster tile server, e.g. a self-hosted one. Put the API key straight in the URL if needed.',
    key: false,
    maxZoom: 19,
    attribution: '',
  },
]

export function getMapProvider(id) {
  return MAP_PROVIDERS.find(p => p.id === id) || MAP_PROVIDERS[0]
}

// ── Shared settings ─────────────────────────────────────────────────────────
// Seeded from localStorage so maps open with the right tiles before the API
// answers; refreshed once per page load and after every save.
const STORAGE_KEY = 'mapTiles'

export const mapTileSettings = reactive({
  provider: 'osm',
  api_keys: {},
  custom_url: '',
  custom_dark_url: '',
})

function applyMapTileSettings(data) {
  mapTileSettings.provider = data?.provider || 'osm'
  mapTileSettings.api_keys = { ...(data?.api_keys || {}) }
  mapTileSettings.custom_url = data?.custom_url || ''
  mapTileSettings.custom_dark_url = data?.custom_dark_url || ''
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(mapTileSettings)) } catch { /* ignore */ }
}

try {
  const cached = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
  if (cached) applyMapTileSettings(cached)
} catch { /* ignore */ }

let loadPromise = null

export function loadMapTileSettings({ force = false } = {}) {
  if (!loadPromise || force) {
    loadPromise = api('GET', '/api/map-tiles')
      .then(applyMapTileSettings)
      .catch(() => { loadPromise = null })
  }
  return loadPromise
}

export async function saveMapTileSettings(settings) {
  applyMapTileSettings(await api('PUT', '/api/map-tiles', settings))
  return mapTileSettings
}

// ── Tile layer factory ──────────────────────────────────────────────────────
function isDarkTheme() {
  return document.documentElement.getAttribute('data-theme') !== 'light'
}

function withKey(url, provider) {
  const key = provider.key && mapTileSettings.api_keys[provider.id]
  if (!key) return url
  return `${url}${url.includes('?') ? '&' : '?'}${provider.keyParam}=${encodeURIComponent(key)}`
}

// Resolve the URL template + Leaflet options for the active provider/theme.
export function resolveTileLayer() {
  const provider = getMapProvider(mapTileSettings.provider)
  const dark = isDarkTheme()
  let light = provider.light
  let darkUrl = provider.dark
  if (provider.id === 'custom') {
    light = mapTileSettings.custom_url || MAP_PROVIDERS[0].light
    darkUrl = mapTileSettings.custom_dark_url || null
  }
  let url = light
  let filtered = false
  if (dark && darkUrl === null) filtered = true
  else if (dark && darkUrl !== 'same') url = darkUrl

  const options = {
    maxZoom: provider.maxZoom,
    attribution: provider.attribution,
    className: filtered ? 'map-tiles-dark-filter' : '',
  }
  if (provider.subdomains) options.subdomains = provider.subdomains
  return { url: withKey(url, provider), options }
}

// Add the configured base layer to `map` and keep it in sync with the theme
// and the provider settings until the map is removed.
export function addBaseLayer(map) {
  const store = useAppStore()
  loadMapTileSettings()

  if (!map.attributionControl) {
    map.attributionControl = L.control.attribution({ prefix: false }).addTo(map)
  }

  let layer = null
  function render() {
    const { url, options } = resolveTileLayer()
    if (layer) map.removeLayer(layer)
    layer = L.tileLayer(url, options).addTo(map)
    layer.bringToBack()
  }
  render()

  const stop = watch(
    [() => store.theme, () => JSON.stringify(mapTileSettings)],
    render,
  )
  map.once('unload', stop)
}
