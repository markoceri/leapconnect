<template>
  <div class="evdc-panel">
    <div class="panel-title"><Receipt :size="13" /> EVDC</div>

    <!-- Linked -->
    <template v-if="session.external_source === 'evdc'">
      <div class="linked">
        <span>Billed energy, cost and fees imported from EVDC.</span>
        <a v-if="session.id" class="link" :href="receiptUrl" target="_blank" rel="noopener"><FileText :size="12" /> Receipt</a>
        <span class="spacer" />
        <button class="btn btn-ghost" :disabled="busy" @click="unlink">Unlink</button>
      </div>
    </template>

    <!-- Not linked -->
    <template v-else>
      <p v-if="session.auto_link_disabled" class="note">Unlinked by you: the automatic import won't link it again.</p>
      <div v-if="loading" class="note">Looking for this charge on EVDC…</div>
      <div v-else-if="loadError" class="error">{{ loadError }}</div>
      <template v-else>
        <p v-if="!candidates.length" class="note">No EVDC session around this charge.</p>
        <template v-else>
          <p v-if="!candidates[0].best && !picked" class="note">
            No EVDC session clearly matches this charge: pick one if it's yours.
          </p>
          <div v-if="current" class="candidate" :class="{ warn: current.problems.length || current.linked_cost_id }">
            <div class="cand-head">
              <span class="tag">{{ current.best && !picked ? 'Found' : 'Selected' }}</span>
              <strong>{{ formatDateTime(current.session.started_at) }}</strong>
              <span>· {{ fmtKwh(current.session.energy_kwh) }} · {{ fmtEur(current.session.cost) }}</span>
              <span v-for="f in current.session.fees" :key="f.label" class="fee">(+ {{ f.label }} {{ fmtEur(f.amount) }})</span>
            </div>
            <div v-if="current.session.operator || current.session.location" class="sub">
              {{ [current.session.operator, current.session.location].filter(Boolean).join(' · ') }}
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
            <select v-if="candidates.length > 1 || !candidates[0].best" v-model="pickedId" class="pick">
              <option :value="null" disabled>{{ current ? 'Not this one? Choose another…' : 'Choose an EVDC session…' }}</option>
              <option v-for="c in candidates" :key="c.session.external_id" :value="c.session.external_id">
                {{ formatDateTime(c.session.started_at) }} · {{ fmtKwh(c.session.energy_kwh) }} · {{ fmtEur(c.session.cost) }}{{ c.problems.length || c.overlap_minutes == null ? ' ⚠' : '' }}
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
import { FileText, Receipt } from 'lucide-vue-next'
import { api } from '../composables/useApi'
import { parseUTC } from '../utils/maintenance'

const props = defineProps({
  vin: { type: String, required: true },
  // A row of the session list
  session: { type: Object, required: true },
})
const emit = defineEmits(['changed'])

const base = computed(() => `/api/vehicles/${props.vin}/charging-costs`)
const receiptUrl = computed(() => `.${base.value}/${props.session.id}/receipt`)
const loading = ref(false)
const loadError = ref('')
const error = ref('')
const busy = ref(false)
const candidates = ref([])
const pickedId = ref(null)

const picked = computed(() => candidates.value.find(c => c.session.external_id === pickedId.value) || null)
// The candidate shown: the one picked, else the best one
const current = computed(() => picked.value || (candidates.value[0]?.best ? candidates.value[0] : null))

const fmtKwh = v => (v == null ? '—' : `${v.toFixed(2)} kWh`)
const fmtEur = v => (v == null ? '—' : `€${v.toFixed(2)}`)
const formatDateTime = ts => (ts
  ? parseUTC(ts).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  : '—')

// The session: its record, or its start when seen only in the history
const target = () => (props.session.id ? { cost_id: props.session.id } : { start_ts: props.session.start_ts })

onMounted(async () => {
  if (props.session.external_source) return
  loading.value = true
  try {
    const query = new URLSearchParams(target()).toString()
    candidates.value = (await api('GET', `${base.value}/link/evdc/candidates?${query}`)).candidates
  } catch (e) {
    loadError.value = e.message || 'EVDC lookup failed'
  } finally {
    loading.value = false
  }
})

async function link() {
  busy.value = true
  error.value = ''
  try {
    const sc = await api('POST', `${base.value}/link/evdc`, { external_id: current.value.session.external_id, ...target() })
    emit('changed', sc)
  } catch (e) {
    error.value = e.message || 'Link failed'
  } finally {
    busy.value = false
  }
}

async function unlink() {
  if (!confirm('Unlink this session from EVDC? Energy and cost go back to the measured ones (unless entered by hand), the EVDC fees are removed, and the automatic import won\'t link it again.')) return
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
.evdc-panel { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 12px; }
.panel-title { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin-bottom: 8px; }
.linked, .actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.actions { margin-top: 8px; }
.spacer { flex: 1; }
.note { color: var(--muted); margin: 0 0 6px; }
.candidate { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; display: flex; flex-direction: column; gap: 3px; }
.candidate.warn { border-color: color-mix(in srgb, #ffb74d 60%, transparent); }
.cand-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.tag { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 1px 6px; background: var(--accent); color: var(--card); }
.fee { color: #ffb74d; }
.sub { color: var(--muted); }
.warning { color: #ffb74d; }
.pick { background: var(--input); border: 1px solid var(--border); border-radius: 8px; padding: 6px 8px; color: var(--text); font-size: 12px; min-width: 0; max-width: 100%; }
.link { display: inline-flex; align-items: center; gap: 3px; color: var(--accent); text-decoration: none; }
.btn { border: none; border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn:disabled { opacity: 0.5; cursor: default; }
.btn-primary { background: var(--accent); color: var(--card); }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text); }
.error { color: var(--red); margin-top: 6px; }
</style>
