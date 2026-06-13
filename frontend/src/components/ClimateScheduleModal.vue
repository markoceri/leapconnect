<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="acs-overlay" @click.self="$emit('close')">
        <div class="acs-modal">
          <div class="acs-header">
            <div class="acs-header-left">
              <CalendarClock :size="16" class="acs-header-icon" />
              <span class="acs-title">Climate Schedules</span>
            </div>
            <button class="acs-close" @click="$emit('close')">&times;</button>
          </div>

          <!-- Loading -->
          <div v-if="loading" class="acs-loading">
            <Loader :size="18" class="spinning" />
            <span>Loading schedules…</span>
          </div>

          <!-- List view -->
          <div v-else-if="!editing" class="acs-body">
            <div v-if="schedules.length === 0" class="acs-empty">
              <CalendarClock :size="32" class="acs-empty-icon" />
              <span>No climate schedules set</span>
            </div>

            <div
              v-for="(s, idx) in schedules"
              :key="s.setId || s.set_id || idx"
              class="acs-schedule-card"
            >
              <div class="acs-card-top">
                <div class="acs-card-time">
                  <Clock :size="14" />
                  <span>{{ extractTime(s) }}</span>
                </div>
                <span class="acs-card-badge" :class="{ off: s.on === '0' }">
                  {{ s.on === '1' ? 'ON' : 'OFF' }}
                </span>
              </div>
              <div class="acs-card-details">
                <span>{{ formatMode(s.mode) }} · {{ s.temperature }}°C · Fan {{ s.windlevel }}</span>
                <span v-if="cardDays(s)">{{ cardDays(s) }}</span>
              </div>
              <div class="acs-card-actions">
                <button class="acs-card-btn edit" @click="editSchedule(idx)">
                  <Pencil :size="13" /> Edit
                </button>
                <button class="acs-card-btn delete" @click="removeSchedule(idx)">
                  <Trash2 :size="13" /> Delete
                </button>
              </div>
            </div>

            <button class="acs-add-btn" @click="addNew">
              <Plus :size="16" />
              <span>Add Schedule</span>
            </button>
          </div>

          <!-- Edit / Add form -->
          <div v-else class="acs-body">
            <button class="acs-back-btn" @click="editing = false">
              <ChevronLeft :size="16" />
              <span>Back to list</span>
            </button>

            <!-- Enable toggle -->
            <div class="acs-row">
              <span class="acs-label">Enabled</span>
              <button class="acs-toggle" :class="{ on: form.enabled }" @click="form.enabled = !form.enabled">
                <span class="acs-toggle-dot" />
              </button>
            </div>

            <!-- Start time -->
            <div class="acs-field">
              <span class="acs-label">Start Time</span>
              <div class="acs-time-picker">
                <div class="acs-time-col">
                  <button class="acs-time-arrow" @click="stepHour(1)"><ChevronUp :size="18" /></button>
                  <span class="acs-time-digit">{{ padTwo(formHour) }}</span>
                  <button class="acs-time-arrow" @click="stepHour(-1)"><ChevronDown :size="18" /></button>
                </div>
                <span class="acs-time-sep">:</span>
                <div class="acs-time-col">
                  <button class="acs-time-arrow" @click="stepMinute(5)"><ChevronUp :size="18" /></button>
                  <span class="acs-time-digit">{{ padTwo(formMinute) }}</span>
                  <button class="acs-time-arrow" @click="stepMinute(-5)"><ChevronDown :size="18" /></button>
                </div>
              </div>
            </div>

            <!-- Temperature -->
            <div class="acs-row">
              <span class="acs-label">Temperature</span>
              <div class="acs-temp-control">
                <button class="acs-step-btn" @click="form.temp = Math.max(16, form.temp - 1)">−</button>
                <span class="acs-temp-value">{{ form.temp }}°C</span>
                <button class="acs-step-btn" @click="form.temp = Math.min(32, form.temp + 1)">+</button>
              </div>
            </div>

            <!-- Fan Level -->
            <div class="acs-field">
              <span class="acs-label">Fan Level</span>
              <div class="acs-fan-control">
                <button
                  v-for="lv in 7"
                  :key="lv"
                  class="acs-fan-btn"
                  :class="{ active: form.fan === lv }"
                  @click="form.fan = lv"
                >{{ lv }}</button>
              </div>
            </div>

            <!-- Mode -->
            <div class="acs-field">
              <span class="acs-label">Mode</span>
              <div class="acs-mode-control">
                <button v-for="m in modes" :key="m.value" class="acs-mode-btn" :class="{ active: form.mode === m.value }" @click="form.mode = m.value">
                  <component :is="m.icon" :size="14" />
                  <span>{{ m.label }}</span>
                </button>
              </div>
            </div>

            <!-- Operate -->
            <div class="acs-field">
              <span class="acs-label">Operate</span>
              <div class="acs-mode-control">
                <button class="acs-mode-btn" :class="{ active: form.operate === 'auto' }" @click="form.operate = 'auto'">Auto</button>
                <button class="acs-mode-btn" :class="{ active: form.operate === 'manual' }" @click="form.operate = 'manual'">Manual</button>
              </div>
            </div>

            <!-- Circulation -->
            <div class="acs-field">
              <span class="acs-label">Circulation</span>
              <div class="acs-mode-control">
                <button class="acs-mode-btn" :class="{ active: form.circle === 'in' }" @click="form.circle = 'in'">
                  <RotateCcw :size="14" />
                  <span>Recirculate</span>
                </button>
                <button class="acs-mode-btn" :class="{ active: form.circle === 'out' }" @click="form.circle = 'out'">
                  <Wind :size="14" />
                  <span>Fresh</span>
                </button>
              </div>
            </div>

            <!-- Days of week -->
            <div class="acs-field">
              <span class="acs-label">Days</span>
              <div class="acs-days">
                <button
                  v-for="d in dayOptions"
                  :key="d.value"
                  class="acs-day-btn"
                  :class="{ active: form.selectedDays.has(d.value) }"
                  @click="toggleDay(d.value)"
                >{{ d.short }}</button>
              </div>
              <span class="acs-hint">Leave empty for one-time only</span>
            </div>

            <!-- Windshield -->
            <div class="acs-field">
              <span class="acs-label">Windshield</span>
              <div class="acs-mode-control">
                <button class="acs-mode-btn" :class="{ active: form.wshld === '0' }" @click="form.wshld = '0'">Normal</button>
                <button class="acs-mode-btn" :class="{ active: form.wshld === '1' }" @click="form.wshld = '1'">
                  <ThermometerSnowflake :size="14" />
                  <span>Defrost</span>
                </button>
              </div>
            </div>

            <!-- Save -->
            <button
              class="acs-apply"
              :disabled="!!saving || !form.startTime"
              @click="saveForm"
            >
              <Loader v-if="saving" :size="16" class="spinning" />
              <span v-else>{{ editingIndex >= 0 ? 'Update Schedule' : 'Add Schedule' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <ConfirmDialog
      :visible="showDeleteConfirm"
      :title="deleteAll ? 'Cancel All Schedules?' : 'Delete Schedule?'"
      :message="deleteAll
        ? 'This will remove all climate schedules from the Leapmotor cloud.'
        : 'This schedule will be removed. Other schedules will remain active.'"
      :confirm-label="deleteAll ? 'Cancel All' : 'Delete'"
      cancel-label="Keep"
      variant="danger"
      icon="trash"
      :loading="deleting"
      @confirm="doDelete"
      @cancel="showDeleteConfirm = false"
    />
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import {
  CalendarClock, Loader, Snowflake, Flame, Wind, RotateCcw,
  ThermometerSnowflake, Trash2, Plus, Pencil, Clock, ChevronLeft,
  ChevronUp, ChevronDown
} from 'lucide-vue-next'
import { api } from '../composables/useApi'
import ConfirmDialog from './ConfirmDialog.vue'

const props = defineProps({
  visible: Boolean,
  vin: String,
})

const emit = defineEmits(['close', 'saved'])

// --- state ---
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const editingIndex = ref(-1) // -1 = new
const schedules = ref([])
const showDeleteConfirm = ref(false)
const deleteAll = ref(false)
const deleteIdx = ref(-1)
const deleting = ref(false)

const form = reactive({
  enabled: true,
  startTime: '07:00',
  temp: 24,
  fan: 3,
  mode: 'wind',
  operate: 'manual',
  circle: 'out',
  wshld: '0',
  selectedDays: new Set([1, 2, 3, 4, 5]),
  setId: '',
})

const modes = [
  { value: 'cold', label: 'Cool', icon: Snowflake },
  { value: 'hot', label: 'Heat', icon: Flame },
  { value: 'wind', label: 'Fan', icon: Wind },
]

const dayOptions = [
  { value: 0, short: 'Sun' },
  { value: 1, short: 'Mon' },
  { value: 2, short: 'Tue' },
  { value: 3, short: 'Wed' },
  { value: 4, short: 'Thu' },
  { value: 5, short: 'Fri' },
  { value: 6, short: 'Sat' },
]

const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

// --- helpers ---
function generateSetId() {
  const epochMs = Date.now()
  const devicePart = Math.random().toString(36).substring(2, 10)
  return `air_set${devicePart}${epochMs}`
}

// --- time picker helpers ---

const formHour = computed(() => {
  const parts = (form.startTime || '00:00').split(':')
  return parseInt(parts[0], 10) || 0
})
const formMinute = computed(() => {
  const parts = (form.startTime || '00:00').split(':')
  return parseInt(parts[1], 10) || 0
})

function padTwo(n) { return String(n).padStart(2, '0') }

function stepHour(delta) {
  let h = (formHour.value + delta + 24) % 24
  form.startTime = `${padTwo(h)}:${padTwo(formMinute.value)}`
}
function stepMinute(delta) {
  let m = (formMinute.value + delta + 60) % 60
  form.startTime = `${padTwo(formHour.value)}:${padTwo(m)}`
}

function formatStartTime(timeStr) {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d} ${timeStr}:00`
}

function extractTime(s) {
  // startTime can be "HH:mm" or "yyyy-MM-dd HH:mm:00"
  const st = s.startTime || s.start_time || ''
  const match = st.match(/(\d{2}:\d{2})/)
  return match ? match[1] : st
}

function formatMode(m) {
  if (m === 'cold') return 'Cool'
  if (m === 'hot') return 'Heat'
  if (m === 'wind') return 'Fan'
  return m
}

function cardDays(s) {
  const d = s.days
  if (!d || !Array.isArray(d) || d.length === 0) return 'One-time'
  if (d.length === 7) return 'Every day'
  return d.map(v => dayLabels[v] || v).join(', ')
}

function toggleDay(val) {
  if (form.selectedDays.has(val)) form.selectedDays.delete(val)
  else form.selectedDays.add(val)
}

function resetForm() {
  form.enabled = true
  form.startTime = '07:00'
  form.temp = 24
  form.fan = 3
  form.mode = 'wind'
  form.operate = 'manual'
  form.circle = 'out'
  form.wshld = '0'
  form.selectedDays = new Set([1, 2, 3, 4, 5])
  form.setId = ''
}

function loadFormFromSchedule(s) {
  form.enabled = s.on !== '0'
  const st = s.startTime || s.start_time || '07:00'
  const m = st.match(/(\d{2}:\d{2})/)
  form.startTime = m ? m[1] : '07:00'
  form.temp = parseInt(s.temperature, 10) || 24
  form.fan = parseInt(s.windlevel, 10) || 3
  form.mode = s.mode || 'wind'
  form.operate = s.operate || 'manual'
  form.circle = s.circle || 'out'
  form.wshld = s.wshld || '0'
  form.setId = s.setId || s.set_id || ''
  form.selectedDays = new Set(Array.isArray(s.days) ? s.days : [])
}

function formToEntry() {
  return {
    mode: form.mode,
    on: form.enabled ? '1' : '0',
    operate: form.operate,
    set_id: form.setId || generateSetId(),
    start_time: formatStartTime(form.startTime),
    temperature: String(form.temp),
    update_time: String(Date.now()),
    windlevel: String(form.fan),
    days: Array.from(form.selectedDays).sort(),
    circle: form.circle,
    position: 'all',
    wshld: form.wshld,
  }
}

// Normalize cloud keys (camelCase) to snake_case for consistent local handling
function normalizeEntry(s) {
  return {
    mode: s.mode || 'wind',
    on: s.on || '1',
    operate: s.operate || 'manual',
    set_id: s.setId || s.set_id || '',
    start_time: s.startTime || s.start_time || '',
    temperature: s.temperature || '24',
    update_time: s.updateTime || s.update_time || '',
    windlevel: s.windlevel || '3',
    days: Array.isArray(s.days) ? s.days : [],
    circle: s.circle ?? 'out',
    position: s.position || 'all',
    wshld: s.wshld || '0',
  }
}

// --- actions ---
async function fetchSchedules() {
  if (!props.vin) return
  loading.value = true
  try {
    const data = await api('GET', `/api/vehicles/${props.vin}/ac-schedule`)
    schedules.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Failed to fetch schedules:', err)
    schedules.value = []
  } finally {
    loading.value = false
  }
}

function addNew() {
  resetForm()
  editingIndex.value = -1
  editing.value = true
}

function editSchedule(idx) {
  loadFormFromSchedule(schedules.value[idx])
  editingIndex.value = idx
  editing.value = true
}

function removeSchedule(idx) {
  deleteIdx.value = idx
  deleteAll.value = false
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!props.vin) return
  deleting.value = true
  try {
    const updated = schedules.value
      .filter((_, i) => i !== deleteIdx.value)
      .map(normalizeEntry)
    const body = { controls: updated }
    await api('PUT', `/api/vehicles/${props.vin}/ac-schedule`, body)
    showDeleteConfirm.value = false
    await fetchSchedules()
    emit('saved')
  } catch (err) {
    showDeleteConfirm.value = false
    alert('Failed to delete schedule: ' + (err.message || err))
  } finally {
    deleting.value = false
  }
}

async function saveForm() {
  if (!props.vin) return
  saving.value = true
  try {
    const entry = formToEntry()
    const existing = schedules.value.map(normalizeEntry)
    let updated
    if (editingIndex.value >= 0) {
      // Replace at index
      updated = [...existing]
      updated[editingIndex.value] = entry
    } else {
      // Append new
      updated = [...existing, entry]
    }
    const body = { controls: updated }
    await api('PUT', `/api/vehicles/${props.vin}/ac-schedule`, body)
    editing.value = false
    await fetchSchedules()
    emit('saved')
  } catch (err) {
    alert('Failed to save schedule: ' + (err.message || err))
  } finally {
    saving.value = false
  }
}

// --- lifecycle ---
watch(() => props.visible, (val) => {
  if (val) {
    editing.value = false
    editingIndex.value = -1
    fetchSchedules()
  }
})
</script>

<style scoped>
.acs-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.acs-modal {
  background: var(--card); border-radius: 16px; padding: 0;
  width: 92vw; max-width: 440px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
  max-height: 90vh; overflow-y: auto;
}
.acs-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,.06);
  position: sticky; top: 0; background: var(--card); z-index: 1;
}
.acs-header-left { display: flex; align-items: center; gap: 8px; }
.acs-header-icon { color: #00d4ff; }
.acs-title { font-size: 15px; font-weight: 600; color: var(--text); }
.acs-close {
  background: none; border: none; color: var(--muted); font-size: 22px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.acs-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

/* Rows & Fields */
.acs-label { font-size: 13px; font-weight: 500; color: var(--text); }
.acs-row {
  display: flex; align-items: center; justify-content: space-between;
}
.acs-field { display: flex; flex-direction: column; gap: 8px; }
.acs-hint { font-size: 11px; color: var(--muted2); }

/* Time picker */
.acs-time-picker {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  background: var(--bg); border: 1px solid rgba(255,255,255,.08);
  border-radius: 14px; padding: 8px 16px;
}
.acs-time-col {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.acs-time-arrow {
  background: none; border: none; color: var(--muted);
  cursor: pointer; padding: 4px; border-radius: 8px;
  transition: all .15s; display: flex; align-items: center; justify-content: center;
}
.acs-time-arrow:hover { color: #00d4ff; background: rgba(0,212,255,.1); }
.acs-time-arrow:active { transform: scale(0.9); }
.acs-time-digit {
  font-size: 32px; font-weight: 700; color: var(--text);
  min-width: 48px; text-align: center; line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.acs-time-sep {
  font-size: 28px; font-weight: 700; color: var(--muted);
  padding: 0 2px; align-self: center;
}

.acs-input {
  padding: 8px 12px; border: 1px solid rgba(255,255,255,.1); border-radius: 10px;
  background: var(--bg); color: var(--text); font-size: 14px;
  outline: none; transition: border-color .2s;
}
.acs-input:focus { border-color: #00d4ff; }

/* Temperature */
.acs-temp-control { display: flex; align-items: center; gap: 10px; }
.acs-step-btn {
  width: 32px; height: 32px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px;
  background: var(--bg); color: var(--text); cursor: pointer;
  font-size: 18px; display: flex; align-items: center; justify-content: center;
  transition: border-color .2s;
}
.acs-step-btn:hover { border-color: #00d4ff; }
.acs-temp-value { font-size: 18px; font-weight: 700; color: var(--text); min-width: 56px; text-align: center; }

/* Fan */
.acs-fan-control { display: flex; gap: 6px; }
.acs-fan-btn {
  flex: 1; padding: 8px 0; border: 1px solid rgba(255,255,255,.08); border-radius: 8px;
  background: var(--bg); color: var(--muted); cursor: pointer;
  font-size: 13px; font-weight: 600; transition: all .2s; text-align: center;
}
.acs-fan-btn.active {
  border-color: #00d4ff; color: #00d4ff;
  background: rgba(0,212,255,.1);
}

/* Mode / Operate buttons */
.acs-mode-control { display: flex; gap: 6px; }
.acs-mode-btn {
  flex: 1; padding: 8px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px;
  background: var(--bg); color: var(--muted); cursor: pointer;
  font-size: 12px; font-weight: 600; transition: all .2s;
  display: flex; align-items: center; justify-content: center; gap: 4px;
}
.acs-mode-btn.active {
  border-color: #00d4ff; color: #00d4ff;
  background: rgba(0,212,255,.1);
}

/* Days */
.acs-days { display: flex; gap: 6px; }
.acs-day-btn {
  flex: 1; padding: 8px 0; border: 1px solid rgba(255,255,255,.08); border-radius: 8px;
  background: var(--bg); color: var(--muted); cursor: pointer;
  font-size: 11px; font-weight: 600; transition: all .2s; text-align: center;
}
.acs-day-btn.active {
  border-color: #00d4ff; color: #00d4ff;
  background: rgba(0,212,255,.08);
}

/* Toggle */
.acs-toggle {
  width: 44px; height: 24px; border-radius: 12px; border: none;
  background: rgba(255,255,255,.1); cursor: pointer;
  position: relative; transition: background .2s; padding: 0;
}
.acs-toggle.on { background: #00e676; }
.acs-toggle-dot {
  position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; transition: transform .2s;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}
.acs-toggle.on .acs-toggle-dot { transform: translateX(20px); }

/* Apply */
.acs-apply {
  width: 100%; padding: 12px; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #00d4ff, #7c6aff);
  color: #fff; font-weight: 600; font-size: 14px;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: opacity .2s;
}
.acs-apply:hover { opacity: 0.9; }
.acs-apply:disabled { opacity: 0.5; cursor: not-allowed; }

.acs-delete {
  width: 100%; padding: 10px; border: 1px solid rgba(255,80,80,.3); border-radius: 10px;
  background: transparent; color: #ff5050; font-weight: 600; font-size: 13px;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: all .2s;
}
.acs-delete:hover { background: rgba(255,80,80,.1); }
.acs-delete:disabled { opacity: 0.5; cursor: not-allowed; }

.acs-footer-hint {
  font-size: 11px; color: var(--muted2); text-align: center;
  line-height: 1.5; padding-top: 4px;
}

.acs-loading {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 32px 0; color: var(--muted);
}

/* Empty state */
.acs-empty {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 28px 0; color: var(--muted);
}
.acs-empty-icon { opacity: 0.3; }

/* Schedule cards */
.acs-schedule-card {
  background: var(--bg); border: 1px solid rgba(255,255,255,.06);
  border-radius: 12px; padding: 14px 16px;
  display: flex; flex-direction: column; gap: 8px;
}
.acs-card-top {
  display: flex; align-items: center; justify-content: space-between;
}
.acs-card-time {
  display: flex; align-items: center; gap: 6px;
  font-size: 18px; font-weight: 700; color: var(--text);
}
.acs-card-badge {
  font-size: 11px; font-weight: 700; padding: 3px 10px;
  border-radius: 20px; background: rgba(0,230,118,.15); color: #00e676;
}
.acs-card-badge.off {
  background: rgba(255,255,255,.06); color: var(--muted);
}
.acs-card-details {
  display: flex; flex-direction: column; gap: 2px;
  font-size: 12px; color: var(--muted);
}
.acs-card-actions {
  display: flex; gap: 8px; margin-top: 4px;
}
.acs-card-btn {
  flex: 1; padding: 7px; border-radius: 8px; font-size: 12px; font-weight: 600;
  cursor: pointer; border: 1px solid rgba(255,255,255,.08);
  background: transparent; transition: all .2s;
  display: flex; align-items: center; justify-content: center; gap: 4px;
}
.acs-card-btn.edit { color: #00d4ff; }
.acs-card-btn.edit:hover { background: rgba(0,212,255,.1); border-color: #00d4ff44; }
.acs-card-btn.delete { color: #ff5050; }
.acs-card-btn.delete:hover { background: rgba(255,80,80,.1); border-color: #ff505044; }

/* Add button */
.acs-add-btn {
  width: 100%; padding: 12px; border: 1px dashed rgba(255,255,255,.15);
  border-radius: 10px; background: transparent; color: #00d4ff;
  font-weight: 600; font-size: 13px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: all .2s;
}
.acs-add-btn:hover { background: rgba(0,212,255,.06); border-color: #00d4ff44; }

/* Back button */
.acs-back-btn {
  display: flex; align-items: center; gap: 4px;
  background: none; border: none; color: var(--muted); font-size: 13px;
  cursor: pointer; padding: 0; margin-bottom: 4px; font-weight: 500;
  transition: color .2s;
}
.acs-back-btn:hover { color: #00d4ff; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

@keyframes lm-spin { to { transform: rotate(360deg); } }
.spinning { animation: lm-spin .7s linear infinite; }
</style>
