<template>
  <div class="settings-tab">
    <!-- Account -->
    <SectionCard title="Account" :icon="User">
      <div class="account-row">
        <div class="account-avatar">{{ initials }}</div>
        <div>
          <div class="account-name">{{ displayName }}</div>
          <div class="account-email">{{ accountEmail }}</div>
        </div>
      </div>
      <button class="action-btn" @click="showAccountEdit = !showAccountEdit">
        {{ showAccountEdit ? 'Cancel' : 'Edit Credentials' }}
      </button>
      <div v-if="showAccountEdit" class="edit-panel">
        <div class="form-group">
          <label>Email</label>
          <input v-model="accountForm.username" type="email" placeholder="your@email.com" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="accountForm.password" type="password" placeholder="New password" />
        </div>
        <div class="form-divider">Certificates</div>
        <div class="form-group">
          <label>App Certificate (.crt / .pem)</label>
          <div class="file-upload" :class="{ filled: certFile }" @click="$refs.certInput.click()">
            <span>{{ certFile ? certFile.name : 'Choose file…' }}</span>
          </div>
          <input ref="certInput" type="file" accept=".crt,.pem,.cer" hidden @change="e => certFile = e.target.files[0]" />
        </div>
        <div class="form-group">
          <label>Private Key (.key / .pem)</label>
          <div class="file-upload" :class="{ filled: keyFile }" @click="$refs.keyInput.click()">
            <span>{{ keyFile ? keyFile.name : 'Choose file…' }}</span>
          </div>
          <input ref="keyInput" type="file" accept=".key,.pem" hidden @change="e => keyFile = e.target.files[0]" />
        </div>
        <small class="form-hint">Leave certificate fields empty to keep existing ones.</small>
        <button class="save-btn" :disabled="accountSaving" @click="saveAccount">
          {{ accountSaving ? 'Saving…' : 'Save & Reconnect' }}
        </button>
        <div v-if="accountError" class="field-error">{{ accountError }}</div>
        <div v-if="accountSuccess" class="field-success">{{ accountSuccess }}</div>
      </div>
      <InfoRow label="App version" value="v2.4.1" color="#5c6478" />
    </SectionCard>

    <!-- Vehicle -->
    <SectionCard title="Vehicle" :icon="Car">
      <InfoRow label="Model" :value="`${vehicle.year || ''} Leapmotor ${vehicle.car_type || ''}`" color="#e2e6f0" />
      <InfoRow label="VIN" color="#e2e6f0">
        <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
      </InfoRow>
      <InfoRow label="Nickname" :value="vehicle.nickname || '—'" color="#00d4ff" />
    </SectionCard>

    <!-- Notifications -->
    <SectionCard title="Notifications" :icon="Bell">
      <div v-for="n in notifications" :key="n.key" class="notif-row">
        <span class="notif-label">{{ n.label }}</span>
        <ToggleSwitch v-model="n.enabled" />
      </div>
    </SectionCard>

    <!-- Preferences -->
    <SectionCard title="Preferences" :icon="SlidersHorizontal">
      <InfoRow label="Distance unit" value="km" color="#e2e6f0" />
      <InfoRow label="Pressure unit" value="bar" color="#e2e6f0" />
      <InfoRow label="Theme" value="Dark" color="#7c6aff" />
      <InfoRow label="Language" value="English" color="#e2e6f0" />
    </SectionCard>

    <!-- Data Collection Scheduler -->
    <SectionCard title="Data Collection" :icon="BarChart3">
      <div class="notif-row">
        <span class="notif-label">Automatic collection</span>
        <ToggleSwitch :modelValue="scheduler.enabled" @update:modelValue="toggleScheduler" />
      </div>
      <div class="interval-row">
        <span class="interval-label">Collection interval</span>
        <div class="interval-control">
          <button class="interval-btn" :disabled="!scheduler.enabled" @click="changeInterval(-5)">−</button>
          <span class="interval-value" :class="{ disabled: !scheduler.enabled }">{{ scheduler.interval_minutes }} min</span>
          <button class="interval-btn" :disabled="!scheduler.enabled" @click="changeInterval(5)">+</button>
        </div>
      </div>
      <div class="scheduler-status">
        <div class="status-row">
          <span class="status-dot" :class="scheduler.is_running ? 'running' : 'stopped'" />
          <span class="status-text">{{ scheduler.is_running ? 'Running' : 'Stopped' }}</span>
        </div>
        <div v-if="scheduler.last_run" class="status-detail">
          Last update: {{ formatTime(scheduler.last_run) }}
        </div>
        <div class="status-detail">
          Runs: {{ scheduler.total_runs }} · Errors: {{ scheduler.total_errors }}
        </div>
        <div v-if="scheduler.last_error" class="status-error">
          {{ scheduler.last_error }}
        </div>
      </div>
    </SectionCard>

    <!-- Raw Data toggle -->
    <SectionCard title="Raw Data" :icon="Code">
      <button class="raw-toggle" @click="showRaw = !showRaw">
        {{ showRaw ? 'Hide' : 'Show' }} full JSON
      </button>
      <div v-if="showRaw" class="raw-panel">
        <pre>{{ JSON.stringify(rawData, null, 2) }}</pre>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import SectionCard from '../components/SectionCard.vue'
