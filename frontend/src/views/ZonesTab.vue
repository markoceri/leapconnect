<template>
  <div class="zones-tab">
    <div class="zone-map-container" ref="mapEl"></div>

    <!-- Floating zones panel (top-left) -->
    <div class="zone-panel" :class="{ collapsed: panelCollapsed }">
      <div class="zone-panel-head">
        <div class="zone-panel-title">
          <MapPinned :size="15" />
          <span>Zones</span>
          <span class="zone-count" v-if="zones.length">{{ zones.length }}</span>
        </div>
        <button class="icon-btn" @click="panelCollapsed = !panelCollapsed" :title="panelCollapsed ? 'Expand' : 'Collapse'">
          <component :is="panelCollapsed ? ChevronDown : ChevronUp" :size="16" />
        </button>
      </div>

      <div v-show="!panelCollapsed" class="zone-panel-body">
        <p class="zone-panel-desc">
          Geographic areas defined on the map, reusable across several app features.
        </p>
        <div class="zone-add-wrap">
          <button class="add-btn" @click="addMenuOpen = !addMenuOpen">
            <Plus :size="15" /> Add zone
          </button>
          <div v-if="addMenuOpen" class="add-menu">
            <button @click="startDraw('Circle')"><Circle :size="14" /> Circle</button>
            <button @click="startDraw('Polygon')"><Hexagon :size="14" /> Polygon</button>
          </div>
        </div>

        <p v-if="drawingHint" class="draw-hint">{{ drawingHint }}</p>

        <div class="zone-list">
          <p v-if="!zones.length" class="zone-empty">No zones yet. Draw one on the map.</p>
          <div v-for="z in zones" :key="z.id" class="zone-row" :class="{ editing: editingShapeId === z.id }" @click="focusZone(z)">
            <component :is="z.shape_type === 'polygon' ? Hexagon : Circle" :size="14" class="zone-row-icon" />
            <div class="zone-row-main">
              <span class="zone-row-name">{{ z.name }}</span>
              <span class="zone-row-meta">
                <span v-if="z.notify_on_enter || z.notify_on_exit">
                  {{ [z.notify_on_enter && 'enter', z.notify_on_exit && 'exit'].filter(Boolean).join('/') }}
                </span>
                <span v-if="z.charging_tier_id" class="zone-row-tier">· {{ tierLabel(z.charging_tier_id) }}</span>
              </span>
            </div>
            <button class="icon-btn" @click.stop="editShape(z)" title="Edit shape"><Spline :size="14" /></button>
            <button class="icon-btn" @click.stop="openEditForm(z)" title="Edit details"><Pencil :size="14" /></button>
            <button class="icon-btn danger" @click.stop="deleteTarget = z" title="Delete"><Trash2 :size="14" /></button>
          </div>
        </div>
        <p v-if="zones.length" class="zone-tip">Tip: click a zone on the map (or the shape icon) to reshape it.</p>
      </div>
    </div>

    <!-- Layers control (bottom-left) -->
    <div class="layers-control" :class="{ open: layersOpen }">
      <button class="layers-toggle" @click="layersOpen = !layersOpen">
        <Layers :size="15" />
        <span>Layers</span>
        <Loader2 v-if="overlayLoading" :size="13" class="spin" />
      </button>
      <div v-show="layersOpen" class="layers-body">
        <label v-for="o in OVERLAY_DEFS" :key="o.key" class="layer-row">
          <input type="checkbox" :checked="overlays[o.key]" @change="toggleOverlay(o.key)" />
          <span class="layer-swatch" :style="{ background: o.color }">{{ o.emoji }}</span>
          <span class="layer-label">{{ o.label }}</span>
        </label>
        <p v-if="anyOverlayOn && zoomTooLow" class="layer-note">Zoom in to load points.</p>
        <p class="layer-attrib">POI data © OpenStreetMap</p>
      </div>
    </div>

    <div v-if="editingShapeId != null" class="edit-hint">
      <span>Editing “{{ editingZoneName }}” — drag the points to reshape.</span>
      <button class="edit-done" @click="disableShapeEdit">Done</button>
    </div>

    <div v-if="error" class="zone-error">{{ error }}</div>

    <!-- Add / Edit modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
      <div class="modal-dialog">
        <div class="modal-head">
          <h3>{{ editingId ? 'Edit zone' : 'New zone' }}</h3>
          <button class="icon-btn" @click="closeForm"><X :size="18" /></button>
        </div>

        <div class="form-group">
          <label>Name</label>
          <input v-model="form.name" type="text" placeholder="Home, Work, ..." />
        </div>

        <div class="form-group">
          <label>Shape</label>
          <div class="shape-pill">
            <component :is="formShapeType === 'polygon' ? Hexagon : Circle" :size="14" />
            <span>{{ formShapeType === 'polygon' ? 'Polygon' : 'Circle' }}</span>
            <span class="shape-pill-hint" v-if="!editingId">drawn on the map</span>
            <span class="shape-pill-hint" v-else>reshape it from the map</span>
          </div>
        </div>

        <div class="form-group">
          <label>Notifications</label>
          <div class="toggle-row">
            <label class="chk"><input type="checkbox" v-model="form.notify_on_enter" /> Notify on enter</label>
            <label class="chk"><input type="checkbox" v-model="form.notify_on_exit" /> Notify on exit</label>
          </div>
        </div>

        <div class="form-group">
          <label>Charging tier</label>
          <select v-model="form.charging_tier_id" class="select">
            <option value="">No auto-selection</option>
            <option v-for="t in chargingTiers" :key="t.id" :value="t.id">{{ t.label }}</option>
          </select>
          <p class="field-desc">
            When an AC charge starts inside this zone, the session is billed at
            this tier. DC charges always stay "public_dc".
          </p>
        </div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="closeForm">Cancel</button>
          <button class="btn-primary" :disabled="saving || !form.name" @click="saveForm">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :visible="deleteTarget != null"
      title="Delete zone?"
      :message="`Delete the zone '${deleteTarget?.name}'? This cannot be undone.`"
      confirm-label="Delete"
      cancel-label="Cancel"
      variant="danger"
      icon="trash"
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { api } from '../composables/useApi'
import { useAppStore } from '../stores/appStore'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  MapPinned, Plus, Pencil, Trash2, Circle, Hexagon, Layers, Spline,
  ChevronDown, ChevronUp, X, Loader2,
} from 'lucide-vue-next'

