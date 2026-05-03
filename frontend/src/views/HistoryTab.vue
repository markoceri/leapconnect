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
          :disabled="p.days > 1 && p.days !== 0 && allSnapshots.length < 2"
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

    <!-- KPI cards -->
    <div class="summary-grid">
      <div v-for="s in kpiCards" :key="s.label" class="summary-card">
        <div class="summary-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="summary-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- Charts -->
    <template v-if="viewMode === 'chart'">
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
        <div class="chart-card">
          <div class="chart-header"><MapPin :size="16" class="chart-icon" /> Trip map (lat/lon)</div>
          <div class="chart-area"><canvas ref="tripMapCanvas" /></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><BatteryWarning :size="16" class="chart-icon" /> Vampire drain (SOC loss while parked)</div>
          <div class="chart-area"><canvas ref="vampireCanvas" /></div>
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

    <div class="history-note" v-if="allSnapshots.length">
      Real data collected from vehicle · {{ allSnapshots.length }} snapshots available
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
import { Battery, Map, Zap, Route, Thermometer, BarChart3, Table2, Gauge, Clock, CircleDot, MapPin, Circle, BatteryWarning } from 'lucide-vue-next'

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
// Data source
// ---------------------------------------------------------------------------
const allSnapshots = ref([])
const allData = ref([])
const todaySnapshots = ref([])