import InfoRow from '../components/InfoRow.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import { api } from '../composables/useApi'
import { User, Car, Bell, SlidersHorizontal, BarChart3, Code } from 'lucide-vue-next'

const props = defineProps({
  vehicle: { type: Object, required: true },
  rawData: { type: Object, default: () => ({}) },
})

const showRaw = ref(false)
const showAccountEdit = ref(false)
const accountSaving = ref(false)
const accountError = ref('')
const accountSuccess = ref('')
const certFile = ref(null)
const keyFile = ref(null)

const accountForm = reactive({
  username: '',
  password: '',
})

const accountEmail = ref('—')

const email = computed(() => accountEmail.value)
const displayName = computed(() => props.vehicle.nickname || 'User')
const initials = computed(() => {
  const n = displayName.value
  return n.substring(0, 2).toUpperCase()
})

const notifications = reactive([
  { label: 'Charge complete', key: 'notifCharge', enabled: true },
  { label: 'Low battery (<20%)', key: 'notifLow', enabled: true },
  { label: 'Tire pressure', key: 'notifTire', enabled: true },
  { label: 'Software updates', key: 'notifOTA', enabled: false },
])

// -- Scheduler state --------------------------------------------------------
const scheduler = reactive({
  enabled: false,
  interval_minutes: 15,
  is_running: false,
  last_run: null,
  last_error: null,
  total_runs: 0,
  total_errors: 0,
})

let schedulerUpdating = false

async function loadScheduler() {
  try {
    const data = await api('GET', '/api/scheduler')
    Object.assign(scheduler, data)
  } catch {
    // scheduler not available yet
  }
}

async function updateScheduler(patch) {
  if (schedulerUpdating) return
  schedulerUpdating = true
  try {
    const data = await api('PUT', '/api/scheduler', patch)
    Object.assign(scheduler, data)
  } catch {
    // revert on error — reload current state
    await loadScheduler()
  } finally {
    schedulerUpdating = false
  }
}

function toggleScheduler(val) {
  updateScheduler({ enabled: val })
}