const store = useAppStore()

// Overpass POI overlay definitions: emoji marker + the OSM selectors used to
// fetch them for the current viewport.
const OVERLAY_DEFS = [
  {
    key: 'charging', label: 'EV chargers', emoji: '⚡', color: '#22c55e',
    selectors: ['node["amenity"="charging_station"]'],
    match: (t) => t.amenity === 'charging_station',
  },
  {
    key: 'parking', label: 'Parking', emoji: '🅿️', color: '#3b82f6',
    selectors: ['nwr["amenity"="parking"]'],
    match: (t) => t.amenity === 'parking',
  },
  {
    key: 'shopping', label: 'Shopping', emoji: '🛒', color: '#f59e0b',
    selectors: ['nwr["shop"~"^(mall|supermarket)$"]'],
    match: (t) => t.shop === 'mall' || t.shop === 'supermarket',
  },
  {
    key: 'fuel', label: 'Fuel / service areas', emoji: '⛽', color: '#ef4444',
    selectors: ['nwr["amenity"="fuel"]', 'nwr["highway"~"^(services|rest_area)$"]'],
    match: (t) => t.amenity === 'fuel' || t.highway === 'services' || t.highway === 'rest_area',
  },
]
const OVERPASS_MIN_ZOOM = 12

const mapEl = ref(null)
const zones = ref([])
const chargingTiers = ref([])
const error = ref('')
const saving = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

const panelCollapsed = ref(false)
const addMenuOpen = ref(false)
const layersOpen = ref(false)
const drawingHint = ref('')

const editingShapeId = ref(null)
const showForm = ref(false)
const editingId = ref(null)
const formShapeType = ref('circle')
const form = reactive({
  name: '', notify_on_enter: true, notify_on_exit: true, charging_tier_id: '',
})
// Geometry captured from a freshly drawn shape (add flow only).
let pendingGeometry = null

