<template>
  <div class="provider-panel">
    <div class="panel-title"><Receipt :size="13" /> Charging provider</div>

    <!-- Linked -->
    <template v-if="session.external_source">
      <div class="linked">
        <span class="provider-chip">{{ providerLabel }}</span>
        <span class="linked-text">
          Billed energy, cost and fees imported<template v-if="account"> with {{ account.username }}</template>.
        </span>
        <a v-if="session.id" class="link" :href="receiptUrl" target="_blank" rel="noopener"><FileText :size="12" /> Receipt</a>
        <span class="spacer" />
        <button class="btn btn-ghost" :disabled="busy" @click="unlink">Unlink</button>
      </div>

      <!-- The charging point used -->
      <div v-if="session.evse_id" class="station">
        <div v-if="stationLoading && !station" class="note">Loading the charging point…</div>
        <template v-else-if="station">
          <div class="station-head">
            <MapPin :size="13" />
            <strong>{{ station.name || station.operator || 'Charging point' }}</strong>
            <span v-if="station.status" class="status-chip" :class="statusClass(station.status)">{{ station.status }}</span>
          </div>
          <div v-if="station.operator && station.name" class="sub">{{ station.operator }}</div>
          <div v-if="station.address" class="sub">{{ station.address }}</div>
          <div class="station-facts">
            <span v-if="station.max_power_kw">{{ station.max_power_kw }} kW {{ station.is_dc == null ? '' : station.is_dc ? 'DC' : 'AC' }}</span>
            <span v-if="station.plugs.length">{{ station.plugs.map(plugLabel).join(', ') }}</span>
            <span v-if="station.price != null">Now €{{ station.price.toFixed(2) }}/{{ station.price_unit || 'kWh' }}</span>
            <span v-if="station.is_open_24h">Open 24h</span>
          </div>
          <div class="sub mono">{{ station.evse_id }}</div>
        </template>
        <div v-else class="note">Charging point {{ session.evse_id }} (no details available)</div>
      </div>
    </template>

    <!-- Not linked -->
    <template v-else>
      <p v-if="session.auto_link_disabled" class="note">Unlinked by you: the automatic import won't link it again.</p>
      <div v-if="loading" class="note">Looking for this charge on your charging providers…</div>
      <div v-else-if="loadError" class="error">{{ loadError }}</div>
      <template v-else>
        <p v-if="!candidates.length" class="note">No billed session around this charge.</p>
        <template v-else>
          <p v-if="!candidates[0].best && !picked" class="note">
            No billed session clearly matches this charge: pick one if it's yours.
          </p>
          <div v-if="current" class="candidate" :class="{ warn: current.problems.length || current.linked_cost_id }">
            <div class="cand-head">
              <span class="tag">{{ current.best && !picked ? 'Found' : 'Selected' }}</span>
              <span class="provider-chip" :title="current.session.account_username || ''">{{ current.session.provider_label }}</span>
              <strong>{{ formatDateTime(current.session.started_at) }}</strong>
              <span>· {{ fmtKwh(current.session.energy_kwh) }} · {{ fmtEur(current.session.cost) }}</span>
              <span v-for="f in current.session.fees" :key="f.label" class="fee">(+ {{ f.label }} {{ fmtEur(f.amount) }})</span>
            </div>
            <div v-if="current.session.operator || current.session.location" class="sub">
              {{ [current.session.operator, current.session.location].filter(Boolean).join(' · ') }}
            </div>
            <div v-if="accounts.length > 1 && current.session.account_username" class="sub">
              Account: {{ current.session.account_username }}
            </div>
            <div class="sub">
              kWh {{ fmtKwh(session.energy_kwh) }} → <b>{{ fmtKwh(current.proposed.energy_kwh) }}</b>
              · Total {{ fmtEur(session.total_cost) }} → <b>{{ fmtEur(current.proposed.total_cost) }}</b>
            </div>
            <div v-if="current.overlap_minutes == null" class="warning">Doesn't overlap this charge in time</div>
            <div v-for="p in current.problems" :key="p" class="warning">{{ p }} — maybe another vehicle's charge</div>
            <div v-if="current.linked_cost_id" class="warning">Linked to another session: linking it here moves it</div>
          </div>
          <div class="actions">
            <select v-if="candidates.length > 1 || !candidates[0].best" v-model="pickedKey" class="pick">
              <option :value="null" disabled>{{ current ? 'Not this one? Choose another…' : 'Choose a billed session…' }}</option>
              <option v-for="c in candidates" :key="keyOf(c)" :value="keyOf(c)">
                {{ c.session.provider_label }} · {{ formatDateTime(c.session.started_at) }} · {{ fmtKwh(c.session.energy_kwh) }} · {{ fmtEur(c.session.cost) }}{{ c.problems.length || c.overlap_minutes == null ? ' ⚠' : '' }}
              </option>
            </select>
            <span class="spacer" />
            <button v-if="current" class="btn btn-primary" :disabled="busy" @click="link">{{ busy ? '…' : 'Link' }}</button>
          </div>
        </template>
      </template>
    </template>
    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { FileText, MapPin, Receipt } from 'lucide-vue-next'
