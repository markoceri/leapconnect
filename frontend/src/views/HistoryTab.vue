<template>
  <div class="history-tab">
    <!-- Header + period selector -->
    <div class="history-header">
      <div>
        <h2>Storico dati</h2>
        <p>Analisi delle performance nel tempo</p>
      </div>
      <div class="period-selector">
        <button
          v-for="(p, i) in periods"
          :key="i"
          class="period-btn"
          :class="{ active: period === i }"
          @click="period = i"
        >{{ p.label }}</button>
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
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-header"><span class="chart-icon">🔋</span> Livello batteria (%)</div>
        <div class="chart-area"><canvas ref="batteryCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><span class="chart-icon">🗺</span> Autonomia stimata (km)</div>
        <div class="chart-area"><canvas ref="rangeCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><span class="chart-icon">⚡</span> Energia consumata per giorno</div>
        <div class="chart-area"><canvas ref="energyCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><span class="chart-icon">🛣</span> km percorsi per giorno</div>
        <div class="chart-area"><canvas ref="kmCanvas" /></div>
      </div>
    </div>

    <!-- Full-width temp chart -->
    <div class="chart-card wide">
      <div class="chart-header"><span class="chart-icon">🌡</span> Temperatura esterna vs Consumo energetico</div>
      <div class="chart-area tall"><canvas ref="tempCanvas" /></div>
    </div>

    <div class="history-note">
      I dati storici sono generati localmente a scopo dimostrativo. In futuro verranno raccolti dal backend.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const props = defineProps({
  status: { type: Object, required: true },
})

const periods = [
  { label: '7 giorni', days: 7 },
  { label: '30 giorni', days: 30 },
  { label: '90 giorni', days: 90 },
]
const period = ref(1)

// Generate synthetic history data based on current status
const allData = ref([])
onMounted(() => {
  const soc = props.status?.battery?.soc ?? 60
  const odo = props.status?.driving?.total_mileage ?? 3000
  allData.value = generateHistory(odo, soc)
})

function generateHistory(startOdo, startBattery) {
  const data = []
  let battery = startBattery || 75
  let odo = startOdo || 0
  for (let i = 89; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const label = d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' })
    const driven = Math.random() * 30
    odo += driven
    const charged = Math.random() > 0.55
    battery = Math.max(10, Math.min(100, battery - driven * 0.5 + (charged ? Math.random() * 45 + 15 : 0)))
    data.push({
      date: label,
      battery: Math.round(battery),
      range: Math.round(battery * 2.06),
      kmDriven: Math.round(driven),
      energy: parseFloat((driven * (0.12 + Math.random() * 0.10)).toFixed(1)),
      temp: Math.round(8 + Math.random() * 14),
      odometer: Math.round(odo),
    })
  }
  return data
}

const data = computed(() => allData.value.slice(-periods[period.value].days))

const summaryCards = computed(() => {
  const d = data.value
  const totalKm = d.reduce((s, x) => s + x.kmDriven, 0)
  const totalEnergy = d.reduce((s, x) => s + x.energy, 0)
  const avgBattery = Math.round(d.reduce((s, x) => s + x.battery, 0) / (d.length || 1))
  const sessions = d.filter(x => x.kmDriven > 1).length
  return [
    { label: 'km percorsi', value: Math.round(totalKm).toLocaleString(), color: '#00d4ff' },
    { label: 'Energia usata', value: `${totalEnergy.toFixed(1)} kWh`, color: '#ffab40' },
    { label: 'Batteria media', value: `${avgBattery}%`, color: '#00e676' },
    { label: 'Sessioni guida', value: sessions, color: '#7c6aff' },
  ]
})

// Chart refs
const batteryCanvas = ref(null)
const rangeCanvas = ref(null)
const energyCanvas = ref(null)
const kmCanvas = ref(null)
const tempCanvas = ref(null)

const charts = []

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
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

  // Battery
  if (batteryCanvas.value) {
    charts.push(new Chart(batteryCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: d.map(x => x.battery),
          borderColor: '#00e676', backgroundColor: 'rgba(0,230,118,0.08)',
          fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2,
        }],
      },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, min: 0, max: 100, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v}%` } } } },
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
          fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2,
        }],
      },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} km` } } } },
    }))
  }

  // Energy
  if (energyCanvas.value) {
    charts.push(new Chart(energyCanvas.value, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: d.map(x => x.energy),
          backgroundColor: d.map(x => x.energy > 5 ? 'rgba(255,171,64,0.7)' : 'rgba(255,171,64,0.35)'),
          borderColor: '#ffab40', borderWidth: 1, borderRadius: 4,
        }],
      },
      options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, ticks: { ...chartDefaults.scales.y.ticks, callback: v => `${v} kWh` } } } },
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

  // Temp vs Energy
  if (tempCanvas.value) {
    charts.push(new Chart(tempCanvas.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Temperatura', data: d.map(x => x.temp),
            borderColor: '#ff7043', backgroundColor: 'rgba(255,112,67,0.06)',
            fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2,
          },
          {
            label: 'Consumo', data: d.map(x => x.energy),
            borderColor: '#ffab40', backgroundColor: 'transparent',
            tension: 0.4, pointRadius: 0, borderWidth: 1.5, borderDash: [4, 3],
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

watch(data, () => { nextTick(buildCharts) })
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
  justify-content: space-between;
  align-items: center;
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
.period-btn.active {
  background: #1c2240;
  color: #00d4ff;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
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
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.chart-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
}
.chart-card.wide { grid-column: span 2; }
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

.history-note {
  font-size: 11px;
  color: var(--muted2);
  text-align: center;
  padding: 8px;
  background: #0d1018;
  border-radius: 8px;
}

@media (max-width: 768px) {
  .charts-grid { grid-template-columns: 1fr; }
  .chart-card.wide { grid-column: span 1; }
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
