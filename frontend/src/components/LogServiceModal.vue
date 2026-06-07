<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-dialog">
        <h3>{{ isEdit ? 'Edit Service Record' : 'Log Service' }}</h3>
        <p class="edit-date">{{ displayLabel }}</p>
        <div class="form-group">
          <label>Date</label>
          <input v-model="form.timestamp" type="datetime-local" />
        </div>
        <div class="form-group">
          <label>Mileage (km)</label>
          <div class="mileage-row">
            <input v-model.number="form.mileage_km" type="number" min="0" />
            <button class="fetch-km-btn" title="Use current odometer reading" @click="fetchCurrentKm">
              <RefreshCw :size="14" :class="{ spinning: fetchingKm }" />
              {{ fetchingKm ? 'Loading…' : 'Use current' }}
            </button>
          </div>
        </div>
        <div class="form-group">
          <label>Cost (&euro;)</label>
          <input v-model.number="form.cost" type="number" step="0.01" min="0" placeholder="0.00" />
        </div>
        <div class="form-group">
          <label>Provider</label>
          <input v-model="form.provider" type="text" placeholder="Service center name" />
        </div>
        <div class="form-group">
          <label>Notes</label>
          <input v-model="form.notes" type="text" placeholder="Optional notes" />
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
import { computed, ref, watch } from 'vue'
import { api } from '../composables/useApi'
import { RefreshCw } from 'lucide-vue-next'
import { parseUTC } from '../utils/maintenance'

const props = defineProps({
  visible: { type: Boolean, default: false },
  vin: { type: String, required: true },
  serviceType: { type: String, default: '' },
  label: { type: String, default: '' },
  // When provided, the modal edits this existing record instead of creating one.
  record: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const form = ref({})
const saving = ref(false)
const fetchingKm = ref(false)
const errorMsg = ref('')

const isEdit = computed(() => !!props.record)
const displayLabel = computed(() => props.record?.label || props.label)

function toLocalInput(date) {
  return date.getFullYear() + '-' +
    String(date.getMonth() + 1).padStart(2, '0') + '-' +
    String(date.getDate()).padStart(2, '0') + 'T' +
    String(date.getHours()).padStart(2, '0') + ':' +
    String(date.getMinutes()).padStart(2, '0')
}

watch(() => props.visible, (v) => {
  if (!v) return
  errorMsg.value = ''
  if (props.record) {
    const d = parseUTC(props.record.timestamp) || new Date()
    form.value = {
      timestamp: toLocalInput(d),
      mileage_km: props.record.mileage_km,
      cost: props.record.cost,
      provider: props.record.provider || '',
      notes: props.record.notes || '',
    }
  } else {
    form.value = { timestamp: toLocalInput(new Date()), mileage_km: null, cost: null, provider: '', notes: '' }
  }
})

async function fetchCurrentKm() {
  fetchingKm.value = true
  try {
    const data = await api('GET', `/api/vehicles/${props.vin}/maintenance/current-mileage`)
    if (data.mileage_km != null) form.value.mileage_km = data.mileage_km
  } catch {
    /* ignore — leave field as-is */
  }
  fetchingKm.value = false
}

function isoFromLocalInput(value) {
  if (!value) return null
  const [datePart, timePart] = value.split('T')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm] = timePart.split(':').map(Number)
  return new Date(y, m - 1, d, hh, mm).toISOString()
}

async function submit() {
  saving.value = true
  errorMsg.value = ''
  try {
    if (isEdit.value) {
      const body = {
        timestamp: isoFromLocalInput(form.value.timestamp),
        mileage_km: form.value.mileage_km,
        cost: form.value.cost,
        provider: form.value.provider,
        notes: form.value.notes,
      }
      await api('PUT', `/api/vehicles/${props.vin}/maintenance/records/${props.record.id}`, body)
    } else {
      const body = { service_type: props.serviceType, label: props.label, ...form.value }
      body.timestamp = isoFromLocalInput(body.timestamp)
      await api('POST', `/api/vehicles/${props.vin}/maintenance/records`, body)
    }
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
.modal-dialog h3 { margin: 0 0 8px; color: var(--text); }
.edit-date { color: var(--muted); font-size: 13px; margin: 0 0 16px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-group input {
  width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--input); color: var(--text); font-size: 14px;
}
.mileage-row { display: flex; gap: 8px; align-items: center; }
.mileage-row input { flex: 1; }
.fetch-km-btn {
  display: flex; align-items: center; gap: 6px; white-space: nowrap;
  padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(0,212,255,0.27);
  background: rgba(0,212,255,0.06); color: var(--cyan); cursor: pointer; font-size: 12px; font-weight: 600;
  transition: all 0.15s;
}
.fetch-km-btn:hover { background: rgba(0,212,255,0.13); border-color: rgba(0,212,255,0.53); }
.fetch-km-btn:disabled { opacity: 0.5; cursor: default; }
.spinning { animation: spin 0.8s linear infinite; }
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
@keyframes spin { to { transform: rotate(360deg); } }
</style>
