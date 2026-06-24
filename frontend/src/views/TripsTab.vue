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
        <div class="summary-value" style="color: var(--accent)">{{ formatKm(totals.total_mileage) }}</div>
        <div class="summary-label">Total distance</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #00e676">{{ formatEnergy(totals.total_energy) }}</div>
        <div class="summary-label">Total energy</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #42a5f5">{{ formatEnergy(totals.total_energy_recovered) }}</div>
        <div class="summary-label">Regen energy</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #ff7043">{{ totals.max_speed || '—' }} km/h</div>
        <div class="summary-label">Max speed</div>
      </div>
      <div class="summary-card">
        <div class="summary-value" style="color: #7c6aff">{{ formatTime(totals.total_hours) }}</div>
        <div class="summary-label">Driving time</div>
      </div>
      <div v-if="avgConsumption" class="summary-card">
        <div class="summary-value" style="color: #fdd835">{{ avgConsumption }}</div>
        <div class="summary-label">Avg kWh/100km</div>
      </div>
    </div>

    <!-- Compare bar -->
    <div v-if="compareMode || selectedCompareTrips.length" class="compare-bar">
      <div class="compare-bar-inner">
        <button class="compare-bar-btn" :class="{ active: compareMode }" @click="toggleCompareMode">
          <Diff :size="14" />
          <span>{{ compareMode ? 'Exit selection' : 'Select trips' }}</span>
        </button>
        <div v-if="selectedCompareTrips.length" class="compare-bar-count">
          <span class="compare-count-num">{{ selectedCompareTrips.length }}</span>
          <span class="compare-count-label">/ 2 selected</span>
        </div>
        <button v-if="selectedCompareTrips.length" class="compare-bar-btn clear" @click="clearCompareSelection">
          <X :size="14" />
        </button>
        <button
          class="compare-bar-btn primary"
          :disabled="selectedCompareTrips.length !== 2"
          @click="openManualCompare"
        >
          <GitCompare :size="14" />
          <span>Compare now</span>
        </button>
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
          <span class="day-summary">{{ day.trips.length }} trip{{ day.trips.length > 1 ? 's' : '' }} · {{ formatKm(day.accumulated_mileage) }} · {{ formatEnergy(day.accumulated_energy_consumed) }}</span>
        </div>
        <div v-for="trip in day.trips" :key="trip.gpskey || trip.beginTime" class="trip-row" @click="onTripRowClick(trip)">
          <label v-if="compareMode" class="compare-checkbox" @click.stop>
            <input
              type="checkbox"
              :checked="isTripSelectedForCompare(trip)"
              @change="toggleTripCompare(trip)"
            />
          </label>
          <div class="trip-time">
            <Clock :size="14" class="trip-icon" />
            <span>{{ formatTripTime(trip.beginTime) }} – {{ formatTripTime(trip.endTime) }}</span>
          </div>
          <div class="trip-stats">
            <span class="trip-stat"><Navigation :size="12" /> {{ formatTripKm(trip.travelMile) }}</span>
            <span class="trip-stat"><Zap :size="12" /> {{ formatTripEnergy(trip.energyConsumed) }}</span>
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
      <div v-if="selectedTrip" class="modal-backdrop" @click.self="closeTripDetail">
        <div class="modal-dialog trip-modal">
          <!-- Header -->
          <div class="modal-header">
            <button v-if="modalView !== 'detail'" class="modal-back-btn" @click="modalView = 'detail'">
              <ChevronLeft :size="18" />
            </button>
            <h3>
              <template v-if="modalView === 'detail'">Trip Detail</template>
              <template v-else-if="modalView === 'similar'">Similar Trips</template>
              <template v-else>Trip Comparison</template>
            </h3>
            <button class="close-btn" @click="closeTripDetail">✕</button>
          </div>

          <!-- PAGE: Detail -->
          <template v-if="modalView === 'detail'">
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
                <span class="stat-value" style="color: var(--accent)">{{ formatTripKm(selectedTrip.travelMile) }}</span>
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
                <span class="stat-value" style="color: #00e676">{{ formatTripEnergy(selectedTrip.energyConsumed) }}</span>
              </div>
              <div class="detail-stat">
                <span class="stat-label">Regen</span>
                <span class="stat-value" style="color: #42a5f5">{{ formatTripRegen(selectedTrip.energyRecovered) }}</span>
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

            <!-- Action buttons below map -->
            <div class="trip-actions">
              <button class="trip-action-btn" :disabled="similarLoading" @click="findSimilarTrips(selectedTrip)">
                <Search :size="15" />
                <span>{{ similarLoading ? 'Searching...' : 'Find Similar Trips' }}</span>
              </button>
              <button class="trip-action-btn secondary" @click="enterManualCompareFromDetail">
                <GitCompare :size="15" />
                <span>Choose Trip to Compare</span>
              </button>
            </div>
          </template>

          <!-- PAGE: Similar suggestions -->
          <template v-if="modalView === 'similar'">
            <div v-if="similarLoading" class="map-loading"><div class="spinner" /></div>
            <div v-else-if="similarError" class="map-empty">
              <p>Error loading similar trips</p>
              <p class="empty-hint">{{ similarError }}</p>
            </div>
            <template v-else>
              <div v-if="similarTrips.length" class="similar-section">
                <p class="similar-hint">
                  <template v-if="similarScope === 'month'">Found in the same month as this trip.</template>
                  <template v-else>Search extended to all available data.</template>
                </p>
                <div v-for="group in similarTripsGrouped" :key="group.month" class="similar-group">
                  <div class="similar-group-header">{{ group.label }}</div>
                  <div class="similar-list">
                    <div v-for="item in group.items" :key="item.trip.gpskey" class="similar-row">
                      <div class="similar-main">
                        <strong>{{ formatTripTime(item.trip.beginTime) }} — {{ formatTripTime(item.trip.endTime) }}</strong>
                        <span>{{ formatTripKm(item.trip.travelMile) }} · {{ tripConsumption(item.trip) }} kWh/100km</span>
                      </div>
                      <div class="similar-side">
                        <span class="similar-score">Score {{ formatScore(item.similarity_score) }}</span>
                        <button class="compare-bar-btn primary" style="padding:4px 10px;font-size:12px" @click="openSuggestedCompare(item)">Compare</button>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- Extend search prompt (always shown in month scope) -->
                <div v-if="similarScope === 'month'" class="extend-search-box">
                  <p>Search limited to this trip's month.</p>
                  <button class="trip-action-btn" @click="findSimilarTrips(selectedTrip, 'all')">
                    <Search :size="15" />
                    <span>Extend search to all available months</span>
                  </button>
                  <span class="extend-hint">This may take a few seconds.</span>
                </div>
              </div>
              <div v-else class="map-empty">
                <p v-if="similarScope === 'month'">No similar trips found in this month.</p>
                <p v-else>No similar trips found in the extended range.</p>
                <div v-if="similarScope === 'month'" class="extend-search-box" style="margin-top:12px">
                  <button class="trip-action-btn" @click="findSimilarTrips(selectedTrip, 'all')">
                    <Search :size="15" />
                    <span>Extend search to all available months</span>
                  </button>
                  <span class="extend-hint">This may take a few seconds.</span>
                </div>
              </div>
            </template>
          </template>

          <!-- PAGE: Comparison -->
          <template v-if="modalView === 'compare' && activeCompare">
            <div class="compare-columns">
              <div class="compare-col">
                <div class="compare-title">Trip A</div>
                <div class="compare-sub">{{ formatTripTime(activeCompare.a.beginTime) }} — {{ formatTripTime(activeCompare.a.endTime) }}</div>
                <div class="compare-sub">{{ formatTripKm(activeCompare.a.travelMile) }} · {{ tripConsumption(activeCompare.a) }} kWh/100km</div>
              </div>
              <div class="compare-col">
                <div class="compare-title">Trip B</div>
                <div class="compare-sub">{{ formatTripTime(activeCompare.b.beginTime) }} — {{ formatTripTime(activeCompare.b.endTime) }}</div>
                <div class="compare-sub">{{ formatTripKm(activeCompare.b.travelMile) }} · {{ tripConsumption(activeCompare.b) }} kWh/100km</div>
              </div>
            </div>

            <div v-if="activeCompare.score != null" class="rank-box">
              Similarity Score: <strong>{{ formatScore(activeCompare.score) }}</strong>
              <span v-if="activeCompare.breakdown">(route {{ formatScore(activeCompare.breakdown.route) }}, time {{ formatScore(activeCompare.breakdown.time) }}, distance {{ formatScore(activeCompare.breakdown.distance) }})</span>
            </div>

            <div class="compare-table">
              <div class="compare-row head">
                <span>Metric</span><span>Trip A</span><span>Trip B</span><span>Delta (B−A)</span>
              </div>
              <div v-for="m in compareMetrics(activeCompare.a, activeCompare.b)" :key="m.key" class="compare-row">
                <span>{{ m.label }}</span>
                <span>{{ m.a }}</span>
                <span>{{ m.b }}</span>
                <span :class="deltaClass(m)">{{ m.delta }}</span>
              </div>
            </div>

            <div class="insight-grid">
              <div class="insight-card">
                <div class="insight-title">Efficiency</div>
                <div>{{ compareEfficiencyInsight(activeCompare.a, activeCompare.b) }}</div>
              </div>
              <div class="insight-card">
                <div class="insight-title">Performance</div>
                <div>{{ comparePerformanceInsight(activeCompare.a, activeCompare.b) }}</div>
              </div>
              <div class="insight-card">
                <div class="insight-title">Conditions</div>
                <div>{{ compareConditionInsight(activeCompare.a, activeCompare.b) }}</div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- Manual compare modal (from trip list selection) -->
      <div v-if="compareDialog" class="modal-backdrop" @click.self="compareDialog = null">
        <div class="modal-dialog compare-modal">
          <div class="modal-header">
            <h3>Trip Comparison</h3>
            <button class="close-btn" @click="compareDialog = null">✕</button>
          </div>

          <div class="compare-columns">
            <div class="compare-col">
              <div class="compare-title">Trip A</div>
              <div class="compare-sub">{{ formatTripTime(compareDialog.a.beginTime) }} — {{ formatTripTime(compareDialog.a.endTime) }}</div>
              <div class="compare-sub">{{ formatTripKm(compareDialog.a.travelMile) }} · {{ tripConsumption(compareDialog.a) }} kWh/100km</div>
            </div>
            <div class="compare-col">
              <div class="compare-title">Trip B</div>
              <div class="compare-sub">{{ formatTripTime(compareDialog.b.beginTime) }} — {{ formatTripTime(compareDialog.b.endTime) }}</div>
              <div class="compare-sub">{{ formatTripKm(compareDialog.b.travelMile) }} · {{ tripConsumption(compareDialog.b) }} kWh/100km</div>
            </div>
          </div>

          <div class="compare-table">
            <div class="compare-row head">
              <span>Metric</span><span>Trip A</span><span>Trip B</span><span>Delta (B−A)</span>
            </div>
            <div v-for="m in compareMetrics(compareDialog.a, compareDialog.b)" :key="m.key" class="compare-row">
              <span>{{ m.label }}</span>
              <span>{{ m.a }}</span>
              <span>{{ m.b }}</span>
              <span :class="deltaClass(m)">{{ m.delta }}</span>
            </div>
          </div>

          <div class="insight-grid">
            <div class="insight-card">
              <div class="insight-title">Efficiency</div>
              <div>{{ compareEfficiencyInsight(compareDialog.a, compareDialog.b) }}</div>
            </div>
            <div class="insight-card">
              <div class="insight-title">Performance</div>
              <div>{{ comparePerformanceInsight(compareDialog.a, compareDialog.b) }}</div>
            </div>
            <div class="insight-card">
              <div class="insight-title">Conditions</div>
              <div>{{ compareConditionInsight(compareDialog.a, compareDialog.b) }}</div>
            </div>
          </div>

          <div v-if="compareDialog.score != null" class="rank-box">
            Similarity Score: <strong>{{ formatScore(compareDialog.score) }}</strong>
            <span v-if="compareDialog.breakdown">(route {{ formatScore(compareDialog.breakdown.route) }}, time {{ formatScore(compareDialog.breakdown.time) }}, distance {{ formatScore(compareDialog.breakdown.distance) }})</span>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { accentHex, accentRgba } from '../utils/theme'