const overlays = reactive({ charging: false, parking: false, shopping: false, fuel: false })
const overlayLoading = ref(false)
const currentZoom = ref(13)

const anyOverlayOn = computed(() => Object.values(overlays).some(Boolean))
const zoomTooLow = computed(() => currentZoom.value < OVERPASS_MIN_ZOOM)
const editingZoneName = computed(
  () => zones.value.find(z => z.id === editingShapeId.value)?.name || '',
)

// Non-reactive Leaflet handles
let map = null
let baseLayer = null
const zoneLayers = new Map() // zone id -> leaflet layer
const overlayGroups = {} // key -> L.layerGroup
let overpassTimer = null

function tierLabel(id) {
  return chargingTiers.value.find(t => t.id === id)?.label || id
}

async function load() {
  try {
    const [zoneData, tierData] = await Promise.all([
      api('GET', '/api/zones'),
      api('GET', '/api/charging/tiers'),
    ])
    zones.value = zoneData
    chargingTiers.value = (tierData.tiers || []).filter(t => t.enabled)
    await nextTick()
    initMap()
  } catch (e) {
    error.value = e.message || 'Failed to load zones'
  }
}

// ── Map setup ────────────────────────────────────────────────────────────
function tileUrl() {
  const theme = document.documentElement.getAttribute('data-theme')
  const style = theme === 'light' ? 'light_all' : 'dark_all'
  return `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png`
}

function initMap() {
  if (map || !mapEl.value) return
  const center = zones.value.length
    ? [zones.value[0].latitude, zones.value[0].longitude]
    : [45.4642, 9.19]
  map = L.map(mapEl.value, {
    center, zoom: 13, zoomControl: false, attributionControl: false,
  })
  L.control.zoom({ position: 'bottomright' }).addTo(map)
  baseLayer = L.tileLayer(tileUrl(), { maxZoom: 19, subdomains: 'abcd' }).addTo(map)
  currentZoom.value = map.getZoom()

  // No persistent toolbar — geoman controls only appear while drawing (driven
  // by the panel buttons) or while editing a single shape (on shape click).
  map.pm.setGlobalOptions({ continueDrawing: false, allowSelfIntersection: false })
  map.on('pm:create', onShapeCreated)
  map.on('click', () => disableShapeEdit())
  map.on('zoomend', () => { currentZoom.value = map.getZoom() })
  map.on('moveend', scheduleOverpass)

  for (const o of OVERLAY_DEFS) overlayGroups[o.key] = L.layerGroup()

  renderZones()
  setTimeout(() => map && map.invalidateSize(), 120)
}

function renderZones(fit = true) {
  editingShapeId.value = null
  for (const layer of zoneLayers.values()) map.removeLayer(layer)
  zoneLayers.clear()
  const drawn = []
  for (const z of zones.value) {
    let layer
    if (z.shape_type === 'polygon' && z.points && z.points.length >= 3) {
      layer = L.polygon(z.points, zoneStyle())
    } else {
      layer = L.circle([z.latitude, z.longitude], { radius: z.radius_m, ...zoneStyle() })
    }
    layer._zoneId = z.id
    layer.bindTooltip(z.name, { direction: 'top', offset: [0, -6] })
    layer.on('click', (e) => { L.DomEvent.stopPropagation(e); enableShapeEdit(z.id) })
    layer.on('pm:update', () => persistGeometry(z.id, layer))
    layer.addTo(map)
    zoneLayers.set(z.id, layer)
    drawn.push(layer)
  }
  if (fit && drawn.length) {
    const g = L.featureGroup(drawn)
    map.fitBounds(g.getBounds().pad(0.3))
  }
}

function zoneStyle() {
  return { color: '#00d4ff', fillColor: '#00d4ff', fillOpacity: 0.12, weight: 2 }
}

function focusZone(z) {
  const layer = zoneLayers.get(z.id)
  if (!layer || !map) return
  if (layer.getBounds) map.fitBounds(layer.getBounds().pad(0.5))
  else map.setView([z.latitude, z.longitude], 15)
  layer.openTooltip()
}

// ── Draw / create ──────────────────────────────────────────────────────────
function startDraw(shape) {
  addMenuOpen.value = false
  if (!map) return
  drawingHint.value = shape === 'Polygon'
    ? 'Click to add vertices, double-click to finish.'
    : 'Click and drag on the map to draw the circle.'
  map.pm.enableDraw(shape)
}