import { api } from '../composables/useApi'
import { parseUTC } from '../utils/maintenance'
import { plugLabel, statusClass } from '../utils/chargingStations'

const props = defineProps({
  vin: { type: String, required: true },
  // A row of the session list
  session: { type: Object, required: true },
  // The charging provider accounts (all of them: a linked session may be of
  // an account no longer connected)
  accounts: { type: Array, default: () => [] },
  providerLabels: { type: Object, default: () => ({}) },
})
// `station`: the charging point used, for the session map
const emit = defineEmits(['changed', 'station'])

const base = computed(() => `/api/vehicles/${props.vin}/charging-costs`)
const receiptUrl = computed(() => `.${base.value}/${props.session.id}/receipt`)
const account = computed(() => props.accounts.find(a => a.id === props.session.provider_account_id) || null)
const providerLabel = computed(() => props.providerLabels[props.session.external_source] || props.session.external_source)
const loading = ref(false)
const loadError = ref('')
const error = ref('')
const busy = ref(false)
const candidates = ref([])
const pickedKey = ref(null)
const station = ref(null)
const stationLoading = ref(false)

const keyOf = c => `${c.session.account_id}:${c.session.external_id}`
const picked = computed(() => candidates.value.find(c => keyOf(c) === pickedKey.value) || null)
// The candidate shown: the one picked, else the best one
const current = computed(() => picked.value || (candidates.value[0]?.best ? candidates.value[0] : null))

const fmtKwh = v => (v == null ? '—' : `${v.toFixed(2)} kWh`)
const fmtEur = v => (v == null ? '—' : `€${v.toFixed(2)}`)
const formatDateTime = ts => (ts
  ? parseUTC(ts).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  : '—')

// The session: its record, or its start when seen only in the history
const target = () => (props.session.id ? { cost_id: props.session.id } : { start_ts: props.session.start_ts })

async function loadStation() {
  const { external_source: provider, evse_id: evse } = props.session
  stationLoading.value = true
  try {
    station.value = await api('GET', `/api/charging/stations/${encodeURIComponent(provider)}/${encodeURIComponent(evse)}`)
    emit('station', station.value)
  } catch {
    station.value = null
  } finally {
    stationLoading.value = false
  }
}

async function loadCandidates() {
  if (!props.accounts.some(a => a.connected)) return
  loading.value = true
  try {
    const query = new URLSearchParams(target()).toString()
    candidates.value = (await api('GET', `${base.value}/link/candidates?${query}`)).candidates
  } catch (e) {
    loadError.value = e.message || 'Lookup failed'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (props.session.external_source) {
    if (props.session.evse_id) loadStation()
  } else {
    loadCandidates()
  }
})

async function link() {
  busy.value = true
  error.value = ''
  try {
    const sc = await api('POST', `${base.value}/link`, {
      account_id: current.value.session.account_id,
      external_id: current.value.session.external_id,
      ...target(),
    })
    emit('changed', sc)
  } catch (e) {
    error.value = e.message || 'Link failed'
  } finally {
    busy.value = false
  }
}

async function unlink() {
  if (!confirm(`Unlink this session from ${providerLabel.value}? Energy and cost go back to the measured ones (unless entered by hand), the billed fees are removed, and the automatic import won't link it again.`)) return
  busy.value = true
  error.value = ''
  try {
    emit('changed', await api('DELETE', `${base.value}/${props.session.id}/link`))
  } catch (e) {
    error.value = e.message || 'Unlink failed'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.provider-panel { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 12px; }
.panel-title { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin-bottom: 8px; }
.linked, .actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.linked-text { min-width: 0; overflow-wrap: anywhere; }
.actions { margin-top: 8px; }
.spacer { flex: 1; }
.note { color: var(--muted); margin: 0 0 6px; }
.candidate, .station { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; display: flex; flex-direction: column; gap: 3px; }
.station { margin-top: 8px; }
.station-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.station-facts { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--text); }
.candidate.warn { border-color: color-mix(in srgb, #ffb74d 60%, transparent); }
.cand-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.tag, .provider-chip, .status-chip { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 1px 6px; }
.tag { background: var(--accent); color: var(--card); }
.provider-chip { border: 1px solid var(--accent); color: var(--accent); }
.status-chip { border: 1px solid var(--border); color: var(--muted); }
.status-chip.available { border-color: #22c55e; color: #22c55e; }
.status-chip.busy { border-color: #ffb74d; color: #ffb74d; }
.status-chip.down { border-color: var(--red); color: var(--red); }
.fee { color: #ffb74d; }
.sub { color: var(--muted); overflow-wrap: anywhere; }
.mono { font-family: ui-monospace, monospace; font-size: 10px; }
.warning { color: #ffb74d; }
.pick { background: var(--input); border: 1px solid var(--border); border-radius: 8px; padding: 6px 8px; color: var(--text); font-size: 12px; min-width: 0; max-width: 100%; }
.link { display: inline-flex; align-items: center; gap: 3px; color: var(--accent); text-decoration: none; }
.btn { border: none; border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn:disabled { opacity: 0.5; cursor: default; }
.btn-primary { background: var(--accent); color: var(--card); }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text); }
.error { color: var(--red); margin-top: 6px; }
</style>
