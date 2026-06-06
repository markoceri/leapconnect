<template>
  <div class="maintenance-tab">
    <!-- Header -->
    <div class="mnt-header">
      <div class="header-title">
        <h2>Maintenance</h2>
        <p>Service tracker &amp; history</p>
      </div>
    </div>

    <!-- C10 Variant Prompt -->
    <div v-if="needsC10Confirmation" class="variant-prompt">
      <div class="prompt-card">
        <h3>C10 Variant Required</h3>
        <p>Select your C10 model variant to load the correct service schedule:</p>
        <div class="variant-buttons">
          <button class="variant-btn" @click="confirmVariant('bev')">
            <Zap :size="20" />
            <span>Pure Electric (BEV)</span>
          </button>
          <button class="variant-btn" @click="confirmVariant('reev')">
            <Flame :size="20" />
            <span>Range Extender (REEV)</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-row">
      <div class="spinner" />
    </div>

    <!-- Overview cards -->
    <div v-if="!loading && !needsC10Confirmation" class="mnt-content">
      <div class="summary-grid">
        <div class="summary-card" :class="{ warn: overview.overdue_count > 0 }">
          <div class="summary-value" :style="{ color: overview.overdue_count > 0 ? '#ff5252' : '#00e676' }">
            {{ overview.overdue_count }}
          </div>
          <div class="summary-label">Overdue</div>
        </div>
        <div class="summary-card">
          <div class="summary-value" style="color: #ffab40">{{ overview.upcoming_count }}</div>
          <div class="summary-label">Upcoming</div>
        </div>
        <div class="summary-card">
          <div class="summary-value">{{ overview.total_items }}</div>
          <div class="summary-label">Total Items</div>
        </div>
        <div class="summary-card">
          <div class="summary-value">{{ overview.model_key }}</div>
          <div class="summary-label">Model</div>
        </div>
      </div>

      <!-- Next Action -->
      <div v-if="overview.next_item" class="next-action-card">
        <div class="next-header">
          <AlertTriangle :size="18" />
          <span>Next action</span>
        </div>
        <div class="next-body">
          <span class="next-label">{{ overview.next_item.label }}</span>
          <span class="next-priority" :class="'prio-' + overview.next_item.priority">
            {{ overview.next_item.priority }}
          </span>
        </div>
      </div>

      <!-- Plan Items -->
      <div class="chart-card wide">
        <div class="chart-header"><ClipboardList :size="16" class="chart-icon" /> Service Plan</div>
        <div class="plan-table-wrap">
          <table class="plan-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Category</th>
                <th>Interval</th>
                <th>Priority</th>
                <th>Last Done</th>
                <th>Due</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.plan" :key="item.id" :class="{ disabled: !item.enabled }">
                <td>{{ item.label }}</td>
                <td><span class="cat-badge">{{ item.category }}</span></td>
                <td>{{ formatInterval(item) }}</td>
                <td><span class="prio-badge" :class="'prio-' + item.priority">{{ item.priority }}</span></td>
                <td>{{ formatLastDone(item) }}</td>
                <td>{{ formatDue(item) }}</td>
                <td>
                  <button class="icon-btn" title="Log service" @click="openRecord(item)">&#10003;</button>
                  <button class="icon-btn" title="Edit" @click="openEdit(item)">&#9998;</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Recent Records -->
      <div class="chart-card wide">
        <div class="chart-header"><History :size="16" class="chart-icon" /> Recent Service Records</div>
        <div v-if="!overview.recent_records.length" class="empty-row">No service records yet</div>
        <div v-for="r in overview.recent_records" :key="r.id" class="record-row">
          <div class="rec-info">
            <span class="rec-label">{{ r.label }}</span>
            <span class="rec-date">{{ formatDate(r.timestamp) }}</span>
          </div>
          <div class="rec-details">
            <span v-if="r.mileage_km != null">{{ r.mileage_km.toLocaleString() }} km</span>
            <span v-if="r.provider">{{ r.provider }}</span>
            <span v-if="r.cost != null" class="rec-cost">&euro;{{ r.cost.toFixed(2) }}</span>
          </div>
          <button class="icon-btn icon-delete" title="Delete" @click="openDelete(r)">&times;</button>
        </div>
      </div>
    </div>

    <!-- Log Service Modal -->
    <Teleport to="body">
      <div v-if="showRecordModal" class="modal-backdrop" @click.self="showRecordModal = false">
        <div class="modal-dialog">
          <h3>Log Service</h3>
          <p class="edit-date">{{ recordForm.label }}</p>
          <div class="form-group">
            <label>Date</label>
            <input v-model="recordForm.timestamp" type="datetime-local" />
          </div>
          <div class="form-group">
            <label>Mileage (km)</label>
            <div class="mileage-row">
              <input v-model.number="recordForm.mileage_km" type="number" min="0" />
              <button class="fetch-km-btn" title="Use current odometer reading" @click="fetchCurrentKm">
                <RefreshCw :size="14" :class="{ spinning: fetchingKm }" />
                {{ fetchingKm ? 'Loading…' : 'Use current' }}
              </button>
            </div>
          </div>
          <div class="form-group">
            <label>Cost (&euro;)</label>
            <input v-model.number="recordForm.cost" type="number" step="0.01" min="0" placeholder="0.00" />
          </div>
          <div class="form-group">
            <label>Provider</label>
            <input v-model="recordForm.provider" type="text" placeholder="Service center name" />
          </div>
          <div class="form-group">
            <label>Notes</label>
            <input v-model="recordForm.notes" type="text" placeholder="Optional notes" />
          </div>
          <div class="modal-actions">
            <button class="btn-cancel" @click="showRecordModal = false">Cancel</button>
            <button class="btn-save" :disabled="saving" @click="submitRecord">{{ saving ? 'Saving…' : 'Save' }}</button>
          </div>
          <div v-if="errorMsg" class="field-error">{{ errorMsg }}</div>
        </div>
      </div>
    </Teleport>

    <!-- Edit Plan Item Modal -->
    <Teleport to="body">
      <div v-if="editItem" class="modal-backdrop" @click.self="editItem = null">
        <div class="modal-dialog">
          <h3>Edit: {{ editItem.label }}</h3>
          <div class="form-group">
            <label>Interval (km)</label>
            <input v-model.number="editForm.interval_km" type="number" min="0" />
          </div>
          <div class="form-group">
            <label>Interval (months)</label>
            <input v-model.number="editForm.interval_months" type="number" min="0" />
          </div>
          <div class="form-group">
            <label>Trigger mode</label>
            <select v-model="editForm.trigger_mode">
              <option value="or">Either (km or time)</option>
              <option value="km">Kilometers only</option>
              <option value="time">Time only</option>
              <option value="and">Both required</option>
            </select>
          </div>
          <div class="form-group">
            <label>Priority</label>
            <select v-model="editForm.priority">
              <option value="routine">Routine</option>
              <option value="important">Important</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
          <div class="form-group">
            <label>Last done (km)</label>
            <input v-model.number="editForm.last_done_km" type="number" min="0" />
          </div>
          <div class="form-group">
            <label>Enabled</label>
            <div class="toggle-wrap">
              <button class="toggle-btn" :class="{ on: editForm.enabled }" @click="editForm.enabled = !editForm.enabled">
                {{ editForm.enabled ? 'ON' : 'OFF' }}
              </button>
            </div>
            <p class="field-hint">When OFF, the item stays visible but is excluded from overdue/upcoming counts and reminders. Use this to temporarily disable services that don't apply to your usage.</p>
          </div>
          <div class="modal-actions">
            <button class="btn-cancel" @click="editItem = null">Cancel</button>
            <button class="btn-save" :disabled="saving" @click="submitEdit">{{ saving ? 'Saving…' : 'Save' }}</button>
          </div>
          <div v-if="errorMsg" class="field-error">{{ errorMsg }}</div>
        </div>
      </div>
    </Teleport>

    <!-- Delete confirmation -->
    <ConfirmDialog
      :visible="showDeleteConfirm"
      title="Delete service record?"
      :message="`Are you sure you want to delete '${deleteTargetLabel}'? This cannot be undone.`"
      confirm-label="Delete"
      cancel-label="Cancel"
      variant="danger"
      icon="trash"
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { api } from '../composables/useApi'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { Wrench, Zap, Flame, AlertTriangle, ClipboardList, History, RefreshCw } from 'lucide-vue-next'

