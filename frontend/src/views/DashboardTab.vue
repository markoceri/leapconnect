<template>
  <div class="dashboard-tab">
    <!-- Hero -->
    <div class="hero">
      <div class="hero-glow" :class="{ charging: s.battery?.is_charging, ac: s.climate?.ac_switch }" />
      <div class="hero-car">
        <img
          :src="`/api/vehicles/${vehicle.vin}/picture/image`"
          alt="Vehicle"
          class="hero-car-img"
          :class="{ 'glow-charging': s.battery?.is_charging, 'glow-ac': s.climate?.ac_switch }"
        />
        <div class="hero-badges">
          <span v-if="s.battery?.is_charging" class="badge badge-charging">⚡</span>
          <span v-if="s.climate?.ac_switch" class="badge badge-ac">❄</span>
          <span v-if="s.doors?.is_locked" class="badge badge-lock">🔒</span>
          <span v-if="s.doors?.trunk" class="badge badge-trunk">📦</span>
        </div>
      </div>
      <div class="hero-info">
        <div class="hero-name">{{ vehicle.nickname || vehicle.car_type || 'Leapmotor' }}</div>
        <div class="hero-vin">{{ vehicle.vin }}</div>
      </div>
    </div>

    <!-- Stats grid -->
    <div class="stats-row">
      <StatCard
        label="Battery" :value="s.battery?.soc ?? '—'" unit="%" :color="battColor"
        :sub="s.battery?.is_charging ? 'Charging' : 'Not charging'"
        :icon="s.battery?.is_charging ? '⚡' : ''" :pulse="!!s.battery?.is_charging"
      />
      <StatCard
        label="Range" :value="s.battery?.expected_mileage ?? '—'" unit="km" color="#00d4ff"
        :sub="s.battery?.dump_energy != null ? `${s.battery.dump_energy} kWh available` : ''"
      />
      <StatCard
        label="Speed" :value="s.driving?.speed ?? 0" unit="km/h" color="#e2e6f0"
        :sub="s.driving?.is_parked ? 'Parked' : 'Moving'"
      />
      <StatCard
        label="Odometer"
        :value="s.driving?.total_mileage != null ? s.driving.total_mileage.toLocaleString() : '—'"
        unit="km" color="#ffab40"
      />
      <StatCard
        label="Outside Temp" :value="s.climate?.outdoor_temp ?? '—'" unit="°C" color="#7c6aff"
        :sub="s.climate?.ac_switch ? 'A/C on' : 'A/C off'"
      />
    </div>

    <!-- Battery bar -->
    <div class="battery-bar-container">
      <div class="battery-bar-fill" :style="{ width: (s.battery?.soc ?? 0) + '%', background: battColor, boxShadow: s.battery?.is_charging ? `0 0 8px ${battColor}` : 'none' }" />
    </div>

    <!-- Lock status + charging info row -->
    <div class="info-strip">
      <div class="lock-widget" :style="{ borderColor: s.doors?.is_locked ? '#ffab4044' : '#00e67644' }">
        <div class="lock-label">Lock Status</div>
        <div class="lock-main">
          <span class="lock-icon">{{ s.doors?.is_locked ? '🔒' : '🔓' }}</span>
          <span class="lock-text" :style="{ color: s.doors?.is_locked ? '#ffab40' : '#00e676' }">
            {{ s.doors?.is_locked === true ? 'Locked' : s.doors?.is_locked === false ? 'Unlocked' : '—' }}
          </span>
        </div>
        <div class="lock-time">Updated {{ s.timestamps?.collect_time ? formatTime(s.timestamps.collect_time) : '—' }}</div>
      </div>

      <div v-if="s.battery?.is_charging" class="charging-widget">
        <div class="lock-label">Charging</div>
        <div class="charging-stats">
          <div class="charging-stat">
            <div class="charging-val" style="color:#00e676">{{ chargeTimeStr }}</div>
            <div class="charging-sub">Rimanente</div>
          </div>
          <div class="charging-stat">
            <div class="charging-val" style="color:#00d4ff">{{ Math.abs(s.battery?.battery_current ?? 0) }} A</div>
            <div class="charging-sub">Corrente</div>
          </div>
          <div class="charging-stat">
            <div class="charging-val" style="color:#7c6aff">{{ s.battery?.battery_voltage ?? '—' }} V</div>
            <div class="charging-sub">Voltaggio</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Remote Controls -->
    <div class="controls-card">
      <div class="controls-header">
        <span class="controls-icon">🛡</span>
        <span class="controls-title">Remote Controls</span>
      </div>
      <div class="controls-grid">
        <button
          v-for="c in controls"
          :key="c.action"
          class="ctrl-btn"
          :class="{ active: isActive(c.action), loading: loadingAction === c.action }"
          :style="{ '--c': c.color }"
          @click="exec(c.action)"
        >
          <span class="ctrl-icon" :class="{ spinning: loadingAction === c.action }">
            {{ loadingAction === c.action ? '⏳' : c.icon }}
          </span>
          <span class="ctrl-label">{{ c.label }}</span>
        </button>
      </div>
    </div>

    <!-- Charge limit -->
    <div class="charge-limit-card">
      <div class="charge-limit-header">
        <span class="charge-limit-title">Charge Limit</span>
        <span class="charge-limit-current">Current: {{ s.battery?.charge_soc_setting ?? '—' }}%</span>
      </div>
      <div class="charge-limit-row">
        <span class="charge-min">20%</span>
        <input type="range" min="20" max="100" step="5" v-model.number="pendingLimit" class="charge-slider" />
        <div class="charge-limit-right">
          <span class="charge-dot" />
          <span class="charge-val">{{ pendingLimit }}%</span>
          <button class="charge-set-btn" @click="doSetChargeLimit">Set</button>
        </div>
      </div>
    </div>

    <PinDialog
      ref="pinDialogRef"
      :visible="showPinDialog"
      @confirmed="onPinConfirmed"
      @cancelled="onPinCancelled"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import { formatTime } from '../utils/formatters'