import { api } from '../composables/useApi'
import { Clock, Navigation, Zap, ChevronRight, ChevronLeft, Map, Gauge, Search, GitCompare, Diff, X } from 'lucide-vue-next'
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
const similarLoading = ref(false)
const similarTrips = ref([])
const similarScope = ref('month') // 'month' | 'all'
const similarTotalCount = ref(0)
const similarError = ref(null)
const gpsLoading = ref(false)
const gpsPoints = ref([])
const mapContainer = ref(null)
const speedCanvas = ref(null)
const mapKey = ref(0)
const viewMode = ref('simple')
let mapInstance = null
let tileLayerInstance = null
let speedChartInstance = null
const compareMode = ref(false)
const selectedCompareTrips = ref([])
const compareDialog = ref(null)
const modalView = ref('detail') // 'detail' | 'similar' | 'compare'
const activeCompare = ref(null)

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
    accumulated_energy_consumed: day.accumulated_energy_consumed,
    current_mileage: day.current_mileage,
    trips: [...(day.drivingRecord || [])].reverse(),
  })).filter(d => d.trips.length > 0)
})

const avgConsumption = computed(() => {
  if (!totals.value) return null
  const km = parseFloat(totals.value.total_mileage) || 0
  const energy = parseFloat(totals.value.total_energy) || 0
  if (km <= 0) return null
  return (energy / km * 100).toFixed(1)
})

