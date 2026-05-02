<template>
  <div class="settings-tab">
    <!-- LeapConnect Account -->
    <SectionCard title="LeapConnect Account" :icon="User">
      <div class="account-row">
        <div class="account-avatar">{{ initials }}</div>
        <div>
          <div class="account-name">{{ displayName }}</div>
          <div class="account-role">Local account</div>
        </div>
      </div>
      <button class="action-btn" @click="showUserEdit = !showUserEdit">
        {{ showUserEdit ? 'Cancel' : 'Edit Account' }}
      </button>
      <div v-if="showUserEdit" class="edit-panel">
        <div class="form-group">
          <label>Display Name</label>
          <input v-model="userForm.display_name" type="text" placeholder="Your name" />
        </div>
        <div class="form-group">
          <label>New Password</label>
          <input v-model="userForm.password" type="password" placeholder="Leave empty to keep current" />
        </div>
        <div class="form-divider">Verification</div>
        <div class="form-group">
          <label>Current Password</label>
          <input v-model="userForm.current_password" type="password" placeholder="Required to save changes" />
        </div>
        <button class="save-btn" :disabled="userSaving" @click="saveUser">
          {{ userSaving ? 'Saving…' : 'Save Changes' }}
        </button>
        <div v-if="userError" class="field-error">{{ userError }}</div>
        <div v-if="userSuccess" class="field-success">{{ userSuccess }}</div>
      </div>
      <InfoRow label="App version" value="v2.5.0" color="#5c6478" />
    </SectionCard>

    <!-- Leapmotor Credentials -->
    <SectionCard title="Leapmotor Credentials" :icon="KeyRound">
      <InfoRow label="Email" :value="leapmotorEmail" color="#e2e6f0" />
      <InfoRow label="Connection" :value="store.connected ? 'Connected' : 'Offline'" :color="store.connected ? '#00e676' : '#ffab40'" :dot="true" />
      <button class="action-btn" @click="showLeapmotorEdit = !showLeapmotorEdit">
        {{ showLeapmotorEdit ? 'Cancel' : 'Edit Credentials' }}
      </button>
      <div v-if="showLeapmotorEdit" class="edit-panel">
        <div class="form-group">
          <label>Leapmotor Email</label>
          <input v-model="accountForm.username" type="email" placeholder="your@email.com" />
        </div>
        <div class="form-group">
          <label>Leapmotor Password</label>
          <input v-model="accountForm.password" type="password" placeholder="Leapmotor account password" />
        </div>
        <button class="save-btn" :disabled="accountSaving" @click="saveLeapmotorAccount">
          {{ accountSaving ? 'Saving…' : 'Save & Reconnect' }}
        </button>
        <div v-if="accountError" class="field-error">{{ accountError }}</div>
        <div v-if="accountSuccess" class="field-success">{{ accountSuccess }}</div>
      </div>
    </SectionCard>

    <!-- Certificates -->
    <SectionCard title="Certificates" :icon="ShieldCheck">
      <InfoRow label="App Certificate" :value="certsStatus.cert_exists ? 'Installed' : 'Missing'" :color="certsStatus.cert_exists ? '#00e676' : '#ff5252'" :dot="true" />
      <InfoRow label="Private Key" :value="certsStatus.key_exists ? 'Installed' : 'Missing'" :color="certsStatus.key_exists ? '#00e676' : '#ff5252'" :dot="true" />
      <button class="action-btn" @click="showCertEdit = !showCertEdit">
        {{ showCertEdit ? 'Cancel' : 'Update Certificates' }}
      </button>
      <div v-if="showCertEdit" class="edit-panel">
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
        <button class="save-btn" :disabled="certSaving || !certFile || !keyFile" @click="saveCertificates">
          {{ certSaving ? 'Uploading…' : 'Upload Certificates' }}
        </button>
        <div v-if="certError" class="field-error">{{ certError }}</div>
        <div v-if="certSuccess" class="field-success">{{ certSuccess }}</div>
      </div>
    </SectionCard>

    <!-- Vehicle -->
    <SectionCard title="Vehicle" :icon="Car">
      <InfoRow label="Model" :value="`Leapmotor ${vehicle.car_type || ''} ${vehicle.year || ''}`" color="#e2e6f0" />
      <InfoRow label="VIN" color="#e2e6f0">
        <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
      </InfoRow>
      <InfoRow label="Nickname" :value="vehicle.vehicle_nickname || '—'" color="#00d4ff" />
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
      <div class="scheduler-service">
        <div class="service-status">
          <span class="status-dot" :class="scheduler.is_running ? 'running' : 'stopped'" />
          <span class="service-text">
            {{ scheduler.is_running ? 'Running' : 'Stopped' }}
            <span v-if="scheduler.is_running" class="service-interval">· every {{ scheduler.interval_minutes }} min</span>
          </span>
        </div>
        <button
          class="service-btn"
          :class="scheduler.is_running ? 'btn-stop' : 'btn-start'"
          :disabled="schedulerUpdating"
          @click="toggleScheduler(!scheduler.enabled)"
        >
          {{ scheduler.is_running ? 'Stop' : 'Start' }}
        </button>
      </div>

      <div class="interval-row">
        <span class="interval-label">Collection interval</span>
        <div class="interval-control">
          <button class="interval-btn" @click="pendingInterval = Math.max(1, pendingInterval - 5)">−</button>
          <span class="interval-value">{{ pendingInterval }} min</span>
          <button class="interval-btn" @click="pendingInterval = Math.min(1440, pendingInterval + 5)">+</button>
          <button
            class="interval-set-btn"
            :disabled="pendingInterval === scheduler.interval_minutes || schedulerUpdating"
            @click="applyInterval"
          >Set</button>
        </div>
      </div>

      <div class="scheduler-status">
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
      <div v-if="showRaw">
        <div class="raw-tabs">
          <button class="raw-tab" :class="{ active: rawTab === 'vehicle' }" @click="rawTab = 'vehicle'">Vehicle</button>
          <button class="raw-tab" :class="{ active: rawTab === 'status' }" @click="rawTab = 'status'">Status</button>
        </div>
        <div class="raw-panel">
          <pre v-if="rawTab === 'vehicle'">{{ JSON.stringify(rawData?.vehicle_raw, null, 2) }}</pre>
          <pre v-else>{{ JSON.stringify(rawData?.status_raw, null, 2) }}</pre>
        </div>
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
import { useAppStore } from '../stores/appStore'
import { User, Car, Bell, SlidersHorizontal, BarChart3, Code, KeyRound, ShieldCheck } from 'lucide-vue-next'

