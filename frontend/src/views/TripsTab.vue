<template>
  <div class="trips-tab">
    <div class="trips-header">
      <div class="header-title">
        <h2>Trips</h2>
        <p>Driving records &amp; statistics</p>
      </div>
      <div class="month-nav">
        <button class="toolbar-btn" @click="prevMonth"><ChevronLeft :size="16" /></button>
        <span class="month-label">{{ monthLabel }}</span>
        <button class="toolbar-btn" :disabled="isCurrentMonth" @click="nextMonth"><ChevronRight :size="16" /></button>
      </div>
    </div>

    <!-- Totals KPI -->
    <div v-if="totals" class="summary-grid">
      <div class="summary-card">
        <div class="summary-value" style="color: #00d4ff">{{ formatKm(totals.totalmileage) }}</div>
        <div class="summary-label">Total distance</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #00e676">{{ formatEnergy(totals.totalenery) }}</div>
        <div class="summary-label">Total energy</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #42a5f5">{{ formatEnergy(totals.totalrecoveryenery) }}</div>
        <div class="summary-label">Regen energy</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #ff7043">{{ totals.maxspeed || '—' }} km/h</div>
        <div class="summary-label">Max speed</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #7c6aff">{{ formatTime(totals.ustime) }}</div>
        <div class="summary-label">Driving time</div>
      </div>
      <div v-if="avgConsumption" class="summary-card">
        <div class="summary-value" style="color: #fdd835">{{ avgConsumption }}</div>
        <div class="summary-label">Avg kWh/100km</div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-center">
      <div class="spinner" />
    </div>

    <!-- Trip list -->
    <div v-else-if="tripDays.length" class="trip-days">
      <div v-for="day in tripDays" :key="day.day" class="trip-day-group">
        <div class="day-header">
          <span class="day-date">{{ formatDayLabel(day.day) }}</span>
          <span class="day-summary">{{ day.trips.length }} trip{{ day.trips.length > 1 ? 's' : '' }} · {{ formatKm(day.accumulated_mileage) }} · {{ formatEnergy(day.accumulated_enery_consume) }}</span>
        </div>
        <div v-for="trip in day.trips" :key="trip.gpskey || trip.beginTime" class="trip-row" @click="selectTrip(trip)">
          <div class="trip-time">
            <Clock :size="14" class="trip-icon" />
            <span>{{ formatTripTime(trip.beginTime) }} – {{ formatTripTime(trip.endTime) }}</span>
          </div>
          <div class="trip-stats">
            <span class="trip-stat"><Navigation :size="12" /> {{ formatTripKm(trip.travelMile) }}</span>
            <span class="trip-stat"><Zap :size="12" /> {{ formatTripEnergy(trip.eneryConsume) }}</span>
            <span v-if="trip.travelMile > 0" class="trip-stat consumption">{{ tripConsumption(trip) }} kWh/100km</span>
          </div>
          <ChevronRight :size="16" class="trip-arrow" />
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading && loaded" class="empty-state">
      <Navigation :size="48" class="empty-icon" />
      <p>No trips found for this period</p>
      <p class="empty-hint">Try selecting a different month</p>
    </div>

    <!-- Trip detail modal -->
    <Teleport to="body">
      <div v-if="selectedTrip" class="modal-backdrop" @click.self="selectedTrip = null">
        <div class="modal-dialog trip-modal">
          <div class="modal-header">
            <h3>Trip Detail</h3>
            <button class="close-btn" @click="selectedTrip = null">✕</button>
          </div>
          <div class="trip-detail-stats">
            <div class="detail-stat">
              <span class="stat-label">Time</span>
              <span class="stat-value">{{ formatTripTime(selectedTrip.beginTime) }} – {{ formatTripTime(selectedTrip.endTime) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Duration</span>
              <span class="stat-value" style="color: #7c6aff">{{ tripDuration(selectedTrip) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Distance</span>
              <span class="stat-value" style="color: #00d4ff">{{ formatTripKm(selectedTrip.travelMile) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Avg speed</span>
              <span class="stat-value" style="color: #ffab40">{{ formatAvgSpeed(selectedTrip) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Max speed</span>
              <span class="stat-value" style="color: #ff7043">{{ selectedTrip.maxSpeed != null ? selectedTrip.maxSpeed + ' km/h' : '—' }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Energy</span>
              <span class="stat-value" style="color: #00e676">{{ formatTripEnergy(selectedTrip.eneryConsume) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Regen</span>
              <span class="stat-value" style="color: #42a5f5">{{ formatTripRegen(selectedTrip.recoveryEnery) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Consumption</span>
              <span class="stat-value" style="color: #fdd835">{{ tripConsumption(selectedTrip) }} kWh/100km</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">SOC</span>
              <span class="stat-value" style="color: #66bb6a">{{ formatSocRange(selectedTrip) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">SOC used</span>
              <span class="stat-value" style="color: #ef5350">{{ formatSocDelta(selectedTrip) }}</span>
            </div>
            <div v-if="selectedTrip.outdoorTemp != null" class="detail-stat">
              <span class="stat-label">Outside temp</span>
              <span class="stat-value" style="color: #90caf9">{{ selectedTrip.outdoorTemp }}°C</span>
            </div>
          </div>
          <!-- GPS Map / Speed chart -->
          <div v-if="gpsLoading" class="map-loading"><div class="spinner" /></div>
          <template v-else-if="gpsPoints.length">
            <div class="view-toggle">
              <button :class="{ active: viewMode === 'simple' }" @click="switchView('simple')"><Map :size="14" /> Simple</button>
              <button :class="{ active: viewMode === 'speedmap' }" @click="switchView('speedmap')"><Map :size="14" /> Speed</button>
              <button :class="{ active: viewMode === 'chart' }" @click="switchView('chart')"><Gauge :size="14" /> Chart</button>
            </div>
            <div v-show="viewMode === 'simple' || viewMode === 'speedmap'" ref="mapContainer" :key="'map-' + mapKey" class="trip-map" />
            <div v-show="viewMode === 'chart'" class="chart-area">
              <canvas ref="speedCanvas" />
            </div>
          </template>
          <div v-else-if="selectedTrip?.gpskey" class="map-empty">
            <p>No GPS data available for this trip</p>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { api } from '../composables/useApi'
import { Clock, Navigation, Zap, ChevronRight, ChevronLeft, Map, Gauge } from 'lucide-vue-next'
import { Chart, registerables } from 'chart.js'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useAppStore } from '../stores/appStore'

Chart.register(...registerables)

const props = defineProps({
  vin: { type: String, required: true },
})

const store = useAppStore()

// State
const loading = ref(false)
const loaded = ref(false)
const selectedMonth = ref(new Date())
const tripsData = ref(null)
const totals = ref(null)
const selectedTrip = ref(null)
const gpsLoading = ref(false)
const gpsPoints = ref([])
const mapContainer = ref(null)
const speedCanvas = ref(null)
const mapKey = ref(0)
const viewMode = ref('simple')
let mapInstance = null
let tileLayerInstance = null
let speedChartInstance = null

function getMapTileUrl() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light'
  return isLight
    ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
}

// Month navigation
const monthLabel = computed(() => {
  const d = selectedMonth.value
  return d.toLocaleString('en-US', { month: 'long', year: 'numeric' })
})
const isCurrentMonth = computed(() => {
  const now = new Date()
  const d = selectedMonth.value
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
})
function prevMonth() {
  const d = new Date(selectedMonth.value)
  d.setMonth(d.getMonth() - 1)
  selectedMonth.value = d
}
function nextMonth() {
  const d = new Date(selectedMonth.value)
  d.setMonth(d.getMonth() + 1)
  selectedMonth.value = d
}

// Computed
const tripDays = computed(() => {
  if (!tripsData.value?.data) return []
  return tripsData.value.data.map(day => ({
    day: day.day,
    accumulated_mileage: day.accumulated_mileage,
    accumulated_enery_consume: day.accumulated_enery_consume,
    current_mileage: day.current_mileage,
    trips: day.drivingRecord || [],
  })).filter(d => d.trips.length > 0)
})

const avgConsumption = computed(() => {
  if (!totals.value) return null
  const km = parseFloat(totals.value.totalmileage) || 0
  const energy = parseFloat(totals.value.totalenery) || 0
  if (km <= 0) return null
  return (energy / km * 100).toFixed(1)
})

// Load data
async function loadData() {
  loading.value = true
  loaded.value = false
  try {
    const y = selectedMonth.value.getFullYear()
    const m = selectedMonth.value.getMonth()
    const fromDate = `${y}-${String(m + 1).padStart(2, '0')}-01`
    const lastDay = new Date(y, m + 1, 0).getDate()
    const toDate = `${y}-${String(m + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`

    const [records, stats] = await Promise.all([
      api('GET', `/api/vehicles/${props.vin}/trips?begin_time=${fromDate}&end_time=${toDate}`),
      api('GET', `/api/vehicles/${props.vin}/trips/totals?begin_time=${fromDate}&end_time=${toDate}`),
    ])
    tripsData.value = records
    totals.value = stats
  } catch (e) {
    console.error('Failed to load trips:', e)
  } finally {
    loading.value = false
    loaded.value = true
  }
}

// Trip selection & GPS
async function selectTrip(trip) {
  selectedTrip.value = trip
  gpsPoints.value = []
  gpsLoading.value = false
  mapKey.value++ // force map container recreation
  viewMode.value = 'simple'
  destroySpeedChart()
  if (!trip.gpskey) return
  gpsLoading.value = true
  try {
    const data = await api('GET', `/api/vehicles/${props.vin}/trips/gps/${encodeURIComponent(trip.gpskey)}`)
    if (data && Array.isArray(data)) {
      gpsPoints.value = data
    } else if (data?.points) {
      gpsPoints.value = data.points
    } else if (data?.data) {
      gpsPoints.value = Array.isArray(data.data) ? data.data : []
    }
    gpsLoading.value = false
    if (gpsPoints.value.length) {
      await nextTick()
      renderSimpleMap()
    }
  } catch (e) {
    console.error('Failed to load GPS data:', e)
    gpsLoading.value = false
  }
}

function renderSimpleMap() {
  if (!mapContainer.value || !gpsPoints.value.length) return
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
    tileLayerInstance = null
  }
  mapInstance = L.map(mapContainer.value, { zoomControl: true, attributionControl: false })
  tileLayerInstance = L.tileLayer(getMapTileUrl(), {
    maxZoom: 18,
    subdomains: 'abcd',
  }).addTo(mapInstance)

  const points = gpsPoints.value.filter(p => (p.lat || p.latitude) && (p.lng || p.longitude))
  if (!points.length) return

  const coords = points.map(p => [p.lat || p.latitude, p.lng || p.longitude])

  // Single-color polyline
  L.polyline(coords, { color: '#00d4ff', weight: 3, opacity: 0.8 }).addTo(mapInstance)

  // Start / end markers
  L.circleMarker(coords[0], { radius: 8, color: '#fff', fillColor: '#66bb6a', fillOpacity: 1, weight: 2 })
    .bindTooltip('Start', { permanent: false })
    .addTo(mapInstance)
  L.circleMarker(coords[coords.length - 1], { radius: 8, color: '#fff', fillColor: '#ef5350', fillOpacity: 1, weight: 2 })
    .bindTooltip('End', { permanent: false })
    .addTo(mapInstance)

  const bounds = L.latLngBounds(coords)
  mapInstance.fitBounds(bounds, { padding: [20, 20] })
}

function renderSpeedMap() {
  if (!mapContainer.value || !gpsPoints.value.length) return
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
    tileLayerInstance = null
  }
  mapInstance = L.map(mapContainer.value, { zoomControl: true, attributionControl: false })
  tileLayerInstance = L.tileLayer(getMapTileUrl(), {
    maxZoom: 18,
    subdomains: 'abcd',
  }).addTo(mapInstance)

  const points = gpsPoints.value.filter(p => (p.lat || p.latitude) && (p.lng || p.longitude))
  if (!points.length) return

  const coords = points.map(p => [p.lat || p.latitude, p.lng || p.longitude])

  // Draw polyline segments colored by speed
  for (let i = 1; i < coords.length; i++) {
    const speed = points[i].speed ?? 0
    const color = speed > 80 ? '#ef5350' : speed > 40 ? '#ffab40' : '#66bb6a'
    L.polyline([coords[i - 1], coords[i]], { color, weight: 3, opacity: 0.8 }).addTo(mapInstance)
  }

  // Speed markers on each point
  for (let i = 0; i < coords.length; i++) {
    const speed = points[i].speed ?? 0
    const time = points[i].timestamp
      ? new Date(points[i].timestamp + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : ''
    L.circleMarker(coords[i], {
      radius: 4,
      color: speed > 80 ? '#ef5350' : speed > 40 ? '#ffab40' : '#66bb6a',
      fillColor: speed > 80 ? '#ef5350' : speed > 40 ? '#ffab40' : '#66bb6a',
      fillOpacity: 0.7,
      weight: 1,
    }).bindTooltip(`${speed} km/h${time ? ' — ' + time : ''}`, { direction: 'top', offset: [0, -6] }).addTo(mapInstance)
  }

  // Start / end markers (larger)
  L.circleMarker(coords[0], { radius: 8, color: '#fff', fillColor: '#66bb6a', fillOpacity: 1, weight: 2 })
    .bindTooltip('Start', { permanent: false })
    .addTo(mapInstance)
  L.circleMarker(coords[coords.length - 1], { radius: 8, color: '#fff', fillColor: '#ef5350', fillOpacity: 1, weight: 2 })
    .bindTooltip('End', { permanent: false })
    .addTo(mapInstance)

  const bounds = L.latLngBounds(coords)
  mapInstance.fitBounds(bounds, { padding: [20, 20] })
}

// --- View switching (simple / speed map / chart) ---
function switchView(mode) {
  viewMode.value = mode
  destroySpeedChart()
  nextTick(() => {
    if (mode === 'simple') {
      renderSimpleMap()
    } else if (mode === 'speedmap') {
      renderSpeedMap()
    } else {
      renderSpeedChart()
    }
  })
}

function destroySpeedChart() {
  if (speedChartInstance) {
    speedChartInstance.destroy()
    speedChartInstance = null
  }
}

function renderSpeedChart() {
  destroySpeedChart()
  const canvas = speedCanvas.value
  if (!canvas || !gpsPoints.value.length) return

  const ctx = canvas.getContext('2d')
  const points = gpsPoints.value.filter(p => p.speed != null)

  // Build labels: time if available, else index
  const labels = points.map((p, i) => {
    if (p.timestamp) {
      return new Date(p.timestamp + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return i
  })

  // Color segments by speed range
  const speeds = points.map(p => p.speed || 0)
  const colors = speeds.map(s => s > 80 ? '#ef5350' : s > 40 ? '#ffab40' : '#66bb6a')

  speedChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Speed (km/h)',
        data: speeds,
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0,212,255,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        pointBackgroundColor: colors,
        pointBorderColor: colors,
        segment: {
          borderColor: ctx => {
            const i = ctx.p0DataIndex
            return speeds[i] > 80 ? '#ef5350' : speeds[i] > 40 ? '#ffab40' : '#66bb6a'
          },
        },
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.parsed.y} km/h`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#888', font: { size: 10 }, maxTicksLimit: 10 },
          grid: { display: false },
        },
        y: {
          ticks: { color: '#888', callback: v => v + ' km/h' },
          grid: { color: 'rgba(255,255,255,0.05)' },
          beginAtZero: true,
        },
      },
    },
  })
}

// Formatters
function formatKm(val) {
  const km = parseFloat(val) || 0
  return km >= 1000 ? `${(km / 1000).toFixed(1)}k km` : `${km.toFixed(1)} km`
}

function formatEnergy(val) {
  const wh = parseFloat(val) || 0
  return wh >= 1000 ? `${(wh / 1000).toFixed(1)} kWh` : `${wh.toFixed(0)} Wh`
}

function formatTime(hours) {
  const h = parseFloat(hours) || 0
  if (h < 1) return `${Math.round(h * 60)} min`
  return `${Math.floor(h)}h ${Math.round((h % 1) * 60)}m`
}

function formatDayLabel(dayStr) {
  if (!dayStr) return ''
  const d = new Date(dayStr)
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
}

function formatTripTime(ts) {
  if (!ts) return '—'
  // ts is "YYYY-MM-DD HH:MM:SS" in UTC — parse and display in local TZ
  const d = new Date(ts.replace(' ', 'T') + 'Z')
  if (isNaN(d)) return ts.slice(11, 16)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function formatTripKm(meters) {
  const km = (parseFloat(meters) || 0) / 1000
  return `${km.toFixed(1)} km`
}

function formatTripEnergy(wh) {
  const kwh = (parseFloat(wh) || 0) / 1000
  return `${kwh.toFixed(2)} kWh`
}

function formatTripRegen(wh) {
  const val = parseFloat(wh) || 0
  return val >= 1000 ? `${(val / 1000).toFixed(2)} kWh` : `${val.toFixed(0)} Wh`
}

function formatSocRange(trip) {
  const start = trip.startSoc
  const end = trip.endSoc
  if (start == null && end == null) return '—'
  const s = start != null ? `${start}%` : '?'
  const e = end != null ? `${end}%` : '?'
  return `${s} → ${e}`
}

function formatSocDelta(trip) {
  const start = trip.startSoc
  const end = trip.endSoc
  if (start == null || end == null) return '—'
  const delta = start - end
  if (delta === 0) return '0%'
  return `-${delta}%`
}

function tripConsumption(trip) {
  const km = (parseFloat(trip.travelMile) || 0) / 1000
  const kwh = (parseFloat(trip.eneryConsume) || 0) / 1000
  if (km <= 0) return '—'
  return (kwh / km * 100).toFixed(1)
}

function tripDuration(trip) {
  if (!trip.beginTime || !trip.endTime) return '—'
  const start = new Date(trip.beginTime.replace(' ', 'T') + 'Z')
  const end = new Date(trip.endTime.replace(' ', 'T') + 'Z')
  if (isNaN(start) || isNaN(end)) return '—'
  const mins = Math.round((end - start) / 60000)
  if (mins < 60) return `${mins} min`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function formatAvgSpeed(trip) {
  if (!trip.beginTime || !trip.endTime) return '—'
  const start = new Date(trip.beginTime.replace(' ', 'T') + 'Z')
  const end = new Date(trip.endTime.replace(' ', 'T') + 'Z')
  const hours = (end - start) / 3600000
  if (hours <= 0) return '—'
  const km = (parseFloat(trip.travelMile) || 0) / 1000
  return `${(km / hours).toFixed(0)} km/h`
}

// Lifecycle
onMounted(loadData)

watch(() => props.vin, loadData)
watch(selectedMonth, loadData)

// Swap tile layer when theme changes (if map is currently open)
watch(() => store.theme, () => {
  if (!mapInstance || !tileLayerInstance) return
  mapInstance.removeLayer(tileLayerInstance)
  tileLayerInstance = L.tileLayer(getMapTileUrl(), {
    maxZoom: 18,
    subdomains: 'abcd',
  }).addTo(mapInstance)
})

onBeforeUnmount(() => {
  destroySpeedChart()
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
    tileLayerInstance = null
  }
})
</script>

<style scoped>
.trips-tab { padding: 16px; max-width: 900px; margin: 0 auto; }
.trips-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.header-title h2 { font-size: 20px; font-weight: 700; color: var(--text); margin: 0; }
.header-title p { font-size: 12px; color: var(--muted); margin: 2px 0 0; }
.month-nav { display: flex; align-items: center; gap: 8px; }
.month-label { font-size: 14px; font-weight: 600; color: var(--text); min-width: 130px; text-align: center; }
.toolbar-btn { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 6px; color: var(--text); cursor: pointer; display: flex; align-items: center; }
.toolbar-btn:disabled { opacity: 0.4; cursor: default; }
.toolbar-btn:hover:not(:disabled) { background: var(--bg2); }

/* Summary grid */
.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
.summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 12px; text-align: center; }
.summary-value { font-size: 18px; font-weight: 700; }
.summary-label { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* Trip days */
.trip-days { display: flex; flex-direction: column; gap: 12px; }
.trip-day-group { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.day-header { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); background: var(--bg2); }
.day-date { font-weight: 600; font-size: 13px; color: var(--text); }
.day-summary { font-size: 11px; color: var(--muted); }
.trip-row { display: flex; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; }
.trip-row:last-child { border-bottom: none; }
.trip-row:hover { background: var(--bg2); }
.trip-time { display: flex; align-items: center; gap: 6px; min-width: 120px; font-size: 13px; color: var(--text); }
.trip-icon { color: var(--muted); }
.trip-stats { display: flex; align-items: center; gap: 12px; flex: 1; font-size: 12px; color: var(--muted); }
.trip-stat { display: flex; align-items: center; gap: 4px; }
.trip-stat.consumption { color: #fdd835; font-weight: 600; }
.trip-arrow { color: var(--muted); }

/* Empty state */
.empty-state { text-align: center; padding: 48px 16px; color: var(--muted); }
.empty-icon { opacity: 0.3; margin-bottom: 16px; }
.empty-hint { font-size: 12px; margin-top: 8px; }

/* Loading */
.loading-center { display: flex; justify-content: center; padding: 48px; }

/* Modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.modal-dialog.trip-modal { background: var(--card); border: 1px solid var(--border); border-radius: 16px; max-width: 700px; width: 100%; max-height: 85vh; overflow-y: auto; padding: 24px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text); margin: 0; }
.close-btn { background: none; border: none; color: var(--muted); font-size: 18px; cursor: pointer; }
.close-btn:hover { color: var(--text); }
.trip-detail-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 16px; }
.detail-stat { background: var(--bg2); border-radius: 8px; padding: 10px 12px; }
.stat-label { display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px; }
.stat-value { font-size: 14px; font-weight: 600; color: var(--text); }
.trip-map { height: 350px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
.map-loading { display: flex; justify-content: center; padding: 32px; }
.map-empty { text-align: center; padding: 32px; color: var(--muted); font-size: 13px; }

/* View toggle (map ↔ chart) */
.view-toggle { display: flex; gap: 4px; margin-bottom: 8px; }
.view-toggle button {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 12px;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 5px;
}
.view-toggle button.active {
  background: var(--card);
  border-color: var(--cyan);
  color: var(--cyan);
}
.view-toggle button:hover:not(.active) {
  color: var(--text);
}

/* Speed chart */
.chart-area { height: 350px; position: relative; }

@media (max-width: 640px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
  .trip-row { flex-wrap: wrap; gap: 6px; }
}
</style>