function geometryFromLayer(layer) {
  if (layer instanceof L.Circle) {
    const c = layer.getLatLng()
    return {
      shape_type: 'circle',
      latitude: +c.lat.toFixed(5),
      longitude: +c.lng.toFixed(5),
      radius_m: Math.round(layer.getRadius()),
    }
  }
  const pts = layer.getLatLngs()[0].map(ll => [+ll.lat.toFixed(5), +ll.lng.toFixed(5)])
  return { shape_type: 'polygon', points: pts }
}

function onShapeCreated(e) {
  drawingHint.value = ''
  const layer = e.layer
  if (!(layer instanceof L.Circle) && !(layer instanceof L.Polygon)) {
    map.removeLayer(layer)
    return
  }
  pendingGeometry = geometryFromLayer(layer)
  map.removeLayer(layer) // re-rendered from the server after save
  openAddForm()
}

function editShape(z) {
  focusZone(z)
  enableShapeEdit(z.id)
}

function enableShapeEdit(id) {
  if (editingShapeId.value === id) return
  disableShapeEdit()
  const layer = zoneLayers.get(id)
  if (!layer) return
  layer.pm.enable({ allowSelfIntersection: false })
  editingShapeId.value = id
}

function disableShapeEdit() {
  if (editingShapeId.value == null) return
  const layer = zoneLayers.get(editingShapeId.value)
  if (layer && layer.pm) layer.pm.disable()
  editingShapeId.value = null
}

// ── Form ─────────────────────────────────────────────────────────────────
function openAddForm() {
  editingId.value = null
  formShapeType.value = pendingGeometry?.shape_type || 'circle'
  form.name = ''
  form.notify_on_enter = true
  form.notify_on_exit = true
  form.charging_tier_id = ''
  showForm.value = true
}

function openEditForm(z) {
  editingId.value = z.id
  formShapeType.value = z.shape_type
  form.name = z.name
  form.notify_on_enter = z.notify_on_enter
  form.notify_on_exit = z.notify_on_exit
  form.charging_tier_id = z.charging_tier_id || ''
  pendingGeometry = null
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  pendingGeometry = null
}

async function saveForm() {
  saving.value = true
  try {
    if (editingId.value == null) {
      const payload = {
        name: form.name,
        notify_on_enter: form.notify_on_enter,
        notify_on_exit: form.notify_on_exit,
        charging_tier_id: form.charging_tier_id || null,
        ...pendingGeometry,
      }
      if (pendingGeometry?.shape_type === 'polygon') {
        payload.latitude = pendingGeometry.points[0][0]
        payload.longitude = pendingGeometry.points[0][1]
      }
      const z = await api('POST', '/api/zones', payload)
      zones.value.push(z)
    } else {
      const z = await api('PUT', `/api/zones/${editingId.value}`, {
        name: form.name,
        notify_on_enter: form.notify_on_enter,
        notify_on_exit: form.notify_on_exit,
        charging_tier_id: form.charging_tier_id || '',
      })
      const idx = zones.value.findIndex(x => x.id === z.id)
      if (idx !== -1) zones.value[idx] = z
    }
    renderZones()
    closeForm()
  } catch (e) {
    error.value = e.message || 'Failed to save zone'
  } finally {
    saving.value = false
  }
}

async function persistGeometry(id, layer) {
  try {
    const geom = geometryFromLayer(layer)
    const payload = { ...geom }
    if (geom.shape_type === 'polygon') {
      payload.latitude = geom.points[0][0]
      payload.longitude = geom.points[0][1]
    }
    const z = await api('PUT', `/api/zones/${id}`, payload)
    const idx = zones.value.findIndex(x => x.id === id)
    if (idx !== -1) zones.value[idx] = z
  } catch (e) {
    error.value = e.message || 'Failed to update geometry'
  }
}