const store = useAppStore()

const props = defineProps({
  vehicle: { type: Object, required: true },
  rawData: { type: Object, default: () => ({}) },
})

const showRaw = ref(false)
const rawTab = ref('vehicle')

// LeapConnect user edit
const showUserEdit = ref(false)
const userSaving = ref(false)
const userError = ref('')
const userSuccess = ref('')
const userForm = reactive({ display_name: '', password: '', current_password: '' })
const displayName = ref('User')

// Leapmotor credentials edit
const showLeapmotorEdit = ref(false)
const accountSaving = ref(false)
const accountError = ref('')
const accountSuccess = ref('')
const leapmotorEmail = ref('—')
const accountForm = reactive({ username: '', password: '' })

// Certificates edit
const showCertEdit = ref(false)
const certSaving = ref(false)
const certError = ref('')
const certSuccess = ref('')
const certFile = ref(null)
const keyFile = ref(null)
const certsStatus = reactive({ cert_exists: false, key_exists: false })

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

const pendingInterval = ref(15)
const schedulerUpdating = ref(false)

async function loadScheduler() {
  try {
    const data = await api('GET', '/api/scheduler')
    Object.assign(scheduler, data)
    pendingInterval.value = data.interval_minutes
  } catch {
    // scheduler not available yet
  }
}

async function updateScheduler(patch) {
  if (schedulerUpdating.value) return
  schedulerUpdating.value = true
  try {
    const data = await api('PUT', '/api/scheduler', patch)
    Object.assign(scheduler, data)
    pendingInterval.value = data.interval_minutes
  } catch {
    await loadScheduler()
  } finally {
    schedulerUpdating.value = false
  }
}

function toggleScheduler(val) {
  updateScheduler({ enabled: val })
}