const props = defineProps({
  vin: { type: String, required: true },
  status: { type: Object, default: () => ({}) },
  vehicle: { type: Object, default: () => ({}) },
})

const loading = ref(true)
const errorMsg = ref('')
const overview = ref({ total_items: 0, upcoming_count: 0, overdue_count: 0, critical_count: 0, model_key: '', display_name: '', plan: [], recent_records: [], next_item: null })
const needsC10Confirmation = ref(false)
const saving = ref(false)
const fetchingKm = ref(false)
const showDeleteConfirm = ref(false)
const deleteTargetId = ref(null)
const deleteTargetLabel = ref('')
const deleting = ref(false)

// Load data
async function load() {
  loading.value = true
  errorMsg.value = ''

  try {
    // First check model resolution
    const modelInfo = await api('GET', `/api/vehicles/${props.vin}/maintenance/model`)
    if (modelInfo.needs_confirmation) {
      needsC10Confirmation.value = true
      loading.value = false
      return
    }
    needsC10Confirmation.value = false
    // Load overview
    overview.value = await api('GET', `/api/vehicles/${props.vin}/maintenance/overview`)
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function confirmVariant(variant) {
  loading.value = true
  try {
    await api('POST', `/api/vehicles/${props.vin}/maintenance/model`, { variant })
    needsC10Confirmation.value = false
    overview.value = await api('GET', `/api/vehicles/${props.vin}/maintenance/overview`)
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

// Record modal
const showRecordModal = ref(false)
const recordForm = ref({})

function openRecord(item) {
  // Format current local time for datetime-local input (YYYY-MM-DDTHH:MM)
  const now = new Date()
  const localTS = now.getFullYear() + '-' +
    String(now.getMonth() + 1).padStart(2, '0') + '-' +
    String(now.getDate()).padStart(2, '0') + 'T' +
    String(now.getHours()).padStart(2, '0') + ':' +
    String(now.getMinutes()).padStart(2, '0')

  recordForm.value = {
    service_type: item.service_type,
    label: item.label,
    timestamp: localTS,
    mileage_km: null,
    cost: null,
    provider: '',
    notes: '',
  }
  showRecordModal.value = true
}

async function submitRecord() {
  saving.value = true
  errorMsg.value = ''
  try {
    // Convert local datetime-local value to ISO UTC string for the API
    const body = { ...recordForm.value }
    if (body.timestamp) {
      // Parse as local time (datetime-local input has no timezone)
      const [datePart, timePart] = body.timestamp.split('T')
      const [y, m, d] = datePart.split('-').map(Number)
      const [hh, mm] = timePart.split(':').map(Number)
      const localDate = new Date(y, m - 1, d, hh, mm)
      body.timestamp = localDate.toISOString()
    }
    await api('POST', `/api/vehicles/${props.vin}/maintenance/records`, body)
    showRecordModal.value = false
    await load()
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
  }
}

// Edit plan item modal
const editItem = ref(null)
const editForm = ref({})

function openEdit(item) {
  editItem.value = item
  editForm.value = {
    interval_km: item.interval_km,
    interval_months: item.interval_months,
    trigger_mode: item.trigger_mode,
    priority: item.priority,
    last_done_km: item.last_done_km,
    enabled: item.enabled,
    notes: item.notes,
  }
}

async function submitEdit() {
  saving.value = true
  errorMsg.value = ''
  try {
    await api('PUT', `/api/vehicles/${props.vin}/maintenance/plan/${encodeURIComponent(editItem.value.service_type)}`, editForm.value)
    editItem.value = null
    await load()
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
  }
}

function openDelete(record) {
  deleteTargetId.value = record.id
  deleteTargetLabel.value = record.label || 'this record'
  showDeleteConfirm.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    await api('DELETE', `/api/vehicles/${props.vin}/maintenance/records/${deleteTargetId.value}`)
    showDeleteConfirm.value = false
    deleteTargetId.value = null
    await load()
  } catch (e) {
    errorMsg.value = e.message
    showDeleteConfirm.value = false
  } finally {
    deleting.value = false
  }
}

function cancelDelete() {
  showDeleteConfirm.value = false
  deleteTargetId.value = null
}

async function fetchCurrentKm() {
  fetchingKm.value = true
  try {
    const data = await api('GET', `/api/vehicles/${props.vin}/maintenance/current-mileage`)
    if (data.mileage_km != null) {
      recordForm.value.mileage_km = data.mileage_km
      overview.value.current_km = data.mileage_km
    }
  } catch (e) {
    // if fetch fails, try the overview cached value
    if (overview.value.current_km != null) {
      recordForm.value.mileage_km = overview.value.current_km
    }
  }
  fetchingKm.value = false
}

// Formatting helpers

/** Parse a naive-UTC ISO string from the API as a proper UTC Date. */
function parseUTC(ts) {
  if (!ts) return null
  // If already has timezone marker, use as-is
  if (ts.endsWith('Z') || ts.includes('+') || ts.includes('-', 10)) return new Date(ts)
  // Naive datetime from SQLite — interpret as UTC
  return new Date(ts + 'Z')
}

function formatInterval(item) {
  const parts = []
  if (item.interval_km) parts.push(`${item.interval_km.toLocaleString()} km`)
  if (item.interval_months) parts.push(`${item.interval_months} mo`)
  return parts.join(' / ') || '—'
}

function formatLastDone(item) {
  if (item.last_done_date) {
    const d = parseUTC(item.last_done_date)
    return `${d.toLocaleDateString()}${item.last_done_km != null ? ' @ ' + item.last_done_km.toLocaleString() + ' km' : ''}`
  }
  return 'Never'
}

function formatDue(item) {
  if (!item.last_done_date && !item.last_done_km) return '—'
  const parts = []
  if (item.last_done_km != null && item.interval_km) {
    parts.push(`${(item.last_done_km + item.interval_km).toLocaleString()} km`)
  }
  if (item.last_done_date && item.interval_months) {
    const due = parseUTC(item.last_done_date)
    due.setMonth(due.getMonth() + item.interval_months)
    parts.push(due.toLocaleDateString())
  }
  return parts.join(' / ') || '—'
}

function formatDate(ts) {
  if (!ts) return '—'
  return parseUTC(ts).toLocaleDateString()
}

onMounted(load)
watch(() => props.vin, load)
</script>

<style scoped>
.maintenance-tab {
  padding: 20px 16px;
  max-width: 1100px;
  margin: 0 auto;
}
@media (min-width: 640px) {
  .maintenance-tab { padding: 24px 24px; }
}

.mnt-header {
  margin-bottom: 20px;
}
.mnt-header h2 {
  font-size: 20px; font-weight: 700; color: var(--text); margin: 0;
}
.mnt-header p {
  font-size: 13px; color: var(--text2); margin: 4px 0 0;
}

/* C10 variant prompt */
.variant-prompt {
  display: flex; justify-content: center; padding: 40px 0;
}
.prompt-card {
  background: var(--bg2); border: 1px solid var(--border2); border-radius: 16px;
  padding: 32px; max-width: 480px; text-align: center;
}
.prompt-card h3 { margin: 0 0 8px; color: var(--text); font-size: 18px; }
.prompt-card p { color: var(--text2); margin: 0 0 20px; }
.variant-buttons { display: flex; gap: 12px; justify-content: center; }
.variant-btn {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px 24px; border-radius: 12px; border: 1.5px solid var(--border2);
  background: var(--bg); color: var(--text); cursor: pointer; font-size: 14px;
  transition: all 0.2s; min-width: 160px;
}
.variant-btn:hover { border-color: #00d4ff; background: #00d4ff0a; }

/* Summary grid */
.summary-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px; margin-bottom: 20px;
}
.summary-card {
  background: var(--bg2); border: 1px solid var(--border2); border-radius: 12px;
  padding: 16px; text-align: center;
}
.summary-card.warn { border-color: #ff525244; }
.summary-value { font-size: 28px; font-weight: 700; }
.summary-label { font-size: 12px; color: var(--text2); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.04em; }

/* Next action card */
.next-action-card {
  background: var(--bg2); border: 1px solid #ffab4044; border-radius: 12px;
  padding: 16px 20px; margin-bottom: 20px; display: flex; align-items: center; gap: 16px;
}
.next-header { display: flex; align-items: center; gap: 8px; color: #ffab40; font-weight: 600; font-size: 13px; }
.next-body { display: flex; align-items: center; gap: 12px; flex: 1; }
.next-label { font-size: 15px; font-weight: 600; color: var(--text); }
.next-priority { font-size: 11px; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; font-weight: 700; }

/* Chart card */
.chart-card {
  background: var(--bg2); border: 1px solid var(--border2); border-radius: 14px;
  padding: 20px; margin-bottom: 16px;
}
.chart-card.wide { grid-column: 1 / -1; }
.chart-header { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 16px; }
.chart-icon { color: var(--text2); }

/* Plan table */
.plan-table-wrap { overflow-x: auto; }
.plan-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.plan-table th { text-align: left; color: var(--text2); font-weight: 600; padding: 8px 10px; border-bottom: 1px solid var(--border2); font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; }
.plan-table td { padding: 10px 10px; border-bottom: 1px solid var(--border); color: var(--text); }
.plan-table tr.disabled td { opacity: 0.4; }

.cat-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; background: var(--border); color: var(--text2); }
.prio-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; font-weight: 700; }
.prio-routine { background: #00e67618; color: #00e676; }
.prio-important { background: #ffab4018; color: #ffab40; }
.prio-urgent { background: #ff525218; color: #ff5252; }

/* Records */
.record-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; border-bottom: 1px solid var(--border); gap: 12px;
}
.record-row:last-child { border-bottom: none; }
.rec-info { display: flex; flex-direction: column; }
.rec-label { font-size: 14px; font-weight: 600; color: var(--text); }
.rec-date { font-size: 12px; color: var(--text2); }
.rec-details { display: flex; gap: 16px; font-size: 12px; color: var(--text2); }
.rec-cost { color: #00e676; font-weight: 600; }

/* Buttons */
.icon-btn {
  width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--border2);
  background: var(--bg); color: var(--text2); cursor: pointer; font-size: 16px;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.icon-btn:hover { border-color: #00d4ff; color: #00d4ff; }
.icon-delete:hover { border-color: #ff5252; color: #ff5252; }

/* Modals */
.modal-backdrop {
  position: fixed; inset: 0; background: #00000080; display: flex;
  align-items: center; justify-content: center; z-index: 2000;
}
.modal-dialog {
  background: var(--bg2); border: 1px solid var(--border2); border-radius: 16px;
  padding: 24px; width: 90%; max-width: 420px; max-height: 80vh; overflow-y: auto;
}
.modal-dialog h3 { margin: 0 0 8px; color: var(--text); }
.edit-date { color: var(--text2); font-size: 13px; margin: 0 0 16px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; color: var(--text2); margin-bottom: 4px; }
.form-group input, .form-group select {
  width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border2);
  background: var(--bg); color: var(--text); font-size: 14px;
}
.mileage-row { display: flex; gap: 8px; align-items: center; }
.mileage-row input { flex: 1; }
.fetch-km-btn {
  display: flex; align-items: center; gap: 6px; white-space: nowrap;
  padding: 8px 14px; border-radius: 8px; border: 1px solid #00d4ff44;
  background: #00d4ff10; color: #00d4ff; cursor: pointer; font-size: 12px; font-weight: 600;
  transition: all 0.15s;
}
.fetch-km-btn:hover { background: #00d4ff20; border-color: #00d4ff88; }
.fetch-km-btn:disabled { opacity: 0.5; cursor: default; }
.spinning { animation: spin 0.8s linear infinite; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.btn-cancel {
  padding: 8px 16px; border-radius: 8px; background: var(--bg); border: 1px solid var(--border2);
  color: var(--text2); cursor: pointer; font-size: 13px;
}
.btn-save {
  padding: 8px 16px; border-radius: 8px; background: #00d4ff; border: none;
  color: #000; cursor: pointer; font-size: 13px; font-weight: 600;
}
.btn-save:disabled { opacity: 0.5; cursor: default; }
.field-error { color: #ff5252; font-size: 13px; margin-top: 8px; }
.empty-row { padding: 20px; text-align: center; color: var(--text2); font-size: 13px; }
.loading-row { display: flex; justify-content: center; padding: 60px 0; }

/* Toggle */
.toggle-wrap { display: flex; }
.toggle-btn {
  padding: 6px 18px; border-radius: 8px; border: 1.5px solid var(--border2);
  background: var(--bg); color: var(--text2); cursor: pointer; font-size: 12px; font-weight: 700;
  transition: all 0.15s;
}
.toggle-btn.on { border-color: #00e676; color: #00e676; background: #00e67610; }
.field-hint {
  margin: 6px 0 0; font-size: 11px; color: var(--text2); line-height: 1.45;
}

.spinner {
  width: 28px; height: 28px; border: 3px solid var(--border2); border-top-color: #00d4ff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
