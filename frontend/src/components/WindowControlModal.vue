<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="wc-overlay" @click.self="$emit('close')">
        <div class="wc-modal">
          <div class="wc-header">
            <div class="wc-header-left">
              <Columns2 :size="16" class="wc-header-icon" />
              <span class="wc-title">Windows</span>
            </div>
            <button class="wc-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="wc-body">
            <!-- Quick actions -->
            <div class="wc-quick">
              <button
                class="wc-quick-btn open"
                :class="{ loading: loadingAction === 'open' }"
                :disabled="!!loadingAction"
                @click="quickAction('open')"
              >
                <Loader v-if="loadingAction === 'open'" :size="16" class="spinning" />
                <ChevronDown v-else :size="16" />
                <span>Open</span>
              </button>
              <button
                class="wc-quick-btn close"
                :class="{ loading: loadingAction === 'close' }"
                :disabled="!!loadingAction"
                @click="quickAction('close')"
              >
                <Loader v-if="loadingAction === 'close'" :size="16" class="spinning" />
                <ChevronUp v-else :size="16" />
                <span>Close</span>
              </button>
            </div>

            <!-- Slider -->
            <div class="wc-slider-area">
              <div class="wc-slider-track">
                <div class="wc-slider-fill" :style="{ width: sliderValue + '%' }" />
                <!-- Individual window indicators -->
                <div
                  v-for="win in windowIndicators"
                  :key="win.key"
                  class="wc-indicator"
                  :class="'wc-indicator-' + win.side"
                  :style="{ left: win.value + '%', '--wc': win.color }"
                  :title="win.label + ': ' + win.value + '%'"
                >
                  <span class="wc-indicator-dot" />
                  <span class="wc-indicator-val">{{ win.value }}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  v-model.number="sliderValue"
                  class="wc-slider-input"
                />
              </div>
              <div class="wc-slider-labels">
                <span class="wc-label-left">0% — Closed</span>
                <span class="wc-slider-value">{{ sliderValue }}%</span>
                <span class="wc-label-right">100% — Open</span>
              </div>
            </div>

            <!-- Legend -->
            <div v-if="windowIndicators.length > 0" class="wc-legend">
              <div v-for="win in windowIndicators" :key="win.key" class="wc-legend-item">
                <span class="wc-legend-dot" :style="{ background: win.color }" />
                <span class="wc-legend-label">{{ win.label }}</span>
              </div>
            </div>

            <!-- Apply -->
            <button
              class="wc-apply-btn"
              :class="{ loading: loadingAction === 'custom' }"
              :disabled="!!loadingAction"
              @click="applyCustom"
            >
              <Loader v-if="loadingAction === 'custom'" :size="14" class="spinning" />
              <span>Set to {{ sliderValue }}%</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ChevronUp, ChevronDown, Columns2, Loader } from 'lucide-vue-next'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
  windows: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const sliderValue = ref(0)
const loadingAction = ref(null)

const windowIndicators = computed(() => {
  const w = props.windows
  if (!w) return []
  const defs = [
    { key: 'lf', field: 'left_front_window_percent', label: 'Left Front', color: '#00d4ff', side: 'bottom' },
    { key: 'rf', field: 'right_front_window_percent', label: 'Right Front', color: '#7c6aff', side: 'top' },
    { key: 'lr', field: 'left_rear_window_percent', label: 'Left Rear', color: '#00e676', side: 'bottom' },
    { key: 'rr', field: 'right_rear_window_percent', label: 'Right Rear', color: '#ffab40', side: 'top' },
  ]
  return defs
    .filter(d => w[d.field] != null)
    .map(d => ({ ...d, value: w[d.field] }))
})

// Initialize slider to average of current window positions when modal opens
watch(() => props.visible, (val) => {
  if (val && windowIndicators.value.length > 0) {
    const vals = windowIndicators.value.map(w => w.value)
    const avg = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length / 5) * 5
    sliderValue.value = avg
  }
})

async function quickAction(type) {
  const action = type === 'open' ? 'windows/open' : 'windows/close'
  loadingAction.value = type
  try {
    if (props.onExec) await props.onExec({ action, body: null })
  } finally {
    loadingAction.value = null
  }
}

async function applyCustom() {
  loadingAction.value = 'custom'
  try {
    if (props.onExec) await props.onExec({ action: 'windows', body: { value: String(sliderValue.value) } })
  } finally {
    loadingAction.value = null
  }
}
</script>

<style scoped>
.wc-overlay {
  position: fixed;
  inset: 0;
  background: #000000aa;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5000;
  backdrop-filter: blur(4px);
}

.wc-modal {
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: 16px;
  width: 320px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 16px 48px #00000088;
}

.wc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--border2);
}

.wc-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wc-header-icon {
  color: #7c6aff;
}

.wc-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}

.wc-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 20px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.wc-close:hover {
  color: var(--text);
}

.wc-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Quick actions */
.wc-quick {
  display: flex;
  gap: 10px;
}

.wc-quick-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 0;
  border-radius: 10px;
  border: 1px solid var(--border2);
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.wc-quick-btn.open {
  color: #7c6aff;
  border-color: #7c6aff44;
}
.wc-quick-btn.open:hover:not(:disabled) {
  background: #7c6aff18;
}

.wc-quick-btn.close {
  color: #00d4ff;
  border-color: #00d4ff44;
}
.wc-quick-btn.close:hover:not(:disabled) {
  background: #00d4ff18;
}

.wc-quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Slider area */
.wc-slider-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 28px;
  padding-bottom: 10px;
}

.wc-slider-track {
  position: relative;
  width: 100%;
  height: 40px;
  background: #0d1422;
  border: 1px solid var(--border2);
  border-radius: 20px;
  overflow: visible;
}

.wc-slider-fill {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  background: linear-gradient(to right, #7c6aff, #00d4ff);
  border-radius: 20px 0 0 20px;
  transition: width 0.15s ease;
  pointer-events: none;
}

.wc-slider-input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  margin: 0;
}

.wc-slider-labels {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24px;
}

.wc-label-left,
.wc-label-right {
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.wc-slider-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--text);
  font-family: var(--mono);
  letter-spacing: -0.02em;
}

/* Current state indicators */
.wc-indicator {
  position: absolute;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  z-index: 2;
}

.wc-indicator-bottom {
  top: 100%;
  margin-top: 4px;
}

.wc-indicator-top {
  bottom: 100%;
  margin-bottom: 4px;
  flex-direction: column-reverse;
}

.wc-indicator-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--wc);
  box-shadow: 0 0 5px var(--wc);
  flex-shrink: 0;
}

.wc-indicator-val {
  font-size: 9px;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--wc);
  white-space: nowrap;
  margin-top: 2px;
}

.wc-indicator-top .wc-indicator-val {
  margin-top: 0;
  margin-bottom: 2px;
}

/* Legend */
.wc-legend {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 12px;
}

.wc-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wc-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.wc-legend-label {
  font-size: 10px;
  color: var(--muted);
  font-weight: 600;
}

/* Apply button */
.wc-apply-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #7c6aff, #00d4ff);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
}
.wc-apply-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.wc-apply-btn:disabled {
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
.modal-enter-active .wc-modal,
.modal-leave-active .wc-modal {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .wc-modal,
.modal-leave-to .wc-modal {
  transform: scale(0.95);
  opacity: 0;
}
</style>
