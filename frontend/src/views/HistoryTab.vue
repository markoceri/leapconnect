<template>
  <div class="history-tab">
    <!-- Header + period selector -->
    <div class="history-header">
      <div>
        <h2>Data History</h2>
        <p>Performance analysis over time</p>
      </div>
      <div class="period-selector">
        <button
          v-for="(p, i) in periods"
          :key="i"
          class="period-btn"
          :class="{ active: period === i }"
          :disabled="p.days > 1 && p.days !== 0 && allData.length < 2"
          @click="period = i"
        >{{ p.label }}</button>
      </div>
      <div class="view-toggle">
        <button class="view-btn" :class="{ active: viewMode === 'chart' }" @click="viewMode = 'chart'">
          <BarChart3 :size="14" /> Charts
        </button>
        <button class="view-btn" :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">
          <Table2 :size="14" /> Table
        </button>
      </div>
    </div>

    <!-- Summary cards -->
    <div class="summary-grid">
      <div v-for="s in summaryCards" :key="s.label" class="summary-card">
        <div class="summary-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="summary-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- Charts 2-col grid -->
    <template v-if="viewMode === 'chart'">
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

      <!-- Full-width temp chart -->
      <div class="chart-card wide">
        <div class="chart-header"><Thermometer :size="16" class="chart-icon" /> Outside temperature vs Energy consumption</div>
        <div class="chart-area tall"><canvas ref="tempCanvas" /></div>
      </div>
    </template>

    <!-- Table view -->
    <div v-else class="data-table-wrapper">
      <div class="data-table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ isToday ? 'Time' : 'Date' }}</th>
              <th>Battery %</th>
              <th>Range km</th>
              <th>km Driven</th>
              <th>Battery kWh</th>
              <th>Temp °C</th>
              <th>Charges</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in tableData" :key="i">
              <td class="td-date">{{ row.date }}</td>
              <td><span class="td-badge" style="--c:#00e676">{{ row.battery }}</span></td>
              <td>{{ row.range }}</td>
              <td>{{ row.kmDriven }}</td>
              <td>{{ row.batteryEnergy }}</td>
              <td>{{ row.temp }}</td>
              <td>{{ row.chargeSessions }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="history-note" v-if="allData.length || todaySnapshots.length">
      Real data collected from vehicle · {{ allData.length }} days available
    </div>
    <div class="history-note" v-else>
      No data yet. Enable automatic collection in Settings to populate history.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import { api } from '../composables/useApi'
import { Battery, Map, Zap, Route, Thermometer, BarChart3, Table2 } from 'lucide-vue-next'

Chart.register(...registerables)

const props = defineProps({
  status: { type: Object, required: true },
  vin: { type: String, default: null },
})

const periods = [
  { label: 'Today', days: 1 },
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: 'All', days: 0 },
]
const period = ref(0)
const viewMode = ref('chart')

// ---------------------------------------------------------------------------
// Data source: real API → fallback to mock
// ---------------------------------------------------------------------------
const allData = ref([])
const todaySnapshots = ref([])

