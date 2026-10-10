<template>
  <div class="cloud-stats">
    <!-- Loading state -->
    <div v-if="loading" class="cs-loading">
      <Loader2 :size="20" class="spinning" />
      <span>Loading cloud statistics...</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="cs-error">
      <AlertCircle :size="16" />
      <span>{{ error }}</span>
      <button class="cs-retry-btn" @click="fetchAll">Retry</button>
    </div>

    <!-- Content -->
    <template v-else-if="weeklyRank">
      <!-- Gauge + Donut side by side on desktop -->
      <div class="cs-top-row">
        <!-- Consumption per 100km -->
        <div class="cs-card cs-gauge-card">
          <div class="cs-card-title">Energy consumption per 100 km — last 6 weeks</div>
          <div class="cs-gauge-row">
            <div class="cs-gauge-wrapper">
              <svg viewBox="0 0 120 120" class="cs-gauge-svg">
                <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="10" stroke-dasharray="245" stroke-dashoffset="0" stroke-linecap="round" transform="rotate(135 60 60)" />
                <circle cx="60" cy="60" r="52" fill="none" :stroke="gaugeColor" stroke-width="10" :stroke-dasharray="gaugeArc + ' 327'" stroke-dashoffset="0" stroke-linecap="round" transform="rotate(135 60 60)" />
              </svg>
              <div class="cs-gauge-value">
                <span class="cs-gauge-number">{{ gaugeValue }}</span>
                <span class="cs-gauge-unit">%</span>
              </div>
            </div>
            <div class="cs-rank-info">
              <span class="cs-rank-badge" :style="{ background: rankBadgeColor }">{{ rankLabel }}</span>
              <span class="cs-rank-text">Top <span class="cs-rank-pct">{{ rankPctText }}</span> users</span>
            </div>
          </div>
          <div class="cs-rank-note">The ranking may differ from the official app, which clamps values below 10% to 10% and above 99% to 99%.</div>
        </div>

        <!-- Energy breakdown donut (selectable period) -->
        <div class="cs-card cs-donut-card">
          <div class="cs-card-header">
            <div class="cs-card-title">Energy distribution <span class="cs-period-label">{{ breakdownLabel }}</span></div>
            <select v-model="breakdownPeriod" class="cs-select" :disabled="breakdownLoading" @change="onPeriodChange">
              <option v-for="p in PERIODS" :key="p.id" :value="p.id">{{ p.label }}</option>
            </select>
          </div>
          <div v-if="breakdownPeriod === 'custom'" class="cs-custom-range">
            <input v-model="customFrom" type="date" class="cs-select" :max="customTo || todayIso()" />
            <span class="cs-range-sep">–</span>
            <input v-model="customTo" type="date" class="cs-select" :min="customFrom" :max="todayIso()" />
            <button class="cs-retry-btn" :disabled="!customRangeValid || breakdownLoading" @click="fetchBreakdown">Apply</button>
          </div>
          <div v-if="breakdownLoading" class="cs-charging-loading">
            <Loader2 :size="16" class="spinning" /> Loading...
          </div>
          <div v-else-if="breakdownError" class="cs-breakdown-error">
            <AlertCircle :size="14" /> {{ breakdownError }}
          </div>
          <div v-else-if="breakdown" class="cs-donut-row">
            <div class="cs-donut-wrapper">
              <canvas ref="donutCanvas" width="180" height="180" />
              <div class="cs-donut-center">
                <span class="cs-donut-value">{{ breakdown.total_ec.toFixed(1) }}</span>
                <span class="cs-donut-unit">kWh</span>
              </div>
            </div>
            <div class="cs-donut-legend">
              <div class="cs-legend-item">
                <span class="cs-legend-dot" style="background: #4caf50" />
                <span class="cs-legend-label">Driving {{ driverPct }}%</span>
              </div>
              <div class="cs-legend-item">
                <span class="cs-legend-dot" style="background: #42a5f5" />
                <span class="cs-legend-label">A/C {{ acPct }}%</span>
              </div>
              <div class="cs-legend-item">
                <span class="cs-legend-dot" style="background: #ffab40" />
                <span class="cs-legend-label">Other {{ otherPct }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Weekly bar chart -->
      <div class="cs-card">
        <div class="cs-card-title">Weekly consumption (kWh/100km)</div>
        <div class="cs-bar-chart">
          <div v-for="(w, i) in weeklyRank.weekly" :key="i" class="cs-bar-col">
            <span class="cs-bar-val">{{ w.hundred_km_ec.toFixed(1) }}</span>
            <div class="cs-bar-track">
              <div
                class="cs-bar-fill"
                :class="{ 'cs-bar-current': i === weeklyRank.weekly.length - 1 }"
                :style="{ height: barHeight(w.hundred_km_ec) + '%' }"
              />
            </div>
            <span class="cs-bar-label">{{ formatWeekLabel(w.week_start, w.week_end) }}</span>
          </div>
        </div>
      </div>

      <!-- Daily distance & energy (cloud) -->
      <div class="cs-card">
        <div class="cs-card-header">
          <div class="cs-card-title">Daily {{ dailyMetric === 'km' ? 'distance' : 'energy' }} <span class="cs-period-label">{{ dailyLabel }}</span></div>
          <div class="cs-header-controls">
            <div class="cs-seg" role="group" aria-label="Metric">
              <button :class="{ active: dailyMetric === 'km' }" @click="setDailyMetric('km')">Distance</button>
              <button :class="{ active: dailyMetric === 'kwh' }" @click="setDailyMetric('kwh')">Energy</button>
            </div>
            <select v-model="dailyPeriod" class="cs-select" :disabled="dailyLoading" @change="fetchDaily">
              <option v-for="p in DAILY_PERIODS" :key="p.id" :value="p.id">{{ p.label }}</option>
            </select>
          </div>
        </div>
        <div v-if="dailyLoading" class="cs-charging-loading">
          <Loader2 :size="16" class="spinning" /> Loading...
        </div>
        <div v-else-if="dailyError" class="cs-breakdown-error">
          <AlertCircle :size="14" /> {{ dailyError }}
        </div>
        <template v-else-if="daily">
          <div class="cs-tiles">
            <div class="cs-tile">
              <span class="cs-tile-label">Distance in period</span>
              <span class="cs-tile-value">{{ fmtNum(daily.window_mileage_km, 0) }} <small>km</small></span>
            </div>
            <div class="cs-tile">
              <span class="cs-tile-label">Energy in period</span>
              <span class="cs-tile-value">≈ {{ fmtNum(daily.window_energy_kwh, 0) }} <small>kWh</small></span>
            </div>
            <div class="cs-tile">
              <span class="cs-tile-label">Lifetime energy</span>
              <span class="cs-tile-value">{{ fmtNum(daily.total_energy_kwh, 1) }} <small>kWh</small></span>
            </div>
            <div class="cs-tile">
              <span class="cs-tile-label">Lifetime distance</span>
              <span class="cs-tile-value">{{ fmtNum(daily.total_mileage_km, 0) }} <small>km</small></span>
              <span v-if="daily.delivery_days != null" class="cs-tile-sub">{{ daily.delivery_days }} days since delivery</span>
            </div>
          </div>
          <div v-if="daily.days.length" class="cs-daily-chart">
            <canvas ref="dailyCanvas" />
          </div>
          <div v-else class="cs-empty">No data for this period.</div>
          <div class="cs-rank-note">Daily energy from the cloud is approximate (often rounded to whole kWh); lifetime energy includes standby consumption.</div>
        </template>
      </div>

      <!-- Charging history -->
      <div class="cs-card">
        <div class="cs-card-header">
          <div class="cs-card-title">Charging History</div>
          <div class="cs-page-controls">
            <button class="cs-page-btn" :disabled="chargePage <= 1 || chargingLoading" @click="chargePage--; fetchCharging()">
              <ChevronLeft :size="14" />
            </button>
            <span class="cs-page-label">Page {{ chargePage }}</span>
            <button class="cs-page-btn" :disabled="chargeRecords.length < chargePageSize || chargingLoading" @click="chargePage++; fetchCharging()">
              <ChevronRight :size="14" />
            </button>
          </div>
        </div>
        <div v-if="chargingLoading" class="cs-charging-loading">
          <Loader2 :size="16" class="spinning" /> Loading...
        </div>
        <div v-else-if="chargeRecords.length === 0" class="cs-empty">No charging sessions found for this period.</div>
        <div v-else class="cs-charge-list">
          <div v-for="(rec, i) in chargeRecords" :key="i" class="cs-charge-item">
            <div class="cs-charge-icon" :class="rec.is_fast_charge ? 'fast' : 'slow'">
              <Zap :size="14" />
            </div>
            <div class="cs-charge-info">
              <div class="cs-charge-date">{{ formatChargeDate(rec.start_datetime) }}</div>
              <div class="cs-charge-meta">
                {{ formatDuration(rec.duration_seconds) }} ·
                {{ rec.is_fast_charge ? 'DC Fast' : 'AC Slow' }}
              </div>
            </div>
            <div class="cs-charge-energy">
              <span class="cs-charge-kwh">{{ rec.energy_kwh.toFixed(1) }}</span>
              <span class="cs-charge-unit">kWh</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
import { api } from '../composables/useApi'
import { accentHex } from '../utils/theme'
import { Loader2, AlertCircle, ChevronLeft, ChevronRight, Zap } from 'lucide-vue-next'

const props = defineProps({
  vin: { type: String, required: true },
})

const loading = ref(false)
const error = ref(null)
const weeklyRank = ref(null)
const breakdown = ref(null)
const breakdownLoading = ref(false)
const breakdownError = ref(null)
// The cloud's last-week split is Monday–Sunday (UTC); every other period is a
// range of whole days in the user's time zone.
const PERIODS = [
  { id: 'last_week', label: 'Last week' },
  { id: 'last_30', label: 'Last 30 days' },
  { id: 'this_month', label: 'This month' },
  { id: 'last_month', label: 'Last month' },
  { id: 'this_year', label: 'This year' },
  { id: 'custom', label: 'Custom…' },
]
const breakdownPeriod = ref('last_week')
const customFrom = ref('')
const customTo = ref('')

const chargeRecords = ref([])
const chargingLoading = ref(false)
const chargePage = ref(1)
const chargePageSize = 10

const donutCanvas = ref(null)
let donutChart = null

Chart.register(...registerables)

const DAILY_PERIODS = [
  { id: 'last_7', label: 'Last 7 days' },
  { id: 'last_30', label: 'Last 30 days' },
  { id: 'this_month', label: 'This month' },
  { id: 'last_month', label: 'Last month' },
]
const daily = ref(null)
const dailyLoading = ref(false)
const dailyError = ref(null)
const dailyPeriod = ref('last_30')
const dailyMetric = ref('km')
const dailyCanvas = ref(null)
let dailyChart = null

// Gauge computed
// The percentile is in `rank.rank`, a string like "85%". `rank.result` is
// only the API status code (0 = OK), not the ranking — reading it pinned the
// gauge to 0% for everyone.
const rankPercent = computed(() => {
  const raw = weeklyRank.value?.rank?.rank
  if (raw == null || raw === '') return null
  const m = String(raw).match(/-?\d+(?:\.\d+)?/)
  return m ? parseFloat(m[0]) : null
})

const gaugeValue = computed(() => {
  const r = rankPercent.value
  return r != null ? r : '—'
})

const gaugeArc = computed(() => {
  const val = rankPercent.value ?? 0
  // 0–100% rank, map to full 245 arc (270°)
  const pct = Math.min(val / 100, 1)
  return pct * 245
})

const gaugeColor = computed(() => {
  const val = rankPercent.value ?? 0
  if (val > 80) return '#00B359'
  if (val >= 40) return '#0093FF'
  return '#FFA900'
})

const rankLabel = computed(() => {
  const r = rankPercent.value
  if (r == null) return '—'
  if (r > 80) return 'Excellent'
  if (r >= 40) return 'Good'
  return 'Ordinary'
})

const rankPctText = computed(() => {
  const r = rankPercent.value
  return r != null ? `${r}%` : '—'
})

const rankBadgeColor = computed(() => {
  const r = rankPercent.value
  if (r == null) return 'var(--border)'
  if (r > 80) return '#00B359'
  if (r >= 40) return '#0093FF'
  return '#FFA900'
})

function sharePct(key) {
  if (!breakdown.value || breakdown.value.total_ec === 0) return '0'
  return ((breakdown.value[key] / breakdown.value.total_ec) * 100).toFixed(2)
}
const driverPct = computed(() => sharePct('driver_ec'))
const acPct = computed(() => sharePct('ac_ec'))
const otherPct = computed(() => sharePct('other_ec'))

const breakdownLabel = computed(() => {
  if (breakdownPeriod.value === 'last_week') {
    const weekly = weeklyRank.value?.weekly
    if (!weekly || weekly.length === 0) return ''
    const last = weekly[weekly.length - 1]
    return `${formatShortDate(last.week_start)}–${formatShortDate(last.week_end)}`
  }
  if (!breakdown.value?.start) return ''
  return formatRange(breakdown.value.start, breakdown.value.end)
})

const customRangeValid = computed(() =>
  !!customFrom.value && !!customTo.value && customFrom.value <= customTo.value)

function isoDay(d) {
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function todayIso() {
  return isoDay(new Date())
}

// [from, to] (inclusive, local days) of a preset period.
function periodRange(id) {
  const now = new Date()
  const y = now.getFullYear(), m = now.getMonth()
  switch (id) {
    case 'last_7': return [isoDay(new Date(y, m, now.getDate() - 6)), isoDay(now)]
    case 'last_30': return [isoDay(new Date(y, m, now.getDate() - 29)), isoDay(now)]
    case 'this_month': return [isoDay(new Date(y, m, 1)), isoDay(now)]
    case 'last_month': return [isoDay(new Date(y, m - 1, 1)), isoDay(new Date(y, m, 0))]
    case 'this_year': return [isoDay(new Date(y, 0, 1)), isoDay(now)]
    case 'custom': return customRangeValid.value ? [customFrom.value, customTo.value] : null
    default: return null
  }
}

function formatRange(from, to) {
  const opts = { day: 'numeric', month: 'short' }
  const f = new Date(`${from}T00:00:00`), t = new Date(`${to}T00:00:00`)
  if (from === to) return f.toLocaleDateString('en-GB', { ...opts, year: 'numeric' })
  const sameYear = f.getFullYear() === t.getFullYear()
  const fromText = f.toLocaleDateString('en-GB', sameYear ? opts : { ...opts, year: 'numeric' })
  return `${fromText} – ${t.toLocaleDateString('en-GB', { ...opts, year: 'numeric' })}`
}

function barHeight(val) {
  if (!weeklyRank.value?.weekly?.length) return 0
  const max = Math.max(...weeklyRank.value.weekly.map(w => w.hundred_km_ec), 1)
  return Math.max((val / (max * 1.2)) * 100, 4)
}

function formatWeekLabel(start, end) {
  if (!start || !end) return '—'
  const s = start.replace(/-/g, '/')
  const e = end.replace(/-/g, '/')
  // Show as "M/D" abbreviated
  const sp = s.split('/')
  const ep = e.split('/')
  return `${parseInt(sp[1])}/${parseInt(sp[2])}-${parseInt(ep[1])}/${parseInt(ep[2])}`
}

function formatShortDate(d) {
  if (!d) return ''
  const parts = d.split('-')
  return `${parseInt(parts[1])}/${parseInt(parts[2])}`
}

function formatChargeDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(sec) {
  if (!sec || sec <= 0) return '—'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

async function fetchAll() {
  if (!props.vin) return
  loading.value = true
  error.value = null
  try {
    weeklyRank.value = await api('GET', `/api/vehicles/${props.vin}/consumption/weekly-rank`)
    loading.value = false
    await Promise.all([fetchBreakdown(), fetchDaily()])
    // Start fetching charging history
    chargePage.value = 1
    await fetchCharging()
  } catch (e) {
    error.value = e.message || 'Failed to load cloud statistics'
  } finally {
    loading.value = false
  }
}

const dailyLabel = computed(() =>
  daily.value?.start ? formatRange(daily.value.start, daily.value.end) : '')

function fmtNum(v, digits) {
  if (v == null) return '—'
  return Number(v).toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

// The cloud's `day_ms` is the day's local midnight; fall back to its `day` text.
function dailyDayLabel(d) {
  if (d.day_ms) return new Date(d.day_ms).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  return d.day
}

async function fetchDaily() {
  if (!props.vin) return
  const [from, to] = periodRange(dailyPeriod.value)
  dailyLoading.value = true
  dailyError.value = null
  try {
    daily.value = await api('GET', `/api/vehicles/${props.vin}/mileage/daily?from_date=${from}&to_date=${to}`)
  } catch (e) {
    daily.value = null
    dailyError.value = e.message || 'Failed to load daily distance and energy'
  } finally {
    dailyLoading.value = false
  }
  await nextTick()
  drawDaily()
}

function setDailyMetric(metric) {
  dailyMetric.value = metric
  drawDaily()
}

function drawDaily() {
  if (dailyChart) { dailyChart.destroy(); dailyChart = null }
  const canvas = dailyCanvas.value
  if (!canvas || !daily.value?.days?.length) return
  const s = getComputedStyle(document.documentElement)
  const css = (name, fallback) => s.getPropertyValue(name).trim() || fallback
  const isKm = dailyMetric.value === 'km'
  const unit = isKm ? 'km' : 'kWh'
  const days = daily.value.days
  dailyChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: days.map(dailyDayLabel),
      datasets: [{
        data: days.map(d => (isKm ? d.mileage_km : d.energy_kwh)),
        backgroundColor: accentHex(),
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: 'bottom',
        maxBarThickness: 28,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--tooltip-bg', '#161b2a'),
          titleColor: css('--sub', '#8892a8'),
          bodyColor: css('--text', '#e2e6f0'),
          borderColor: css('--tooltip-border', '#1c2240'),
          borderWidth: 1,
          padding: 10,
          displayColors: false,
          callbacks: {
            label: ctx => (ctx.raw == null ? 'No data' : `${fmtNum(ctx.raw, isKm ? 1 : 0)} ${unit}`),
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: css('--chart-tick', '#4a5468'), font: { size: 10 }, maxTicksLimit: 8, maxRotation: 0 } },
        y: { beginAtZero: true, grid: { color: css('--chart-grid', '#1c2135'), drawTicks: false }, ticks: { color: css('--chart-tick', '#4a5468'), font: { size: 10 }, callback: v => `${v} ${unit}` } },
      },
    },
  })
}

function onPeriodChange() {
  if (breakdownPeriod.value === 'custom') {
    // Seed the custom range with the period shown so far.
    if (!customRangeValid.value) {
      [customFrom.value, customTo.value] = breakdown.value?.start
        ? [breakdown.value.start, breakdown.value.end]
        : periodRange('last_30')
    }
    return
  }
  fetchBreakdown()
}

async function fetchBreakdown() {
  if (!props.vin) return
  breakdownLoading.value = true
  breakdownError.value = null
  try {
    if (breakdownPeriod.value === 'last_week') {
      breakdown.value = await api('GET', `/api/vehicles/${props.vin}/consumption/last-week`)
    } else {
      const range = periodRange(breakdownPeriod.value)
      if (!range) return
      const [from, to] = range
      breakdown.value = await api('GET', `/api/vehicles/${props.vin}/consumption/breakdown?from_date=${from}&to_date=${to}`)
    }
  } catch (e) {
    breakdown.value = null
    breakdownError.value = e.message || 'Failed to load the energy distribution'
  } finally {
    breakdownLoading.value = false
  }
  await nextTick()
  drawDonut()
}

async function fetchCharging() {
  chargingLoading.value = true
  try {
    const now = new Date()
    const start = new Date(now.getFullYear(), now.getMonth() - 3, 1).toISOString().slice(0, 10)
    const end = now.toISOString().slice(0, 10)
    const res = await api('GET', `/api/vehicles/${props.vin}/charging-history?start=${start}&end=${end}&page=${chargePage.value}&size=${chargePageSize}`)
    chargeRecords.value = res.records || []
  } catch (e) {
    chargeRecords.value = []
  } finally {
    chargingLoading.value = false
  }
}

function drawDonut() {
  const canvas = donutCanvas.value
  if (!canvas || !breakdown.value) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  canvas.width = 180 * dpr
  canvas.height = 180 * dpr
  ctx.scale(dpr, dpr)

  const cx = 90, cy = 90, r = 70, lw = 18
  const total = breakdown.value.total_ec || 1
  const segments = [
    { val: breakdown.value.driver_ec, color: '#4caf50' },
    { val: breakdown.value.ac_ec, color: '#42a5f5' },
    { val: breakdown.value.other_ec, color: '#ffab40' },
  ]

  ctx.clearRect(0, 0, 180, 180)
  let startAngle = -Math.PI / 2

  for (const seg of segments) {
    const sweep = (seg.val / total) * Math.PI * 2
    if (sweep > 0.001) {
      ctx.beginPath()
      ctx.arc(cx, cy, r, startAngle, startAngle + sweep)
      ctx.strokeStyle = seg.color
      ctx.lineWidth = lw
      ctx.lineCap = 'round'
      ctx.stroke()
      startAngle += sweep
    }
  }

  // If nothing, draw empty ring
  if (total <= 0) {
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.strokeStyle = 'var(--border)'
    ctx.lineWidth = lw
    ctx.stroke()
  }
}

watch(() => props.vin, () => { fetchAll() })

onBeforeUnmount(() => {
  if (donutChart) { donutChart.destroy(); donutChart = null }
  if (dailyChart) { dailyChart.destroy(); dailyChart = null }
})

// Initial fetch
fetchAll()
</script>

<style scoped>
.cloud-stats { display: flex; flex-direction: column; gap: 14px; }

.cs-loading, .cs-error { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 40px 20px; font-size: 13px; color: var(--muted); background: var(--card); border: 1px solid var(--border); border-radius: 14px; }
.cs-error { color: #ff5252; flex-direction: column; gap: 12px; }
.cs-retry-btn { padding: 6px 16px; border-radius: 8px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text); font-size: 12px; cursor: pointer; transition: all 0.15s; }
.cs-retry-btn:hover { border-color: var(--accent); color: var(--accent); }

.cs-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 20px; }
.cs-card-title { font-size: 13px; font-weight: 700; color: var(--heading); margin-bottom: 16px; }
.cs-card-subtitle { font-size: 12px; color: var(--muted); margin-bottom: 20px; }
.cs-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.cs-card-header .cs-card-title { margin-bottom: 0; }

