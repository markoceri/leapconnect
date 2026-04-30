<template>
  <div class="settings-tab">
    <!-- Account -->
    <SectionCard title="Account" :icon="User">
      <div class="account-row">
        <div class="account-avatar">{{ initials }}</div>
        <div>
          <div class="account-name">{{ displayName }}</div>
          <div class="account-email">{{ email }}</div>
        </div>
      </div>
      <InfoRow label="Versione app" value="v2.4.1" color="#5c6478" />
    </SectionCard>

    <!-- Vehicle -->
    <SectionCard title="Veicolo" :icon="Car">
      <InfoRow label="Modello" :value="`${vehicle.year || ''} Leapmotor ${vehicle.car_type || ''}`" color="#e2e6f0" />
      <InfoRow label="VIN" color="#e2e6f0">
        <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
      </InfoRow>
      <InfoRow label="Nickname" :value="vehicle.nickname || '—'" color="#00d4ff" />
    </SectionCard>

    <!-- Notifications -->
    <SectionCard title="Notifiche" :icon="Bell">
      <div v-for="n in notifications" :key="n.key" class="notif-row">
        <span class="notif-label">{{ n.label }}</span>
        <ToggleSwitch v-model="n.enabled" />
      </div>
    </SectionCard>

    <!-- Preferences -->
    <SectionCard title="Preferenze" :icon="SlidersHorizontal">
      <InfoRow label="Unità distanza" value="km" color="#e2e6f0" />
      <InfoRow label="Unità pressione" value="bar" color="#e2e6f0" />
      <InfoRow label="Tema" value="Dark" color="#7c6aff" />
      <InfoRow label="Lingua" value="Italiano" color="#e2e6f0" />
    </SectionCard>

    <!-- Data Collection Scheduler -->
    <SectionCard title="Raccolta dati" :icon="BarChart3">
      <div class="notif-row">
        <span class="notif-label">Raccolta automatica</span>
        <ToggleSwitch :modelValue="scheduler.enabled" @update:modelValue="toggleScheduler" />
      </div>
      <div class="interval-row">
        <span class="interval-label">Intervallo di raccolta</span>
        <div class="interval-control">
          <button class="interval-btn" :disabled="!scheduler.enabled" @click="changeInterval(-5)">−</button>
          <span class="interval-value" :class="{ disabled: !scheduler.enabled }">{{ scheduler.interval_minutes }} min</span>
          <button class="interval-btn" :disabled="!scheduler.enabled" @click="changeInterval(5)">+</button>
        </div>
      </div>
      <div class="scheduler-status">
        <div class="status-row">
          <span class="status-dot" :class="scheduler.is_running ? 'running' : 'stopped'" />
          <span class="status-text">{{ scheduler.is_running ? 'In esecuzione' : 'Fermo' }}</span>
        </div>
        <div v-if="scheduler.last_run" class="status-detail">
          Ultimo aggiornamento: {{ formatTime(scheduler.last_run) }}
        </div>
        <div class="status-detail">
          Raccolte: {{ scheduler.total_runs }} · Errori: {{ scheduler.total_errors }}
        </div>
        <div v-if="scheduler.last_error" class="status-error">
          {{ scheduler.last_error }}
        </div>
      </div>
    </SectionCard>

    <!-- Raw Data toggle -->
    <SectionCard title="Dati grezzi" :icon="Code">
      <button class="raw-toggle" @click="showRaw = !showRaw">
        {{ showRaw ? 'Nascondi' : 'Mostra' }} JSON completo
      </button>
      <div v-if="showRaw" class="raw-panel">
        <pre>{{ JSON.stringify(rawData, null, 2) }}</pre>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import SectionCard from '../components/SectionCard.vue'
import InfoRow from '../components/InfoRow.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import { api } from '../composables/useApi'
import { User, Car, Bell, SlidersHorizontal, BarChart3, Code } from 'lucide-vue-next'

const props = defineProps({
  vehicle: { type: Object, required: true },
  rawData: { type: Object, default: () => ({}) },
})

const showRaw = ref(false)

const email = computed(() => {
  // We don't have user email from the API, show placeholder
  return '—'
})
const displayName = computed(() => props.vehicle.nickname || 'User')
const initials = computed(() => {
  const n = displayName.value
  return n.substring(0, 2).toUpperCase()
})

const notifications = reactive([
  { label: 'Carica completata', key: 'notifCharge', enabled: true },
  { label: 'Batteria scarica (<20%)', key: 'notifLow', enabled: true },
  { label: 'Pressione pneumatici', key: 'notifTire', enabled: true },
  { label: 'Aggiornamenti software', key: 'notifOTA', enabled: false },
])

// -- Scheduler state --------------------------------------------------------
const scheduler = reactive({
  enabled: false,
  interval_minutes: 15,
  is_running: false,
  last_run: null,
  last_error: null,
  total_runs: 0,
  total_errors: 0,
})

let schedulerUpdating = false

async function loadScheduler() {
  try {
    const data = await api('GET', '/api/scheduler')
    Object.assign(scheduler, data)
  } catch {
    // scheduler not available yet
  }
}

async function updateScheduler(patch) {
  if (schedulerUpdating) return
  schedulerUpdating = true
  try {
    const data = await api('PUT', '/api/scheduler', patch)
    Object.assign(scheduler, data)
  } catch {
    // revert on error — reload current state
    await loadScheduler()
  } finally {
    schedulerUpdating = false
  }
}

function toggleScheduler(val) {
  updateScheduler({ enabled: val })
}

function changeInterval(delta) {
  const next = Math.max(1, Math.min(1440, scheduler.interval_minutes + delta))
  if (next !== scheduler.interval_minutes) {
    updateScheduler({ interval_minutes: next })
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(loadScheduler)
</script>

<style scoped>
.settings-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 100%;
}
@media (min-width: 768px) {
  .settings-tab { max-width: 640px; }
}

.account-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0 16px;
}
.account-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #00d4ff22;
  border: 2px solid #00d4ff55;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #00d4ff;
}
.account-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.account-email {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.notif-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #181d2c;
}
.notif-row:last-child { border-bottom: none; }
.notif-label { font-size: 13px; color: var(--sub); }

.raw-toggle {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--muted);
  font-size: 12px;
  font-family: var(--mono);
  cursor: pointer;
  transition: all 0.2s;
}
.raw-toggle:hover { color: var(--sub); border-color: #00d4ff44; }

.raw-panel {
  max-height: 400px;
  overflow: auto;
  background: #0d1018;
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
}
.raw-panel pre {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted3);
  white-space: pre-wrap;
  word-break: break-all;
}

/* Scheduler / Data Collection */
.interval-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #181d2c;
}
.interval-label {
  font-size: 13px;
  color: var(--sub);
}
.interval-control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.interval-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--sub);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.interval-btn:hover:not(:disabled) {
  border-color: #00d4ff55;
  color: #00d4ff;
}
.interval-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.interval-value {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  min-width: 52px;
  text-align: center;
  font-family: var(--mono);
}
.interval-value.disabled {
  color: var(--muted);
}
.scheduler-status {
  margin-top: 12px;
  padding: 10px 12px;
  background: #0d1018;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.running {
  background: #00e676;
  box-shadow: 0 0 6px #00e67688;
}
.status-dot.stopped {
  background: #5c6478;
}
.status-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--sub);
}
.status-detail {
  font-size: 11px;
  color: var(--muted);
}
.status-error {
  font-size: 11px;
  color: #ff5252;
  font-family: var(--mono);
}
</style>