const allTrips = computed(() => tripDays.value.flatMap(d => d.trips || []))

const similarTripsGrouped = computed(() => {
  const groups = {}
  for (const item of similarTrips.value) {
    const day = item.trip?.beginTime?.slice(0, 7) // "YYYY-MM"
    if (!day) continue
    if (!groups[day]) groups[day] = []
    groups[day].push(item)
  }
  return Object.entries(groups)
    .sort(([a], [b]) => b.localeCompare(a)) // newest first
    .map(([month, items]) => ({
      month,
      label: formatMonthYear(month),
      items,
    }))
})

const monthRange = computed(() => {
  const y = selectedMonth.value.getFullYear()
  const m = selectedMonth.value.getMonth()
  const fromDate = `${y}-${String(m + 1).padStart(2, '0')}-01`
  const lastDay = new Date(y, m + 1, 0).getDate()
  const toDate = `${y}-${String(m + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  return { fromDate, toDate }
})

// Load data
async function loadData() {
  loading.value = true
  loaded.value = false
  try {
    const { fromDate, toDate } = monthRange.value

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

function onTripRowClick(trip) {
  if (compareMode.value) {
    toggleTripCompare(trip)
    return
  }
  selectTrip(trip)
}

function compareTripKey(trip) {
  return trip?.gpskey || `${trip?.beginTime || ''}-${trip?.endTime || ''}`
}

function isTripSelectedForCompare(trip) {
  return selectedCompareTrips.value.some(t => compareTripKey(t) === compareTripKey(trip))
}

function toggleTripCompare(trip) {
  const idx = selectedCompareTrips.value.findIndex(t => compareTripKey(t) === compareTripKey(trip))
  if (idx >= 0) {
    selectedCompareTrips.value.splice(idx, 1)
  } else {
    if (selectedCompareTrips.value.length >= 2) {
      selectedCompareTrips.value.shift()
    }
    selectedCompareTrips.value.push({ ...trip })
  }
}

function toggleCompareMode() {
  compareMode.value = !compareMode.value
  if (!compareMode.value) {
    clearCompareSelection()
  }
}

function clearCompareSelection() {
  selectedCompareTrips.value = []
}

function openManualCompare() {
  if (selectedCompareTrips.value.length !== 2) return
  compareDialog.value = {
    a: selectedCompareTrips.value[0],
    b: selectedCompareTrips.value[1],
    score: null,
    breakdown: null,
  }
}

async function findSimilarTrips(trip, scope = 'month') {
  if (!trip?.gpskey) return
  similarLoading.value = true
  similarTrips.value = []
  similarError.value = null
  similarScope.value = scope
  similarTotalCount.value = 0
  modalView.value = 'similar'
  try {
    // Compute trip's own month range
    const tripMonth = trip.beginTime?.slice(0, 7) || monthRange.value.fromDate.slice(0, 7)
    const y = parseInt(tripMonth.slice(0, 4))
    const m = parseInt(tripMonth.slice(5, 7))
    const lastDay = new Date(y, m, 0).getDate()
    const tripFrom = `${tripMonth}-01`
    const tripTo = `${tripMonth}-${String(lastDay).padStart(2, '0')}`

    let fromDate, toDate
    if (scope === 'month') {
      fromDate = tripFrom
      toDate = tripTo
    } else {
      // Extended: 90 days before trip, up to today (no future dates)
      fromDate = fromDateISO(trip.beginTime, -90)
      toDate = new Date().toISOString().slice(0, 10)
    }

    console.log(`[similar] scope=${scope} from=${fromDate} to=${toDate} gpskey=${trip.gpskey}`)
    const data = await api(
      'GET',
      `/api/vehicles/${props.vin}/trips/similar?gpskey=${encodeURIComponent(trip.gpskey)}&limit=5&begin_time=${fromDate}&end_time=${toDate}`,
    )
    similarTrips.value = Array.isArray(data?.items) ? data.items : []
    similarTotalCount.value = data?.count ?? 0
  } catch (e) {
    console.error('Failed to load similar trips:', e)
    similarError.value = e?.message || 'Unknown error'
  } finally {
    similarLoading.value = false
  }
}

function fromDateISO(dateStr, deltaDays) {
  if (!dateStr) return ''
  const d = new Date(dateStr.replace(' ', 'T') + 'Z')
  if (isNaN(d)) return ''
  d.setDate(d.getDate() + deltaDays)
  return d.toISOString().slice(0, 10)
}

function openSuggestedCompare(item) {
  if (!selectedTrip.value || !item?.trip) return
  activeCompare.value = {
    a: selectedTrip.value,
    b: item.trip,
    score: item.similarity_score,
    breakdown: item.score_breakdown || null,
  }
  modalView.value = 'compare'
}

// Trip selection & GPS
async function selectTrip(trip) {
  selectedTrip.value = trip
  modalView.value = 'detail'
  similarTrips.value = []
  similarLoading.value = false
  similarError.value = null
  similarScope.value = 'month'
  similarTotalCount.value = 0
  activeCompare.value = null
  gpsPoints.value = []
  gpsLoading.value = false
  mapKey.value++
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

function closeTripDetail() {
  selectedTrip.value = null
  modalView.value = 'detail'
  similarTrips.value = []
  similarLoading.value = false
  similarError.value = null
  similarScope.value = 'month'
  similarTotalCount.value = 0
  activeCompare.value = null
}

function enterManualCompareFromDetail() {
  const trip = selectedTrip.value
  closeTripDetail()
  compareMode.value = true
  if (trip) {
    selectedCompareTrips.value = [{ ...trip }]
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
  L.polyline(coords, { color: accentHex(), weight: 3, opacity: 0.8 }).addTo(mapInstance)

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

function getChartColors() {
  const s = getComputedStyle(document.documentElement)
  return {
    grid: s.getPropertyValue('--chart-grid').trim() || '#1c2135',
    tick: s.getPropertyValue('--chart-tick').trim() || '#4a5468',
  }
}

function renderSpeedChart() {
  destroySpeedChart()
  const canvas = speedCanvas.value
  if (!canvas || !gpsPoints.value.length) return

  const ctx = canvas.getContext('2d')
  const points = gpsPoints.value.filter(p => p.speed != null)
  const cc = getChartColors()

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
        borderColor: accentHex(),
        backgroundColor: accentRgba(0.08),
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
          ticks: { color: cc.tick, font: { size: 10 }, maxTicksLimit: 10 },
          grid: { display: false },
        },
        y: {
          ticks: { color: cc.tick, callback: v => v + ' km/h' },
          grid: { color: cc.grid },
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

function formatMonthYear(monthStr) {
  if (!monthStr) return ''
  const [y, m] = monthStr.split('-')
  const d = new Date(+y, +m - 1, 1)
  return d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
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
  const kwh = (parseFloat(trip.energyConsumed) || 0) / 1000
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
  if (trip?.avgSpeed != null) {
    return `${Number(trip.avgSpeed).toFixed(0)} km/h`
  }
  if (!trip.beginTime || !trip.endTime) return '—'
  const start = new Date(trip.beginTime.replace(' ', 'T') + 'Z')
  const end = new Date(trip.endTime.replace(' ', 'T') + 'Z')
  const hours = (end - start) / 3600000
  if (hours <= 0) return '—'
  const km = (parseFloat(trip.travelMile) || 0) / 1000
  return `${(km / hours).toFixed(0)} km/h`
}

function formatScore(score) {
  const n = Number(score)
  if (Number.isNaN(n)) return '—'
  return `${Math.round(n * 100)}%`
}

function compareMetrics(a, b) {
  const aKm = (parseFloat(a.travelMile) || 0) / 1000
  const bKm = (parseFloat(b.travelMile) || 0) / 1000
  const aKwh = (parseFloat(a.energyConsumed) || 0) / 1000
  const bKwh = (parseFloat(b.energyConsumed) || 0) / 1000
  const aCons = parseFloat(tripConsumption(a))
  const bCons = parseFloat(tripConsumption(b))
  const aDur = tripDurationMinutes(a)
  const bDur = tripDurationMinutes(b)
  const aAvg = parseFloat(formatAvgSpeed(a)) || 0
  const bAvg = parseFloat(formatAvgSpeed(b)) || 0
  const aTemp = a.outdoorTemp
  const bTemp = b.outdoorTemp

  return [
    { key: 'distance', label: 'Distance (km)', a: aKm.toFixed(1), b: bKm.toFixed(1), delta: formatSignedNumber(bKm - aKm, 1), betterIfLower: false },
    { key: 'duration', label: 'Duration (min)', a: String(aDur), b: String(bDur), delta: formatSignedNumber(bDur - aDur, 0), betterIfLower: true },
    { key: 'energy', label: 'Energy (kWh)', a: aKwh.toFixed(2), b: bKwh.toFixed(2), delta: formatSignedNumber(bKwh - aKwh, 2), betterIfLower: true },
    { key: 'consumption', label: 'Consumption (kWh/100km)', a: Number.isFinite(aCons) ? aCons.toFixed(1) : '—', b: Number.isFinite(bCons) ? bCons.toFixed(1) : '—', delta: Number.isFinite(aCons) && Number.isFinite(bCons) ? formatSignedNumber(bCons - aCons, 1) : '—', betterIfLower: true },
    { key: 'avg-speed', label: 'Avg speed (km/h)', a: String(Math.round(aAvg)), b: String(Math.round(bAvg)), delta: formatSignedNumber(bAvg - aAvg, 1), betterIfLower: false },
    { key: 'temp', label: 'Outside temp (°C)', a: aTemp ?? '—', b: bTemp ?? '—', delta: aTemp != null && bTemp != null ? formatSignedNumber(bTemp - aTemp, 0) : '—', betterIfLower: null },
  ]
}

function tripDurationMinutes(trip) {
  if (!trip.beginTime || !trip.endTime) return 0
  const start = new Date(trip.beginTime.replace(' ', 'T') + 'Z')
  const end = new Date(trip.endTime.replace(' ', 'T') + 'Z')
  if (isNaN(start) || isNaN(end)) return 0
  return Math.max(0, Math.round((end - start) / 60000))
}

function formatSignedNumber(val, digits = 1) {
  const n = Number(val)
  if (Number.isNaN(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(digits)}`
}

function deltaClass(metric) {
  if (metric.delta === '—' || metric.betterIfLower == null) return ''
  const delta = Number(metric.delta)
  if (Number.isNaN(delta) || delta === 0) return ''
  const good = metric.betterIfLower ? delta < 0 : delta > 0
  return good ? 'delta-good' : 'delta-bad'
}

function compareEfficiencyInsight(a, b) {
  const aCons = parseFloat(tripConsumption(a))
  const bCons = parseFloat(tripConsumption(b))
  if (!Number.isFinite(aCons) || !Number.isFinite(bCons)) return 'Not enough data to compare efficiency.'
  if (bCons < aCons) return `Trip B is more efficient by ${(aCons - bCons).toFixed(1)} kWh/100km.`
  if (bCons > aCons) return `Trip A is more efficient by ${(bCons - aCons).toFixed(1)} kWh/100km.`
  return 'Both trips have equivalent efficiency.'
}

function comparePerformanceInsight(a, b) {
  const aDur = tripDurationMinutes(a)
  const bDur = tripDurationMinutes(b)
  if (!aDur || !bDur) return 'Not enough data to compare travel time.'
  if (bDur < aDur) return `Trip B is faster by ${aDur - bDur} minutes.`
  if (bDur > aDur) return `Trip A is faster by ${bDur - aDur} minutes.`
  return 'Travel times are equivalent.'
}

function compareConditionInsight(a, b) {
  if (a.outdoorTemp == null || b.outdoorTemp == null) return 'No outdoor temperature available for one of the trips.'
  const diff = b.outdoorTemp - a.outdoorTemp
  if (diff === 0) return 'Both trips ran at the same outside temperature.'
  if (diff > 0) return `Trip B ran in warmer conditions (+${diff}°C).`
  return `Trip B ran in colder conditions (${diff}°C).`
}

// Lifecycle
onMounted(loadData)

watch(() => props.vin, loadData)
watch(selectedMonth, loadData)
watch(selectedTrip, () => {
  similarTrips.value = []
  similarLoading.value = false
  similarError.value = null
  similarScope.value = 'month'
  similarTotalCount.value = 0
  modalView.value = 'detail'
  activeCompare.value = null
})

// Re-render map when navigating back to detail view (DOM was destroyed by v-if)
watch(modalView, async (newView) => {
  if (newView === 'detail' && gpsPoints.value.length) {
    mapInstance?.remove()
    mapInstance = null
    tileLayerInstance = null
    await nextTick()
    if (viewMode.value === 'speedmap') {
      renderSpeedMap()
    } else if (viewMode.value === 'chart') {
      renderSpeedChart()
    } else {
      renderSimpleMap()
    }
  }
})

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
.trips-tab { width: 100%; }
.trips-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.header-title h2 { font-size: 20px; font-weight: 700; color: var(--text); margin: 0; }
.header-title p { font-size: 12px; color: var(--muted); margin: 2px 0 0; }
.month-nav { display: flex; align-items: center; gap: 8px; }
.month-label { font-size: 14px; font-weight: 600; color: var(--text); min-width: 130px; text-align: center; }
.toolbar-btn { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 6px; color: var(--text); cursor: pointer; display: flex; align-items: center; transition: all 0.15s; }
.toolbar-btn:disabled { opacity: 0.4; cursor: default; }
.toolbar-btn:hover:not(:disabled) { background: var(--btn-bg); color: var(--cyan); border-color: var(--cyan); }
.toolbar-btn.active { border-color: var(--cyan); color: var(--cyan); }

/* Compare bar */
.compare-bar { margin-bottom: 16px; }
.compare-bar-inner {
  display: flex; align-items: center; gap: 8px;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 8px 12px;
}
.compare-bar-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 12px;
  color: var(--muted); font-size: 13px; cursor: pointer;
  transition: all 0.2s;
}
.compare-bar-btn:hover:not(:disabled) { color: var(--accent); border-color: rgba(var(--accent-rgb), 0.267); }
.compare-bar-btn:disabled { opacity: 0.4; cursor: default; }
.compare-bar-btn.active { border-color: rgba(var(--accent-rgb), 0.333); color: var(--accent); background: rgba(var(--accent-rgb), 0.067); }
.compare-bar-btn.primary {
  background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.133), rgba(var(--accent-rgb), 0.267));
  border: 1px solid rgba(var(--accent-rgb), 0.333);
  color: var(--accent); font-weight: 600;
}
.compare-bar-btn.primary:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.2), rgba(var(--accent-rgb), 0.333));
}
.compare-bar-btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.compare-bar-btn.clear {
  background: transparent; border-color: transparent; color: var(--muted); padding: 6px;
}
.compare-bar-btn.clear:hover { color: #ef5350; background: transparent; }
.compare-bar-count {
  display: flex; align-items: baseline; gap: 2px; margin: 0 4px;
}
.compare-count-num { font-size: 18px; font-weight: 700; color: var(--cyan); }
.compare-count-label { font-size: 11px; color: var(--muted); }

/* Summary grid */
.summary-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }
@media (min-width: 768px) {
  .summary-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
}
.summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; text-align: center; }
.summary-value { font-size: 20px; font-weight: 700; }
.summary-label { font-size: 10px; color: var(--muted); margin-top: 4px; }

