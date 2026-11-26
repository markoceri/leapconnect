<template>
  <SectionCard title="Charging Providers" :icon="Receipt">
    <p class="hint">
      Connect the apps you pay public charges with (e-mobility service providers) to import billed kWh, price and fees,
      and to see their charging points on the map. Read-only — passwords are not stored.
    </p>

    <ul v-if="accounts.length" class="accounts">
      <li v-for="a in accounts" :key="a.id" class="account">
        <div class="row">
          <span class="status-dot" :class="{ running: a.connected && !a.last_error, warn: a.last_error }" />
          <span class="row-text">
            <span><b>{{ a.label }}</b> · {{ a.username }}</span>
            <span v-if="a.last_sync" class="sub">Last import: {{ formatDate(a.last_sync) }}</span>
            <span v-if="!a.connected" class="sub err">Not connected: remove it and connect it again</span>
          </span>
          <button class="btn btn-danger" :disabled="busy" @click="remove(a)">Disconnect</button>
        </div>
        <div class="row">
          <span class="row-text">
            Import automatically
            <span class="sub">after each public charge and once a day</span>
          </span>
          <ToggleSwitch :modelValue="a.auto_sync" @update:modelValue="v => setAutoSync(a, v)" />
        </div>
        <div v-if="a.last_error" class="error">Last import failed: {{ a.last_error }}</div>
      </li>
    </ul>
    <p v-else-if="loaded && !adding" class="sub">No charging provider connected.</p>

    <!-- Add an account -->
    <div v-if="adding" class="add">
      <template v-if="pending">
        <p class="hint">
          {{ pending.method === 'totp' ? 'Enter the code of your authenticator app.' : `Enter the code ${type?.label} sent you by e-mail.` }}
        </p>
        <div class="form">
          <input v-model="code" class="input" inputmode="numeric" autocomplete="one-time-code" placeholder="Verification code" @keyup.enter="verify" />
          <button class="btn btn-primary" :disabled="busy || !code" @click="verify">{{ busy ? '…' : 'Verify' }}</button>
          <button class="btn btn-ghost" :disabled="busy" @click="cancel">Cancel</button>
        </div>
      </template>
      <template v-else>
        <div class="form">
          <select v-model="form.provider" class="input select" :disabled="types.length < 2">
            <option v-for="t in types" :key="t.id" :value="t.id">{{ t.label }}</option>
          </select>
        </div>
        <p v-if="type" class="hint">
          <a :href="type.url" target="_blank" rel="noopener">{{ type.label }}</a> account.
          <template v-if="type.note"> {{ type.note }}</template>
        </p>
        <div class="form">
          <input v-model="form.username" class="input" type="email" autocomplete="username" :placeholder="`${type?.label || ''} ${(type?.username_label || 'e-mail').toLowerCase()}`" />
          <input v-model="form.password" class="input" type="password" autocomplete="current-password" placeholder="Password" @keyup.enter="connect" />
        </div>
        <div class="form">
          <span class="spacer" />
          <button class="btn btn-ghost" :disabled="busy" @click="cancel">Cancel</button>
          <button class="btn btn-primary" :disabled="busy || !form.username || !form.password" @click="connect">{{ busy ? '…' : 'Connect' }}</button>
        </div>
      </template>
    </div>
    <button v-else class="btn btn-ghost add-btn" :disabled="!types.length" @click="startAdd"><Plus :size="13" /> Add a charging provider</button>

    <div v-if="error" class="error">{{ error }}</div>
  </SectionCard>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { Plus, Receipt } from 'lucide-vue-next'
import SectionCard from './SectionCard.vue'
import ToggleSwitch from './ToggleSwitch.vue'
import { api } from '../composables/useApi'

const URL = '/api/charging/providers'
const types = ref([])
const accounts = ref([])
const loaded = ref(false)
const adding = ref(false)
const pending = ref(null) // { id, method } while a login waits for its code
const form = reactive({ provider: '', username: '', password: '' })
const code = ref('')
const busy = ref(false)
const error = ref('')

const type = computed(() => types.value.find(t => t.id === form.provider) || null)

async function run(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
  } catch (e) {
    error.value = e.message || 'Request failed'
  } finally {
    busy.value = false
  }
}

async function load() {
  await run(async () => {
    const data = await api('GET', URL)
    types.value = data.types
    accounts.value = data.accounts
  })
  loaded.value = true
}

function startAdd() {
  Object.assign(form, { provider: types.value[0]?.id || '', username: '', password: '' })
  adding.value = true
}

function cancel() {
  adding.value = false
  pending.value = null
  code.value = ''
  form.password = ''
}

const connect = () => run(async () => {
  const data = await api('POST', URL, { ...form })
  form.password = ''
  if (data.pending_id) {
    pending.value = { id: data.pending_id, method: data.two_factor_method }
    return
  }
  cancel()
  await load()
})

const verify = () => run(async () => {
  await api('POST', `${URL}/pending/${pending.value.id}/verify`, { code: code.value })
  cancel()
  await load()
})

function remove(a) {
  if (!confirm(`Disconnect the ${a.label} account ${a.username}? Sessions already imported keep their costs.`)) return
  run(async () => {
    await api('DELETE', `${URL}/${a.id}`)
    accounts.value = accounts.value.filter(x => x.id !== a.id)
  })
}

const setAutoSync = (a, value) => run(async () => {
  Object.assign(a, await api('PUT', `${URL}/${a.id}`, { auto_sync: value }))
})

function formatDate(iso) {
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>

<style scoped>
.hint { font-size: 12px; color: var(--muted); margin: 0 0 10px; line-height: 1.45; }
.hint a { color: var(--accent); }
.accounts { list-style: none; padding: 0; margin: 0 0 10px; display: flex; flex-direction: column; gap: 8px; }
.account { border: 1px solid var(--border); border-radius: 8px; padding: 4px 10px 6px; }
.row { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.row-text { flex: 1; min-width: 0; font-size: 13px; display: flex; flex-direction: column; gap: 2px; overflow-wrap: anywhere; }
.sub { font-size: 11px; color: var(--muted); }
.sub.err { color: var(--red); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
.status-dot.running { background: #00e676; }
.status-dot.warn { background: #ffb74d; }
.add { border: 1px dashed var(--border); border-radius: 8px; padding: 10px; margin-bottom: 6px; }
.form { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.spacer { flex: 1; }
.input { flex: 1 1 160px; min-width: 0; background: var(--input); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; color: var(--text); font-size: 13px; }
.select { flex: 0 1 200px; }
.btn { border: none; border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; }
.btn:disabled { opacity: 0.5; cursor: default; }
.btn-primary { background: var(--accent); color: var(--card); }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text); }
.btn-danger { background: none; border: 1px solid var(--red); color: var(--red); }
.add-btn { margin-top: 2px; }
.error { font-size: 12px; color: var(--red); margin-top: 6px; }
</style>