async function fetchHistory() {
  if (!props.vin) return
  try {
    const [dailyRes, snapshotRes, allSnapshotRes] = await Promise.all([
      api('GET', `/api/vehicles/${props.vin}/history/daily?days=3650`),
      api('GET', `/api/vehicles/${props.vin}/history?days=1`),
      api('GET', `/api/vehicles/${props.vin}/history?days=3650`),
    ])
    const daily = dailyRes.daily || []
    const snaps = snapshotRes.snapshots || []
    const allSnaps = allSnapshotRes.snapshots || []

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
  const [, m, d] = isoDate.split('-')
  return `${d}/${m}`
}

function formatTimestamp(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

watch(() => props.vin, fetchHistory)
onMounted(fetchHistory)

// ---------------------------------------------------------------------------
// Filtered snapshots for selected period
// ---------------------------------------------------------------------------
const filteredSnapshots = computed(() => {
  const days = periods[period.value].days
  if (days === 0) return allSnapshots.value
  const now = new Date()
  let since
  if (days === 1) {
    since = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  } else {
    since = new Date(now.getTime() - days * 86400000)
  }
  return allSnapshots.value.filter(s => new Date(s.timestamp) >= since)
})

// ---------------------------------------------------------------------------
// Visible display data based on selected period
// ---------------------------------------------------------------------------
const isToday = computed(() => periods[period.value].days === 1)

const data = computed(() => {
  if (isToday.value) return todaySnapshots.value
  const days = periods[period.value].days
  return days === 0 ? allData.value : allData.value.slice(-days)
})

const tableData = computed(() => [...data.value].reverse())

// ---------------------------------------------------------------------------
// KPI Cards
// ---------------------------------------------------------------------------
const kpiCards = computed(() => {
  const snaps = filteredSnapshots.value
  if (!snaps.length) return []

  let energyUsed = 0
  let energyCharged = 0
  for (let i = 1; i < snaps.length; i++) {
    const curr = (snaps[i].battery_dump_energy ?? 0) / 1000
    const prev = (snaps[i - 1].battery_dump_energy ?? 0) / 1000
    const delta = curr - prev
    if (delta < 0) energyUsed += Math.abs(delta)
    else energyCharged += delta
  }

  const mileages = snaps.map(s => s.drive_total_mileage).filter(m => m != null && m > 0)
  const totalKm = mileages.length >= 2 ? Math.max(0, mileages[mileages.length - 1] - mileages[0]) : 0

  const consumption = totalKm > 0 ? (energyUsed / totalKm) * 100 : 0

  let chargeSessions = 0
  for (let i = 1; i < snaps.length; i++) {
    if (snaps[i - 1].battery_is_charging && !snaps[i].battery_is_charging) chargeSessions++
  }
  if (snaps.length > 0 && snaps[snaps.length - 1].battery_is_charging) chargeSessions++

  const costPerKwh = 0.25
  const cost = energyCharged * costPerKwh

  const co2Saved = totalKm * 0.12

  let regenEnergy = 0
  for (let i = 1; i < snaps.length; i++) {
    const curr = (snaps[i].battery_dump_energy ?? 0) / 1000
    const prev = (snaps[i - 1].battery_dump_energy ?? 0) / 1000
    const delta = curr - prev
    if (delta > 0 && !snaps[i].vehicle_is_plugged) regenEnergy += delta
  }
  const regenEfficiency = energyUsed > 0 ? (regenEnergy / energyUsed) * 100 : 0

  const highSocSnaps = snaps.filter(s => (s.battery_soc ?? 0) >= 95 && s.battery_expected_mileage)
  const avgRangeAtFull = highSocSnaps.length > 0
    ? Math.round(highSocSnaps.reduce((s, x) => s + x.battery_expected_mileage, 0) / highSocSnaps.length)
    : null

  const batteryCapacityKwh = snaps[0]?.battery_dump_energy ? (snaps[0].battery_dump_energy / 1000) / ((snaps[0].battery_soc ?? 100) / 100) : null
  const realAutonomy = consumption > 0 && batteryCapacityKwh ? Math.round((batteryCapacityKwh / consumption) * 100) : null

  return [
    { label: 'km driven', value: Math.round(totalKm).toLocaleString(), color: '#00d4ff' },
    { label: 'Energy used', value: `${energyUsed.toFixed(1)} kWh`, color: '#ffab40' },
    { label: 'Energy charged', value: `${energyCharged.toFixed(1)} kWh`, color: '#00e676' },
    { label: 'Charge sessions', value: chargeSessions, color: '#7c6aff' },
    { label: 'kWh/100km', value: consumption > 0 ? consumption.toFixed(1) : '\u2014', color: '#ff7043' },
    { label: 'Cost (\u20ac)', value: cost > 0 ? `\u20ac${cost.toFixed(2)}` : '\u2014', color: '#ffd54f' },
    { label: 'CO\u2082 saved', value: co2Saved > 0 ? `${co2Saved.toFixed(1)} kg` : '\u2014', color: '#4caf50' },
    { label: 'Regen efficiency', value: regenEfficiency > 0 ? `${regenEfficiency.toFixed(0)}%` : '\u2014', color: '#26c6da' },
    { label: 'Range @100%', value: avgRangeAtFull ? `${avgRangeAtFull} km` : '\u2014', color: '#ab47bc' },
    { label: 'Real autonomy', value: realAutonomy ? `${realAutonomy} km` : '\u2014', color: '#5c6bc0' },
  ]
})

// ---------------------------------------------------------------------------
// Heatmap data (7 days x 24 hours)
// ---------------------------------------------------------------------------
const heatmapData = computed(() => {
  const grid = Array.from({ length: 7 }, () => Array(24).fill(0))
  for (const s of filteredSnapshots.value) {
    if (s.drive_is_parked === false) {
      const d = new Date(s.timestamp)
      const dow = (d.getDay() + 6) % 7
      const hour = d.getHours()
      grid[dow][hour]++
    }
  }
  return grid
})

function heatmapColor(val) {
  if (val === 0) return '#1a1f2e'
  if (val === 1) return '#1b3a2a'
  if (val <= 3) return '#2e7d52'
  if (val <= 6) return '#43a047'
  return '#66bb6a'
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
        sessions.push({
          label: formatTimestamp(snaps[sessionStart].timestamp),
          energy: Math.round(energyAdded * 10) / 10,
          startSoc: snaps[sessionStart].battery_soc ?? 0,
          endSoc: snaps[i].battery_soc ?? 0,
        })
      }
    }
  }
  if (inSession && snaps.length > 0) {
    const startEnergy = (snaps[sessionStart].battery_dump_energy ?? 0) / 1000
    const endEnergy = (snaps[snaps.length - 1].battery_dump_energy ?? 0) / 1000
    const energyAdded = endEnergy - startEnergy
    if (energyAdded > 0) {
      sessions.push({
        label: formatTimestamp(snaps[sessionStart].timestamp) + ' (ongoing)',
        energy: Math.round(energyAdded * 10) / 10,
        startSoc: snaps[sessionStart].battery_soc ?? 0,
        endSoc: snaps[snaps.length - 1].battery_soc ?? 0,
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
        const hours = (new Date(snaps[i - 1].timestamp) - new Date(snaps[parkedStart].timestamp)) / 3600000
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
const tripMapCanvas = ref(null)
const vampireCanvas = ref(null)
const tirePressureCanvas = ref(null)
const tireTempCanvas = ref(null)
const tireDiffCanvas = ref(null)

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
      data: { labels, datasets: [{ data: d.map(x => x.range), borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.07)', fill: true, tension: 0.4, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2 }] },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Km
  if (kmCanvas.value) {
    charts.push(new Chart(kmCanvas.value, {
      type: 'bar',
      data: { labels, datasets: [{ data: d.map(x => x.kmDriven), backgroundColor: 'rgba(124,106,255,0.45)', borderColor: '#7c6aff', borderWidth: 1, borderRadius: 4 }] },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Power
  if (powerCanvas.value) {
    charts.push(new Chart(powerCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Charging', data: d.map(x => x.chargingPower), borderColor: '#66bb6a', backgroundColor: 'rgba(102,187,106,0.08)', fill: true, tension: 0.3, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2 },
          { label: 'Discharging', data: d.map(x => -x.dischargingPower), borderColor: '#ef5350', backgroundColor: 'rgba(239,83,80,0.08)', fill: true, tension: 0.3, pointRadius: pointR, pointHoverRadius: 5, borderWidth: 2 },
        ],
      },
      options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} kW` } } } },
    }))
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
        options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, min: 0, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v}` } } } },
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
        options: { ...chartDefaults, scales: { x: { ...chartDefaults.scales.x, title: { display: true, text: '\u00b0C', color: '#4a5468' } }, y: { ...chartDefaults.scales.y, min: 0, title: { display: true, text: 'kWh/100km', color: '#4a5468' } } } },
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
        options: { ...chartDefaults, scales: { x: { ...chartDefaults.scales.x, title: { display: true, text: 'km/h', color: '#4a5468' } }, y: { ...chartDefaults.scales.y, min: 0, title: { display: true, text: 'kWh/100km', color: '#4a5468' } } } },
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
        options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} km` } } } },
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
          ...chartDefaults,
          plugins: {
            ...chartDefaults.plugins,
            tooltip: {
              ...chartDefaults.plugins.tooltip,
              callbacks: { afterLabel: (ctx) => { const s = sessions[ctx.dataIndex]; return `SOC: ${s.startSoc}% \u2192 ${s.endSoc}%` } },
            },
          },
          scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} kWh` } } },
        },
      }))
    }
  }

  // ===== VEHICLE USAGE =====

  // Usage pie
  if (usagePieCanvas.value && snaps.length > 0) {
    const parked = snaps.filter(s => s.drive_is_parked === true).length
    const driving = snaps.length - parked
    charts.push(new Chart(usagePieCanvas.value, {
      type: 'doughnut',
      data: {
        labels: ['Parked', 'In use'],
        datasets: [{ data: [parked, driving], backgroundColor: ['#1c2240', '#00d4ff'], borderColor: ['#2a3050', '#00d4ff'], borderWidth: 1 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: true, position: 'bottom', labels: { color: '#5c6478', font: { size: 11 } } }, tooltip: { ...chartDefaults.plugins.tooltip } },
      },
    }))
  }

  // Trip map (scatter lat/lon)
  if (tripMapCanvas.value) {
    const mapPoints = snaps.filter(s => s.vehicle_latitude && s.vehicle_longitude).map(s => ({
      x: s.vehicle_longitude,
      y: s.vehicle_latitude,
      speed: s.drive_speed ?? 0,
    }))
    if (mapPoints.length > 0) {
      charts.push(new Chart(tripMapCanvas.value, {
        type: 'scatter',
        data: {
          datasets: [{
            data: mapPoints,
            backgroundColor: mapPoints.map(p => p.speed > 50 ? '#ef5350' : p.speed > 20 ? '#ffab40' : '#66bb6a'),
            pointRadius: 4,
            pointHoverRadius: 6,
          }],
        },
        options: {
          ...chartDefaults,
          scales: {
            x: { ...chartDefaults.scales.x, title: { display: true, text: 'Longitude', color: '#4a5468' } },
            y: { ...chartDefaults.scales.y, title: { display: true, text: 'Latitude', color: '#4a5468' } },
          },
          plugins: { ...chartDefaults.plugins, tooltip: { ...chartDefaults.plugins.tooltip, callbacks: { label: (ctx) => `Speed: ${mapPoints[ctx.dataIndex].speed} km/h` } } },
        },
      }))
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
        options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v}%/day` } } } },
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
        options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} bar` } } } },
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
        options: { ...chartDefaults, scales: { x: { ...chartDefaults.scales.x, title: { display: true, text: '\u00b0C', color: '#4a5468' } }, y: { ...chartDefaults.scales.y, title: { display: true, text: 'Avg pressure (bar)', color: '#4a5468' } } } },
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
        options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } }, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} bar` } } } },
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
        ...chartDefaults,
        plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#5c6478', font: { size: 10 }, boxWidth: 20 } } },
        scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v}\u00b0C` } }, y2: { position: 'right', grid: { display: false }, ticks: { color: '#4a5468', font: { size: 10 }, callback: v => `${v}kWh` } } },
      },
    }))
  }
}

watch(data, () => { if (viewMode.value === 'chart') nextTick(buildCharts) })
watch(filteredSnapshots, () => { if (viewMode.value === 'chart') nextTick(buildCharts) })
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
  background: #0d1018;
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
