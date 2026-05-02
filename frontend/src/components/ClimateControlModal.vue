<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="cc-overlay" @click.self="$emit('close')">
        <div class="cc-modal">
          <div class="cc-header">
            <div class="cc-header-left">
              <Thermometer :size="16" class="cc-header-icon" />
              <span class="cc-title">Climate</span>
            </div>
            <div class="cc-header-status" v-if="climate">
              <span class="cc-status-dot" :class="{ on: climate.ac_switch }" />
              <span class="cc-status-text">{{ climate.ac_switch ? 'ON' : 'OFF' }}</span>
            </div>
            <button class="cc-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="cc-body">
            <!-- Quick actions -->
            <div class="cc-section-label">Quick Actions</div>
            <div class="cc-quick">
              <button
                v-for="qa in quickActions"
                :key="qa.action"
                class="cc-quick-btn"
                :class="{ loading: loadingAction === qa.action }"
                :style="{ '--qa': qa.color }"
                :disabled="!!loadingAction"
                @click="doQuickAction(qa.action)"
              >
                <Loader v-if="loadingAction === qa.action" :size="14" class="spinning" />
                <component v-else :is="qa.icon" :size="14" />
                <span>{{ qa.label }}</span>
              </button>
            </div>

            <!-- Current status -->
            <div v-if="climate" class="cc-current">
              <div class="cc-current-item" v-if="climate.outdoor_temp != null">
                <span class="cc-current-label">Outside</span>
                <span class="cc-current-val">{{ climate.outdoor_temp }}°C</span>
              </div>
              <div class="cc-current-item" v-if="climate.ac_setting != null">
                <span class="cc-current-label">Set Temp</span>
                <span class="cc-current-val">{{ climate.ac_setting }}°C</span>
              </div>
              <div class="cc-current-item" v-if="climate.ac_air_volume_setting != null">
                <span class="cc-current-label">Fan</span>
                <span class="cc-current-val">{{ climate.ac_air_volume_setting }}</span>
              </div>
              <div class="cc-current-item" v-if="climate.ac_circle_mode != null">
                <span class="cc-current-label">Circ.</span>
                <span class="cc-current-val">{{ climate.ac_circle_mode ? 'In' : 'Out' }}</span>
              </div>
            </div>

            <!-- Manual controls -->
            <div class="cc-section-label">Manual Control</div>

            <!-- Temperature -->
            <div class="cc-control-row">
              <span class="cc-control-label">Temperature</span>
              <div class="cc-temp-control">
                <button class="cc-step-btn" @click="temp = Math.max(16, temp - 1)">−</button>
                <span class="cc-temp-value">{{ temp }}°C</span>
                <button class="cc-step-btn" @click="temp = Math.min(32, temp + 1)">+</button>
              </div>
            </div>

            <!-- Fan level -->
            <div class="cc-control-row">
              <span class="cc-control-label">Fan Level</span>
              <div class="cc-fan-control">
                <button
                  v-for="lv in 7"
                  :key="lv"
                  class="cc-fan-btn"
                  :class="{ active: fan === lv }"
                  @click="fan = lv"
                >{{ lv }}</button>
              </div>
            </div>

            <!-- Mode -->
            <div class="cc-control-row">
              <span class="cc-control-label">Mode</span>
              <div class="cc-mode-control">
                <button
                  v-for="m in modes"
                  :key="m.value"
                  class="cc-mode-btn"
                  :class="{ active: mode === m.value }"
                  @click="mode = m.value"
                >
                  <component :is="m.icon" :size="14" />
                  <span>{{ m.label }}</span>
                </button>
              </div>
            </div>

            <!-- Operate -->
            <div class="cc-control-row">
              <span class="cc-control-label">Operate</span>
              <div class="cc-mode-control">
                <button class="cc-mode-btn" :class="{ active: operate === 'auto' }" @click="operate = 'auto'">Auto</button>
                <button class="cc-mode-btn" :class="{ active: operate === 'manual' }" @click="operate = 'manual'">Manual</button>
              </div>
            </div>

            <!-- Air circulation -->
            <div class="cc-control-row">
              <span class="cc-control-label">Circulation</span>
              <div class="cc-mode-control">
                <button class="cc-mode-btn" :class="{ active: circle === 'in' }" @click="circle = 'in'">
                  <RotateCcw :size="14" />
                  <span>Recirculate</span>
                </button>
                <button class="cc-mode-btn" :class="{ active: circle === 'out' }" @click="circle = 'out'">
                  <Wind :size="14" />
                  <span>Fresh</span>
                </button>
              </div>
            </div>

            <!-- Windshield -->
            <div class="cc-control-row">
              <span class="cc-control-label">Windshield</span>
              <div class="cc-mode-control">
                <button class="cc-mode-btn" :class="{ active: wshld === '1' }" @click="wshld = '1'">Normal</button>
                <button class="cc-mode-btn" :class="{ active: wshld === '2' }" @click="wshld = '2'">
                  <ThermometerSnowflake :size="14" />
                  <span>Defrost</span>
                </button>
              </div>
            </div>

            <!-- Apply -->
            <button
              class="cc-apply-btn"
              :class="{ loading: loadingAction === 'custom' }"
              :disabled="!!loadingAction"
              @click="applyCustom"
            >
              <Loader v-if="loadingAction === 'custom'" :size="14" class="spinning" />
              <span>Apply Settings</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import {
  Thermometer, Snowflake, Flame, Wind, ThermometerSnowflake,
  RotateCcw, Loader, Power
} from 'lucide-vue-next'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
  climate: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const temp = ref(24)
