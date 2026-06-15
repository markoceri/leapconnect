<template>
  <div class="charging-tab">
    <div class="charging-header">
      <div class="header-title">
        <h2>Charging</h2>
        <p>Energy, sessions &amp; costs</p>
      </div>
      <div class="month-nav">
        <button class="toolbar-btn" @click="prevMonth"><ChevronLeft :size="16" /></button>
        <span class="month-label">{{ monthLabel }}</span>
        <button class="toolbar-btn" :disabled="isCurrentMonth" @click="nextMonth"><ChevronRight :size="16" /></button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-center">
      <div class="spinner" />
    </div>

    <template v-else>
    <!-- KPI cards -->
    <div v-if="kpiCards.length" class="summary-grid">
      <div v-for="s in kpiCards" :key="s.label" class="summary-card">
        <div class="summary-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="summary-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- Charts row: three charts side by side on desktop -->
    <div class="charts-grid charts-grid-3">
      <div class="chart-card">
        <div class="chart-header"><Zap :size="16" class="chart-icon" /> Energy per session (kWh)</div>
        <div class="chart-area"><canvas ref="energyCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><TrendingUp :size="16" class="chart-icon" /> Daily cost (€)</div>
        <div class="chart-area"><canvas ref="costCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><PieChart :size="16" class="chart-icon" /> Energy by tier</div>
        <div class="chart-area"><canvas ref="pieCanvas" /></div>
      </div>
    </div>

    <!-- Time-of-use visualization -->
    <div v-if="homePricingMode === 'time_of_use' && timeBands.length" class="chart-card wide tou-card">
      <div class="chart-header"><Clock :size="16" class="chart-icon" /> Time-of-use bands — energy distribution</div>
      <div class="tou-bands">
        <div v-for="band in timeBandsWithEnergy" :key="band.id" class="tou-band-row">
          <span class="tou-color" :style="{ background: band.color || '#888' }" />
          <span class="tou-name">{{ band.name }}</span>
          <span class="tou-price">€{{ band.price_kwh.toFixed(3) }}/kWh</span>
          <div class="tou-bar-track">
            <div class="tou-bar-fill" :style="{ width: band.pct + '%', background: band.color || '#888' }" />
          </div>
          <span class="tou-energy">{{ band.energy.toFixed(1) }} kWh</span>
          <span class="tou-cost">€{{ band.cost.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Monthly summary -->
    <div class="chart-card wide">
      <div class="chart-header"><CalendarDays :size="16" class="chart-icon" /> Monthly summary</div>
      <div class="monthly-table-wrap">
        <table class="monthly-table">
          <thead>
            <tr>
              <th>Month</th>
              <th>Sessions</th>
              <th>Energy (kWh)</th>
              <th>Home grid</th>
              <th v-if="hasSolarPanels">Solar</th>
              <th>Public</th>
              <th>Cost (€)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in monthlySummary" :key="m.month">
              <td>{{ m.month }}</td>
              <td>{{ m.sessions }}</td>
              <td>{{ m.energy.toFixed(1) }}</td>
              <td>{{ m.homeGrid.toFixed(1) }}</td>
              <td v-if="hasSolarPanels">{{ m.solar.toFixed(1) }}</td>
              <td>{{ m.public.toFixed(1) }}</td>
              <td>€{{ m.cost.toFixed(2) }}</td>
            </tr>
            <tr v-if="!monthlySummary.length">
              <td :colspan="hasSolarPanels ? 7 : 6" class="empty-row">No data available</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Session list -->
    <div class="chart-card wide">
      <div class="chart-header"><List :size="16" class="chart-icon" /> Charging sessions</div>
      <div class="session-list">
        <div class="session-head">
          <span>Date</span>
          <span>Time</span>
          <span>Energy</span>
          <span>Peak</span>
          <span>Tier</span>
          <span>Zone</span>
          <span>Cost</span>
          <span class="head-edit" />
        </div>
        <div v-for="s in filteredSessions" :key="s.id || s.start_ts" class="session-row">
          <span class="cell cell-date" data-label="Date">{{ formatDate(s.start_ts) }}</span>
          <span class="cell cell-time" data-label="Time">{{ formatTimeRange(s.start_ts, s.end_ts) }}</span>
          <span class="cell cell-energy" data-label="Energy">{{ s.energy_kwh != null ? s.energy_kwh.toFixed(1) + ' kWh' : '—' }}</span>
          <span class="cell cell-peak" data-label="Peak">{{ s.peak_power_kw != null ? s.peak_power_kw.toFixed(1) + ' kW' : '—' }}</span>
          <span class="cell cell-tier" data-label="Tier">
            <span v-if="s.tier_label" class="tier-badge" :class="'tier-' + s.tier_id">{{ s.tier_label }}</span>
            <span v-else class="tier-badge tier-none">No tier</span>
          </span>
          <span class="cell cell-zone" data-label="Zone">{{ s.zone_name || '—' }}</span>
          <span class="cell cell-cost" data-label="Cost">
            <span v-if="s.cost != null">€{{ s.cost.toFixed(2) }}</span>
            <span v-else class="cost-none">—</span>
          </span>
          <span class="cell cell-edit">
            <button class="edit-btn" @click="editSession(s)" title="Edit session cost">
              <Pencil :size="14" />
            </button>
          </span>
        </div>
        <div v-if="!filteredSessions.length" class="empty-row">No charging sessions in this period</div>
      </div>
    </div>

    <!-- Charging by location -->
    <div v-if="costByLocation.length" class="chart-card wide">
      <div class="chart-header"><MapPin :size="16" class="chart-icon" /> Charging by location</div>
      <div class="location-list">
        <div v-for="loc in costByLocation" :key="loc.zone" class="location-row">
          <span class="loc-name">{{ loc.zone }}</span>
          <span class="loc-stat">{{ loc.sessions }} session{{ loc.sessions === 1 ? '' : 's' }}</span>
          <span class="loc-stat">{{ loc.energy.toFixed(1) }} kWh</span>
          <span class="loc-cost">€{{ loc.cost.toFixed(2) }}</span>
        </div>
      </div>
    </div>
    </template>

    <!-- Edit session dialog -->
    <Teleport to="body">
      <div v-if="editingSession" class="modal-backdrop" @click.self="editingSession = null">
        <div class="modal-dialog">
          <h3>Edit session cost</h3>
          <p class="edit-date">{{ formatDate(editingSession.start_ts) }} {{ formatTimeRange(editingSession.start_ts, editingSession.end_ts) }}</p>
          <div class="form-group">
            <label>Tier</label>
            <select v-model="editForm.tier_id">
              <option v-for="t in availableTiers" :key="t.id" :value="t.id">{{ t.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Energy (kWh)</label>
            <input v-model.number="editForm.energy_kwh" type="number" step="0.1" min="0" />
          </div>
          <div class="form-group">
            <label>Cost override (€) — leave empty for auto</label>
            <input v-model.number="editForm.cost" type="number" step="0.01" min="0" placeholder="Auto-calculate" />
          </div>
          <div class="form-group">
            <label>Note</label>
            <input v-model="editForm.note" type="text" placeholder="Optional note" />
          </div>
          <div class="modal-actions">
            <button class="btn-cancel" @click="editingSession = null">Cancel</button>
            <button class="btn-save" :disabled="saving" @click="saveSession">{{ saving ? 'Saving…' : 'Save' }}</button>
          </div>
          <div v-if="editError" class="field-error">{{ editError }}</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'
import { api } from '../composables/useApi'
import { parseUTC } from '../utils/maintenance'
import { Zap, TrendingUp, PieChart, Clock, CalendarDays, ChevronLeft, ChevronRight, List, Pencil, MapPin } from 'lucide-vue-next'

Chart.register(...registerables)

const props = defineProps({
  vin: { type: String, required: true },
})

// State
const selectedMonth = ref(new Date())
const sessionCosts = ref([])
const detectedSessions = ref([])
const availableTiers = ref([])
const timeBands = ref([])
const homePricingMode = ref('flat')
const hasSolarPanels = ref(false)
const editingSession = ref(null)
const editForm = ref({})
const editError = ref('')
const saving = ref(false)
const loading = ref(true)

// Charts
const energyCanvas = ref(null)
const costCanvas = ref(null)
const pieCanvas = ref(null)
let charts = []
let resizeTimeout

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

// Filtered sessions for selected month — merges snapshot-detected sessions with cost records
const filteredSessions = computed(() => {
  const y = selectedMonth.value.getFullYear()
  const m = selectedMonth.value.getMonth()

  // Start with detected sessions from snapshots
  const merged = detectedSessions.value.map(ds => {
    // Try to match with a cost record (within 2 min of start_ts)
    const match = sessionCosts.value.find(sc =>
      sc.start_ts && Math.abs(parseUTC(sc.start_ts) - parseUTC(ds.start_ts)) < 120000
    )
    if (match) {
      return { ...match, energy_kwh: match.energy_kwh ?? ds.energy_kwh, peak_power_kw: match.peak_power_kw ?? ds.peak_power_kw, _detected: true }
    }
    // No cost record — return detected session as-is
    return { ...ds, id: null, tier_id: null, tier_label: null, cost: null, _detected: true }
  })

  // Also include cost records that don't match any detected session (e.g. manually created)
  for (const sc of sessionCosts.value) {
    const d = parseUTC(sc.start_ts)
    if (d.getFullYear() !== y || d.getMonth() !== m) continue
    const alreadyMerged = merged.some(ms => ms.id === sc.id)
    if (!alreadyMerged) {
      merged.push(sc)
    }
  }

  return merged.sort((a, b) => parseUTC(b.start_ts) - parseUTC(a.start_ts))
})

// KPI cards
const kpiCards = computed(() => {
  const sessions = filteredSessions.value
  if (!sessions.length) return []

  const totalEnergy = sessions.reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const totalCost = sessions.reduce((s, c) => s + (c.cost || 0), 0)
  const homeGrid = sessions.filter(c => c.tier_id === 'home_grid').reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const solar = sessions.filter(c => c.tier_id === 'home_solar').reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const pub = sessions.filter(c => c.tier_id === 'public_ac' || c.tier_id === 'public_dc').reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const homeCost = sessions.filter(c => c.tier_id === 'home_grid' || c.tier_id === 'home_solar').reduce((s, c) => s + (c.cost || 0), 0)
  const pubCost = sessions.filter(c => c.tier_id === 'public_ac' || c.tier_id === 'public_dc').reduce((s, c) => s + (c.cost || 0), 0)

  const cards = [
    { label: 'Sessions', value: sessions.length, color: '#7c6aff' },
    { label: 'Total energy', value: `${totalEnergy.toFixed(1)} kWh`, color: '#00e676' },
    { label: 'Home grid', value: `${homeGrid.toFixed(1)} kWh`, color: '#66bb6a' },
  ]
  if (hasSolarPanels.value) {
    cards.push({ label: 'Solar', value: `${solar.toFixed(1)} kWh`, color: '#fdd835' })
  }
  cards.push(
    { label: 'Public', value: `${pub.toFixed(1)} kWh`, color: '#42a5f5' },
    { label: 'Total cost', value: `€${totalCost.toFixed(2)}`, color: '#ffd54f' },
    { label: 'Home cost', value: `€${homeCost.toFixed(2)}`, color: '#a5d6a7' },
    { label: 'Public cost', value: `€${pubCost.toFixed(2)}`, color: '#90caf9' },
  )
  return cards
})

// Monthly summary (last 6 months)
const monthlySummary = computed(() => {
  const all = sessionCosts.value
  if (!all.length) return []
  const months = {}
  for (const s of all) {
    const d = parseUTC(s.start_ts)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    if (!months[key]) months[key] = { month: key, sessions: 0, energy: 0, homeGrid: 0, solar: 0, public: 0, cost: 0 }
    months[key].sessions++
    months[key].energy += s.energy_kwh || 0
    months[key].cost += s.cost || 0
    if (s.tier_id === 'home_grid') months[key].homeGrid += s.energy_kwh || 0
    else if (s.tier_id === 'home_solar') months[key].solar += s.energy_kwh || 0
    else months[key].public += s.energy_kwh || 0
  }
  return Object.values(months).sort((a, b) => b.month.localeCompare(a.month)).slice(0, 12)
})

// Charging energy/cost grouped by the zone the session happened in
const costByLocation = computed(() => {
  const groups = {}
  for (const s of filteredSessions.value) {
    const key = s.zone_name || 'Unknown location'
    if (!groups[key]) groups[key] = { zone: key, sessions: 0, energy: 0, cost: 0 }
    groups[key].sessions++
    groups[key].energy += s.energy_kwh || 0
    groups[key].cost += s.cost || 0
  }
  return Object.values(groups).sort((a, b) => b.energy - a.energy)
})

// Time-of-use bands with energy distribution
const timeBandsWithEnergy = computed(() => {
  if (!timeBands.value.length) return []
  const sessions = filteredSessions.value
  const bandEnergy = {}
  for (const b of timeBands.value) bandEnergy[b.id] = { energy: 0, cost: 0 }
  for (const s of sessions) {
    if (s.time_band_id && bandEnergy[s.time_band_id]) {
      bandEnergy[s.time_band_id].energy += s.energy_kwh || 0
      bandEnergy[s.time_band_id].cost += s.cost || 0
    }
  }
  const maxE = Math.max(1, ...Object.values(bandEnergy).map(b => b.energy))
  return timeBands.value.map(b => ({
    ...b,
    energy: bandEnergy[b.id]?.energy || 0,
    cost: bandEnergy[b.id]?.cost || 0,
    pct: ((bandEnergy[b.id]?.energy || 0) / maxE) * 100,
  }))
})

// Formatting
function formatDate(ts) {
  if (!ts) return '—'
  return parseUTC(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
function formatTimeRange(start, end) {
  const s = start ? parseUTC(start).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : ''
  const e = end ? parseUTC(end).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : 'ongoing'
  return `${s} – ${e}`
}

// Edit session
function editSession(session) {
  editingSession.value = session
  editForm.value = {
    tier_id: session.tier_id || (availableTiers.value[0]?.id || 'home_grid'),
    energy_kwh: session.energy_kwh,
    cost: session.cost,
    note: session.note || '',
  }
  editError.value = ''
}

async function saveSession() {
  saving.value = true
  editError.value = ''
  try {
    const s = editingSession.value
    const body = {
      tier_id: editForm.value.tier_id,
      energy_kwh: editForm.value.energy_kwh || undefined,
      peak_power_kw: s.peak_power_kw ?? undefined,
      note: editForm.value.note || undefined,
    }
    if (s.id) {
      // Update existing
      await api('PUT', `/api/vehicles/${props.vin}/charging-costs/${s.id}`, body)
    } else {
      // Create new for a session without cost record
      body.start_ts = s.start_ts
      body.end_ts = s.end_ts || undefined
      await api('POST', `/api/vehicles/${props.vin}/charging-costs`, body)
    }
    await loadData()
    editingSession.value = null
  } catch (e) {
    editError.value = e.message || 'Failed to save'
  } finally {
    saving.value = false
  }
}

// Detect charge sessions from snapshots (same algorithm as HistoryTab)
function detectSessionsFromSnapshots(snapshots) {
  const sessions = []
  let inSession = false
  let startIdx = -1
  let peakKw = 0
  for (let i = 0; i < snapshots.length; i++) {
    const snap = snapshots[i]
    if (snap.battery_is_charging && !inSession) {
      inSession = true
      startIdx = i
      peakKw = snap.battery_charging_power_kw != null ? snap.battery_charging_power_kw : 0
    } else if (snap.battery_is_charging && inSession) {
      // Track peak while session continues
      const power = snap.battery_charging_power_kw
      if (power != null && power > peakKw) peakKw = power
    } else if (!snap.battery_is_charging && inSession) {
      inSession = false
      const startSnap = snapshots[startIdx]
      const endSnap = snapshots[i - 1] || snap
      const startEnergy = startSnap.battery_dump_energy != null ? startSnap.battery_dump_energy / 1000 : null
      const endEnergy = endSnap.battery_dump_energy != null ? endSnap.battery_dump_energy / 1000 : null
      const energy = (startEnergy != null && endEnergy != null) ? Math.abs(endEnergy - startEnergy) : null
      sessions.push({
        start_ts: startSnap.timestamp,
        end_ts: endSnap.timestamp,
        energy_kwh: energy != null ? Math.round(energy * 100) / 100 : null,
        start_soc: startSnap.battery_soc,
        end_soc: endSnap.battery_soc,
        peak_power_kw: peakKw > 0 ? Math.round(peakKw * 10) / 10 : null,
      })
    }
  }
  // Handle session still in progress at end of data
  if (inSession && startIdx >= 0) {
    const startSnap = snapshots[startIdx]
    const endSnap = snapshots[snapshots.length - 1]
    const startEnergy = startSnap.battery_dump_energy != null ? startSnap.battery_dump_energy / 1000 : null
    const endEnergy = endSnap.battery_dump_energy != null ? endSnap.battery_dump_energy / 1000 : null
    const energy = (startEnergy != null && endEnergy != null) ? Math.abs(endEnergy - startEnergy) : null
    sessions.push({
      start_ts: startSnap.timestamp,
      end_ts: null,
      energy_kwh: energy != null ? Math.round(energy * 100) / 100 : null,
      start_soc: startSnap.battery_soc,
      end_soc: endSnap.battery_soc,
      peak_power_kw: peakKw > 0 ? Math.round(peakKw * 10) / 10 : null,
    })
  }
  return sessions
}

// Data loading
async function loadData() {
  loading.value = true
  try {
    // Build date range for selected month
    const y = selectedMonth.value.getFullYear()
    const m = selectedMonth.value.getMonth()
    const fromDate = `${y}-${String(m + 1).padStart(2, '0')}-01`
    const lastDay = new Date(y, m + 1, 0).getDate()
    const toDate = `${y}-${String(m + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`

    const [tiersData, costs, prefs, historyData] = await Promise.all([
      api('GET', '/api/charging/tiers'),
      api('GET', `/api/vehicles/${props.vin}/charging-costs`),
      api('GET', '/api/preferences'),
      api('GET', `/api/vehicles/${props.vin}/history?from_date=${fromDate}&to_date=${toDate}&max_points=5000`),
    ])
    availableTiers.value = tiersData.tiers || []
    timeBands.value = tiersData.time_bands || []
    homePricingMode.value = tiersData.home_pricing_mode || 'flat'
    sessionCosts.value = costs || []
    hasSolarPanels.value = prefs.has_solar_panels ?? false

    // Detect sessions from snapshots
    const snapshots = historyData?.snapshots || historyData || []
    detectedSessions.value = detectSessionsFromSnapshots(snapshots)
  } catch { /* ignore */ }
  loading.value = false
  await nextTick()
  renderCharts()
}

// Charts
function destroyCharts() {
  charts.forEach(c => c.destroy())
  charts = []
}

function getChartColors() {
  const s = getComputedStyle(document.documentElement)
  return {
    grid: s.getPropertyValue('--chart-grid').trim() || '#1c2135',
    tick: s.getPropertyValue('--chart-tick').trim() || '#4a5468',
    label: s.getPropertyValue('--label').trim() || '#6a748a',
  }
}

function renderCharts() {
  destroyCharts()
  const sessions = [...filteredSessions.value].reverse() // chronological order (oldest first)
  const cc = getChartColors()

  // Energy per session bar chart
  if (energyCanvas.value && sessions.length) {
    const ctx = energyCanvas.value.getContext('2d')
    const tierColors = { home_grid: '#66bb6a', home_solar: '#fdd835', public_ac: '#42a5f5', public_dc: '#7c6aff' }
    charts.push(new Chart(ctx, {
      type: 'bar',
      data: {
        labels: sessions.map(s => formatDate(s.start_ts)),
        datasets: [{
          data: sessions.map(s => s.energy_kwh || 0),
          backgroundColor: sessions.map(s => tierColors[s.tier_id] || '#888'),
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: (ctx) => {
                const s = sessions[ctx.dataIndex]
                if (s.peak_power_kw != null) return `Peak: ${s.peak_power_kw.toFixed(1)} kW`
                return ''
              },
            },
          },
        },
        scales: {
          x: { ticks: { color: cc.tick, font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: cc.tick }, grid: { color: cc.grid } },
        },
      },
    }))
  }

  // Daily cost line chart
  if (costCanvas.value && sessions.length) {
    const ctx = costCanvas.value.getContext('2d')
    // Aggregate by day
    const daily = {}
    for (const s of sessions) {
      const day = parseUTC(s.start_ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
      daily[day] = (daily[day] || 0) + (s.cost || 0)
    }
    const labels = Object.keys(daily)
    const data = labels.map(l => daily[l])
    charts.push(new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data,
          borderColor: '#ffd54f',
          backgroundColor: 'rgba(255,213,79,0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: cc.tick, font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: cc.tick, callback: v => `€${v.toFixed(2)}` }, grid: { color: cc.grid } },
        },
      },
    }))
  }

  // Tier pie chart
  if (pieCanvas.value && sessions.length) {
    const ctx = pieCanvas.value.getContext('2d')
    const tierEnergy = {}
    for (const s of sessions) {
      const tid = s.tier_id || 'unknown'
      tierEnergy[tid] = (tierEnergy[tid] || 0) + (s.energy_kwh || 0)
    }
    const tierColors = { home_grid: '#66bb6a', home_solar: '#fdd835', public_ac: '#42a5f5', public_dc: '#7c6aff', unknown: '#888' }
    const tierLabels = { home_grid: 'Home Grid', home_solar: 'Solar', public_ac: 'Public AC', public_dc: 'Public DC', unknown: 'Unknown' }
    const keys = Object.keys(tierEnergy).filter(k => tierEnergy[k] > 0)
    charts.push(new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: keys.map(k => tierLabels[k] || k),
        datasets: [{
          data: keys.map(k => tierEnergy[k]),
          backgroundColor: keys.map(k => tierColors[k] || '#888'),
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: cc.label, font: { size: 11 } } },
        },
      },
    }))
  }
}

