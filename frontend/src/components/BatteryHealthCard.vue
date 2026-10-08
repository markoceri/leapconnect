<template>
  <SectionCard title="Battery Health (estimated)" :icon="HeartPulse">
    <div v-if="loading" class="no-data">Loading…</div>
    <div v-else-if="error" class="no-data">{{ error }}</div>
    <template v-else-if="health">
      <template v-if="health.soh_pct != null">
        <div class="soh-hero">
          <span class="soh-value" :style="{ color: sohColor }">{{ health.soh_pct.toFixed(1) }}%</span>
          <span class="soh-caption">vs {{ health.reference_kwh }} kWh reference</span>
        </div>
        <InfoRow label="Full-charge Capacity" :value="`${health.capacity_kwh} kWh`" color="var(--accent)" />
        <InfoRow label="Last Full Charge" :value="formatDay(health.last_full_charge)" color="var(--sub)" />
        <InfoRow label="Full-charge Days" :value="health.samples" color="var(--sub)" />
        <div v-if="health.series.length > 1" class="soh-chart">
          <canvas ref="canvas" />
        </div>
      </template>
      <div v-else class="soh-empty">
        Needs at least {{ health.min_samples }} days with a charge to 100%
        ({{ health.samples }} so far).
      </div>

      <div class="soh-ref">
        <label class="soh-ref-label" for="soh-ref-input">Reference capacity</label>
        <div class="soh-ref-row">
          <input
            id="soh-ref-input"
            v-model="referenceInput"
            type="number"
            min="10"
            max="200"
            step="0.1"
            inputmode="decimal"
            :placeholder="health.reference_source === 'observed' ? `${health.reference_kwh} (observed)` : 'Observed peak'"
            class="soh-ref-input"
          />
          <span class="soh-ref-unit">kWh</span>
          <button class="soh-ref-btn" :disabled="saving || !referenceDirty" @click="saveReference">Save</button>
        </div>
        <div class="soh-note">
          Estimated from the energy the BMS reports at 100% charge — not an official SOH reading.
          Leave the reference empty to use the peak capacity observed since LeapConnect started recording.
        </div>
      </div>
    </template>
  </SectionCard>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
import { HeartPulse } from 'lucide-vue-next'
import SectionCard from './SectionCard.vue'
import InfoRow from './InfoRow.vue'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'

Chart.register(...registerables)

const props = defineProps({
  vin: { type: String, required: true },
})

const { toast } = useToast()
const health = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const referenceInput = ref('')
const canvas = ref(null)
let chart = null

const sohColor = computed(() => {
  const v = health.value?.soh_pct
  if (v == null) return 'var(--text)'
  return v >= 90 ? 'var(--green)' : v >= 80 ? 'var(--amber)' : 'var(--red)'
})

const referenceDirty = computed(() => {
  const current = health.value?.user_reference_kwh ?? ''
  return String(referenceInput.value ?? '') !== String(current)
})

function formatDay(iso) {
  if (!iso) return '—'
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

function apply(data) {
  health.value = data
  referenceInput.value = data.user_reference_kwh ?? ''
  nextTick(renderChart)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    apply(await api('GET', `/api/vehicles/${props.vin}/battery/health`))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function saveReference() {
  const raw = referenceInput.value
  const value = raw === '' || raw == null ? null : Number(raw)
  if (value != null && (Number.isNaN(value) || value < 10 || value > 200)) {
    toast('Reference capacity must be between 10 and 200 kWh', 'error')
    return
  }
  saving.value = true
  try {
    apply(await api('PUT', `/api/vehicles/${props.vin}/battery/health/reference`, { reference_kwh: value }))
    toast('Reference capacity saved', 'success')
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    saving.value = false
  }
}

function renderChart() {
  if (chart) { chart.destroy(); chart = null }
  const series = health.value?.series || []
  if (!canvas.value || series.length < 2) return
  const s = getComputedStyle(document.documentElement)
  const grid = s.getPropertyValue('--chart-grid').trim() || '#1c2135'
  const tick = s.getPropertyValue('--chart-tick').trim() || '#4a5468'
  const accent = s.getPropertyValue('--accent').trim() || '#00d4ff'
  const accentRgb = s.getPropertyValue('--accent-rgb').trim() || '0, 212, 255'
  chart = new Chart(canvas.value.getContext('2d'), {
    type: 'line',
    data: {
      labels: series.map(p => formatDay(p.day)),
      datasets: [
        {
          label: 'Capacity',
          data: series.map(p => p.capacity_kwh),
          borderColor: accent,
          backgroundColor: `rgba(${accentRgb}, 0.1)`,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: 'Daily reading',
          data: series.map(p => p.energy_kwh),
          borderColor: 'transparent',
          backgroundColor: tick,
          pointRadius: 2,
          showLine: false,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} kWh`,
            afterBody: (items) => {
              const p = series[items[0]?.dataIndex]
              return p ? `SOH: ${p.soh_pct.toFixed(1)}%` : ''
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: tick, font: { size: 10 }, maxTicksLimit: 6 }, grid: { display: false } },
        y: { ticks: { color: tick, callback: v => `${v.toFixed(1)}` }, grid: { color: grid } },
      },
    },
  })
}

watch(() => props.vin, load, { immediate: true })
onBeforeUnmount(() => { if (chart) chart.destroy() })
</script>

<style scoped>
.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 80px;
  color: var(--muted);
  font-size: 13px;
}
.soh-hero {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  padding-bottom: 6px;
}
.soh-value { font-size: 32px; font-weight: 700; line-height: 1.1; }
.soh-caption { font-size: 12px; color: var(--sub); }
.soh-chart { position: relative; height: 160px; margin-top: 12px; }
.soh-empty {
  font-size: 13px;
  color: var(--sub);
  padding: 12px;
  background: var(--elevated);
  border-radius: 8px;
}
.soh-ref { margin-top: 14px; }
.soh-ref-label {
  display: block;
  font-size: 10px;
  color: var(--muted2);
  margin-bottom: 6px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.soh-ref-row { display: flex; align-items: center; gap: 8px; }
.soh-ref-input {
  flex: 1;
  min-width: 0;
  background: var(--input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
}
.soh-ref-input:focus { outline: none; border-color: var(--accent); }
.soh-ref-unit { font-size: 12px; color: var(--sub); }
.soh-ref-btn {
  background: var(--btn-bg);
  border: 1px solid var(--btn-border);
  color: var(--text);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}
.soh-ref-btn:hover:not(:disabled) { background: var(--btn-hover); }
.soh-ref-btn:disabled { opacity: 0.5; cursor: default; }
.soh-note {
  font-size: 11px;
  color: var(--muted3);
  margin-top: 8px;
  line-height: 1.4;
}
</style>
