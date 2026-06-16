<template>
  <div class="history-tab">
    <!-- Header + period selector -->
    <div class="history-header">
      <div class="header-title">
        <h2>Data History</h2>
        <p>Performance analysis over time</p>
      </div>
      <div class="source-toggle">
        <button class="source-btn" :class="{ active: dataSource === 'local' }" @click="dataSource = 'local'">
          <HardDrive :size="14" /> Local
        </button>
        <button class="source-btn" :class="{ active: dataSource === 'cloud' }" @click="dataSource = 'cloud'">
          <Cloud :size="14" /> Cloud
        </button>
        <button class="source-btn" :class="{ active: dataSource === 'events' }" @click="dataSource = 'events'; loadEvents()">
          <Activity :size="14" /> Events
        </button>
      </div>
      <div v-if="dataSource === 'local'" class="time-toolbar">
          <button class="toolbar-btn" @click="showDatePicker = !showDatePicker" title="Select date range">
            <CalendarDays :size="15" />
          </button>
          <span class="toolbar-date-label">{{ dateRangeLabel }}</span>
          <div class="toolbar-controls">
            <button class="toolbar-pill" @click="goToToday">Today</button>
            <button class="toolbar-btn" @click="goBack" title="Previous day">
              <ChevronLeft :size="16" />
            </button>
            <button class="toolbar-btn" :disabled="isAtToday" @click="goForward" title="Next day">
              <ChevronRight :size="16" />
            </button>
            <div class="toolbar-menu-wrapper">
              <button class="toolbar-btn" @click="showToolbarMenu = !showToolbarMenu" title="More options">
                <MoreVertical :size="16" />
              </button>
              <div v-if="showToolbarMenu" class="toolbar-menu">
                <button class="toolbar-menu-item" @click="exportCsv(); showToolbarMenu = false">
                  <Download :size="14" /> Download CSV
                </button>
              </div>
              <div v-if="showToolbarMenu" class="toolbar-menu-overlay" @click="showToolbarMenu = false"></div>
            </div>
          </div>
        </div>

      <!-- Date Range Picker Dropdown -->
      <div v-if="showDatePicker" class="date-picker-overlay" @click.self="showDatePicker = false"></div>
      <div v-if="showDatePicker" class="date-picker-dropdown">
        <div class="date-picker-presets">
          <button v-for="preset in datePresets" :key="preset.label" class="preset-btn" @click="applyPreset(preset)">{{ preset.label }}</button>
        </div>
        <div class="date-picker-calendar">
          <div class="calendar-nav">
            <button class="cal-nav-btn" @click="calendarMonth--; normalizeCalendarMonth()"><ChevronLeft :size="16" /></button>
            <span class="cal-month-label">{{ calendarMonthLabel }}</span>
            <button class="cal-nav-btn" @click="calendarMonth++; normalizeCalendarMonth()"><ChevronRight :size="16" /></button>
          </div>
          <div class="calendar-grid">
            <span class="cal-weekday" v-for="d in ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']" :key="d">{{ d }}</span>
            <span
              v-for="(cell, idx) in calendarCells"
              :key="idx"
              class="cal-day"
              :class="{
                'other-month': !cell.current,
                'today': cell.isToday,
                'selected': cell.isSelected,
                'in-range': cell.inRange
              }"
              @click="cell.current && selectCalendarDay(cell.date)"
            >{{ cell.day }}</span>
          </div>
          <div class="calendar-footer">
            <span class="cal-range-label" v-if="customFrom && customTo">{{ formatCalDate(customFrom) }} - {{ formatCalDate(customTo) }}</span>
            <span class="cal-range-label" v-else-if="customFrom">{{ formatCalDate(customFrom) }} - ...</span>
            <span class="cal-range-label" v-else>&nbsp;</span>
          </div>
        </div>
        <div class="date-picker-actions">
          <button class="dp-cancel" @click="showDatePicker = false" :disabled="loadingRange">Cancel</button>
          <button class="dp-select" :disabled="!customFrom || !customTo || loadingRange" @click="applyCustomRange()">
            <span v-if="loadingRange" class="dp-spinner"></span>
            {{ loadingRange ? 'Loading...' : 'Select' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Cloud stats view -->
    <CloudStatsView v-if="dataSource === 'cloud'" :vin="props.vin" />

    <!-- Events view -->
    <div v-if="dataSource === 'events'" class="events-section">
      <div class="events-toolbar">
        <select v-model="eventsFilter" class="events-filter" @change="loadEvents()">
          <option value="">All events</option>
          <option value="regen_start">Regen start</option>
          <option value="regen_stop">Regen stop</option>
          <option value="charge_start">Charge start</option>
          <option value="charge_stop">Charge stop</option>
          <option value="plugged_in">Plugged in</option>
          <option value="unplugged">Unplugged</option>
          <option value="driving_start">Driving start</option>
          <option value="parked">Parked</option>
          <option value="locked">Locked</option>
          <option value="unlocked">Unlocked</option>
          <option value="ignition_on">Ignition on</option>
          <option value="ignition_off">Ignition off</option>
          <option value="moving_start">Moving start</option>
          <option value="moving_stop">Moving stop</option>
          <option value="soc_change">SOC change</option>
          <option value="charge_state_change">Charge state change</option>
          <option value="geofence_enter">Zone entered</option>
          <option value="geofence_exit">Zone left</option>
          <option value="zone_dwell">Zone dwell too long</option>
          <option value="zone_absence">Zone absence too long</option>
          <option value="movement_alert">Movement alert</option>
          <option value="unlocked_timeout">Unlocked timeout</option>
          <option value="tire_pressure_alert">Tire pressure alert</option>
          <option value="range_low">Low range</option>
          <option value="tracking_start">Tracking start</option>
          <option value="tracking_stop">Tracking stop</option>
        </select>
        <select v-model="eventsDays" class="events-filter" @change="loadEvents()">
          <option :value="1">Today</option>
          <option :value="7">Last 7 days</option>
          <option :value="30">Last 30 days</option>
          <option :value="90">Last 90 days</option>
        </select>
        <span class="events-count">{{ events.length }} events</span>
      </div>

      <div v-if="eventsLoading" class="events-loading">Loading events...</div>

      <div v-else-if="events.length === 0" class="events-empty">
        <Activity :size="32" />
        <p>No events detected yet</p>
        <p class="events-empty-hint">Events are recorded when the vehicle changes state (regen, charging, parking, etc.)</p>
      </div>

      <div v-else class="events-timeline">
        <div v-for="(event, idx) in events" :key="idx" class="event-row">
          <div class="event-dot" :class="eventDotClass(event.event_type)" />
          <div class="event-content">
            <span class="event-type">{{ formatEventType(event.event_type) }}</span>
            <span class="event-field">{{ event.field_name }}</span>
            <span v-if="event.old_value && event.new_value" class="event-values">
              {{ event.old_value }} → {{ event.new_value }}
            </span>
          </div>
          <div class="event-time">{{ formatEventTime(event.timestamp) }}</div>
        </div>
      </div>
    </div>

    <!-- KPI skeleton -->
    <HistorySkeleton v-if="dataSource === 'local' && loadingKpi && !kpiCards.length" :show-kpi="true" :show-charts="false" />

    <!-- KPI cards -->
    <transition name="fade">
      <div v-if="dataSource === 'local' && kpiCards.length" class="summary-grid">
        <div v-for="s in kpiCards" :key="s.label" class="summary-card">
          <div class="summary-value" :style="{ color: s.color }">{{ s.value }}</div>
          <div class="summary-label">{{ s.label }}</div>
        </div>
      </div>
    </transition>

    <!-- Stale indicator -->
    <div v-if="dataSource === 'local' && isStale" class="stale-banner">
      <span class="stale-dot"></span> Updating data...
    </div>

    <!-- Charts skeleton -->
    <HistorySkeleton v-if="dataSource === 'local' && loadingCharts && !data.length" :show-kpi="false" :show-charts="true" :chart-count="4" />

    <!-- Charts -->
    <template v-if="dataSource === 'local' && chartsReady">
      <!-- Existing core charts -->
      <h3 class="section-title">Battery & Energy</h3>
      <div class="charts-grid">
        <div class="chart-card">
          <div class="chart-header"><Battery :size="16" class="chart-icon" /> Battery level & energy</div>
          <div class="chart-area"><canvas ref="batteryCanvas" /></div>
          <div class="chart-legend">
            <span class="legend-item"><span class="legend-line start"></span> Charge start</span>
            <span class="legend-item"><span class="legend-line end"></span> Charge end</span>
          </div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Map :size="16" class="chart-icon" /> Estimated range (km)</div>
          <div class="chart-area"><canvas ref="rangeCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Route :size="16" class="chart-icon" /> Daily km driven</div>
          <div class="chart-area"><canvas ref="kmCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Zap :size="16" class="chart-icon" /> Charging / Discharging power (kW)</div>
          <div class="chart-area"><canvas ref="powerCanvas" /></div>
        </div>
      </div>

      <!-- Efficiency & Consumption -->
      <h3 class="section-title">Efficiency & Consumption</h3>
      <div class="charts-grid">
        <div class="chart-card">
          <div class="chart-header"><Gauge :size="16" class="chart-icon" /> Average consumption (kWh/100km)</div>
          <div class="chart-area"><canvas ref="consumptionCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Thermometer :size="16" class="chart-icon" /> Efficiency vs Temperature</div>
          <div class="chart-area"><canvas ref="effTempCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Gauge :size="16" class="chart-icon" /> Efficiency vs Speed</div>
          <div class="chart-area"><canvas ref="effSpeedCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Map :size="16" class="chart-icon" /> Real vs Estimated range</div>
          <div class="chart-area"><canvas ref="realVsEstCanvas" /></div>
        </div>
      </div>

      <!-- Battery & Charging -->
      <h3 class="section-title">Charging Sessions</h3>
      <div class="charts-grid">
        <div class="chart-card wide">
          <div class="chart-header"><Zap :size="16" class="chart-icon" /> Energy charged per session (kWh)</div>
          <div class="chart-area"><canvas ref="chargeSessionCanvas" /></div>
        </div>
      </div>

      <!-- Vehicle Usage -->
      <h3 class="section-title">Vehicle Usage</h3>
      <div class="charts-grid">
        <div class="chart-card">
          <div class="chart-header"><Clock :size="16" class="chart-icon" /> Usage heatmap (hour / day)</div>
          <div class="heatmap-container">
            <div class="heatmap-row" v-for="(row, dayIdx) in heatmapData" :key="dayIdx">
              <span class="heatmap-day">{{ ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dayIdx] }}</span>
              <div
                v-for="(val, hour) in row"
                :key="hour"
                class="heatmap-cell"
                :style="{ backgroundColor: heatmapColor(val) }"
                :title="`${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dayIdx]} ${hour}:00 - ${val} active`"
              />
            </div>
            <div class="heatmap-hours">
              <span v-for="h in [0,3,6,9,12,15,18,21]" :key="h">{{ h }}h</span>
            </div>
          </div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><CircleDot :size="16" class="chart-icon" /> Parked vs In use</div>
          <div class="chart-area"><canvas ref="usagePieCanvas" /></div>
        </div>
        <div class="chart-card" :class="{ 'map-expanded': mapExpanded }">
          <div class="chart-header">
            <MapPin :size="16" class="chart-icon" /> Trip map (lat/lon)
            <button class="map-expand-btn" @click="toggleMapExpand" :title="mapExpanded ? 'Minimize' : 'Maximize'">
              <component :is="mapExpanded ? Minimize2 : Maximize2" :size="14" />
            </button>
          </div>
          <div class="chart-area map-area" :class="{ 'map-area-expanded': mapExpanded }" ref="tripMapContainer"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><BatteryWarning :size="16" class="chart-icon" /> Vampire drain (SOC loss while parked)</div>
          <div v-if="vampireDrainData.length === 0" class="chart-empty-msg">
            No drain detected — the battery SOC remained stable during all parked sessions in this period. This chart will show data when a measurable SOC drop occurs while the car is parked and not charging for at least 1 hour.
          </div>
          <div v-else class="chart-area"><canvas ref="vampireCanvas" /></div>
        </div>
      </div>

      <!-- Tire Pressure -->
      <h3 class="section-title">Tire Pressure</h3>
      <div class="charts-grid">
        <div class="chart-card">
          <div class="chart-header"><Circle :size="16" class="chart-icon" /> Pressure over time (bar)</div>
          <div class="chart-area"><canvas ref="tirePressureCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><Thermometer :size="16" class="chart-icon" /> Pressure vs Temperature</div>
          <div class="chart-area"><canvas ref="tireTempCanvas" /></div>
        </div>
        <div class="chart-card wide">
          <div class="chart-header"><Circle :size="16" class="chart-icon" /> L/R pressure difference (bar)</div>
          <div class="chart-area"><canvas ref="tireDiffCanvas" /></div>
        </div>
      </div>

      <!-- Full-width temp chart -->
      <div class="chart-card wide" style="margin-top:14px">
        <div class="chart-header"><Thermometer :size="16" class="chart-icon" /> Outside temperature vs Energy consumption</div>
        <div class="chart-area tall"><canvas ref="tempCanvas" /></div>
      </div>
    </template>

    <div v-if="dataSource === 'local'" class="history-note">
      <template v-if="allSnapshots.length || allData.length">
        Real data collected from vehicle · {{ allSnapshots.length }} snapshots in current view
      </template>
      <template v-else>
        No data yet. Enable automatic collection in Settings to populate history.
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import { api } from '../composables/useApi'
import { Battery, Map, Zap, Route, Thermometer, BarChart3, Table2, Gauge, Clock, CircleDot, MapPin, Circle, BatteryWarning, CalendarDays, ChevronLeft, ChevronRight, MoreVertical, Download, Maximize2, Minimize2, HardDrive, Cloud, Activity } from 'lucide-vue-next'
import HistorySkeleton from '../components/HistorySkeleton.vue'
import CloudStatsView from '../components/CloudStatsView.vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

Chart.register(...registerables)

const props = defineProps({
  status: { type: Object, required: true },
  vin: { type: String, default: null },
})

const viewMode = ref('chart')
const dataSource = ref('local')
const showToolbarMenu = ref(false)

// ---------------------------------------------------------------------------
// Events state
// ---------------------------------------------------------------------------
const events = ref([])
const eventsLoading = ref(false)
const eventsFilter = ref('')
const eventsDays = ref(7)

async function loadEvents() {
  if (!props.vin) return
  eventsLoading.value = true
  try {
    let url = `/api/vehicles/${props.vin}/events?days=${eventsDays.value}`
    if (eventsFilter.value) url += `&event_type=${eventsFilter.value}`
    const data = await api('GET', url)
    events.value = (data.events || []).reverse() // newest first
  } catch {
    events.value = []
  } finally {
    eventsLoading.value = false
  }
}

const EVENT_TYPE_LABELS = {
  geofence_enter: 'Zone entered',
  geofence_exit: 'Zone left',
  zone_dwell: 'Zone dwell too long',
  zone_absence: 'Zone absence too long',
}

function formatEventType(type) {
  return EVENT_TYPE_LABELS[type]
    || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatEventTime(ts) {
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return isToday ? time : `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`
}

function eventDotClass(type) {
  if (type.includes('regen')) return 'dot-regen'
  if (type.includes('charge') || type.includes('plugged')) return 'dot-charge'
  if (type.includes('driving') || type.includes('moving')) return 'dot-drive'
  if (type.includes('lock') || type.includes('ignition') || type.includes('movement_alert') || type.includes('unlocked_timeout')) return 'dot-security'
  if (type.includes('geofence') || type.includes('zone')) return 'dot-geofence'
  if (type.includes('tracking')) return 'dot-tracking'
  if (type.includes('tire') || type.includes('range_low')) return 'dot-maintenance'
  if (type.includes('soc')) return 'dot-soc'
  return 'dot-default'
}

// ---------------------------------------------------------------------------
// Custom date range picker
// ---------------------------------------------------------------------------
const showDatePicker = ref(false)
const customRangeActive = ref(false)
const customFrom = ref(null)
const customTo = ref(null)
// Monotonic counter to discard out-of-order range-snapshot responses.
let rangeReqSeq = 0
const calendarYear = ref(new Date().getFullYear())
const calendarMonth = ref(new Date().getMonth()) // 0-based

const datePresets = [
  { label: 'Today', fn: () => { const t = startOfDay(new Date()); return [t, new Date()] } },
  { label: 'Yesterday', fn: () => { const t = startOfDay(new Date()); t.setDate(t.getDate()-1); return [t, startOfDay(new Date())] } },
  { label: 'This week', fn: () => { const t = startOfWeek(new Date()); return [t, new Date()] } },
  { label: 'This month', fn: () => { const t = new Date(); t.setDate(1); t.setHours(0,0,0,0); return [t, new Date()] } },
  { label: 'This quarter', fn: () => { const t = new Date(); const q = Math.floor(t.getMonth()/3)*3; t.setMonth(q,1); t.setHours(0,0,0,0); return [t, new Date()] } },
  { label: 'This year', fn: () => { const t = new Date(); t.setMonth(0,1); t.setHours(0,0,0,0); return [t, new Date()] } },
  { label: 'Last 7 days', fn: () => [daysAgo(7), new Date()] },
  { label: 'Last 30 days', fn: () => [daysAgo(30), new Date()] },
  { label: 'Last 90 days', fn: () => [daysAgo(90), new Date()] },
  { label: 'Last 12 months', fn: () => [daysAgo(365), new Date()] },
]

function startOfDay(d) { d.setHours(0,0,0,0); return d }
function startOfWeek(d) { const day = (d.getDay()+6)%7; d.setDate(d.getDate()-day); d.setHours(0,0,0,0); return d }
function daysAgo(n) { const d = new Date(); d.setDate(d.getDate()-n); d.setHours(0,0,0,0); return d }

function normalizeCalendarMonth() {
  if (calendarMonth.value < 0) { calendarMonth.value = 11; calendarYear.value-- }
  if (calendarMonth.value > 11) { calendarMonth.value = 0; calendarYear.value++ }
}

const calendarMonthLabel = computed(() => {
  const d = new Date(calendarYear.value, calendarMonth.value, 1)
  return d.toLocaleString('en-US', { month: 'long', year: 'numeric' })
})

const calendarCells = computed(() => {
  const y = calendarYear.value, m = calendarMonth.value
  const first = new Date(y, m, 1)
  const startDow = (first.getDay() + 6) % 7 // Monday = 0
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const cells = []
  const today = new Date(); today.setHours(0,0,0,0)

  // Previous month days
  const prevMonthDays = new Date(y, m, 0).getDate()
  for (let i = startDow - 1; i >= 0; i--) {
    const day = prevMonthDays - i
    const date = new Date(y, m - 1, day); date.setHours(0,0,0,0)
    cells.push({ day, date, current: false, isToday: false, isSelected: false, inRange: false })
  }

  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(y, m, d); date.setHours(0,0,0,0)
    const isToday = date.getTime() === today.getTime()
    const isSelected = (customFrom.value && date.getTime() === customFrom.value.getTime()) || (customTo.value && date.getTime() === customTo.value.getTime())
    const inRange = customFrom.value && customTo.value && date > customFrom.value && date < customTo.value
    cells.push({ day: d, date, current: true, isToday, isSelected, inRange })
  }

  // Next month fill
  const remaining = 42 - cells.length
  for (let d = 1; d <= remaining; d++) {
    const date = new Date(y, m + 1, d); date.setHours(0,0,0,0)
    cells.push({ day: d, date, current: false, isToday: false, isSelected: false, inRange: false })
  }
  return cells
})

function selectCalendarDay(date) {
  if (!customFrom.value || (customFrom.value && customTo.value)) {
    customFrom.value = date
    customTo.value = null
  } else {
    if (date < customFrom.value) {
      customTo.value = customFrom.value
      customFrom.value = date
    } else {
      customTo.value = date
    }
  }
}

function applyPreset(preset) {
  const [from, to] = preset.fn()
  customFrom.value = from
  customTo.value = to
}

async function applyCustomRange() {
  loadingRange.value = true
  customRangeActive.value = true
  try {
    await fetchRangeSnapshots(customFrom.value, customTo.value)
  } finally {
    loadingRange.value = false
    showDatePicker.value = false
  }
}

function formatCalDate(d) {
  if (!d) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ---------------------------------------------------------------------------
// Toolbar navigation
// ---------------------------------------------------------------------------
function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

const isAtToday = computed(() => {
  if (!customRangeActive.value) return true // default is today
  if (!customTo.value) return true
  const today = new Date(); today.setHours(0,0,0,0)
  return isSameDay(customTo.value, today)
})

const dateRangeLabel = computed(() => {
  if (!customRangeActive.value || !customFrom.value || !customTo.value) {
    // Default: today
    const today = new Date()
    return today.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
  }
  if (isSameDay(customFrom.value, customTo.value)) {
    return customFrom.value.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
  }
  const fmtFrom = customFrom.value.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
  const fmtTo = customTo.value.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
  return `${fmtFrom} – ${fmtTo}`
})

function goToToday() {
  const today = new Date(); today.setHours(0,0,0,0)
  customFrom.value = today
  customTo.value = today
  customRangeActive.value = true
  fetchRangeSnapshots(today, today)
}

function goBack() {
  if (!customRangeActive.value || !customFrom.value || !customTo.value) {
    // Currently showing today, go to yesterday
    const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1); yesterday.setHours(0,0,0,0)
    customFrom.value = yesterday
    customTo.value = yesterday
    customRangeActive.value = true
    fetchRangeSnapshots(yesterday, yesterday)
    return
  }
  const rangeMs = customTo.value.getTime() - customFrom.value.getTime()
  const dayMs = 86400000
  const shift = Math.max(dayMs, rangeMs + dayMs)
  const newFrom = new Date(customFrom.value.getTime() - shift); newFrom.setHours(0,0,0,0)
  const newTo = new Date(customTo.value.getTime() - shift); newTo.setHours(0,0,0,0)
  customFrom.value = newFrom
  customTo.value = newTo
  customRangeActive.value = true
  fetchRangeSnapshots(newFrom, newTo)
}

function goForward() {
  if (!customRangeActive.value || !customFrom.value || !customTo.value) return
  const today = new Date(); today.setHours(0,0,0,0)
  const rangeMs = customTo.value.getTime() - customFrom.value.getTime()
  const dayMs = 86400000
  const shift = Math.max(dayMs, rangeMs + dayMs)
  const newTo = new Date(customTo.value.getTime() + shift); newTo.setHours(0,0,0,0)
  if (newTo > today) newTo.setTime(today.getTime())
  const newFrom = new Date(customFrom.value.getTime() + shift); newFrom.setHours(0,0,0,0)
  if (newFrom > today) newFrom.setTime(today.getTime())
  customFrom.value = newFrom
  customTo.value = newTo
  customRangeActive.value = true
  fetchRangeSnapshots(newFrom, newTo)
}

function exportCsv() {
  const rows = data.value
  if (!rows.length) return
  const headers = Object.keys(rows[0]).filter(k => k !== 'rawDate')
  const csv = [headers.join(',')]
  for (const row of rows) {
    csv.push(headers.map(h => `"${row[h] ?? ''}"`).join(','))
  }
  const blob = new Blob([csv.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `history_${dateRangeLabel.value.replace(/[^a-zA-Z0-9]/g, '_')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// Loading & caching states
// ---------------------------------------------------------------------------
const loadingKpi = ref(true)
const loadingCharts = ref(true)
const chartsReady = ref(false)
const isStale = ref(false)
const loadingRange = ref(false)

const CACHE_KEY_PREFIX = 'history_cache_'
const CACHE_MAX_AGE_MS = 5 * 60 * 1000 // 5 minutes

function getCacheKey() {
  return `${CACHE_KEY_PREFIX}${props.vin}`
}

function loadFromCache() {
  try {
    const raw = sessionStorage.getItem(getCacheKey())
    if (!raw) return null
    const cached = JSON.parse(raw)
    if (Date.now() - cached.timestamp > CACHE_MAX_AGE_MS * 12) return null // discard if older than 1 hour
    return cached
  } catch { return null }
}

function saveToCache(dailyData, snapshots, allSnaps) {
  try {
    sessionStorage.setItem(getCacheKey(), JSON.stringify({
      timestamp: Date.now(),
      dailyData,
      snapshots,
      allSnaps,
    }))
  } catch { /* quota exceeded, ignore */ }
}

// ---------------------------------------------------------------------------
// Data source
// ---------------------------------------------------------------------------
const allSnapshots = ref([])
const allData = ref([])
const todaySnapshots = ref([])
const electricityPriceKwh = ref(0.25)
const downsamplingEnabled = ref(true)
const downsamplingMaxPoints = ref(2000)
const sessionCosts = ref([])
const chargingTiers = ref({})

function applyData(daily, snaps, allSnaps) {
  allSnapshots.value = allSnaps

  todaySnapshots.value = snaps.map(s => ({
    date: formatTimestamp(s.timestamp),
    battery: s.battery_soc ?? 0,
    range: s.battery_expected_mileage ?? 0,
    kmDriven: 0,
    batteryEnergy: (s.battery_dump_energy ?? 0) / 1000.0,
    chargingPower: s.battery_charging_power_kw ?? 0,
    dischargingPower: s.battery_discharge_power_kw ?? 0,
    temp: s.climate_outdoor_temp ?? 0,
    chargeSessions: s.battery_is_charging ? 1 : 0,
    sampleCount: 1,
  }))

  if (daily.length > 0) {
    allData.value = daily.map(d => ({
      date: formatDate(d.date),
      rawDate: d.date,
      battery: d.avg_soc ?? 0,
      range: d.max_range ?? 0,
      kmDriven: d.km_driven ?? 0,
      batteryEnergy: d.energy_delta ?? 0,
      chargingPower: 0,
      dischargingPower: 0,
      temp: d.avg_temp ?? 0,
      chargeSessions: d.charge_sessions ?? 0,
      sampleCount: d.sample_count ?? 0,
    }))
  }
}

async function fetchHistory() {
  if (!props.vin) return

  // Stale-while-revalidate: load cache first
  const cached = loadFromCache()
  if (cached) {
    applyData(cached.dailyData, cached.snapshots, cached.allSnaps)
    loadingKpi.value = false
    isStale.value = (Date.now() - cached.timestamp) > CACHE_MAX_AGE_MS
    // If cache is fresh enough, show charts immediately
    await nextTick()
    chartsReady.value = true
    loadingCharts.value = false
  }

  try {
    // Only fetch daily summaries + today's snapshots on initial load (lightweight)
    const [dailyRes, snapshotRes] = await Promise.all([
      api('GET', `/api/vehicles/${props.vin}/history/daily?days=3650`),
      api('GET', `/api/vehicles/${props.vin}/history?days=1`),
    ])
    const daily = dailyRes.daily || []
    const snaps = snapshotRes.snapshots || []

    // Progressive loading: KPI first
    applyData(daily, snaps, snaps)
    loadingKpi.value = false
    isStale.value = false

    // Save to cache
    saveToCache(daily, snaps, snaps)

    // Charts slightly deferred for progressive feel
    await nextTick()
    chartsReady.value = true
    loadingCharts.value = false
  } catch (err) {
    console.error('[HistoryTab] fetchHistory failed:', err)
    loadingKpi.value = false
    loadingCharts.value = false
    chartsReady.value = true
  }
}

async function fetchRangeSnapshots(from, to) {
  if (!props.vin || !from || !to) return
  // Guard against out-of-order responses: a slow request for a previous day
  // must not overwrite the data of a newer navigation.
  const seq = ++rangeReqSeq
  loadingKpi.value = true
  loadingCharts.value = true
  chartsReady.value = false
  try {
    const fromStr = toDateStr(from)
    const toStr = toDateStr(to)
    let url = `/api/vehicles/${props.vin}/history?from_date=${fromStr}&to_date=${toStr}`
    if (downsamplingEnabled.value) {
      url += `&max_points=${downsamplingMaxPoints.value}`
    }
    const res = await api('GET', url)
    if (seq !== rangeReqSeq) return // superseded by a newer request
    const snaps = res.snapshots || []
    allSnapshots.value = snaps
    todaySnapshots.value = snaps.map(s => ({
      date: formatTimestamp(s.timestamp),
      battery: s.battery_soc ?? 0,
      range: s.battery_expected_mileage ?? 0,
      kmDriven: 0,
      batteryEnergy: (s.battery_dump_energy ?? 0) / 1000.0,
      chargingPower: s.battery_charging_power_kw ?? 0,
      dischargingPower: s.battery_discharge_power_kw ?? 0,
      temp: s.climate_outdoor_temp ?? 0,
      chargeSessions: s.battery_is_charging ? 1 : 0,
      sampleCount: 1,
    }))
    loadingKpi.value = false
    await nextTick()
    chartsReady.value = true
    loadingCharts.value = false
  } catch (err) {
    if (seq !== rangeReqSeq) return // superseded — let the newer request own the UI state
    console.error('[HistoryTab] fetchRangeSnapshots failed:', err)
    loadingKpi.value = false
    loadingCharts.value = false
    chartsReady.value = true
  }
}

function formatDate(isoDate) {
  const [, m, d] = isoDate.split('-')
  return `${d}/${m}`
}

// Local calendar date as YYYY-MM-DD. Must NOT use toISOString(), which
// converts to UTC and rolls the date back a day for positive-UTC timezones
// (e.g. Italy in summer), making the fetched day lag the displayed label.
function toDateStr(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function formatTimestamp(iso) {
  // timestamps from backend are naive UTC (no TZ suffix) — force UTC parsing
  const d = new Date(iso + 'Z')
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

watch(() => props.vin, fetchHistory)
onMounted(async () => {
  fetchHistory()
  try {
    const prefs = await api('GET', '/api/preferences')
    electricityPriceKwh.value = prefs.electricity_price_kwh
    downsamplingEnabled.value = prefs.downsampling_enabled ?? true
    downsamplingMaxPoints.value = prefs.downsampling_max_points ?? 2000
  } catch { /* use default */ }
  // Load charging tiers and session costs
  try {
    const tiersData = await api('GET', '/api/charging/tiers')
    const tierMap = {}
    for (const t of (tiersData.tiers || [])) { tierMap[t.id] = t }
    chargingTiers.value = tierMap
  } catch { /* ignore */ }
  if (props.vin) {
    try {
      sessionCosts.value = await api('GET', `/api/vehicles/${props.vin}/charging-costs`)
    } catch { /* ignore */ }
  }
})

// ---------------------------------------------------------------------------
// Filtered snapshots for selected period
// ---------------------------------------------------------------------------
const filteredSnapshots = computed(() => {
  // allSnapshots already contains only the current range's data (fetched on-demand)
  return allSnapshots.value
})

// ---------------------------------------------------------------------------
// Visible display data based on selected period
// ---------------------------------------------------------------------------
const isToday = computed(() => {
  if (!customRangeActive.value) return true
  if (!customFrom.value || !customTo.value) return true
  return isSameDay(customFrom.value, customTo.value) && isSameDay(customTo.value, new Date())
})

const data = computed(() => {
  if (customRangeActive.value && customFrom.value && customTo.value) {
    if (isSameDay(customFrom.value, customTo.value)) {
      // Single day view: use snapshot data directly
      return allSnapshots.value.map(s => ({
        date: formatTimestamp(s.timestamp),
        battery: s.battery_soc ?? 0,
        range: s.battery_expected_mileage ?? 0,
        kmDriven: 0,
        batteryEnergy: (s.battery_dump_energy ?? 0) / 1000.0,
        chargingPower: s.battery_charging_power_kw ?? 0,
        dischargingPower: s.battery_discharge_power_kw ?? 0,
        temp: s.climate_outdoor_temp ?? 0,
        chargeSessions: s.battery_is_charging ? 1 : 0,
        sampleCount: 1,
      }))
    }
    const fromStr = toDateStr(customFrom.value)
    const toStr = toDateStr(customTo.value)
    return allData.value.filter(d => d.rawDate && d.rawDate >= fromStr && d.rawDate <= toStr)
  }
  // Default: today snapshots
  return todaySnapshots.value
})

const tableData = computed(() => [...data.value].reverse())

// ---------------------------------------------------------------------------
// KPI Cards
// ---------------------------------------------------------------------------
const kpiCards = computed(() => {
  const snaps = filteredSnapshots.value
  if (!snaps.length) return []

  // Segment-based energy calculation to avoid noise amplification from rapid polling.
  // We split snapshots into contiguous charging/non-charging segments and use NET
  // energy change per segment, so measurement oscillations cancel out.
  let energyUsed = 0    // net decrease during non-charging segments
  let energyCharged = 0 // net increase during charging/plugged segments
  let regenEnergy = 0   // regen recovered during non-charging segments

  let i = 0
  while (i < snaps.length) {
    const isChargingSegment = !!(snaps[i].battery_is_charging || snaps[i].vehicle_is_plugged)
    let j = i + 1
    while (j < snaps.length && !!(snaps[j].battery_is_charging || snaps[j].vehicle_is_plugged) === isChargingSegment) {
      j++
    }
    // Segment from index i to j-1
    const startE = (snaps[i].battery_dump_energy ?? 0) / 1000
    const endE = (snaps[j - 1].battery_dump_energy ?? 0) / 1000
    const segDelta = endE - startE

    if (isChargingSegment) {
      if (segDelta > 0) energyCharged += segDelta
    } else {
      if (segDelta < 0) energyUsed += Math.abs(segDelta)
      // Within non-charging segments, sum valid positive deltas as regen.
      // Skip zero-energy readings (data gaps from sleep) to avoid false positives.
      for (let k = i + 1; k < j; k++) {
        const prevE = (snaps[k - 1].battery_dump_energy ?? 0) / 1000
        const currE = (snaps[k].battery_dump_energy ?? 0) / 1000
        if (prevE > 0 && currE > 0 && currE > prevE) {
          regenEnergy += currE - prevE
        }
      }
    }
    i = j
  }

  const mileages = snaps.map(s => s.drive_total_mileage).filter(m => m != null && m > 0)
  const totalKm = mileages.length >= 2 ? Math.max(0, mileages[mileages.length - 1] - mileages[0]) : 0

  const consumption = totalKm > 0 ? (energyUsed / totalKm) * 100 : 0

  let chargeSessions = 0
  for (let i = 1; i < snaps.length; i++) {
    if (snaps[i - 1].battery_is_charging && !snaps[i].battery_is_charging) chargeSessions++
  }
  if (snaps.length > 0 && snaps[snaps.length - 1].battery_is_charging) chargeSessions++

  const costPerKwh = electricityPriceKwh.value
  // Use per-session costs if available, otherwise flat rate
  const sessionCostTotal = sessionCosts.value.reduce((sum, sc) => sum + (sc.cost || 0), 0)
  const cost = sessionCostTotal > 0 ? sessionCostTotal : energyCharged * costPerKwh

  const co2Saved = totalKm * 0.12

  const regenEfficiency = energyUsed > 0 ? (regenEnergy / energyUsed) * 100 : 0

  const highSocSnaps = snaps.filter(s => (s.battery_soc ?? 0) >= 95 && s.battery_expected_mileage)
  const avgRangeAtFull = highSocSnaps.length > 0
    ? Math.round(highSocSnaps.reduce((s, x) => s + x.battery_expected_mileage, 0) / highSocSnaps.length)
    : null

  const batteryCapacityKwh = snaps[0]?.battery_dump_energy ? (snaps[0].battery_dump_energy / 1000) / ((snaps[0].battery_soc ?? 100) / 100) : null
  const realAutonomy = consumption > 0 && batteryCapacityKwh ? Math.round((batteryCapacityKwh / consumption) * 100) : null

  const cards = [
    { label: 'km driven', value: Math.round(totalKm).toLocaleString(), color: '#00d4ff' },
    { label: 'Energy used', value: `${energyUsed.toFixed(1)} kWh`, color: '#ffab40' },
    { label: 'Total charged', value: `${(energyCharged + regenEnergy).toFixed(1)} kWh`, color: '#00e676' },
    { label: 'Charged (grid)', value: `${energyCharged.toFixed(1)} kWh`, color: '#66bb6a' },
    { label: 'Regen energy', value: `${regenEnergy.toFixed(1)} kWh`, color: '#26c6da' },
    { label: 'Charge sessions', value: chargeSessions, color: '#7c6aff' },
    { label: 'kWh/100km', value: consumption > 0 ? consumption.toFixed(1) : '\u2014', color: '#ff7043' },
    { label: 'Cost (\u20ac)', value: cost > 0 ? `\u20ac${cost.toFixed(2)}` : '\u2014', color: '#ffd54f' },
    { label: 'CO\u2082 saved', value: co2Saved > 0 ? `${co2Saved.toFixed(1)} kg` : '\u2014', color: '#4caf50' },
    { label: 'Regen efficiency', value: regenEfficiency > 0 ? `${regenEfficiency.toFixed(0)}%` : '\u2014', color: '#26c6da' },
    { label: 'Range @100%', value: avgRangeAtFull ? `${avgRangeAtFull} km` : '\u2014', color: '#ab47bc' },
    { label: 'Real autonomy', value: realAutonomy ? `${realAutonomy} km` : '\u2014', color: '#5c6bc0' },
  ]
  return cards
})

// ---------------------------------------------------------------------------
// Heatmap data (7 days x 24 hours)
// ---------------------------------------------------------------------------
const heatmapData = computed(() => {
  const grid = Array.from({ length: 7 }, () => Array(24).fill(0))
  for (const s of filteredSnapshots.value) {
    if (s.drive_is_parked === false) {
      const d = new Date(s.timestamp + 'Z')
      const dow = (d.getDay() + 6) % 7
      const hour = d.getHours()
      grid[dow][hour]++
    }
  }
  return grid
})

function heatmapColor(val) {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light'
  if (val === 0) return isLight ? '#eaf4ef' : '#1a1f2e'
  if (val === 1) return isLight ? '#b2dfdb' : '#1b3a2a'
  if (val <= 3) return isLight ? '#66bb6a' : '#2e7d52'
  if (val <= 6) return isLight ? '#43a047' : '#43a047'
  return isLight ? '#2e7d32' : '#66bb6a'
}

// ---------------------------------------------------------------------------
// Charge sessions data
// ---------------------------------------------------------------------------
const chargeSessionsData = computed(() => {
  const snaps = filteredSnapshots.value
  const sessions = []
  let inSession = false
  let sessionStart = 0
  for (let i = 0; i < snaps.length; i++) {
    if (snaps[i].battery_is_charging && !inSession) {
      inSession = true
      sessionStart = i
    } else if (!snaps[i].battery_is_charging && inSession) {
      inSession = false
      const startEnergy = (snaps[sessionStart].battery_dump_energy ?? 0) / 1000
      const endEnergy = (snaps[i].battery_dump_energy ?? 0) / 1000
      const energyAdded = endEnergy - startEnergy
      if (energyAdded > 0) {
        const startTs = snaps[sessionStart].timestamp
        const matchedCost = sessionCosts.value.find(sc => sc.start_ts && Math.abs(new Date(sc.start_ts) - new Date(startTs)) < 120000)
        sessions.push({
          label: formatTimestamp(startTs),
          energy: Math.round(energyAdded * 10) / 10,
          startSoc: snaps[sessionStart].battery_soc ?? 0,
          endSoc: snaps[i].battery_soc ?? 0,
          tierLabel: matchedCost?.tier_label || null,
          cost: matchedCost?.cost || null,
        })
      }
    }
  }
  if (inSession && snaps.length > 0) {
    const startEnergy = (snaps[sessionStart].battery_dump_energy ?? 0) / 1000
    const endEnergy = (snaps[snaps.length - 1].battery_dump_energy ?? 0) / 1000
    const energyAdded = endEnergy - startEnergy
    if (energyAdded > 0) {
      const startTs = snaps[sessionStart].timestamp
      const matchedCost = sessionCosts.value.find(sc => sc.start_ts && Math.abs(new Date(sc.start_ts) - new Date(startTs)) < 120000)
      sessions.push({
        label: formatTimestamp(startTs) + ' (ongoing)',
        energy: Math.round(energyAdded * 10) / 10,
        startSoc: snaps[sessionStart].battery_soc ?? 0,
        endSoc: snaps[snaps.length - 1].battery_soc ?? 0,
        tierLabel: matchedCost?.tier_label || null,
        cost: matchedCost?.cost || null,
      })
    }
  }
  return sessions
})

// ---------------------------------------------------------------------------
// Vampire drain data
// ---------------------------------------------------------------------------
const vampireDrainData = computed(() => {
  const snaps = filteredSnapshots.value
  const drains = []
  let parkedStart = -1
  for (let i = 0; i < snaps.length; i++) {
    if (snaps[i].drive_is_parked && !snaps[i].battery_is_charging) {
      if (parkedStart === -1) parkedStart = i
    } else {
      if (parkedStart !== -1 && i - parkedStart >= 2) {
        const startSoc = snaps[parkedStart].battery_soc ?? 0
        const endSoc = snaps[i - 1].battery_soc ?? 0
        const loss = startSoc - endSoc
        const hours = (new Date(snaps[i - 1].timestamp + 'Z') - new Date(snaps[parkedStart].timestamp + 'Z')) / 3600000
        if (hours >= 1 && loss > 0) {
          drains.push({
            label: formatTimestamp(snaps[parkedStart].timestamp),
            loss,
            hours: Math.round(hours * 10) / 10,
            lossPerDay: Math.round((loss / hours) * 24 * 10) / 10,
          })
        }
      }
      parkedStart = -1
    }
  }
  return drains
})

// ---------------------------------------------------------------------------
// Chart refs
// ---------------------------------------------------------------------------
const batteryCanvas = ref(null)
const rangeCanvas = ref(null)
const kmCanvas = ref(null)
const powerCanvas = ref(null)
const tempCanvas = ref(null)
const consumptionCanvas = ref(null)
const effTempCanvas = ref(null)
const effSpeedCanvas = ref(null)
const realVsEstCanvas = ref(null)
const chargeSessionCanvas = ref(null)
const usagePieCanvas = ref(null)
const tripMapContainer = ref(null)
const mapExpanded = ref(false)
const vampireCanvas = ref(null)
const tirePressureCanvas = ref(null)
const tireTempCanvas = ref(null)
const tireDiffCanvas = ref(null)

const charts = []
let tripMap = null

function getMapTileUrl() {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
  return isDark
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
}

function toggleMapExpand() {
  mapExpanded.value = !mapExpanded.value
  nextTick(() => {
    if (tripMap) tripMap.invalidateSize()
  })
}

function renderTripMap(points) {
  if (tripMap) {
    tripMap.remove()
    tripMap = null
  }
  const container = tripMapContainer.value
  if (!container || points.length === 0) return

  tripMap = L.map(container, { zoomControl: true, attributionControl: false })
  L.tileLayer(getMapTileUrl(), { maxZoom: 18 }).addTo(tripMap)

  const coords = points.map(s => [s.vehicle_latitude, s.vehicle_longitude])

  // Draw polyline segments colored by speed
  for (let i = 1; i < coords.length; i++) {
    const speed = points[i].drive_speed ?? 0
    const color = speed > 80 ? '#ef5350' : speed > 40 ? '#ffab40' : '#66bb6a'
    L.polyline([coords[i - 1], coords[i]], { color, weight: 3, opacity: 0.8 }).addTo(tripMap)
  }

  // Speed markers on each point
  for (let i = 0; i < coords.length; i++) {
    const speed = points[i].drive_speed ?? 0
    const time = points[i].timestamp ? new Date(points[i].timestamp + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
    L.circleMarker(coords[i], {
      radius: 4,
      color: speed > 80 ? '#ef5350' : speed > 40 ? '#ffab40' : '#66bb6a',
      fillColor: speed > 80 ? '#ef5350' : speed > 40 ? '#ffab40' : '#66bb6a',
      fillOpacity: 0.7,
      weight: 1,
    }).bindTooltip(`${speed} km/h${time ? ' — ' + time : ''}`, { direction: 'top', offset: [0, -6] }).addTo(tripMap)
  }

  // Start / end markers (larger)
  L.circleMarker(coords[0], { radius: 8, color: '#fff', fillColor: '#66bb6a', fillOpacity: 1, weight: 2 })
    .bindTooltip('Start', { permanent: false })
    .addTo(tripMap)
  L.circleMarker(coords[coords.length - 1], { radius: 8, color: '#fff', fillColor: '#ef5350', fillOpacity: 1, weight: 2 })
    .bindTooltip('End', { permanent: false })
    .addTo(tripMap)

  // Fit bounds
  const bounds = L.latLngBounds(coords)
  tripMap.fitBounds(bounds, { padding: [20, 20] })
}

function getChartColors() {
  const s = getComputedStyle(document.documentElement)
  return {
    grid: s.getPropertyValue('--chart-grid').trim() || '#1c2135',
    tick: s.getPropertyValue('--chart-tick').trim() || '#4a5468',
    tooltipBg: s.getPropertyValue('--tooltip-bg').trim() || '#161b2a',
    tooltipBorder: s.getPropertyValue('--tooltip-border').trim() || '#1c2240',
    text: s.getPropertyValue('--text').trim() || '#e2e6f0',
    sub: s.getPropertyValue('--sub').trim() || '#8892a8',
    label: s.getPropertyValue('--label').trim() || '#6a748a',
  }
}

const chartDefaults = computed(() => {
  const c = getChartColors()
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: c.tooltipBg,
        titleColor: c.sub,
        bodyColor: c.text,
        borderColor: c.tooltipBorder,
        borderWidth: 1,
        padding: 10,
      },
    },
    scales: {
      x: { grid: { color: c.grid, drawTicks: false }, ticks: { color: c.tick, font: { size: 10 }, maxTicksLimit: 8 } },
      y: { grid: { color: c.grid, drawTicks: false }, ticks: { color: c.tick, font: { size: 10 } } },
    },
  }
})

function destroyCharts() {
  charts.forEach(c => c.destroy())
  charts.length = 0
  if (tripMap) {
    tripMap.remove()
    tripMap = null
  }
}

function buildCharts() {
  destroyCharts()
  const d = data.value
  if (!d.length) return

  const labels = d.map(x => x.date)
  const pointR = d.length <= 5 ? 4 : 0
  const snaps = filteredSnapshots.value

  // ===== CORE CHARTS =====

  // Battery
  if (batteryCanvas.value) {
    const chargeLines = []
    for (let i = 0; i < d.length; i++) {
      const prev = i > 0 ? d[i - 1].chargeSessions > 0 : false
      const curr = d[i].chargeSessions > 0
      if (curr && !prev) chargeLines.push({ index: i, type: 'start' })
      if (!curr && prev) chargeLines.push({ index: i, type: 'end' })
    }
    const chargeLinesPlugin = {
      id: 'chargeLinesPlugin',
      afterDraw(chart) {
        const { ctx, chartArea, scales } = chart
        const xScale = scales.x
        for (const line of chargeLines) {
          const x = xScale.getPixelForValue(line.index)
          ctx.save()
          ctx.beginPath()
          ctx.setLineDash([4, 3])
          ctx.lineWidth = 1.5
          ctx.strokeStyle = line.type === 'start' ? '#66bb6a' : '#ef5350'
          ctx.moveTo(x, chartArea.top)
          ctx.lineTo(x, chartArea.bottom)
          ctx.stroke()
          ctx.restore()
        }
      },
    }
    charts.push(new Chart(batteryCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'SOC', data: d.map(x => x.battery), borderColor: '#00e676', backgroundColor: 'rgba(0,230,118,0.08)', fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2, yAxisID: 'y' },
          { label: 'Energy (kWh)', data: d.map(x => x.batteryEnergy), borderColor: '#ffab40', backgroundColor: 'transparent', tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 1.5, borderDash: [4, 3], yAxisID: 'y2' },
        ],
      },
      options: {
        ...chartDefaults.value,
        plugins: { ...chartDefaults.value.plugins, legend: { display: true, labels: { color: getChartColors().label, font: { size: 10 }, boxWidth: 20 } } },
        scales: {
          ...chartDefaults.value.scales,
          y: { ...chartDefaults.value.scales.y, min: 0, max: 100, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v}%` } },
          y2: { position: 'right', grid: { display: false }, ticks: { color: getChartColors().tick, font: { size: 10 }, callback: v => `${v} kWh` } },
        },
      },
      plugins: [chargeLinesPlugin],
    }))
  }

  // Range
  if (rangeCanvas.value) {
    charts.push(new Chart(rangeCanvas.value, {
      type: 'line',
      data: { labels, datasets: [{ data: d.map(x => x.range), borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.07)', fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2 }] },
      options: { ...chartDefaults.value, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Km
  if (kmCanvas.value) {
    charts.push(new Chart(kmCanvas.value, {
      type: 'bar',
      data: { labels, datasets: [{ data: d.map(x => x.kmDriven), backgroundColor: 'rgba(124,106,255,0.45)', borderColor: '#7c6aff', borderWidth: 1, borderRadius: 4 }] },
      options: { ...chartDefaults.value, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Power (uses filteredSnapshots for actual power data)
  if (powerCanvas.value) {
    const powerSnaps = snaps.filter(s => s.battery_charging_power_kw != null || s.battery_discharge_power_kw != null)
    if (powerSnaps.length > 0) {
      const powerLabels = powerSnaps.map(s => {
        const dt = new Date(s.timestamp + 'Z')
        return isToday.value ? dt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : dt.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
      })
      const powerPointR = powerSnaps.length <= 5 ? 4 : 0
      charts.push(new Chart(powerCanvas.value, {
        type: 'line',
        data: {
          labels: powerLabels,
          datasets: [
            { label: 'Charging', data: powerSnaps.map(s => s.battery_charging_power_kw ?? 0), borderColor: '#66bb6a', backgroundColor: 'rgba(102,187,106,0.08)', fill: true, tension: 0.3, pointRadius: powerPointR, pointHoverRadius: 5, borderWidth: 2 },
            { label: 'Discharging', data: powerSnaps.map(s => -(s.battery_discharge_power_kw ?? 0)), borderColor: '#ef5350', backgroundColor: 'rgba(239,83,80,0.08)', fill: true, tension: 0.3, pointRadius: powerPointR, pointHoverRadius: 5, borderWidth: 2 },
          ],
        },
        options: { ...chartDefaults.value, plugins: { ...chartDefaults.value.plugins, legend: { display: true, labels: { color: getChartColors().label, font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} kW` } } } },
      }))
    }
  }

  // ===== EFFICIENCY & CONSUMPTION =====

  if (consumptionCanvas.value && snaps.length >= 2) {
    const consumptionData = []
    const consumptionLabels = []
    for (let i = 1; i < snaps.length; i++) {
      const km = (snaps[i].drive_total_mileage ?? 0) - (snaps[i - 1].drive_total_mileage ?? 0)
      const energy = ((snaps[i - 1].battery_dump_energy ?? 0) - (snaps[i].battery_dump_energy ?? 0)) / 1000
      if (km > 0 && energy > 0) {
        consumptionData.push(Math.round((energy / km) * 1000) / 10)
        consumptionLabels.push(formatTimestamp(snaps[i].timestamp))
      }
    }
    if (consumptionData.length > 0) {
      charts.push(new Chart(consumptionCanvas.value, {
        type: 'line',
        data: { labels: consumptionLabels, datasets: [{ data: consumptionData, borderColor: '#ff7043', backgroundColor: 'rgba(255,112,67,0.08)', fill: true, tension: 0.3, pointRadius: consumptionData.length <= 10 ? 4 : 0, pointHoverRadius: 5, borderWidth: 2 }] },
        options: { ...chartDefaults.value, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, min: 0, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v}` } } } },
      }))
    }
  }

  // Efficiency vs Temperature (scatter)
  if (effTempCanvas.value && snaps.length >= 2) {
    const points = []
    for (let i = 1; i < snaps.length; i++) {
      const km = (snaps[i].drive_total_mileage ?? 0) - (snaps[i - 1].drive_total_mileage ?? 0)
      const energy = ((snaps[i - 1].battery_dump_energy ?? 0) - (snaps[i].battery_dump_energy ?? 0)) / 1000
      const temp = snaps[i].climate_outdoor_temp
      if (km > 0 && energy > 0 && temp != null) {
        points.push({ x: temp, y: Math.round((energy / km) * 1000) / 10 })
      }
    }
    if (points.length > 0) {
      charts.push(new Chart(effTempCanvas.value, {
        type: 'scatter',
        data: { datasets: [{ data: points, backgroundColor: '#ff7043', borderColor: '#ff7043', pointRadius: 5, pointHoverRadius: 7 }] },
        options: { ...chartDefaults.value, scales: { x: { ...chartDefaults.value.scales.x, title: { display: true, text: '\u00b0C', color: getChartColors().tick } }, y: { ...chartDefaults.value.scales.y, min: 0, title: { display: true, text: 'kWh/100km', color: getChartColors().tick } } } },
      }))
    }
  }

  // Efficiency vs Speed (scatter)
  if (effSpeedCanvas.value && snaps.length >= 2) {
    const points = []
    for (let i = 1; i < snaps.length; i++) {
      const km = (snaps[i].drive_total_mileage ?? 0) - (snaps[i - 1].drive_total_mileage ?? 0)
      const energy = ((snaps[i - 1].battery_dump_energy ?? 0) - (snaps[i].battery_dump_energy ?? 0)) / 1000
      const speed = snaps[i].drive_speed
      if (km > 0 && energy > 0 && speed != null && speed > 0) {
        points.push({ x: speed, y: Math.round((energy / km) * 1000) / 10 })
      }
    }
    if (points.length > 0) {
      charts.push(new Chart(effSpeedCanvas.value, {
        type: 'scatter',
        data: { datasets: [{ data: points, backgroundColor: '#7c6aff', borderColor: '#7c6aff', pointRadius: 5, pointHoverRadius: 7 }] },
        options: { ...chartDefaults.value, scales: { x: { ...chartDefaults.value.scales.x, title: { display: true, text: 'km/h', color: getChartColors().tick } }, y: { ...chartDefaults.value.scales.y, min: 0, title: { display: true, text: 'kWh/100km', color: getChartColors().tick } } } },
      }))
    }
  }

  // Real vs Estimated range
  if (realVsEstCanvas.value && snaps.length >= 2) {
    const realLabels = []
    const estimated = []
    const actual = []
    const dayMap = {}
    for (const s of snaps) {
      const day = s.timestamp.split('T')[0]
      if (!dayMap[day]) dayMap[day] = []
      dayMap[day].push(s)
    }
    for (const [day, daySnaps] of Object.entries(dayMap)) {
      if (daySnaps.length < 2) continue
      const estRange = daySnaps[0].battery_expected_mileage
      const mileages = daySnaps.map(s => s.drive_total_mileage).filter(m => m != null)
      const kmDriven = mileages.length >= 2 ? mileages[mileages.length - 1] - mileages[0] : 0
      if (estRange && kmDriven > 0) {
        realLabels.push(formatDate(day))
        estimated.push(estRange)
        actual.push(kmDriven)
      }
    }
    if (realLabels.length > 0) {
      charts.push(new Chart(realVsEstCanvas.value, {
        type: 'bar',
        data: {
          labels: realLabels,
          datasets: [
            { label: 'Estimated range', data: estimated, backgroundColor: 'rgba(0,212,255,0.4)', borderColor: '#00d4ff', borderWidth: 1, borderRadius: 4 },
            { label: 'Actual km driven', data: actual, backgroundColor: 'rgba(124,106,255,0.4)', borderColor: '#7c6aff', borderWidth: 1, borderRadius: 4 },
          ],
        },
        options: { ...chartDefaults.value, plugins: { ...chartDefaults.value.plugins, legend: { display: true, labels: { color: getChartColors().label, font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} km` } } } },
      }))
    }
  }

  // ===== CHARGE SESSIONS =====
  if (chargeSessionCanvas.value) {
    const sessions = chargeSessionsData.value
    if (sessions.length > 0) {
      charts.push(new Chart(chargeSessionCanvas.value, {
        type: 'bar',
        data: {
          labels: sessions.map(s => s.label),
          datasets: [{
            label: 'Energy charged (kWh)',
            data: sessions.map(s => s.energy),
            backgroundColor: 'rgba(102,187,106,0.5)',
            borderColor: '#66bb6a',
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          ...chartDefaults.value,
          plugins: {
            ...chartDefaults.value.plugins,
            tooltip: {
              ...chartDefaults.value.plugins.tooltip,
              callbacks: { afterLabel: (ctx) => { const s = sessions[ctx.dataIndex]; return `SOC: ${s.startSoc}% \u2192 ${s.endSoc}%` } },
            },
          },
          scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} kWh` } } },
        },
      }))
    }
  }

  // ===== VEHICLE USAGE =====

  // Usage pie
  if (usagePieCanvas.value && snaps.length > 0) {
    const parked = snaps.filter(s => s.drive_is_parked === true).length
    const driving = snaps.length - parked
    const parkedPct = Math.round((parked / snaps.length) * 100)
    const drivingPct = 100 - parkedPct
    charts.push(new Chart(usagePieCanvas.value, {
      type: 'doughnut',
      data: {
        labels: [`Parked`, `In use`],
        datasets: [{ data: [parkedPct, drivingPct], backgroundColor: [getChartColors().grid, '#00d4ff'], borderColor: [getChartColors().tick, '#00d4ff'], borderWidth: 1 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'bottom', labels: { color: getChartColors().label, font: { size: 11 } } },
          tooltip: {
            ...chartDefaults.value.plugins.tooltip,
            callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.raw}%` }
          },
        },
      },
    }))
  }

  // Trip map (Leaflet)
  if (tripMapContainer.value) {
    const mapPoints = snaps.filter(s => s.vehicle_latitude && s.vehicle_longitude)
    if (mapPoints.length > 0) {
      renderTripMap(mapPoints)
    }
  }

  // Vampire drain
  if (vampireCanvas.value) {
    const drains = vampireDrainData.value
    if (drains.length > 0) {
      charts.push(new Chart(vampireCanvas.value, {
        type: 'bar',
        data: {
          labels: drains.map(d => `${d.label} (${d.hours}h)`),
          datasets: [{
            label: 'SOC loss %/day',
            data: drains.map(d => d.lossPerDay),
            backgroundColor: 'rgba(239,83,80,0.4)',
            borderColor: '#ef5350',
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: { ...chartDefaults.value, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v}%/day` } } } },
      }))
    }
  }

  // ===== TIRE PRESSURE =====

  if (tirePressureCanvas.value) {
    const tireSnaps = snaps.filter(s => s.tire_front_left_pressure != null)
    if (tireSnaps.length > 0) {
      const tireLabels = tireSnaps.map(s => formatTimestamp(s.timestamp))
      const toBar = v => v != null ? Math.round(v / 100 * 100) / 100 : null
      charts.push(new Chart(tirePressureCanvas.value, {
        type: 'line',
        data: {
          labels: tireLabels,
          datasets: [
            { label: 'FL', data: tireSnaps.map(s => toBar(s.tire_front_left_pressure)), borderColor: '#00d4ff', borderWidth: 2, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
            { label: 'FR', data: tireSnaps.map(s => toBar(s.tire_front_right_pressure)), borderColor: '#7c6aff', borderWidth: 2, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
            { label: 'RL', data: tireSnaps.map(s => toBar(s.tire_rear_left_pressure)), borderColor: '#ffab40', borderWidth: 2, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
            { label: 'RR', data: tireSnaps.map(s => toBar(s.tire_rear_right_pressure)), borderColor: '#ff7043', borderWidth: 2, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
          ],
        },
        options: { ...chartDefaults.value, plugins: { ...chartDefaults.value.plugins, legend: { display: true, labels: { color: getChartColors().label, font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} bar` } } } },
      }))
    }
  }

  // Pressure vs Temperature (scatter)
  if (tireTempCanvas.value) {
    const points = snaps
      .filter(s => s.tire_front_left_pressure != null && s.climate_outdoor_temp != null)
      .map(s => ({
        x: s.climate_outdoor_temp,
        y: ((s.tire_front_left_pressure ?? 0) + (s.tire_front_right_pressure ?? 0) + (s.tire_rear_left_pressure ?? 0) + (s.tire_rear_right_pressure ?? 0)) / 400,
      }))
    if (points.length > 0) {
      charts.push(new Chart(tireTempCanvas.value, {
        type: 'scatter',
        data: { datasets: [{ data: points, backgroundColor: '#26c6da', borderColor: '#26c6da', pointRadius: 5, pointHoverRadius: 7 }] },
        options: { ...chartDefaults.value, scales: { x: { ...chartDefaults.value.scales.x, title: { display: true, text: '\u00b0C', color: getChartColors().tick } }, y: { ...chartDefaults.value.scales.y, title: { display: true, text: 'Avg pressure (bar)', color: getChartColors().tick } } } },
      }))
    }
  }

  // L/R pressure difference
  if (tireDiffCanvas.value) {
    const tireSnaps = snaps.filter(s => s.tire_front_left_pressure != null)
    if (tireSnaps.length > 0) {
      const tireLabels = tireSnaps.map(s => formatTimestamp(s.timestamp))
      const toBar = v => v != null ? v / 100 : 0
      charts.push(new Chart(tireDiffCanvas.value, {
        type: 'line',
        data: {
          labels: tireLabels,
          datasets: [
            { label: 'Front (L-R)', data: tireSnaps.map(s => Math.round((toBar(s.tire_front_left_pressure) - toBar(s.tire_front_right_pressure)) * 100) / 100), borderColor: '#00d4ff', borderWidth: 2, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
            { label: 'Rear (L-R)', data: tireSnaps.map(s => Math.round((toBar(s.tire_rear_left_pressure) - toBar(s.tire_rear_right_pressure)) * 100) / 100), borderColor: '#ffab40', borderWidth: 2, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
          ],
        },
        options: { ...chartDefaults.value, plugins: { ...chartDefaults.value.plugins, legend: { display: true, labels: { color: getChartColors().label, font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v} bar` } } } },
      }))
    }
  }

  // Temp vs Energy
  if (tempCanvas.value) {
    charts.push(new Chart(tempCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Temperature', data: d.map(x => x.temp), borderColor: '#ff7043', backgroundColor: 'rgba(255,112,67,0.06)', fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2 },
          { label: 'Battery energy', data: d.map(x => x.batteryEnergy), borderColor: '#ffab40', backgroundColor: 'transparent', tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 1.5, borderDash: [4, 3], yAxisID: 'y2' },
        ],
      },
      options: {
        ...chartDefaults.value,
        plugins: { ...chartDefaults.value.plugins, legend: { display: true, labels: { color: getChartColors().label, font: { size: 10 }, boxWidth: 20 } } },
        scales: { ...chartDefaults.value.scales, y: { ...chartDefaults.value.scales.y, ticks: { ...chartDefaults.value.scales.y.ticks, callback: v => `${v}\u00b0C` } }, y2: { position: 'right', grid: { display: false }, ticks: { color: getChartColors().tick, font: { size: 10 }, callback: v => `${v}kWh` } } },
      },
    }))
  }
}

watch(data, () => { if (viewMode.value === 'chart' && chartsReady.value) nextTick(buildCharts) })
watch(filteredSnapshots, () => { if (viewMode.value === 'chart' && chartsReady.value) nextTick(buildCharts) })
watch(viewMode, (v) => { if (v === 'chart' && chartsReady.value) nextTick(buildCharts) })
watch(chartsReady, (v) => { if (v && viewMode.value === 'chart') nextTick(buildCharts) })
onMounted(() => { if (chartsReady.value) nextTick(buildCharts) })
onBeforeUnmount(destroyCharts)
</script>

<style scoped>
.history-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Stale indicator */
.stale-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
  padding: 6px 12px;
  background: var(--btn-bg);
  border-radius: 8px;
  width: fit-content;
  margin: 0 auto;
}
.stale-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ffab40;
  animation: blink 1.2s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Fade transition */
.fade-enter-active { transition: opacity 0.3s ease; }
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.history-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.header-title { flex: 1; min-width: 0; }
.source-toggle { order: 0; }
.history-header .time-toolbar {
  width: 100%;
  justify-content: center;
}
@media (min-width: 640px) {
  .history-header {
    flex-wrap: nowrap;
    justify-content: space-between;
  }
  .header-title { flex: 0 0 auto; }
  .source-toggle { order: 2; }
  .history-header .time-toolbar {
    order: 1;
    flex: 0 1 auto;
    width: auto;
    justify-content: center;
  }
}
.source-toggle { display: flex; gap: 2px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 3px; }
.source-btn { display: flex; align-items: center; gap: 5px; padding: 6px 14px; border-radius: 7px; border: none; cursor: pointer; font-size: 12px; font-weight: 600; background: transparent; color: var(--muted); transition: all 0.2s; }
.source-btn.active { background: var(--btn-bg); color: #00d4ff; }
.source-btn:hover:not(.active) { color: var(--text); }
.history-header h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}
.history-header p {
  font-size: 12px;
  color: var(--muted);
  margin-top: 3px;
}
.time-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 5px 12px;
}
.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s;
}
.toolbar-btn:hover:not(:disabled) {
  background: var(--btn-bg);
  color: #00d4ff;
}
.toolbar-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.toolbar-date-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  flex: 1;
  text-align: center;
  padding: 0 16px;
}
.toolbar-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.toolbar-pill {
  padding: 5px 12px;
  border-radius: 14px;
  border: 1.5px solid #00b8d4;
  background: transparent;
  color: #00d4ff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.toolbar-pill:hover {
  background: rgba(0, 184, 212, 0.12);
}
.toolbar-menu-wrapper {
  position: relative;
}
.toolbar-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 99;
}
.toolbar-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  min-width: 160px;
  z-index: 100;
  padding: 6px;
  overflow: hidden;
}
.toolbar-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  border-radius: 7px;
  transition: background 0.15s;
  white-space: nowrap;
}
.toolbar-menu-item:hover {
  background: var(--btn-bg);
  color: #00d4ff;
}

