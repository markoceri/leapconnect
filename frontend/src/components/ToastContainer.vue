<template>
  <div class="toast-container">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast"
      :class="[t.type, { removing: t.removing }]"
    >
      <span class="toast-icon">{{ icon(t.type) }}</span>
      {{ t.message }}
    </div>
  </div>
</template>

<script setup>
import { useToast } from '../composables/useToast'

const { toasts } = useToast()

function icon(type) {
  if (type === 'success') return '✓'
  if (type === 'error') return '✕'
  return 'ℹ'
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}

.toast {
  padding: 0.8rem 1.2rem;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  font-size: 0.82rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  pointer-events: auto;
  animation: toastIn 0.35s ease both;
  max-width: 400px;
}
.toast.success { border-color: rgba(0, 230, 118, 0.3); }
.toast.error { border-color: rgba(255, 61, 90, 0.3); }
.toast.removing { animation: toastOut 0.3s ease both; }

.toast-icon { font-weight: 700; }
.toast.success .toast-icon { color: var(--accent-green); }
.toast.error .toast-icon { color: var(--accent-red); }
.toast.info .toast-icon { color: var(--accent); }

@keyframes toastIn {
  from { opacity: 0; transform: translateX(40px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes toastOut {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(40px); }
}
</style>