import StatCard from '../components/StatCard.vue'
import PinDialog from '../components/PinDialog.vue'

const props = defineProps({
  vehicle: { type: Object, required: true },
  status: { type: Object, required: true },
})

const store = useAppStore()
const { toast } = useToast()
const loadingAction = ref(null)

const s = computed(() => props.status || {})

const battColor = computed(() => {
  const soc = s.value.battery?.soc
  if (soc == null) return '#5c6478'
  return soc > 50 ? '#00e676' : soc > 20 ? '#ffab40' : '#ff5252'
})

const chargeTimeStr = computed(() => {
  const min = s.value.battery?.charge_remain_time
  if (min == null) return '—'
  return `${Math.floor(min / 60)}h ${min % 60}m`
})

const hasPin = computed(() => store.hasPin)

const showPinDialog = ref(false)
const pendingAction = ref(null)
const pinDialogRef = ref(null)

const pendingLimit = ref(props.status?.battery?.charge_soc_setting ?? 80)

const controls = [
  { action: 'lock', icon: '🔒', label: 'Lock', color: '#ffab40' },
  { action: 'unlock', icon: '🔓', label: 'Unlock', color: '#00e676' },
  { action: 'trunk/open', icon: '📦', label: 'Open Trunk', color: '#00d4ff' },
  { action: 'trunk/close', icon: '📦', label: 'Close Trunk', color: '#4a5468' },
  { action: 'find', icon: '📡', label: 'Find Car', color: '#00d4ff' },
  { action: 'windows/open', icon: '⬆', label: 'Open Windows', color: '#7c6aff' },
  { action: 'windows/close', icon: '⬇', label: 'Close Windows', color: '#7c6aff' },
  { action: 'sunshade/open', icon: '☀', label: 'Open Sunshade', color: '#ffab40' },
  { action: 'sunshade/close', icon: '🌑', label: 'Close Sunshade', color: '#4a5468' },
  { action: 'ac', icon: '❄', label: 'A/C Toggle', color: '#00d4ff' },
  { action: 'quick-cool', icon: '💨', label: 'Quick Cool', color: '#00d4ff' },
  { action: 'quick-heat', icon: '🔥', label: 'Quick Heat', color: '#ff7043' },
  { action: 'defrost', icon: '❆', label: 'Defrost', color: '#7c6aff' },
  { action: 'battery-preheat', icon: '⚡', label: 'Battery Preheat', color: '#00e676' },
]

function isActive(action) {
  if (action === 'lock') return s.value.doors?.is_locked
  if (action === 'unlock') return s.value.doors?.is_locked === false
  if (action === 'ac') return s.value.climate?.ac_switch
  if (action === 'trunk/open') return s.value.doors?.trunk
  return false
}

async function requirePin() {
  if (hasPin.value) return true
  return new Promise((resolve) => {
    pendingAction.value = { resolve }
    showPinDialog.value = true
  })
}

async function onPinConfirmed({ pin, remember }) {
  try {
    await store.submitPin(pin)
    showPinDialog.value = false
    if (pendingAction.value?.resolve) {
      pendingAction.value.resolve(true)
      pendingAction.value = null
    }
  } catch (err) {
    pinDialogRef.value?.setError(err.message || 'Invalid PIN')
  }
}

function onPinCancelled() {
  showPinDialog.value = false
  if (pendingAction.value?.resolve) {
    pendingAction.value.resolve(false)
    pendingAction.value = null
  }
}

async function exec(action) {
  const ok = await requirePin()
  if (!ok) return
  loadingAction.value = action
  try {
    await store.execControl(props.vehicle.vin, action)
    toast(`${action} executed successfully`, 'success')
    await store.refreshCurrent()
  } catch (err) {
    toast(`${action} failed: ${err.message}`, 'error')
  } finally {
    loadingAction.value = null
  }
}

async function doSetChargeLimit() {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.setChargeLimit(props.vehicle.vin, pendingLimit.value)
    toast(`Charge limit set to ${pendingLimit.value}%`, 'success')
  } catch (err) {
    toast(`Failed: ${err.message}`, 'error')
  }
}
</script>