async function confirmDelete() {
  const zone = deleteTarget.value
  if (!zone) return
  deleting.value = true
  try {
    await api('DELETE', `/api/zones/${zone.id}`)
    zones.value = zones.value.filter(z => z.id !== zone.id)
    if (editingShapeId.value === zone.id) editingShapeId.value = null
    const layer = zoneLayers.get(zone.id)
    if (layer) map.removeLayer(layer)
    zoneLayers.delete(zone.id)
    deleteTarget.value = null
  } catch (e) {
    error.value = e.message || 'Failed to delete zone'
  } finally {
    deleting.value = false
  }
}

// ── POI overlays (Overpass) ────────────────────────────────────────────────
function toggleOverlay(key) {
  overlays[key] = !overlays[key]
  const group = overlayGroups[key]
  if (overlays[key]) {
    group.addTo(map)
    fetchOverpass()
  } else {
    group.clearLayers()
    map.removeLayer(group)
  }
}

function scheduleOverpass() {
  if (!anyOverlayOn.value) return
  clearTimeout(overpassTimer)
  overpassTimer = setTimeout(fetchOverpass, 600)
}

async function fetchOverpass() {
  if (!map) return
  const active = OVERLAY_DEFS.filter(o => overlays[o.key])
  if (!active.length || map.getZoom() < OVERPASS_MIN_ZOOM) return

  const b = map.getBounds()
  const bbox = `${b.getSouth()},${b.getWest()},${b.getNorth()},${b.getEast()}`
  const body = active.flatMap(o => o.selectors).map(s => `${s}(${bbox});`).join('')
  const query = `[out:json][timeout:25];(${body});out center 200;`

  overlayLoading.value = true
  try {
    const res = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body: 'data=' + encodeURIComponent(query),
    })
    if (!res.ok) throw new Error('Overpass ' + res.status)
    const data = await res.json()
    for (const o of active) overlayGroups[o.key].clearLayers()
    for (const el of data.elements || []) {
      const tags = el.tags || {}
      const lat = el.lat ?? el.center?.lat
      const lon = el.lon ?? el.center?.lon
      if (lat == null || lon == null) continue
      const def = active.find(o => o.match(tags))
      if (!def) continue
      L.marker([lat, lon], { icon: poiIcon(def), pmIgnore: true })
        .bindTooltip(tags.name || def.label, { direction: 'top', offset: [0, -10] })
        .addTo(overlayGroups[def.key])
    }
  } catch {
    // Overpass is best-effort; ignore transient failures silently.
  } finally {
    overlayLoading.value = false
  }
}

