<template>
  <div class="card card-full">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(0,210,230,0.1);color:var(--accent)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        </div>
        Remote Controls
      </div>
      <span v-if="!hasPin" style="font-size:0.72rem;color:var(--accent-yellow)">⚠ PIN required for remote actions</span>
    </div>
    <div class="card-body">
      <div class="controls-grid">
        <ControlButton
          v-for="ctrl in controls"
          :key="ctrl.action"
          :label="ctrl.label"
          :css-class="ctrl.cssClass"
          :icon="ctrl.icon"
          :disabled="!hasPin"
          @click="execute(ctrl.action)"
        />
      </div>

      <!-- Charge limit -->
      <div class="charge-section">
        <div class="charge-header">
          <span class="charge-label">Charge Limit</span>
          <span class="charge-current">Current: {{ chargeSocSetting ?? '—' }}%</span>
        </div>
        <div class="charge-limit-section">
          <span class="charge-min">20%</span>
          <div class="charge-slider-wrapper">
            <input
              type="range"
              class="charge-slider"
              min="20"
              max="100"
              step="5"
              v-model.number="chargeLimit"
            />
          </div>
          <span class="charge-limit-value">{{ chargeLimit }}%</span>
          <button class="btn-set-charge" @click="doSetChargeLimit">Set</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import ControlButton from './ControlButton.vue'

const props = defineProps({
  vin: { type: String, required: true },
  hasPin: { type: Boolean, default: false },
  chargeSocSetting: { type: Number, default: null },
})

const store = useAppStore()
const { toast } = useToast()
const chargeLimit = ref(props.chargeSocSetting || 80)

const controls = [
  { action: 'lock', label: 'Lock', cssClass: 'lock', icon: 'lock' },
  { action: 'unlock', label: 'Unlock', cssClass: 'unlock', icon: 'unlock' },
  { action: 'trunk/open', label: 'Open Trunk', cssClass: 'trunk', icon: 'trunk-open' },
  { action: 'trunk/close', label: 'Close Trunk', cssClass: 'trunk', icon: 'trunk-close' },
  { action: 'find', label: 'Find Car', cssClass: 'find', icon: 'find' },
  { action: 'windows/open', label: 'Open Windows', cssClass: 'window', icon: 'window-open' },
  { action: 'windows/close', label: 'Close Windows', cssClass: 'window', icon: 'window-close' },
  { action: 'sunshade/open', label: 'Open Sunshade', cssClass: 'sunshade', icon: 'sun-open' },
  { action: 'sunshade/close', label: 'Close Sunshade', cssClass: 'sunshade', icon: 'sun-close' },
  { action: 'ac', label: 'A/C Toggle', cssClass: 'climate', icon: 'ac' },
  { action: 'quick-cool', label: 'Quick Cool', cssClass: 'climate', icon: 'cool' },
  { action: 'quick-heat', label: 'Quick Heat', cssClass: 'climate', icon: 'heat' },
  { action: 'defrost', label: 'Defrost', cssClass: 'climate', icon: 'defrost' },
  { action: 'battery-preheat', label: 'Battery Preheat', cssClass: 'battery-ctl', icon: 'battery' },
]

async function execute(action) {
  if (!props.hasPin) {
    toast('Vehicle PIN required for remote controls', 'error')
    return
  }
  try {
    await store.execControl(props.vin, action)
    toast(`${action} executed successfully`, 'success')
  } catch (err) {
    toast(`${action} failed: ${err.message}`, 'error')
  }
}

async function doSetChargeLimit() {
  if (!props.hasPin) {
    toast('Vehicle PIN required', 'error')
    return
  }
  try {
    await store.setChargeLimit(props.vin, chargeLimit.value)
    toast(`Charge limit set to ${chargeLimit.value}%`, 'success')
  } catch (err) {
    toast(`Failed to set charge limit: ${err.message}`, 'error')
  }
}
</script>

<style scoped>
.controls-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.8rem;
}

.charge-section {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
}

.charge-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.8rem;
}
.charge-label { font-size: 0.8rem; color: var(--text-secondary); }
.charge-current { font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-tertiary); }

.charge-limit-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.charge-min { font-size: 0.72rem; color: var(--text-tertiary); }

.charge-slider-wrapper { flex: 1; }

.charge-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-elevated);
  outline: none;
}
.charge-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent-green);
  cursor: pointer;
  box-shadow: 0 0 10px rgba(0, 230, 118, 0.3);
  transition: var(--transition);
}
.charge-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }

.charge-limit-value {
  font-family: var(--font-mono);
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--accent-green);
  min-width: 50px;
  text-align: right;
}

.btn-set-charge {
  padding: 0.5rem 1rem;
  background: rgba(0, 230, 118, 0.1);
  border: 1px solid rgba(0, 230, 118, 0.2);
  border-radius: var(--radius-sm);
  color: var(--accent-green);
  font-family: var(--font-display);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
}
.btn-set-charge:hover {
  background: rgba(0, 230, 118, 0.15);
  border-color: rgba(0, 230, 118, 0.3);
}

@media (max-width: 768px) {
  .controls-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
}
</style>
