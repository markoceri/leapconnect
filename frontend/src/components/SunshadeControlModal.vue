<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="sc-overlay" @click.self="$emit('close')">
        <div class="sc-modal">
          <div class="sc-header">
            <div class="sc-header-left">
              <Sun :size="16" class="sc-header-icon" />
              <span class="sc-title">Sunshade</span>
            </div>
            <button class="sc-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="sc-body">
            <!-- Quick actions -->
            <div class="sc-quick">
              <button
                class="sc-quick-btn open"
                :class="{ loading: loadingAction === 'open' }"
                :disabled="!!loadingAction"
                @click="quickAction('open')"
              >
                <Loader v-if="loadingAction === 'open'" :size="16" class="spinning" />
                <Sun v-else :size="16" />
                <span>Open</span>
              </button>
              <button
                class="sc-quick-btn close"
                :class="{ loading: loadingAction === 'close' }"
                :disabled="!!loadingAction"
                @click="quickAction('close')"
              >
                <Loader v-if="loadingAction === 'close'" :size="16" class="spinning" />
                <MoonStar v-else :size="16" />
                <span>Close</span>
              </button>
            </div>

            <!-- Horizontal slider -->
            <div class="sc-slider-area">
              <div class="sc-slider-track">
                <div class="sc-slider-fill" :style="{ width: (sliderValue / 10 * 100) + '%' }" />
                <!-- Current state indicator -->
                <div v-if="currentValue != null" class="sc-indicator" :style="{ left: (currentValue / 10 * 100) + '%' }">
                  <span class="sc-indicator-line" />
                  <span class="sc-indicator-label">{{ currentValue }}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="1"
                  v-model.number="sliderValue"
                  class="sc-slider-input"
                />
              </div>
              <div class="sc-slider-labels">
                <span class="sc-label-left">0 — Closed</span>
                <span class="sc-slider-value">{{ sliderValue }}</span>
                <span class="sc-label-right">10 — Open</span>
              </div>
            </div>

            <!-- Apply -->
            <button
              class="sc-apply-btn"
              :class="{ loading: loadingAction === 'custom' }"
              :disabled="!!loadingAction"
              @click="applyCustom"
            >
              <Loader v-if="loadingAction === 'custom'" :size="14" class="spinning" />
              <span>Set to {{ sliderValue }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Sun, MoonStar, Loader } from 'lucide-vue-next'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
  sunshade: { type: Number, default: null },
})

const emit = defineEmits(['close'])

const sliderValue = ref(0)
const loadingAction = ref(null)

const currentValue = computed(() => {
  return props.sunshade != null ? props.sunshade : null
})

// Initialize slider to current sunshade value when modal opens
watch(() => props.visible, (val) => {
  if (val && props.sunshade != null) {
    sliderValue.value = props.sunshade
  }
})

async function quickAction(type) {
  const action = type === 'open' ? 'sunshade/open' : 'sunshade/close'
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
    if (props.onExec) await props.onExec({ action: 'sunshade', body: { value: String(sliderValue.value) } })
  } finally {
    loadingAction.value = null
  }
}
</script>

<style scoped>
.sc-overlay {
  position: fixed;
  inset: 0;
  background: #000000aa;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5000;
  backdrop-filter: blur(4px);
}

.sc-modal {
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: 16px;
  width: 320px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 16px 48px #00000088;
}

.sc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--border2);
}

.sc-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sc-header-icon {
  color: #ffab40;
}

.sc-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}

.sc-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 20px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.sc-close:hover {
  color: var(--text);
}

.sc-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Quick actions */
.sc-quick {
  display: flex;
  gap: 10px;
}

.sc-quick-btn {
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

.sc-quick-btn.open {
  color: #ffab40;
  border-color: #ffab4044;
}
.sc-quick-btn.open:hover:not(:disabled) {
  background: #ffab4018;
}

.sc-quick-btn.close {
  color: #4a5468;
  border-color: #4a546844;
}
.sc-quick-btn.close:hover:not(:disabled) {
  background: #4a546818;
}

.sc-quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Horizontal slider */
.sc-slider-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sc-slider-track {
  position: relative;
  width: 100%;
  height: 40px;
  background: #0d1422;
  border: 1px solid var(--border2);
  border-radius: 20px;
  overflow: visible;
}

.sc-slider-fill {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  background: linear-gradient(to right, #ffab40, #ffd180);
  border-radius: 20px 0 0 20px;
  transition: width 0.15s ease;
  pointer-events: none;
}

.sc-slider-input {
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

.sc-slider-labels {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sc-label-left,
.sc-label-right {
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.sc-slider-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--text);
  font-family: var(--mono);
  letter-spacing: -0.02em;
}

/* Current state indicator */
.sc-indicator {
  position: absolute;
  top: 100%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  z-index: 2;
}

.sc-indicator-line {
  width: 2px;
  height: 10px;
  background: #ffab40;
}

.sc-indicator-label {
  font-size: 9px;
  font-weight: 700;
  font-family: var(--mono);
  color: #ffab40;
  margin-top: 2px;
}

/* Apply button */
.sc-apply-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #ffab40, #ffd180);
  color: #0d1422;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
}
.sc-apply-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.sc-apply-btn:disabled {
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
.modal-enter-active .sc-modal,
.modal-leave-active .sc-modal {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .sc-modal,
.modal-leave-to .sc-modal {
  transform: scale(0.95);
  opacity: 0;
}
</style>
