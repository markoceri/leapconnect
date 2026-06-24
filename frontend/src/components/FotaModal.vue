<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="fo-overlay" @click.self="$emit('close')">
        <div class="fo-modal">
          <div class="fo-header">
            <div class="fo-header-left">
              <Download :size="16" class="fo-header-icon" />
              <span class="fo-title">Firmware Update (FOTA)</span>
            </div>
            <button class="fo-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="fo-body">
            <div class="fo-warning">
              <AlertTriangle :size="14" />
              <span>Firmware operations may affect vehicle availability. Use with caution.</span>
            </div>

            <!-- Existing FOTA schedules -->
            <div v-if="loadingSchedules" class="fo-loading">
              <Loader :size="16" class="spinning" />
              <span>Loading schedules…</span>
            </div>
            <div v-else-if="existingSchedules.length > 0" class="fo-existing">
              <div class="fo-existing-title">Scheduled Updates</div>
              <div
                v-for="(sch, idx) in existingSchedules"
                :key="idx"
                class="fo-schedule-card"
              >
                <div class="fo-schedule-row">
                  <span class="fo-schedule-label">Task ID</span>
                  <span class="fo-schedule-val">{{ sch.pid || '—' }}</span>
                </div>
                <div class="fo-schedule-row">
                  <span class="fo-schedule-label">Scheduled</span>
                  <span class="fo-schedule-val">{{ formatScheduleTime(sch.start_time || sch.startTime) }}</span>
                </div>
              </div>
            </div>

            <!-- Task ID input -->
            <div class="fo-field">
              <label class="fo-label">Task ID</label>
              <input
                type="number"
                v-model.number="taskId"
                class="fo-input"
                placeholder="Enter FOTA task ID"
                min="1"
              />
            </div>

            <!-- Schedule time (only for schedule action) -->
            <div v-if="selectedAction === 'schedule'" class="fo-field">
              <label class="fo-label">Schedule Time</label>
              <input
                type="datetime-local"
                v-model="scheduleTime"
                class="fo-input"
              />
            </div>

            <!-- Action selector -->
            <div class="fo-actions">
              <button
                v-for="a in actions"
                :key="a.value"
                class="fo-action-btn"
                :class="{ selected: selectedAction === a.value, loading: loadingAction === a.value }"
                :style="{ '--ac': a.color }"
                @click="selectedAction = a.value"
              >
                <component :is="a.icon" :size="14" />
                <span>{{ a.label }}</span>
              </button>
            </div>

            <!-- Execute -->
            <button
              class="fo-apply"
              :disabled="!!loadingAction || !taskId"
              @click="execute"
            >
              <Loader v-if="loadingAction" :size="16" class="spinning" />
              <span v-else>Execute {{ selectedLabel }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Download, Play, Clock, AlertTriangle, Loader, Trash2 } from 'lucide-vue-next'
import { api } from '../composables/useApi'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
  vin: String,
})

defineEmits(['close'])

const taskId = ref(null)
const scheduleTime = ref('')
const selectedAction = ref('download')
const loadingAction = ref(null)
const existingSchedules = ref([])
const loadingSchedules = ref(false)

const actions = [
  { value: 'download', label: 'Download', icon: Download, color: 'var(--accent)' },
  { value: 'install', label: 'Install', icon: Play, color: '#00e676' },
  { value: 'schedule', label: 'Schedule', icon: Clock, color: '#ffab40' },
]

const selectedLabel = computed(() => actions.find(a => a.value === selectedAction.value)?.label ?? '')

watch(() => props.visible, async (val) => {
  if (!val || !props.vin) return
  loadingSchedules.value = true
  try {
    const data = await api('GET', `/api/vehicles/${props.vin}/fota/schedule`)
    existingSchedules.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Failed to fetch FOTA schedules:', err)
    existingSchedules.value = []
  } finally {
    loadingSchedules.value = false
  }
})

function formatScheduleTime(ts) {
  if (!ts) return '—'
  // ts might be epoch seconds or a date string
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  if (isNaN(d.getTime())) return String(ts)
  return d.toLocaleString()
}

async function execute() {
  if (!taskId.value) return
  const action = `fota-${selectedAction.value}`
  loadingAction.value = selectedAction.value
  try {
    const body = { task_id: taskId.value }
    if (selectedAction.value === 'schedule') {
      if (!scheduleTime.value) return
      body.schedule_time = scheduleTime.value
    }
    await props.onExec({ action, body })
    // Refresh schedules after action
    if (props.vin) {
      try {
        const data = await api('GET', `/api/vehicles/${props.vin}/fota/schedule`)
        existingSchedules.value = Array.isArray(data) ? data : []
      } catch (_) { /* ignore */ }
    }
  } finally {
    loadingAction.value = null
  }
}
</script>

<style scoped>
.fo-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.fo-modal {
  background: var(--card); border-radius: 16px; padding: 0;
  width: 92vw; max-width: 420px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
}
.fo-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,.06);
}
.fo-header-left { display: flex; align-items: center; gap: 8px; }
.fo-header-icon { color: #ff5252; }
.fo-title { font-size: 15px; font-weight: 600; color: var(--text); }
.fo-close {
  background: none; border: none; color: var(--muted); font-size: 22px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.fo-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.fo-warning {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; border-radius: 10px;
  background: rgba(255,171,64,.08); border: 1px solid rgba(255,171,64,.2);
  font-size: 12px; color: #ffab40;
}

.fo-field { display: flex; flex-direction: column; gap: 6px; }
.fo-label { font-size: 12px; font-weight: 600; color: var(--muted); }
.fo-input {
  padding: 10px 12px; border: 1px solid rgba(255,255,255,.1); border-radius: 10px;
  background: var(--bg); color: var(--text); font-size: 14px;
  outline: none; transition: border-color .2s;
}
.fo-input:focus { border-color: #ff5252; }

.fo-actions {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.fo-action-btn {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px 8px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px;
  background: var(--bg); color: var(--muted); cursor: pointer;
  font-size: 12px; font-weight: 500; transition: all .2s;
}
.fo-action-btn.selected {
  border-color: var(--ac); color: var(--text);
  background: color-mix(in srgb, var(--ac) 8%, transparent);
}
.fo-action-btn:hover { border-color: rgba(255,255,255,.15); }

.fo-apply {
  width: 100%; padding: 12px; border: none; border-radius: 10px;
  background: #ff5252; color: #fff; font-weight: 600; font-size: 14px;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: opacity .2s;
}
.fo-apply:hover { opacity: 0.9; }
.fo-apply:disabled { opacity: 0.5; cursor: not-allowed; }

/* Existing schedules */
.fo-loading {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--muted); padding: 8px 0;
}
.fo-existing { display: flex; flex-direction: column; gap: 8px; }
.fo-existing-title {
  font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.06em;
}
.fo-schedule-card {
  background: var(--bg); border-radius: 10px; padding: 12px 14px;
  display: flex; flex-direction: column; gap: 6px;
}
.fo-schedule-row {
  display: flex; justify-content: space-between; align-items: center;
}
.fo-schedule-label { font-size: 12px; color: var(--muted2); }
.fo-schedule-val { font-size: 13px; font-weight: 600; color: var(--text); }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

@keyframes lm-spin { to { transform: rotate(360deg); } }
.spinning { animation: lm-spin .7s linear infinite; }
</style>