// Resize handler with debounce
function handleResize() {
  clearTimeout(resizeTimeout)
  resizeTimeout = setTimeout(() => {
    renderCharts()
  }, 300)
}

// Lifecycle
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  clearTimeout(resizeTimeout)
})
watch(() => props.vin, loadData)
watch(selectedMonth, loadData)
</script>

<style scoped>
.charging-tab { width: 100%; }
.loading-center { display: flex; justify-content: center; padding: 48px; }
.charging-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.header-title h2 { font-size: 20px; font-weight: 700; color: var(--text); margin: 0; }
.header-title p { font-size: 12px; color: var(--muted); margin: 2px 0 0; }
.month-nav { display: flex; align-items: center; gap: 8px; }
.month-label { font-size: 14px; font-weight: 600; color: var(--text); min-width: 130px; text-align: center; }
.toolbar-btn { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 6px; color: var(--text); cursor: pointer; display: flex; align-items: center; transition: all 0.15s; }
.toolbar-btn:disabled { opacity: 0.4; cursor: default; }
.toolbar-btn:hover:not(:disabled) { background: var(--btn-bg); color: var(--cyan); border-color: var(--cyan); }

/* KPI — aligned with the Data History tab */
.summary-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }
@media (min-width: 768px) {
  .summary-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
}
.summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; text-align: center; }
.summary-value { font-size: 20px; font-weight: 700; }
.summary-label { font-size: 10px; color: var(--muted); margin-top: 4px; }