/* Date picker overlay & dropdown */
.date-picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(0,0,0,0.4);
}
.date-picker-dropdown {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1000;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: row;
  overflow: hidden;
  max-width: 95vw;
}
.date-picker-presets {
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  border-right: 1px solid var(--border);
  min-width: 160px;
  overflow-y: auto;
  max-height: 380px;
}
.preset-btn {
  padding: 10px 20px;
  text-align: left;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.preset-btn:hover {
  background: var(--btn-bg);
  color: #00d4ff;
}
.date-picker-calendar {
  padding: 16px 20px 60px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.calendar-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.cal-nav-btn {
  background: transparent;
  border: none;
  color: var(--text);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: background 0.15s;
  display: flex;
  align-items: center;
}
.cal-nav-btn:hover {
  background: var(--btn-bg);
}
.cal-month-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  text-transform: capitalize;
}
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  text-align: center;
}
.cal-weekday {
  font-size: 11px;
  color: var(--muted);
  font-weight: 600;
  padding: 4px 0;
}
.cal-day {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 12px;
  cursor: pointer;
  color: var(--text);
  transition: all 0.15s;
}
.cal-day.other-month {
  color: var(--muted);
  opacity: 0.4;
}
.cal-day.today {
  border: 2px solid #00b8d4;
}
.cal-day.selected {
  background: #00b8d4;
  color: #fff;
  font-weight: 700;
}
.cal-day.in-range {
  background: rgba(0, 184, 212, 0.2);
  border-radius: 4px;
}
.cal-day:hover:not(.other-month) {
  background: var(--btn-bg);
}
.calendar-footer {
  text-align: center;
}
.cal-range-label {
  font-size: 11px;
  color: var(--muted);
}
.date-picker-actions {
  position: absolute;
  bottom: 0;
  right: 0;
  left: 0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  background: var(--card);
  border-radius: 0 0 14px 14px;
}
.dp-cancel {
  padding: 8px 18px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.dp-cancel:hover {
  color: var(--text);
}
.dp-select {
  padding: 8px 18px;
  border-radius: 8px;
  border: none;
  background: #00b8d4;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dp-select:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.dp-select:hover:not(:disabled) {
  background: #00a0b8;
}
.dp-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: dp-spin 0.6s linear infinite;
}
@keyframes dp-spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 520px) {
  .date-picker-dropdown {
    flex-direction: column;
    max-height: 90vh;
  }
  .date-picker-presets {
    flex-direction: row;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 1px solid var(--border);
    min-width: unset;
    max-height: 120px;
    padding: 10px;
    gap: 4px;
  }
  .preset-btn {
    padding: 6px 12px;
    font-size: 11px;
    border-radius: 6px;
    background: var(--btn-bg);
  }
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--heading);
  margin: 8px 0 -4px 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
