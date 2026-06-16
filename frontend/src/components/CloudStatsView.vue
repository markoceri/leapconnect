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

        <!-- Last week breakdown donut -->
        <div v-if="lastWeek" class="cs-card cs-donut-card">
          <div class="cs-card-title">Weekly energy distribution {{ lastWeekLabel }}</div>
          <div class="cs-donut-row">
            <div class="cs-donut-wrapper">
              <canvas ref="donutCanvas" width="180" height="180" />
              <div class="cs-donut-center">
                <span class="cs-donut-value">{{ lastWeek.total_ec.toFixed(1) }}</span>
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
import { api } from '../composables/useApi'
import { Loader2, AlertCircle, ChevronLeft, ChevronRight, Zap } from 'lucide-vue-next'

const props = defineProps({
  vin: { type: String, required: true },
})

const loading = ref(false)
const error = ref(null)
const weeklyRank = ref(null)
const lastWeek = ref(null)

const chargeRecords = ref([])
const chargingLoading = ref(false)
const chargePage = ref(1)
const chargePageSize = 10

const donutCanvas = ref(null)
let donutChart = null

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

const driverPct = computed(() => {
  if (!lastWeek.value || lastWeek.value.total_ec === 0) return '0'
  return ((lastWeek.value.driver_ec / lastWeek.value.total_ec) * 100).toFixed(2)
})
const acPct = computed(() => {
  if (!lastWeek.value || lastWeek.value.total_ec === 0) return '0'
  return ((lastWeek.value.ac_ec / lastWeek.value.total_ec) * 100).toFixed(2)
})
const otherPct = computed(() => {
  if (!lastWeek.value || lastWeek.value.total_ec === 0) return '0'
  return ((lastWeek.value.other_ec / lastWeek.value.total_ec) * 100).toFixed(2)
})

const lastWeekLabel = computed(() => {
  const weekly = weeklyRank.value?.weekly
  if (!weekly || weekly.length === 0) return ''
  const last = weekly[weekly.length - 1]
  return `${formatShortDate(last.week_start)}–${formatShortDate(last.week_end)}`
})

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
    const [rankRes, lastRes] = await Promise.all([
      api('GET', `/api/vehicles/${props.vin}/consumption/weekly-rank`),
      api('GET', `/api/vehicles/${props.vin}/consumption/last-week`),
    ])
    weeklyRank.value = rankRes
    lastWeek.value = lastRes
    loading.value = false
    await nextTick()
    drawDonut()
    // Start fetching charging history
    chargePage.value = 1
    await fetchCharging()
  } catch (e) {
    error.value = e.message || 'Failed to load cloud statistics'
  } finally {
    loading.value = false
  }
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
  if (!canvas || !lastWeek.value) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  canvas.width = 180 * dpr
  canvas.height = 180 * dpr
  ctx.scale(dpr, dpr)

  const cx = 90, cy = 90, r = 70, lw = 18
  const total = lastWeek.value.total_ec || 1
  const segments = [
    { val: lastWeek.value.driver_ec, color: '#4caf50' },
    { val: lastWeek.value.ac_ec, color: '#42a5f5' },
    { val: lastWeek.value.other_ec, color: '#ffab40' },
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
})

// Initial fetch
fetchAll()
</script>

<style scoped>
.cloud-stats { display: flex; flex-direction: column; gap: 14px; }

.cs-loading, .cs-error { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 40px 20px; font-size: 13px; color: var(--muted); background: var(--card); border: 1px solid var(--border); border-radius: 14px; }
.cs-error { color: #ff5252; flex-direction: column; gap: 12px; }
.cs-retry-btn { padding: 6px 16px; border-radius: 8px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text); font-size: 12px; cursor: pointer; transition: all 0.15s; }
.cs-retry-btn:hover { border-color: #00d4ff; color: #00d4ff; }

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

/* Charging list */
.cs-charging-loading { display: flex; align-items: center; gap: 8px; padding: 20px; justify-content: center; font-size: 12px; color: var(--muted); }
.cs-empty { text-align: center; padding: 24px; font-size: 12px; color: var(--muted); }
.cs-charge-list { display: flex; flex-direction: column; gap: 2px; }
.cs-charge-item { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--divider); }
.cs-charge-item:last-child { border-bottom: none; }
.cs-charge-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.cs-charge-icon.fast { background: rgba(0, 212, 255, 0.12); color: #00d4ff; }
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
.cs-page-btn:hover:not(:disabled) { border-color: #00d4ff; color: #00d4ff; }
.cs-page-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.cs-page-label { font-size: 12px; color: var(--muted); padding: 0 4px; }

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
