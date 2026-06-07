<template>
  <Teleport to="body">
    <div v-if="item" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-dialog">
        <h3>Edit: {{ item.label }}</h3>
        <div class="form-group">
          <label>Interval (km)</label>
          <input v-model.number="form.interval_km" type="number" min="0" />
        </div>
        <div class="form-group">
          <label>Interval (months)</label>
          <input v-model.number="form.interval_months" type="number" min="0" />
        </div>
        <div class="form-group">
          <label>Trigger mode</label>
          <select v-model="form.trigger_mode">
            <option value="or">Either (km or time)</option>
            <option value="km">Kilometers only</option>
            <option value="time">Time only</option>
            <option value="and">Both required</option>
          </select>
        </div>
        <div class="form-group">
          <label>Priority</label>
          <select v-model="form.priority">
            <option value="routine">Routine</option>
            <option value="important">Important</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
        <div class="form-group">
          <label>Last done (km)</label>
          <input v-model.number="form.last_done_km" type="number" min="0" />
        </div>
        <div class="form-group">
          <label>Enabled</label>
          <div class="toggle-wrap">
            <button class="toggle-btn" :class="{ on: form.enabled }" @click="form.enabled = !form.enabled">
              {{ form.enabled ? 'ON' : 'OFF' }}
            </button>
          </div>
          <p class="field-hint">When OFF, the item stays in your plan but is excluded from overdue/upcoming counts and reminders.</p>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="$emit('close')">Cancel</button>
          <button class="btn-save" :disabled="saving" @click="submit">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
        <div v-if="errorMsg" class="field-error">{{ errorMsg }}</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../composables/useApi'

const props = defineProps({
  vin: { type: String, required: true },
  // Pass the plan item to edit, or null to close.
  item: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const form = ref({})
const saving = ref(false)
const errorMsg = ref('')

watch(() => props.item, (it) => {
  if (it) {
    form.value = {
      interval_km: it.interval_km,
      interval_months: it.interval_months,
      trigger_mode: it.trigger_mode,
      priority: it.priority,
      last_done_km: it.last_done_km,
      enabled: it.enabled,
      notes: it.notes,
    }
    errorMsg.value = ''
  }
})

async function submit() {
  saving.value = true
  errorMsg.value = ''
  try {
    await api('PUT', `/api/vehicles/${props.vin}/maintenance/plan/${encodeURIComponent(props.item.service_type)}`, form.value)
    emit('saved')
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0; background: #00000080; display: flex;
  align-items: center; justify-content: center; z-index: 2000;
}
.modal-dialog {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 24px; width: 90%; max-width: 420px; max-height: 80vh; overflow-y: auto;
}
.modal-dialog h3 { margin: 0 0 16px; color: var(--text); }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-group input, .form-group select {
  width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--input); color: var(--text); font-size: 14px;
}
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.btn-cancel {
  padding: 8px 16px; border-radius: 8px; background: var(--btn-bg); border: 1px solid var(--btn-border);
  color: var(--muted); cursor: pointer; font-size: 13px;
}
.btn-save {
  padding: 8px 16px; border-radius: 8px; background: var(--cyan); border: none;
  color: #000; cursor: pointer; font-size: 13px; font-weight: 600;
}
.btn-save:disabled { opacity: 0.5; cursor: default; }
.field-error { color: var(--red); font-size: 13px; margin-top: 8px; }
.toggle-wrap { display: flex; }
.toggle-btn {
  padding: 6px 18px; border-radius: 8px; border: 1.5px solid var(--btn-border);
  background: var(--btn-bg); color: var(--muted); cursor: pointer; font-size: 12px; font-weight: 700;
  transition: all 0.15s;
}
.toggle-btn.on { border-color: var(--green); color: var(--green); background: rgba(0,230,118,0.06); }
.field-hint { margin: 6px 0 0; font-size: 11px; color: var(--muted); line-height: 1.45; }
</style>