/* Charts */
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; margin-bottom: 12px; }
.charts-grid-3 { grid-template-columns: 1fr; }
@media (min-width: 640px) {
  .charts-grid-3 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
}
.chart-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }
.chart-card.wide { grid-column: 1 / -1; }
.charts-grid + .chart-card.wide,
.chart-card.wide + .chart-card.wide { margin-top: 12px; }
.chart-header { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 10px; }
.chart-icon { opacity: 0.7; }
.chart-area { height: 200px; position: relative; }

/* TOU bands */
.tou-card { margin-bottom: 12px; }
.tou-bands { display: flex; flex-direction: column; gap: 8px; }
.tou-band-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.tou-color { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.tou-name { min-width: 50px; color: var(--text); font-weight: 500; }
.tou-price { min-width: 80px; color: var(--muted); }
.tou-bar-track { flex: 1; height: 8px; background: var(--bg); border-radius: 4px; overflow: hidden; }
.tou-bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.tou-energy { min-width: 60px; text-align: right; color: var(--text); }
.tou-cost { min-width: 50px; text-align: right; color: var(--muted); }

/* Charging by location */
.location-list { display: flex; flex-direction: column; }
.location-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.location-row:last-child { border-bottom: none; }
.loc-name { flex: 1; color: var(--text); font-weight: 500; }
.loc-stat { color: var(--muted); min-width: 70px; text-align: right; }
.loc-cost { color: var(--text); min-width: 60px; text-align: right; font-weight: 600; }

/* Monthly summary */
.monthly-table-wrap { overflow-x: auto; }
.monthly-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.monthly-table th { text-align: left; color: var(--muted); font-weight: 600; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.monthly-table td { padding: 6px 8px; color: var(--text); border-bottom: 1px solid var(--border); }
.empty-row { color: var(--muted); text-align: center; padding: 20px; }

/* Session list */
.session-list { display: flex; flex-direction: column; }
/* Desktop: aligned table with header */
.session-head, .session-row {
  display: grid;
  grid-template-columns: 1.1fr 1.4fr 0.9fr 0.8fr 1.1fr 1fr 0.9fr 40px;
  gap: 12px; align-items: center;
}
.session-head { padding: 0 0 8px; border-bottom: 1px solid var(--border); }
.session-head span { font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); font-weight: 600; }
.session-row { padding: 10px 0; border-bottom: 1px solid var(--border); }
.session-row:last-child { border-bottom: none; }
.cell { font-size: 13px; color: var(--text); min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.cell-date { font-weight: 500; }
.cell-time { font-size: 12px; color: var(--muted); }
.cell-energy { font-weight: 600; color: var(--green); }
.cell-peak { font-size: 12px; color: var(--amber); }
.cell-cost { font-weight: 600; color: var(--amber); }
.cell-edit { display: flex; justify-content: flex-end; }
.cost-none { color: var(--muted); }
.tier-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 500; }
.tier-home_grid { background: rgba(102,187,106,0.15); color: #66bb6a; }
.tier-home_solar { background: rgba(253,216,53,0.15); color: #fdd835; }
.tier-public_ac { background: rgba(66,165,245,0.15); color: #42a5f5; }
.tier-public_dc { background: rgba(124,106,255,0.15); color: #7c6aff; }
.tier-none { background: rgba(136,136,136,0.1); color: #888; }
.edit-btn { background: none; border: 1px solid var(--border); border-radius: 6px; padding: 4px 6px; color: var(--muted); cursor: pointer; display: flex; align-items: center; }
.edit-btn:hover { color: var(--text); border-color: var(--text); }

/* Mobile: each session becomes a compact labelled card */
@media (max-width: 640px) {
  .session-head { display: none; }
  .session-row {
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 8px 12px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 8px;
  }
  .session-row:last-child { border-bottom: 1px solid var(--border); }
  .cell { display: flex; flex-direction: column; font-size: 13px; }
  .cell[data-label]::before {
    content: attr(data-label);
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--muted); margin-bottom: 2px; font-weight: 600;
  }
  .cell-date { grid-column: 1; grid-row: 1; }
  .cell-time { grid-column: 2; grid-row: 1; }
  .cell-energy { grid-column: 1; grid-row: 2; }
  .cell-peak { grid-column: 2; grid-row: 2; }
  .cell-cost { grid-column: 3; grid-row: 2; }
  .cell-tier { grid-column: 4; grid-row: 2; display: flex; align-items: center; width: fit-content; }
  .tier-badge { display: inline-block; }
  .cell-edit { grid-column: 4; grid-row: 1; justify-self: flex-end; }
}

/* Modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.modal-dialog { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; width: 90%; max-width: 380px; }
.modal-dialog h3 { font-size: 16px; font-weight: 700; color: var(--text); margin: 0 0 4px; }
.edit-date { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.form-group input, .form-group select { width: 100%; background: var(--input); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; color: var(--text); font-size: 13px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-cancel { background: var(--btn-bg); border: 1px solid var(--btn-border); border-radius: 8px; padding: 8px 16px; color: var(--muted); cursor: pointer; font-size: 13px; }
.btn-save { background: var(--green); border: none; border-radius: 8px; padding: 8px 16px; color: #000; font-weight: 600; cursor: pointer; font-size: 13px; }
.btn-save:disabled { opacity: 0.5; }
.field-error { color: #ff5252; font-size: 12px; margin-top: 8px; }

@media (max-width: 640px) {
  .charts-grid { grid-template-columns: 1fr; }
}
</style>