/* Trip days */
.trip-days { display: flex; flex-direction: column; gap: 12px; }
.trip-day-group { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.day-header { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); background: var(--bg2); }
.day-date { font-weight: 600; font-size: 13px; color: var(--text); }
.day-summary { font-size: 11px; color: var(--muted); }
.trip-row { display: flex; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; }
.trip-row:last-child { border-bottom: none; }
.trip-row:hover { background: var(--bg2); }
.compare-checkbox { margin-right: 8px; display: flex; align-items: center; }
.compare-checkbox input { width: 16px; height: 16px; }
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
.modal-dialog.compare-modal { background: var(--card); border: 1px solid var(--border); border-radius: 16px; max-width: 860px; width: 100%; max-height: 85vh; overflow-y: auto; padding: 24px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text); margin: 0; }
.modal-back-btn {
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 4px; color: var(--text); cursor: pointer; display: flex; align-items: center;
  margin-right: 8px;
}
.modal-back-btn:hover { background: var(--bg); }
.close-btn { background: none; border: none; color: var(--muted); font-size: 18px; cursor: pointer; }
.close-btn:hover { color: var(--text); }
.trip-detail-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 16px; }
.detail-stat { background: var(--bg2); border-radius: 8px; padding: 10px 12px; }
.stat-label { display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px; }
.stat-value { font-size: 14px; font-weight: 600; color: var(--text); }
.trip-map { height: 350px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
.map-loading { display: flex; justify-content: center; padding: 32px; }
.map-empty { text-align: center; padding: 32px; color: var(--muted); font-size: 13px; }

.trip-actions {
  display: flex; gap: 8px; margin-top: 12px; padding-top: 12px;
  border-top: 1px solid var(--border);
}
.trip-action-btn {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 16px;
  color: var(--text); font-size: 13px; font-weight: 500; cursor: pointer;
  transition: all 0.15s;
}
.trip-action-btn:hover:not(:disabled) { background: var(--card); border-color: var(--cyan); color: var(--cyan); }
.trip-action-btn:disabled { opacity: 0.5; cursor: default; }
.trip-action-btn.secondary { border-color: var(--border); color: var(--muted); }
.trip-action-btn.secondary:hover:not(:disabled) { color: var(--text); border-color: var(--text); }

.similar-section { margin-top: 8px; }
.similar-hint { font-size: 12px; color: var(--muted); margin: 0 0 10px 0; }
.similar-group { margin-bottom: 12px; }
.similar-group-header {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  color: var(--cyan); letter-spacing: 0.5px;
  padding: 4px 0; margin-bottom: 4px;
  border-bottom: 1px solid var(--border);
}
.similar-list { display: flex; flex-direction: column; gap: 6px; }
.similar-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
.similar-main { display: flex; flex-direction: column; gap: 2px; color: var(--muted); font-size: 12px; }
.similar-main strong { color: var(--text); font-size: 12px; }
.similar-side { display: flex; align-items: center; gap: 8px; }
.similar-score { color: #7c6aff; font-weight: 600; font-size: 12px; }

.extend-search-box {
  margin-top: 12px; padding: 12px;
  background: var(--bg2); border: 1px dashed var(--border);
  border-radius: 10px; text-align: center;
}
.extend-search-box p { margin: 0 0 8px 0; font-size: 13px; color: var(--muted); }
.extend-hint { display: block; margin-top: 6px; font-size: 11px; color: var(--muted); opacity: 0.7; }

.compare-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.compare-col { background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
.compare-title { font-weight: 700; color: var(--text); margin-bottom: 4px; }
.compare-sub { color: var(--muted); font-size: 12px; }
.compare-table { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 12px; }
.compare-row { display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 12px; }
.compare-row:last-child { border-bottom: none; }
.compare-row.head { font-weight: 700; background: var(--bg2); color: var(--text); }
.delta-good { color: #00e676; font-weight: 600; }
.delta-bad { color: #ff7043; font-weight: 600; }
.insight-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
.insight-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 10px; font-size: 12px; color: var(--muted); }
.insight-title { font-weight: 700; color: var(--text); margin-bottom: 4px; }
.rank-box { font-size: 12px; color: var(--muted); }

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
  .trip-row { flex-wrap: wrap; gap: 6px; }
  .compare-columns { grid-template-columns: 1fr; }
  .compare-row { grid-template-columns: 1.2fr 1fr 1fr 1fr; font-size: 11px; }
  .insight-grid { grid-template-columns: 1fr; }
}
</style>