<style scoped>
.dashboard-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Hero */
.hero {
  background: linear-gradient(160deg, #0d1422, #111826);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 28px 28px 20px;
  position: relative;
  overflow: hidden;
}
.hero-glow {
  position: absolute;
  top: -60px;
  right: -60px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0,212,255,0.025) 0%, transparent 70%);
  pointer-events: none;
}
.hero-glow.charging { background: radial-gradient(circle, rgba(0,230,118,0.04) 0%, transparent 70%); }
.hero-glow.ac { background: radial-gradient(circle, rgba(0,212,255,0.04) 0%, transparent 70%); }
.hero-car { display: flex; flex-direction: column; align-items: center; margin-bottom: 8px; }
.hero-car-img {
  width: 100%;
  max-width: 480px;
  height: auto;
  object-fit: contain;
  filter: drop-shadow(0 8px 20px rgba(0,0,0,0.6));
  transition: filter 0.6s ease;
}
.hero-car-img.glow-charging { filter: drop-shadow(0 0 14px rgba(0,230,118,0.6)); }
.hero-car-img.glow-ac { filter: drop-shadow(0 0 14px rgba(0,212,255,0.6)); }
.hero-badges {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  backdrop-filter: blur(6px);
}
.badge-charging { background: rgba(0,230,118,0.15); border: 1px solid rgba(0,230,118,0.5); }
.badge-ac { background: rgba(0,212,255,0.12); border: 1px solid rgba(0,212,255,0.45); }
.badge-lock { background: rgba(255,171,64,0.15); border: 1px solid rgba(255,171,64,0.5); }
.badge-trunk { background: rgba(255,171,64,0.15); border: 1px solid rgba(255,171,64,0.5); }
.hero-info { margin-top: 4px; }
.hero-name { font-size: 18px; font-weight: 700; color: var(--text); }
.hero-vin { font-size: 11px; color: var(--muted2); font-family: var(--mono); margin-top: 2px; }

/* Stats row */
.stats-row { display: flex; gap: 10px; flex-wrap: wrap; }

/* Battery bar */
.battery-bar-container {
  height: 4px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.battery-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}

/* Lock + Charging strip */
.info-strip { display: flex; gap: 10px; }
.lock-widget {
  background: var(--card);
  border: 1px solid;
  border-radius: 12px;
  padding: 14px 18px;
  min-width: 160px;
}
.lock-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--muted3);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.lock-main { display: flex; align-items: center; gap: 8px; }
.lock-icon { font-size: 22px; }
.lock-text { font-size: 18px; font-weight: 700; }
.lock-time { font-size: 10px; color: var(--muted2); margin-top: 6px; }

.charging-widget {
  background: var(--card);
  border: 1px solid #00e67633;
  border-radius: 12px;
  padding: 14px 18px;
  flex: 1;
}
.charging-stats { display: flex; gap: 16px; }
.charging-stat {}
.charging-val { font-size: 20px; font-weight: 700; }
.charging-sub { font-size: 11px; color: var(--muted); }

/* Controls card */
.controls-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px 16px;
}
.controls-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.controls-icon { font-size: 14px; }
.controls-title { font-size: 13px; font-weight: 700; color: var(--heading); }
.controls-warn { font-size: 11px; color: #ffab40; margin-left: auto; }

.controls-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}

.ctrl-btn {
  background: var(--elevated);
  border: 1px solid #1c2240;
  border-radius: 12px;
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.15s;
  min-width: 0;
}
.ctrl-btn:hover {
  transform: scale(1.03);
}
.ctrl-btn:active {
  transform: scale(0.95);
}
.ctrl-btn.active {
  background: color-mix(in srgb, var(--c) 10%, transparent);
  border-color: color-mix(in srgb, var(--c) 33%, transparent);
}
.ctrl-btn.loading { cursor: wait; opacity: 0.7; }

.ctrl-icon {
  font-size: 20px;
  color: var(--c);
}
.ctrl-icon.spinning { animation: lm-spin 0.7s linear infinite; }
.ctrl-label {
  font-size: 10px;
  color: var(--label);
  font-weight: 500;
  text-align: center;
  line-height: 1.3;
  letter-spacing: 0.02em;
}
.ctrl-btn.active .ctrl-label { color: var(--c); }

/* Charge limit */
.charge-limit-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 20px;
}
.charge-limit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.charge-limit-title { font-size: 13px; font-weight: 600; color: var(--heading); }
.charge-limit-current { font-size: 12px; color: var(--muted); }

.charge-limit-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.charge-min { font-size: 11px; color: var(--muted2); }
.charge-slider { flex: 1; }
.charge-limit-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.charge-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
}
.charge-val { font-size: 15px; font-weight: 700; color: var(--text); }
.charge-set-btn {
  background: #1c2240;
  border: 1px solid #2a3060;
  border-radius: 7px;
  padding: 5px 12px;
  color: var(--sub);
  font-size: 12px;
  cursor: pointer;
  font-weight: 600;
}
.charge-set-btn:hover { background: #252d50; }

@media (max-width: 900px) {
  .controls-grid { grid-template-columns: repeat(4, 1fr); }
  .stats-row { flex-wrap: wrap; }
}
@media (max-width: 600px) {
  .controls-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