/* Top row: side by side on desktop */
.cs-top-row { display: flex; flex-direction: column; gap: 14px; }
@media (min-width: 768px) {
  .cs-top-row { flex-direction: row; }
  .cs-top-row > .cs-card { flex: 1; min-width: 0; }
}

/* Gauge */
.cs-gauge-card { position: relative; }
.cs-gauge-card .cs-card-title { text-align: left; }
.cs-gauge-card .cs-info-icon { position: absolute; top: 16px; right: 16px; }
.cs-gauge-row { display: flex; flex-direction: column; align-items: center; }
.cs-gauge-wrapper { position: relative; width: 160px; height: 160px; }
.cs-gauge-svg { width: 100%; height: 100%; }
.cs-gauge-value { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }
.cs-gauge-number { display: block; font-size: 32px; font-weight: 800; color: var(--text); }
.cs-gauge-unit { font-size: 13px; color: var(--muted); }
.cs-rank-info { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.cs-rank-badge { display: inline-block; padding: 4px 14px; border-radius: 12px; font-size: 12px; font-weight: 700; color: #fff; }
.cs-rank-text { font-size: 12px; color: var(--muted); }
.cs-rank-pct { color: #4caf50; font-weight: 700; }
.cs-rank-note { font-size: 11px; color: var(--muted); text-align: center; margin-top: 12px; line-height: 1.4; }

/* Bar chart */
.cs-bar-chart { display: flex; align-items: flex-end; gap: 8px; height: 160px; padding-top: 20px; }
.cs-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%; }
.cs-bar-val { font-size: 11px; font-weight: 600; color: var(--text); }
.cs-bar-track { flex: 1; width: 100%; max-width: 42px; background: var(--btn-bg); border-radius: 6px 6px 0 0; position: relative; overflow: hidden; display: flex; align-items: flex-end; }
.cs-bar-fill { width: 100%; background: #bdbdbd; border-radius: 6px 6px 0 0; transition: height 0.5s ease; }
.cs-bar-fill.cs-bar-current { background: linear-gradient(to top, #4caf50, #66bb6a); }
.cs-bar-label { font-size: 9px; color: var(--muted); white-space: nowrap; }

/* Donut */
.cs-donut-card { display: flex; flex-direction: column; }
.cs-donut-row { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; justify-content: center; flex: 1; }
.cs-donut-wrapper { position: relative; width: 180px; height: 180px; flex-shrink: 0; }
.cs-donut-wrapper canvas { width: 180px !important; height: 180px !important; }
.cs-donut-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }
.cs-donut-value { display: block; font-size: 28px; font-weight: 800; color: var(--text); }
.cs-donut-unit { font-size: 12px; color: var(--muted); }
.cs-donut-legend { display: flex; flex-direction: column; gap: 10px; }
.cs-legend-item { display: flex; align-items: center; gap: 8px; }
.cs-legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.cs-legend-label { font-size: 13px; color: var(--text); }
.cs-period-label { font-weight: 500; color: var(--muted); }
.cs-donut-card .cs-card-header { flex-wrap: wrap; gap: 8px; }
.cs-header-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cs-card-header:has(.cs-header-controls) { flex-wrap: wrap; gap: 8px; }
.cs-seg { display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.cs-seg button { background: var(--btn-bg); border: none; color: var(--muted); padding: 6px 10px; font-size: 12px; cursor: pointer; }
.cs-seg button + button { border-left: 1px solid var(--border); }
.cs-seg button.active { color: var(--accent); background: rgba(var(--accent-rgb), 0.12); font-weight: 600; }
.cs-tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 16px; }
@media (min-width: 768px) { .cs-tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.cs-tile { display: flex; flex-direction: column; gap: 4px; padding: 12px; border: 1px solid var(--border); border-radius: 10px; background: var(--btn-bg); min-width: 0; }
.cs-tile-label { font-size: 11px; color: var(--muted); }
.cs-tile-value { font-size: 18px; font-weight: 700; color: var(--text); }
.cs-tile-value small { font-size: 11px; font-weight: 500; color: var(--muted); }
.cs-tile-sub { font-size: 11px; color: var(--muted); }
.cs-daily-chart { position: relative; height: 200px; }
.cs-select { background: var(--btn-bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); padding: 6px 10px; font-size: 12px; cursor: pointer; }
.cs-select:disabled { opacity: 0.6; cursor: default; }
.cs-custom-range { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.cs-range-sep { color: var(--muted); }
.cs-breakdown-error { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 24px; font-size: 12px; color: #ff5252; }

/* Charging list */
.cs-charging-loading { display: flex; align-items: center; gap: 8px; padding: 20px; justify-content: center; font-size: 12px; color: var(--muted); }
.cs-empty { text-align: center; padding: 24px; font-size: 12px; color: var(--muted); }
.cs-charge-list { display: flex; flex-direction: column; gap: 2px; }
.cs-charge-item { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--divider); }
.cs-charge-item:last-child { border-bottom: none; }
.cs-charge-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.cs-charge-icon.fast { background: rgba(var(--accent-rgb), 0.12); color: var(--accent); }
.cs-charge-icon.slow { background: rgba(0, 230, 118, 0.12); color: #00e676; }
.cs-charge-info { flex: 1; min-width: 0; }
.cs-charge-date { font-size: 13px; font-weight: 600; color: var(--text); }
.cs-charge-meta { font-size: 11px; color: var(--muted); margin-top: 2px; }
.cs-charge-energy { text-align: right; }
.cs-charge-kwh { font-size: 18px; font-weight: 700; color: #00e676; }
.cs-charge-unit { font-size: 11px; color: var(--muted); margin-left: 2px; }

/* Pagination */
.cs-page-controls { display: flex; align-items: center; gap: 6px; }
.cs-page-btn { width: 28px; height: 28px; border-radius: 7px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
.cs-page-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.cs-page-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.cs-page-label { font-size: 12px; color: var(--muted); padding: 0 4px; }

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
