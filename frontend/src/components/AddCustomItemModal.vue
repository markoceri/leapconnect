<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-dialog">
        <h3>Add custom intervention</h3>
        <p class="sub">Schedule your own maintenance. It stays local and can be exported to share.</p>
        <div class="form-group">
          <label>Name *</label>
          <input v-model="form.label" type="text" placeholder="e.g. Pollen filter — clean" @input="maybeDeriveType" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Identifier *</label>
            <input v-model="form.service_type" type="text" placeholder="pollen_filter_clean" />
          </div>
          <div class="form-group">
            <label>Category</label>
            <input v-model="form.category" type="text" placeholder="other" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Interval (km)</label>
            <input v-model.number="form.interval_km" type="number" min="0" placeholder="—" />
          </div>
          <div class="form-group">
            <label>Interval (months)</label>
            <input v-model.number="form.interval_months" type="number" min="0" placeholder="—" />
          </div>
        </div>
        <div class="form-row">
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
        </div>
        <div class="form-group">
          <label>Last done (km, optional)</label>
          <input v-model.number="form.last_done_km" type="number" min="0" placeholder="—" />
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="$emit('close')">Cancel</button>
          <button class="btn-save" :disabled="saving || !valid" @click="submit">{{ saving ? 'Saving…' : 'Add' }}</button>
        </div>
        <div v-if="errorMsg" class="field-error">{{ errorMsg }}</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '../composables/useApi'

const props = defineProps({
  visible: { type: Boolean, default: false },
  vin: { type: String, required: true },
})
const emit = defineEmits(['close', 'saved'])

const blank = () => ({
  label: '', service_type: '', category: 'other',
  interval_km: null, interval_months: null,
  trigger_mode: 'or', priority: 'routine', last_done_km: null,
})
const form = ref(blank())
const saving = ref(false)
const errorMsg = ref('')
let typeEdited = false

const valid = computed(() => form.value.label.trim() && form.value.service_type.trim())

watch(() => props.visible, (v) => {
  if (v) { form.value = blank(); errorMsg.value = ''; typeEdited = false }
})

function maybeDeriveType() {
  // Auto-suggest an identifier from the name until the user edits it manually.
  if (typeEdited) return
  form.value.service_type = form.value.label
    .toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

async function submit() {
  saving.value = true
  errorMsg.value = ''
  try {
    await api('POST', `/api/vehicles/${props.vin}/maintenance/plan`, { ...form.value })
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
  padding: 24px; width: 90%; max-width: 460px; max-height: 85vh; overflow-y: auto;
}
.modal-dialog h3 { margin: 0 0 4px; color: var(--text); }
.sub { color: var(--muted); font-size: 12px; margin: 0 0 16px; line-height: 1.4; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
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
</style>
