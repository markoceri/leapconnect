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
              <div class="wc-slider-labels">
                <span class="wc-label-top">0% — Closed</span>
                <span class="wc-label-bottom">100% — Open</span>
              </div>
              <div class="wc-slider-track-wrapper">
                <div class="wc-slider-track">
                  <div class="wc-slider-fill" :style="{ height: sliderValue + '%' }" />
                  <!-- Current min indicator -->
                  <div v-if="currentMin != null" class="wc-indicator wc-indicator-min" :style="{ bottom: currentMin + '%' }" title="Min window">
                    <span class="wc-indicator-line" />
                    <span class="wc-indicator-label">{{ currentMin }}%</span>
                  </div>
                  <!-- Current max indicator -->
                  <div v-if="currentMax != null && currentMax !== currentMin" class="wc-indicator wc-indicator-max" :style="{ bottom: currentMax + '%' }" title="Max window">
                    <span class="wc-indicator-line" />
                    <span class="wc-indicator-label">{{ currentMax }}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    v-model.number="sliderValue"
                    class="wc-slider-input"
                    orient="vertical"
                  />
                </div>
                <div class="wc-slider-value">{{ sliderValue }}%</div>
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

const windowPercents = computed(() => {
  const w = props.windows
  if (!w) return []
  return [
    w.left_front_window_percent,
    w.right_front_window_percent,
    w.left_rear_window_percent,
    w.right_rear_window_percent,
  ].filter(v => v != null)
})

const currentMin = computed(() => {
  if (windowPercents.value.length === 0) return null
  return Math.min(...windowPercents.value)
})

const currentMax = computed(() => {
  if (windowPercents.value.length === 0) return null
  return Math.max(...windowPercents.value)
})

// Initialize slider to average of current window positions when modal opens
watch(() => props.visible, (val) => {
  if (val && windowPercents.value.length > 0) {
    const avg = Math.round(windowPercents.value.reduce((a, b) => a + b, 0) / windowPercents.value.length / 5) * 5
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
  width: 300px;
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
  align-items: stretch;
  gap: 16px;
}

.wc-slider-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.02em;
  flex-shrink: 0;
  width: 90px;
}

.wc-label-top {
  text-align: right;
}
.wc-label-bottom {
  text-align: right;
}

.wc-slider-track-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.wc-slider-track {
  position: relative;
  width: 40px;
  height: 180px;
  background: #0d1422;
  border: 1px solid var(--border2);
  border-radius: 20px;
  overflow: visible;
}

.wc-slider-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to top, #7c6aff, #00d4ff);
  border-radius: 0 0 20px 20px;
  transition: height 0.15s ease;
  pointer-events: none;
}

.wc-slider-input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  writing-mode: vertical-lr;
  direction: rtl;
  -webkit-appearance: none;
  appearance: none;
  margin: 0;
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
  left: 100%;
  transform: translateY(50%);
  display: flex;
  align-items: center;
  pointer-events: none;
  z-index: 2;
}

.wc-indicator-line {
  width: 12px;
  height: 2px;
  flex-shrink: 0;
}

.wc-indicator-min .wc-indicator-line {
  background: #00d4ff;
}

.wc-indicator-max .wc-indicator-line {
  background: #7c6aff;
}

.wc-indicator-label {
  font-size: 9px;
  font-weight: 700;
  font-family: var(--mono);
  white-space: nowrap;
  margin-left: 4px;
}

.wc-indicator-min .wc-indicator-label {
  color: #00d4ff;
}

.wc-indicator-max .wc-indicator-label {
  color: #7c6aff;
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