@media (min-width: 768px) {
  .summary-grid { grid-template-columns: repeat(5, 1fr); }
}
.summary-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  text-align: center;
}
.summary-value { font-size: 20px; font-weight: 700; }
.summary-label { font-size: 10px; color: var(--muted); margin-top: 4px; }

.charts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
@media (min-width: 768px) {
  .charts-grid { grid-template-columns: 1fr 1fr; }
}
.chart-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
}
@media (min-width: 768px) {
  .chart-card.wide { grid-column: span 2; }
}
.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 13px;
  font-weight: 700;
  color: var(--heading);
}
.chart-icon { font-size: 14px; }
.chart-area { height: 180px; }
.chart-area.tall { height: 200px; }
.chart-area.map-area { height: 280px; z-index: 0; border-radius: 8px; overflow: hidden; }
.chart-area.map-area-expanded { height: 70vh; }
.map-expanded {
  grid-column: 1 / -1;
}
.map-expand-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: color 0.2s, background 0.2s;
}
.map-expand-btn:hover {
  color: var(--text);
  background: var(--border);
}
.chart-empty-msg {
  padding: 1.5rem 1rem;
  font-size: 0.82rem;
  color: var(--text-secondary, #888);
  text-align: center;
  line-height: 1.5;
}

.chart-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 8px;
  font-size: 10px;
  color: var(--muted);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.legend-line {
  display: inline-block;
  width: 18px;
  height: 0;
  border-top: 2px dashed;
}
.legend-line.start { border-color: #66bb6a; }
.legend-line.end { border-color: #ef5350; }

/* Heatmap */
.heatmap-container {
  padding: 8px 0;
}
.heatmap-row {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-bottom: 2px;
}
.heatmap-day {
  width: 28px;
  font-size: 9px;
  color: var(--muted);
  text-align: right;
  margin-right: 4px;
}
.heatmap-cell {
  flex: 1;
  height: 16px;
  border-radius: 3px;
  min-width: 8px;
}
.heatmap-hours {
  display: flex;
  justify-content: space-between;
  padding-left: 34px;
  font-size: 8px;
  color: var(--muted2);
  margin-top: 4px;
}

.history-note {
  font-size: 11px;
  color: var(--muted2);
  text-align: center;
  padding: 8px;
  background: var(--elevated);
  border-radius: 8px;
}

/* View toggle */
.view-toggle {
  display: flex;
  gap: 4px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px;
}
.view-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 7px;
  border: none;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  background: transparent;
  color: var(--muted);
  transition: all 0.2s;
}
.view-btn.active {
  background: var(--btn-bg);
  color: #00d4ff;
}

/* Data table */
.data-table-wrapper {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
}
.data-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.data-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
}
.data-table th {
  background: var(--elevated);
  padding: 10px 14px;
  text-align: left;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted3);
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 9px 14px;
  color: var(--sub);
  border-bottom: 1px solid var(--divider);
  white-space: nowrap;
}
.data-table tbody tr:hover {
  background: #ffffff05;
}
.td-date {
  font-family: var(--mono);
  color: var(--muted);
}
.td-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--c) 15%, transparent);
  color: var(--c);
  font-weight: 600;
  font-size: 11px;
}