const _iconCache = {}
function poiIcon(def) {
  if (_iconCache[def.key]) return _iconCache[def.key]
  const icon = L.divIcon({
    className: 'poi-icon',
    html: `<span class="poi-pin" style="background:${def.color}">${def.emoji}</span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
  _iconCache[def.key] = icon
  return icon
}

// Swap base tiles when the app theme changes.
watch(() => store.theme, () => {
  if (baseLayer) baseLayer.setUrl(tileUrl())
})

onMounted(load)
onBeforeUnmount(() => {
  clearTimeout(overpassTimer)
  if (map) { map.remove(); map = null }
})
</script>

<style scoped>
.zones-tab {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 520px;
}
.zone-map-container {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  overflow: hidden;
}

/* Floating zones panel */
.zone-panel {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 600;
  width: 270px;
  max-width: calc(100% - 24px);
  background: color-mix(in srgb, var(--card) 90%, transparent);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border2);
  border-radius: 12px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}
.zone-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
}
.zone-panel-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}
.zone-count {
  font-size: 11px;
  color: var(--sub);
  background: var(--bg2);
  border-radius: 10px;
  padding: 1px 7px;
}
.zone-panel-body {
  padding: 0 12px 12px;
  max-height: min(60vh, 460px);
  overflow-y: auto;
}
.zone-panel-desc {
  margin: 0 0 10px;
  font-size: 11px;
  color: var(--sub);
  line-height: 1.45;
}

.zone-add-wrap { position: relative; }
.add-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 8px;
  color: #00d4ff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.add-btn:hover { background: linear-gradient(135deg, #00d4ff33, #00d4ff55); }
.add-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--card);
  border: 1px solid var(--border2);
  border-radius: 8px;
  overflow: hidden;
  z-index: 5;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
}
.add-menu button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  background: none;
  border: none;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
}
.add-menu button:hover { background: var(--bg2); }

.draw-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: #00d4ff;
}

.zone-list { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
.zone-empty { font-size: 12px; color: var(--muted); margin: 6px 0; }
.zone-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.zone-row:hover { background: var(--bg2); }
.zone-row.editing { background: #00d4ff14; box-shadow: inset 0 0 0 1px #00d4ff55; }
.zone-row-icon { color: #00d4ff; flex-shrink: 0; }
.zone-tip { margin: 8px 2px 0; font-size: 11px; color: var(--muted); line-height: 1.4; }
.zone-row-main { flex: 1; min-width: 0; }
.zone-row-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.zone-row-meta { font-size: 11px; color: var(--sub); }
.zone-row-tier { color: var(--muted); }

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  flex-shrink: 0;
  transition: color 0.15s, background 0.15s;
}
.icon-btn:hover { color: var(--text); background: var(--bg2); }
.icon-btn.danger:hover { color: #f44336; background: #f4433610; }

/* Layers control */
.layers-control {
  position: absolute;
  bottom: 16px;
  left: 12px;
  z-index: 600;
  background: color-mix(in srgb, var(--card) 90%, transparent);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border2);
  border-radius: 12px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}
.layers-toggle {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 9px 12px;
  background: none;
  border: none;
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  width: 100%;
}
.layers-body { padding: 4px 12px 10px; display: flex; flex-direction: column; gap: 6px; }
.layer-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
}
.layer-swatch {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  font-size: 11px;
  line-height: 1;
}
.layer-label { flex: 1; }
.layer-note { font-size: 11px; color: var(--muted); margin: 2px 0 0; }
.layer-attrib { font-size: 10px; color: var(--muted2); margin: 4px 0 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.edit-hint {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 650;
  display: flex;
  align-items: center;
  gap: 12px;
  background: color-mix(in srgb, var(--card) 92%, transparent);
  backdrop-filter: blur(10px);
  border: 1px solid #00d4ff55;
  border-radius: 999px;
  padding: 7px 8px 7px 16px;
  font-size: 12px;
  color: var(--text);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
}
.edit-done {
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 999px;
  color: #00d4ff;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 14px;
  cursor: pointer;
}

.zone-error {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 700;
  background: #f4433620;
  border: 1px solid #f4433655;
  color: #ff6b6b;
  font-size: 12px;
  padding: 8px 14px;
  border-radius: 8px;
}

/* POI marker pins (Leaflet injects the markup, so reach it via :deep) */
:deep(.poi-pin) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: 1.5px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  font-size: 11px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.modal-dialog {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  width: 100%;
  max-width: 420px;
  padding: 20px;
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.modal-head h3 { margin: 0; font-size: 16px; color: var(--text); }

.form-group { margin-bottom: 14px; }
.form-group > label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.form-group input[type="text"], .select {
  width: 100%;
  padding: 10px 12px;
  background: var(--input);
  border: 1px solid var(--btn-border);
  border-radius: 8px;
  color: var(--text);
  font-size: 13px;
  outline: none;
}
/* Custom-styled select: reset the native arrow and supply our own chevron with
   reserved padding-right, otherwise the OS arrow stays pinned to the far right
   and overflows the rounded box. */
.select {
  appearance: none;
  -webkit-appearance: none;
  padding-right: 34px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2388909a' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  cursor: pointer;
}
.form-group input[type="text"]:focus, .select:focus { border-color: #00d4ff55; }
.shape-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
  padding: 8px 10px;
  background: var(--bg2);
  border-radius: 8px;
}
.shape-pill-hint { font-size: 11px; color: var(--muted); }
.toggle-row { display: flex; flex-direction: column; gap: 8px; }
.chk { display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--text); cursor: pointer; }
.field-desc { font-size: 11px; color: var(--sub); margin: 6px 0 0; line-height: 1.5; }

.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.btn-ghost {
  padding: 9px 16px;
  background: none;
  border: 1px solid var(--border2);
  border-radius: 8px;
  color: var(--sub);
  font-size: 13px;
  cursor: pointer;
}
.btn-primary {
  padding: 9px 18px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 8px;
  color: #00d4ff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 640px) {
  .zone-panel { width: calc(100% - 24px); }
}
</style>