async function fetchHistory() {
  if (!props.vin) return
  try {
    const [dailyRes, snapshotRes] = await Promise.all([
      api('GET', `/api/vehicles/${props.vin}/history/daily?days=3650`),
      api('GET', `/api/vehicles/${props.vin}/history?days=1`),
    ])
    const daily = dailyRes.daily || []
    const snaps = snapshotRes.snapshots || []

    todaySnapshots.value = snaps.map(s => ({
      date: formatTimestamp(s.timestamp),
      battery: s.battery_soc ?? 0,
      range: s.battery_expected_mileage ?? 0,
      kmDriven: 0,
      batteryEnergy: (s.battery_dump_energy ?? 0) / 1000.0,
      chargingPower: s.battery_charging_power_kw ?? 0,
      dischargingPower: s.battery_discharge_power_kw ?? 0,
      temp: s.climate_outdoor_temp ?? 0,
      chargeSessions: s.vehicle_is_charging ? 1 : 0,
      sampleCount: 1,
    }))

    if (daily.length > 0) {
      allData.value = daily.map(d => ({
        date: formatDate(d.date),
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
  } catch (err) {
    console.error('[HistoryTab] fetchHistory failed:', err)
  }
}

function formatDate(isoDate) {
  // "2026-04-20" → "20/04"
  const [, m, d] = isoDate.split('-')
  return `${d}/${m}`
}

function formatTimestamp(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

// Reload when vin changes
watch(() => props.vin, fetchHistory)
onMounted(fetchHistory)

// ---------------------------------------------------------------------------
// Visible slice based on selected period
// ---------------------------------------------------------------------------
const isToday = computed(() => periods[period.value].days === 1)

const data = computed(() => {
  if (isToday.value) return todaySnapshots.value
  const days = periods[period.value].days
  return days === 0 ? allData.value : allData.value.slice(-days)
})

const tableData = computed(() => [...data.value].reverse())

const summaryCards = computed(() => {
  const d = data.value
  if (!d.length) return []
  const totalKm = d.reduce((s, x) => s + x.kmDriven, 0)
  const totalEnergy = d.reduce((s, x) => s + x.batteryEnergy, 0)
  const avgBattery = Math.round(d.reduce((s, x) => s + x.battery, 0) / d.length)
  // Count complete charge sessions (transitions from charging → not charging)
  let chargeSessions = 0
  for (let i = 1; i < d.length; i++) {
    if (d[i - 1].chargeSessions > 0 && d[i].chargeSessions === 0) chargeSessions++
  }
  // If still charging at end, count as ongoing session
  if (d.length > 0 && d[d.length - 1].chargeSessions > 0) chargeSessions++
  return [
    { label: 'km driven', value: Math.round(totalKm).toLocaleString(), color: '#00d4ff' },
    { label: 'Energy used', value: `${totalEnergy.toFixed(1)} kWh`, color: '#ffab40' },
    { label: 'Avg battery', value: `${avgBattery}%`, color: '#00e676' },
    { label: 'Charge sessions', value: chargeSessions, color: '#7c6aff' },
  ]
})

// Chart refs
const batteryCanvas = ref(null)
const rangeCanvas = ref(null)
const kmCanvas = ref(null)
const powerCanvas = ref(null)
const tempCanvas = ref(null)

const charts = []

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#161b2a',
      titleColor: '#8892a8',
      bodyColor: '#e2e6f0',
      borderColor: '#1c2240',
      borderWidth: 1,
      padding: 10,
    },
  },
  scales: {
    x: { grid: { color: '#1c2135', drawTicks: false }, ticks: { color: '#4a5468', font: { size: 10 }, maxTicksLimit: 8 } },
    y: { grid: { color: '#1c2135', drawTicks: false }, ticks: { color: '#4a5468', font: { size: 10 } } },
  },
}

function destroyCharts() {
  charts.forEach(c => c.destroy())
  charts.length = 0
}

function buildCharts() {
  destroyCharts()
  const d = data.value
  if (!d.length) return

  const labels = d.map(x => x.date)
  const pointR = d.length <= 5 ? 4 : 0

  // Battery
  if (batteryCanvas.value) {
    // Detect charging transitions: start (0→1) and end (1→0)
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
          {
            label: 'SOC',
            data: d.map(x => x.battery),
            borderColor: '#00e676', backgroundColor: 'rgba(0,230,118,0.08)',
            fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2,
            yAxisID: 'y',
          },
          {
            label: 'Energy (kWh)',
            data: d.map(x => x.batteryEnergy),
            borderColor: '#ffab40', backgroundColor: 'transparent',
            tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 1.5, borderDash: [4, 3],
            yAxisID: 'y2',
          },
        ],
      },
      options: {
        ...chartDefaults,
        plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } },
        scales: {
          ...chartDefaults.scales,
          y: { ...chartDefaults.scales.y, min: 0, max: 100, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v}%` } },
          y2: { position: 'right', grid: { display: false }, ticks: { color: '#4a5468', font: { size: 10 }, callback: v => `${v} kWh` } },
        },
      },
      plugins: [chargeLinesPlugin],
    }))
  }

  // Range
  if (rangeCanvas.value) {
    charts.push(new Chart(rangeCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: d.map(x => x.range),
          borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.07)',
          fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2,
        }],
      },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Km
  if (kmCanvas.value) {
    charts.push(new Chart(kmCanvas.value, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: d.map(x => x.kmDriven),
          backgroundColor: 'rgba(124,106,255,0.45)', borderColor: '#7c6aff', borderWidth: 1, borderRadius: 4,
        }],
      },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Charging / Discharging Power
  if (powerCanvas.value) {
    charts.push(new Chart(powerCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Charging',
            data: d.map(x => x.chargingPower),
            borderColor: '#66bb6a', backgroundColor: 'rgba(102,187,106,0.08)',
            fill: true, tension: 0.3, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2,
          },
          {
            label: 'Discharging',
            data: d.map(x => -x.dischargingPower),
            borderColor: '#ef5350', backgroundColor: 'rgba(239,83,80,0.08)',
            fill: true, tension: 0.3, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2,
          },
        ],
      },
      options: {
        ...chartDefaults,
        plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } },
        scales: {
          ...chartDefaults.scales,
          y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} kW` } },
        },
      },
    }))
  }

  // Temp vs Energy
  if (tempCanvas.value) {
    charts.push(new Chart(tempCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Temperature', data: d.map(x => x.temp),
            borderColor: '#ff7043', backgroundColor: 'rgba(255,112,67,0.06)',
            fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2,
          },
          {
            label: 'Battery energy', data: d.map(x => x.batteryEnergy),
            borderColor: '#ffab40', backgroundColor: 'transparent',
            tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 1.5, borderDash: [4, 3],
            yAxisID: 'y2',
          },
        ],
      },
      options: {
        ...chartDefaults,
        plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } },
        scales: {
          ...chartDefaults.scales,
          y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v}°C` } },
          y2: { position: 'right', grid: { display: false }, ticks: { color: '#4a5468', font: { size: 10 }, callback: v => `${v}kWh` } },
        },
      },
    }))
  }
}

watch(data, () => { if (viewMode.value === 'chart') nextTick(buildCharts) })
watch(viewMode, (v) => { if (v === 'chart') nextTick(buildCharts) })
onMounted(() => { nextTick(buildCharts) })
onBeforeUnmount(destroyCharts)
</script>

<style scoped>
.history-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.history-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
@media (min-width: 640px) {
  .history-header {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
  }
}
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
.period-selector {
  display: flex;
  gap: 4px;
  background: var(--card);
  border: 1px solid var(--border);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: 10px;
  padding: 4px;
}
.period-btn {
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
.period-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.period-btn.active {
  background: #1c2240;
  color: #00d4ff;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
@media (min-width: 768px) {
  .summary-grid { grid-template-columns: repeat(4, 1fr); }
}
.summary-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  text-align: center;
}
.summary-value { font-size: 22px; font-weight: 700; }
.summary-label { font-size: 11px; color: var(--muted); margin-top: 4px; }

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

.history-note {
  font-size: 11px;
  color: var(--muted2);
  text-align: center;
  padding: 8px;
  background: #0d1018;
  border-radius: 8px;
}
.history-note.real {
  color: #00e676;
  background: rgba(0, 230, 118, 0.06);
  border: 1px solid rgba(0, 230, 118, 0.15);
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
  background: #1c2240;
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
  background: #0d1018;
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
  border-bottom: 1px solid #181d2c;
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


</style>
