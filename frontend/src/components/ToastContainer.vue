<template>
  <div class="toast-container">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast"
      :class="[t.type, { removing: t.removing }]"
    >
      <component :is="iconComp(t.type)" :size="15" class="toast-icon" />
      {{ t.message }}
    </div>
  </div>
</template>

<script setup>
import { useToast } from '../composables/useToast'
import { Check, X, Info } from 'lucide-vue-next'

const { toasts } = useToast()

function iconComp(type) {
  if (type === 'success') return Check
  if (type === 'error') return X
  return Info
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 80px;
  left: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  pointer-events: none;
}
@media (min-width: 768px) {
  .toast-container {
    left: auto;
    bottom: 28px;
    right: 28px;
    align-items: flex-end;
  }
}

.toast {
  background: var(--elevated);
  border: 1px solid;
  border-radius: 10px;
  padding: 12px 18px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  font-size: 13px;
  color: var(--heading);
  display: flex;
  align-items: center;
  gap: 10px;
  pointer-events: auto;
  animation: lm-slideup 0.3s ease both;
  max-width: 400px;
}
.toast.success { border-color: #00e67655; border-left: 3px solid #00e676; }
.toast.error { border-color: #ff525255; border-left: 3px solid #ff5252; }
.toast.info { border-color: #00d4ff55; border-left: 3px solid #00d4ff; }
.toast.removing { opacity: 0; transform: translateX(40px); transition: all 0.3s; }

.toast-icon { font-weight: 700; font-size: 15px; }
.toast.success .toast-icon { color: var(--green); }
.toast.error .toast-icon { color: var(--red); }
.toast.info .toast-icon { color: var(--cyan); }
</style>