function changeInterval(delta) {
  const next = Math.max(1, Math.min(1440, scheduler.interval_minutes + delta))
  if (next !== scheduler.interval_minutes) {
    updateScheduler({ interval_minutes: next })
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadAccount() {
  try {
    const data = await api('GET', '/api/status')
    if (data.user_id) {
      accountEmail.value = data.user_id
      accountForm.username = data.user_id
    }
  } catch { /* ignore */ }
}

async function saveAccount() {
  accountError.value = ''
  accountSuccess.value = ''
  if (!accountForm.username || !accountForm.password) {
    accountError.value = 'Email and password are required'
    return
  }
  accountSaving.value = true
  try {
    // Upload new certificates if provided
    if (certFile.value && keyFile.value) {
      const formData = new FormData()
      formData.append('cert_file', certFile.value)
      formData.append('key_file', keyFile.value)
      const certRes = await fetch('/api/setup/certificates', { method: 'POST', body: formData })
      const certData = await certRes.json()
      if (!certRes.ok) throw new Error(certData.detail || 'Certificate upload failed')
    }

    // Save account and reconnect
    const result = await api('POST', '/api/setup/account', {
      username: accountForm.username,
      password: accountForm.password,
    })

    if (result.connected) {
      accountSuccess.value = 'Credentials saved. Connected successfully.'
      accountEmail.value = accountForm.username
    } else {
      accountSuccess.value = 'Credentials saved. ' + (result.connection_error || 'Connection failed — will retry on next restart.')
    }
    certFile.value = null
    keyFile.value = null
  } catch (err) {
    accountError.value = err.message
  } finally {
    accountSaving.value = false
  }
}

onMounted(() => {
  loadScheduler()
  loadAccount()
})
</script>

<style scoped>
.settings-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 100%;
}
@media (min-width: 768px) {
  .settings-tab { max-width: 640px; }
}

.account-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0 16px;
}
.account-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #00d4ff22;
  border: 2px solid #00d4ff55;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #00d4ff;
}
.account-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.account-email {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.action-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 12px;
}
.action-btn:hover { color: #00d4ff; border-color: #00d4ff44; }

.edit-panel {
  padding: 12px 0;
  border-top: 1px solid #181d2c;
  margin-bottom: 12px;
}
.form-group { margin-bottom: 0.9rem; }
.form-group label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.form-group input {
  width: 100%;
  padding: 10px 14px;
  background: var(--input);
  border: 1px solid #1c2240;
  border-radius: 8px;
  color: var(--text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus { border-color: #00d4ff55; }
.form-group input::placeholder { color: var(--muted2); }

.form-divider {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 1rem 0 0.7rem;
  padding-top: 0.8rem;
  border-top: 1px solid #181d2c;
}

.file-upload {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--input);
  border: 1px dashed #1c2240;
  border-radius: 8px;
  color: var(--muted2);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.file-upload:hover { border-color: #00d4ff55; }
.file-upload.filled { border-style: solid; border-color: #00d4ff44; color: var(--text); }

.form-hint {
  display: block;
  font-size: 11px;
  color: var(--muted2);
  margin-bottom: 0.8rem;
}

.save-btn {
  width: 100%;
  padding: 10px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 8px;
  color: #00d4ff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.save-btn:hover { background: linear-gradient(135deg, #00d4ff33, #00d4ff55); }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.field-error {
  margin-top: 0.6rem;
  font-size: 12px;
  color: #ff5252;
}
.field-success {
  margin-top: 0.6rem;
  font-size: 12px;
  color: #00e676;
}

.notif-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #181d2c;
}
.notif-row:last-child { border-bottom: none; }
.notif-label { font-size: 13px; color: var(--sub); }

.raw-toggle {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--muted);
  font-size: 12px;
  font-family: var(--mono);
  cursor: pointer;
  transition: all 0.2s;
}
.raw-toggle:hover { color: var(--sub); border-color: #00d4ff44; }

.raw-panel {
  max-height: 400px;
  overflow: auto;
  background: #0d1018;
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
}
.raw-panel pre {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted3);
  white-space: pre-wrap;
  word-break: break-all;
}

/* Scheduler / Data Collection */
.interval-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #181d2c;
}
.interval-label {
  font-size: 13px;
  color: var(--sub);
}
.interval-control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.interval-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--sub);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.interval-btn:hover:not(:disabled) {
  border-color: #00d4ff55;
  color: #00d4ff;
}
.interval-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.interval-value {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  min-width: 52px;
  text-align: center;
  font-family: var(--mono);
}
.interval-value.disabled {
  color: var(--muted);
}
.scheduler-status {
  margin-top: 12px;
  padding: 10px 12px;
  background: #0d1018;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.running {
  background: #00e676;
  box-shadow: 0 0 6px #00e67688;
}
.status-dot.stopped {
  background: #5c6478;
}
.status-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--sub);
}
.status-detail {
  font-size: 11px;
  color: var(--muted);
}
.status-error {
  font-size: 11px;
  color: #ff5252;
  font-family: var(--mono);
}
</style>