const fan = ref(4)
const mode = ref('nohotcold')
const operate = ref('manual')
const circle = ref('out')
const wshld = ref('1')
const loadingAction = ref(null)

const modes = [
  { value: 'cold', label: 'Cool', icon: Snowflake },
  { value: 'hot', label: 'Heat', icon: Flame },
  { value: 'nohotcold', label: 'Fan', icon: Wind },
]

const quickActions = [
  { action: 'ac', label: 'A/C Toggle', icon: Power, color: '#00d4ff' },
  { action: 'quick-cool', label: 'Quick Cool', icon: Snowflake, color: '#00d4ff' },
  { action: 'quick-heat', label: 'Quick Heat', icon: Flame, color: '#ff7043' },
  { action: 'defrost', label: 'Defrost', icon: ThermometerSnowflake, color: '#7c6aff' },
]

// Initialize from current climate state when modal opens
watch(() => props.visible, (val) => {
  if (val && props.climate) {
    if (props.climate.ac_setting != null) temp.value = Math.round(props.climate.ac_setting)
    if (props.climate.ac_air_volume_setting != null) fan.value = props.climate.ac_air_volume_setting
    if (props.climate.ac_circle_mode != null) circle.value = props.climate.ac_circle_mode ? 'in' : 'out'
  }
})

async function doQuickAction(action) {
  loadingAction.value = action
  try {
    if (props.onExec) await props.onExec({ action, body: null })
  } finally {
    loadingAction.value = null
  }
}

async function applyCustom() {
  loadingAction.value = 'custom'
  try {
    const body = {
      circle: circle.value,
      mode: mode.value,
      operate: operate.value,
      position: 'all',
      temperature: String(temp.value),
      windlevel: String(fan.value),
      wshld: wshld.value,
    }
    if (props.onExec) await props.onExec({ action: 'ac', body })
  } finally {
    loadingAction.value = null
  }
}
</script>

<style scoped>
.cc-overlay {
  position: fixed;
  inset: 0;
  background: #000000aa;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5000;
  backdrop-filter: blur(4px);
}

.cc-modal {
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: 16px;
  width: 360px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 16px 48px #00000088;
  scrollbar-width: thin;
  scrollbar-color: #1c2240 transparent;
}

@media (max-width: 400px) {
  .cc-modal {
    width: calc(100vw - 24px);
  }
}

.cc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--border2);
  position: sticky;
  top: 0;
  background: var(--bg2);
  z-index: 1;
}

.cc-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.cc-header-icon {
  color: #00d4ff;
}

.cc-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}

.cc-header-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 700;
}

.cc-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3a4468;
}
.cc-status-dot.on {
  background: #00e676;
  box-shadow: 0 0 6px #00e676;
}

.cc-status-text {
  color: var(--muted);
}

.cc-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 20px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.cc-close:hover {
  color: var(--text);
}

.cc-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cc-section-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 4px;
}

/* Quick actions */
.cc-quick {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.cc-quick-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  border-radius: 10px;
  border: 1px solid var(--border2);
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  color: var(--qa);
  cursor: pointer;
  transition: all 0.2s;
}
.cc-quick-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--qa) 12%, transparent);
  border-color: color-mix(in srgb, var(--qa) 40%, transparent);
}
.cc-quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Current status */
.cc-current {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.cc-current-item {
  background: #0d1422;
  border: 1px solid var(--border2);
  border-radius: 8px;
  padding: 6px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex: 1;
  min-width: 60px;
}

.cc-current-label {
  font-size: 9px;
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cc-current-val {
  font-size: 14px;
  font-weight: 800;
  color: var(--text);
  font-family: var(--mono);
}

/* Control rows */
.cc-control-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cc-control-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--label);
}

/* Temperature */
.cc-temp-control {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.cc-step-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border2);
  background: transparent;
  color: var(--text);
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.cc-step-btn:hover {
  background: #00d4ff18;
  border-color: #00d4ff44;
  color: #00d4ff;
}

.cc-temp-value {
  font-size: 28px;
  font-weight: 800;
  color: var(--text);
  font-family: var(--mono);
  min-width: 80px;
  text-align: center;
}

/* Fan buttons */
.cc-fan-control {
  display: flex;
  gap: 4px;
}

.cc-fan-btn {
  flex: 1;
  padding: 8px 0;
  border-radius: 8px;
  border: 1px solid var(--border2);
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}
.cc-fan-btn.active {
  background: #00d4ff18;
  border-color: #00d4ff44;
  color: #00d4ff;
}
.cc-fan-btn:hover:not(.active) {
  color: var(--text);
  border-color: #2a3045;
}

/* Mode / operate / circulation buttons */
.cc-mode-control {
  display: flex;
  gap: 6px;
}

.cc-mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 6px;
  border-radius: 8px;
  border: 1px solid var(--border2);
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.cc-mode-btn.active {
  background: #00d4ff18;
  border-color: #00d4ff44;
  color: #00d4ff;
}
.cc-mode-btn:hover:not(.active) {
  color: var(--text);
  border-color: #2a3045;
}

/* Apply button */
.cc-apply-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #00d4ff, #7c6aff);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
  margin-top: 4px;
}
.cc-apply-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.cc-apply-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinning {
  animation: lm-spin 0.7s linear infinite;
}

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-active .cc-modal,
.modal-leave-active .cc-modal {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .cc-modal,
.modal-leave-to .cc-modal {
  transform: scale(0.95);
  opacity: 0;
}
</style>
