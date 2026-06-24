<template>
  <Teleport to="body">
    <Transition name="confirm">
      <div v-if="visible" class="confirm-overlay" @click.self="cancel">
        <div class="confirm-dialog">
          <div class="confirm-icon-wrap" :class="variant">
            <component :is="iconComp" :size="28" />
          </div>
          <h3 class="confirm-title">{{ title }}</h3>
          <p v-if="message" class="confirm-message">{{ message }}</p>
          <div class="confirm-actions">
            <button class="confirm-btn secondary" @click="cancel" :disabled="loading">
              {{ cancelLabel }}
            </button>
            <button class="confirm-btn" :class="variant" @click="ok" :disabled="loading">
              <Loader v-if="loading" :size="14" class="spinning" />
              <span v-else>{{ confirmLabel }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { AlertTriangle, Trash2, Info, Loader } from 'lucide-vue-next'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: 'Are you sure?' },
  message: { type: String, default: '' },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' },
  variant: { type: String, default: 'danger' }, // danger | warning | info
  icon: { type: String, default: '' }, // trash | warning | info
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

const iconComp = computed(() => {
  if (props.icon === 'trash') return Trash2
  if (props.icon === 'info') return Info
  return AlertTriangle
})

function ok() {
  emit('confirm')
}
function cancel() {
  if (!props.loading) emit('cancel')
}
</script>

<style scoped>
.confirm-overlay {
  position: fixed; inset: 0; z-index: 9500;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(6px);
}
.confirm-dialog {
  background: var(--card, #111420);
  border: 1px solid var(--border, #1a1f30);
  border-radius: 18px;
  padding: 28px 24px 22px;
  width: 100%; max-width: 360px;
  margin: 0 16px;
  text-align: center;
  animation: confirm-pop 0.25s cubic-bezier(.34,1.56,.64,1);
}
@media (min-width: 640px) {
  .confirm-dialog { padding: 32px 28px 24px; margin: 0; }
}

@keyframes confirm-pop {
  from { transform: scale(0.85) translateY(12px); opacity: 0; }
  to   { transform: scale(1) translateY(0); opacity: 1; }
}

.confirm-icon-wrap {
  width: 56px; height: 56px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 16px;
}
.confirm-icon-wrap.danger  { background: #ff525218; color: #ff5252; }
.confirm-icon-wrap.warning { background: #ffb30018; color: #ffb300; }
.confirm-icon-wrap.info    { background: rgba(var(--accent-rgb), 0.094); color: var(--accent); }

.confirm-title {
  font-size: 16px; font-weight: 700;
  color: var(--text, #e2e6f0);
  margin: 0 0 6px;
}
.confirm-message {
  font-size: 13px; line-height: 1.5;
  color: var(--muted, #5c6478);
  margin: 0 0 22px;
}

.confirm-actions {
  display: flex; gap: 10px;
}
.confirm-btn {
  flex: 1; padding: 12px;
  border-radius: 10px;
  font-size: 13px; font-weight: 600;
  cursor: pointer; border: 1px solid transparent;
  transition: all 0.2s;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
.confirm-btn.secondary {
  background: transparent;
  border-color: var(--border, #1a1f30);
  color: var(--muted, #5c6478);
}
.confirm-btn.secondary:hover { background: #ffffff08; }

.confirm-btn.danger {
  background: linear-gradient(135deg, #ff525222, #ff525244);
  border-color: #ff525255;
  color: #ff5252;
}
.confirm-btn.danger:hover {
  background: linear-gradient(135deg, #ff525233, #ff525255);
}

.confirm-btn.warning {
  background: linear-gradient(135deg, #ffb30022, #ffb30044);
  border-color: #ffb30055;
  color: #ffb300;
}
.confirm-btn.warning:hover {
  background: linear-gradient(135deg, #ffb30033, #ffb30055);
}

.confirm-btn.info {
  background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.133), rgba(var(--accent-rgb), 0.267));
  border-color: rgba(var(--accent-rgb), 0.333);
  color: var(--accent);
}
.confirm-btn.info:hover {
  background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.2), rgba(var(--accent-rgb), 0.333));
}

.confirm-btn:disabled {
  opacity: 0.5; cursor: not-allowed;
}

.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* transitions */
.confirm-enter-active { transition: opacity 0.15s ease; }
.confirm-leave-active { transition: opacity 0.12s ease; }
.confirm-enter-from, .confirm-leave-to { opacity: 0; }
</style>
