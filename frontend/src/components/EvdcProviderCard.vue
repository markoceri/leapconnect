<template>
  <SectionCard title="EVDC" :icon="Receipt">
    <p class="hint">
      Import the cost of the public charges paid with the <a href="https://evdc.network" target="_blank" rel="noopener">EVDC</a> app:
      billed kWh, price and fees. Read-only — your password is not stored.
    </p>

    <template v-if="status.connected">
      <div class="row">
        <span class="status-dot running" />
        <span class="row-text">Connected as <b>{{ status.email }}</b></span>
        <button class="btn btn-danger" :disabled="busy" @click="disconnect">Disconnect</button>
      </div>
      <div class="row">
        <span class="row-text">
          Import automatically
          <span class="sub">after each public charge and once a day</span>
        </span>
        <ToggleSwitch :modelValue="status.auto_sync" @update:modelValue="setAutoSync" />
      </div>
      <div v-if="status.last_sync" class="sub">Last import: {{ formatDate(status.last_sync) }}</div>
    </template>

    <template v-else-if="status.two_factor_pending">
      <p class="hint">
        {{ status.two_factor_pending === 'totp' ? 'Enter the code of your authenticator app.' : 'Enter the code EVDC sent you by e-mail.' }}
      </p>
      <div class="form">
        <input v-model="code" class="input" inputmode="numeric" autocomplete="one-time-code" placeholder="Verification code" @keyup.enter="verify" />
        <button class="btn btn-primary" :disabled="busy || !code" @click="verify">{{ busy ? '…' : 'Verify' }}</button>
      </div>
    </template>

    <template v-else>
      <div class="form">
        <input v-model="form.email" class="input" type="email" autocomplete="username" placeholder="EVDC e-mail" />
        <input v-model="form.password" class="input" type="password" autocomplete="current-password" placeholder="Password" @keyup.enter="connect" />
        <button class="btn btn-primary" :disabled="busy || !form.email || !form.password" @click="connect">{{ busy ? '…' : 'Connect' }}</button>
      </div>
      <p class="sub">Accounts created with Google or Apple sign-in have no EVDC password and can't be connected.</p>
    </template>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-else-if="status.last_error" class="error">Last import failed: {{ status.last_error }}</div>
  </SectionCard>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { Receipt } from 'lucide-vue-next'
import SectionCard from './SectionCard.vue'
import ToggleSwitch from './ToggleSwitch.vue'
import { api } from '../composables/useApi'

const URL = '/api/charging/providers/evdc'
const status = reactive({ connected: false, email: null, two_factor_pending: null, auto_sync: true, last_sync: null, last_error: null })
const form = reactive({ email: '', password: '' })
const code = ref('')
const busy = ref(false)
const error = ref('')

async function run(fn) {
  busy.value = true
  error.value = ''
  try {
    Object.assign(status, await fn())
  } catch (e) {
    error.value = e.message || 'Request failed'
  } finally {
    busy.value = false
  }
}

const load = () => run(() => api('GET', URL))
const connect = () => run(async () => {
  const data = await api('POST', `${URL}/session`, { ...form })
  form.password = ''
  return data
})
const verify = () => run(async () => {
  const data = await api('POST', `${URL}/session/verify`, { code: code.value })
  code.value = ''
  return data
})
function disconnect() {
  if (!confirm('Disconnect the EVDC account? Sessions already imported keep their costs.')) return
  run(() => api('DELETE', `${URL}/session`))
}
const setAutoSync = value => run(() => api('PUT', URL, { auto_sync: value }))

function formatDate(iso) {
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>

<style scoped>
.hint { font-size: 12px; color: var(--muted); margin: 0 0 10px; line-height: 1.45; }
.hint a { color: var(--accent); }
.row { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.row-text { flex: 1; font-size: 13px; display: flex; flex-direction: column; gap: 2px; }
.sub { font-size: 11px; color: var(--muted); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
.status-dot.running { background: #00e676; }
.form { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.input { flex: 1 1 160px; min-width: 0; background: var(--input); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; color: var(--text); font-size: 13px; }
.btn { border: none; border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn:disabled { opacity: 0.5; cursor: default; }
.btn-primary { background: var(--accent); color: var(--card); }
.btn-danger { background: none; border: 1px solid var(--red); color: var(--red); }
.error { font-size: 12px; color: var(--red); margin-top: 6px; }
</style>
