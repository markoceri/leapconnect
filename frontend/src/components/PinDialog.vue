<template>
  <Teleport to="body">
    <div v-if="visible" class="pin-overlay" @click.self="cancel">
      <div class="pin-dialog">
        <div class="pin-header">
          <span class="pin-icon">🔑</span>
          <span class="pin-title">Vehicle PIN Required</span>
        </div>
        <p class="pin-desc">Enter the vehicle operation PIN to execute remote commands.</p>
        <form @submit.prevent="submit">
          <input
            ref="pinInput"
            v-model="pin"
            type="password"
            class="pin-input"
            placeholder="Enter PIN"
            autofocus
          />
          <label class="pin-remember">
            <input type="checkbox" v-model="remember" />
            <span>Non chiedere più per questa sessione</span>
          </label>
          <div class="pin-actions">
            <button type="button" class="pin-btn cancel" @click="cancel">Cancel</button>
            <button type="submit" class="pin-btn confirm" :disabled="!pin.trim() || submitting">
              {{ submitting ? 'Verifying…' : 'Confirm' }}
            </button>
          </div>
          <div v-if="error" class="pin-error">{{ error }}</div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['confirmed', 'cancelled'])

const pin = ref('')
const remember = ref(false)
const error = ref('')
const submitting = ref(false)
const pinInput = ref(null)

watch(() => props.visible, async (v) => {
  if (v) {
    pin.value = ''
    error.value = ''
    submitting.value = false
    await nextTick()
    pinInput.value?.focus()
  }
})

function cancel() {
  emit('cancelled')
}

async function submit() {
  if (!pin.value.trim()) return
  submitting.value = true
  error.value = ''
  emit('confirmed', { pin: pin.value.trim(), remember: remember.value })
}

function setError(msg) {
  error.value = msg
  submitting.value = false
}

defineExpose({ setError })
</script>

<style scoped>
.pin-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(6px);
  animation: pin-fadein 0.15s ease;
}

@keyframes pin-fadein {
  from { opacity: 0; }
  to { opacity: 1; }
}

.pin-dialog {
  background: var(--card, #111420);
  border: 1px solid var(--border, #1a1f30);
  border-radius: 18px;
  padding: 32px 28px;
  width: 100%;
  max-width: 380px;
  animation: pin-slideup 0.2s ease;
}

@keyframes pin-slideup {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.pin-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.pin-icon { font-size: 20px; }

.pin-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text, #e2e6f0);
}

.pin-desc {
  font-size: 13px;
  color: var(--muted, #5c6478);
  margin-bottom: 18px;
  line-height: 1.4;
}

.pin-input {
  width: 100%;
  padding: 13px 16px;
  background: var(--input, #0d1019);
  border: 1px solid #1c2240;
  border-radius: 10px;
  color: var(--text, #e2e6f0);
  font-size: 16px;
  letter-spacing: 0.15em;
  text-align: center;
  outline: none;
  transition: border-color 0.2s;
}

.pin-input:focus {
  border-color: #00d4ff55;
}

.pin-input::placeholder {
  letter-spacing: normal;
  color: var(--muted2, #343b50);
}

.pin-remember {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--muted, #5c6478);
  cursor: pointer;
  user-select: none;
}

.pin-remember input[type="checkbox"] {
  accent-color: #00d4ff;
  width: 15px;
  height: 15px;
  cursor: pointer;
}

.pin-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.pin-btn {
  flex: 1;
  padding: 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.pin-btn.cancel {
  background: transparent;
  border-color: var(--border, #1a1f30);
  color: var(--muted, #5c6478);
}

.pin-btn.cancel:hover {
  background: #ffffff08;
}

.pin-btn.confirm {
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border-color: #00d4ff55;
  color: #00d4ff;
}

.pin-btn.confirm:hover {
  background: linear-gradient(135deg, #00d4ff33, #00d4ff55);
}

.pin-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pin-error {
  margin-top: 12px;
  padding: 9px 12px;
  background: #ff525210;
  border: 1px solid #ff525230;
  border-radius: 8px;
  color: #ff5252;
  font-size: 12px;
  text-align: center;
}
</style>