/* Table skeleton */
.skeleton-line {
  border-radius: 4px;
  background: var(--skeleton);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-th {
  width: 60px;
  height: 10px;
}
.skeleton-td {
  width: 50px;
  height: 14px;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Events section */
.events-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.events-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.events-filter {
  background: var(--btn-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.events-count {
  font-size: 12px;
  color: var(--muted);
  margin-left: auto;
}

.events-loading {
  text-align: center;
  color: var(--muted);
  padding: 40px;
  font-size: 13px;
}

.events-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 60px 20px;
  color: var(--muted);
  text-align: center;
}

.events-empty p {
  margin: 0;
  font-size: 14px;
}

.events-empty-hint {
  font-size: 12px;
  opacity: 0.7;
}

.events-timeline {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 600px;
  overflow-y: auto;
}

.event-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--btn-bg);
  transition: background 0.15s;
}

.event-row:hover {
  background: var(--card-bg);
}

.event-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-regen { background: #4ade80; }
.dot-charge { background: #60a5fa; }
.dot-drive { background: #f59e0b; }
.dot-security { background: #a78bfa; }
.dot-geofence { background: #f97316; }
.dot-tracking { background: #06b6d4; }
.dot-maintenance { background: #ef4444; }
.dot-soc { background: #f472b6; }
.dot-default { background: var(--muted); }

.event-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.event-type {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
}

.event-field {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
}

.event-values {
  font-size: 11px;
  color: var(--muted);
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-time {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  flex-shrink: 0;
}
</style>