function applyInterval() {
  if (pendingInterval.value !== scheduler.interval_minutes) {
    updateScheduler({ interval_minutes: pendingInterval.value })
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
    if (data.leapmotor_email) {
      leapmotorEmail.value = data.leapmotor_email
      accountForm.username = data.leapmotor_email
    }
    if (data.display_name) {
      displayName.value = data.display_name
      userForm.display_name = data.display_name
    }
  } catch { /* ignore */ }
}

async function loadCertsStatus() {
  try {
    const data = await api('GET', '/api/setup/certificates')
    Object.assign(certsStatus, data)
  } catch { /* ignore */ }
}

async function saveUser() {
  userError.value = ''
  userSuccess.value = ''
  if (!userForm.current_password) {
    userError.value = 'Current password is required'
    return
  }
  userSaving.value = true
  try {
    const payload = { current_password: userForm.current_password }
    if (userForm.display_name) payload.display_name = userForm.display_name
    if (userForm.password) payload.password = userForm.password
    const result = await api('PUT', '/api/setup/user', payload)
    displayName.value = result.display_name
    userForm.current_password = ''
    userForm.password = ''
    userSuccess.value = 'Account updated successfully'
  } catch (err) {
    userError.value = err.message
  } finally {
    userSaving.value = false
  }
}

async function saveLeapmotorAccount() {
  accountError.value = ''
  accountSuccess.value = ''
  if (!accountForm.username || !accountForm.password) {
    accountError.value = 'Email and password are required'
    return
  }
  accountSaving.value = true
  try {
    const result = await api('POST', '/api/setup/account', {
      username: accountForm.username,
      password: accountForm.password,
    })
    if (result.connected) {
      accountSuccess.value = 'Credentials saved. Connected successfully.'
      leapmotorEmail.value = accountForm.username
      store.connected = true
      store.vehicles = result.vehicles || []
    } else {
      accountSuccess.value = 'Credentials saved. ' + (result.connection_error || 'Connection failed.')
    }
  } catch (err) {
    accountError.value = err.message
  } finally {
    accountSaving.value = false
  }
}

async function saveCertificates() {
  certError.value = ''
  certSuccess.value = ''
  if (!certFile.value || !keyFile.value) return
  certSaving.value = true
  try {
    const formData = new FormData()
    formData.append('cert_file', certFile.value)
    formData.append('key_file', keyFile.value)
    const res = await fetch('/api/setup/certificates', { method: 'POST', body: formData, credentials: 'include' })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Upload failed')
    certSuccess.value = 'Certificates updated successfully'
    certFile.value = null
    keyFile.value = null
    await loadCertsStatus()
  } catch (err) {
    certError.value = err.message
  } finally {
    certSaving.value = false
  }
}

onMounted(() => {
  loadScheduler()
  loadAccount()
  loadCertsStatus()
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
.account-role {
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
  border-radius: 0 0 8px 8px;
  padding: 12px;
  margin-top: 0;
}
.raw-panel pre {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted3);
  white-space: pre-wrap;
  word-break: break-all;
}
.raw-tabs {
  display: flex;
  gap: 4px;
  margin-top: 12px;
}
.raw-tab {
  flex: 1;
  padding: 8px 0;
  border: none;
  border-radius: 8px 8px 0 0;
  background: #161a26;
  color: #5c6478;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.raw-tab.active {
  background: #0d1018;
  color: #7c6aff;
}

/* Scheduler / Data Collection */
.scheduler-service {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #181d2c;
}
.service-status {
  display: flex;
  align-items: center;
  gap: 8px;
}
.service-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--sub);
}
.service-interval {
  font-weight: 400;
  color: var(--muted);
}
.service-btn {
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid;
}
.service-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-start {
  background: #00e67618;
  border-color: #00e67644;
  color: #00e676;
}
.btn-start:hover:not(:disabled) { background: #00e67630; }
.btn-stop {
  background: #ff525218;
  border-color: #ff525244;
  color: #ff5252;
}
.btn-stop:hover:not(:disabled) { background: #ff525230; }

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
.interval-set-btn {
  padding: 4px 12px;
  background: #1c2240;
  border: 1px solid #2a3060;
  border-radius: 6px;
  color: var(--sub);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  margin-left: 4px;
}
.interval-set-btn:hover:not(:disabled) { background: #252d50; color: #00d4ff; }
.interval-set-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.scheduler-status {
  margin-top: 12px;
  padding: 10px 12px;
  background: #0d1018;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
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
