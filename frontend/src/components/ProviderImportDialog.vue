<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-dialog modal-wide">
        <h3>Import from charging providers</h3>
        <p class="edit-date">{{ monthLabel }}</p>

        <!-- Several accounts: which one first -->
        <template v-if="step === 'choose'">
          <p class="state">Which charging provider do you want to import the billed sessions from?</p>
          <div class="choices">
            <label v-for="a in accounts" :key="a.id" class="choice">
              <input v-model="accountId" type="radio" :value="a.id" />
              <span><b>{{ a.label }}</b> · {{ a.username }}</span>
            </label>
            <label class="choice">
              <input v-model="accountId" type="radio" :value="null" />
              <span>All of them</span>
            </label>
          </div>
          <div class="modal-actions">
            <span class="modal-actions-spacer" />
            <button class="btn-cancel" @click="$emit('close')">Cancel</button>
            <button class="btn-save" @click="loadPreview">Continue</button>
          </div>
        </template>

        <div v-else-if="loading" class="state">Loading the billed sessions…</div>
        <div v-else-if="error && !items.length" class="field-error">{{ error }}</div>

        <template v-else-if="!result">
          <p v-if="!items.length" class="state">No billed session in this month.</p>
          <ul v-else class="imports">
            <li v-for="item in items" :key="keyOf(item)" class="import" :class="item.status">
              <label class="import-check">
                <input v-model="selected[keyOf(item)]" type="checkbox" :disabled="item.status === 'elsewhere'" />
              </label>
              <div class="import-body">
                <div class="import-head">
                  <strong>{{ formatDateTime(item.session.started_at) }}</strong>
                  <span class="status-chip" :class="item.status">{{ statusLabel(item.status) }}</span>
                  <span class="provider-chip" :title="item.session.account_username || ''">{{ item.session.provider_label }}</span>
                  <span class="import-where">{{ [item.session.operator, item.session.location].filter(Boolean).join(' · ') }}</span>
                </div>
                <div class="import-billed">
                  {{ fmtKwh(item.session.energy_kwh) }} · {{ fmtEur(item.session.cost) }}
                  <span v-if="item.session.price_kwh != null"> · €{{ item.session.price_kwh.toFixed(3) }}/kWh</span>
                  <span v-for="f in item.session.fees" :key="f.label" class="fee">+ {{ f.label }} {{ fmtEur(f.amount) }}</span>
                </div>
                <div v-for="p in item.problems" :key="p" class="import-warning">⚠ {{ p }} — maybe another vehicle's charge</div>
                <div v-if="item.status === 'elsewhere'" class="import-change">
                  Already linked to another session (another vehicle, or another month).
                </div>
                <div v-else-if="item.status !== 'unmatched'" class="import-change">
                  <span>
                    Energy {{ fmtKwh(item.current?.energy_kwh) }} → <b>{{ fmtKwh(item.proposed?.energy_kwh) }}</b>
                    <em v-if="item.energy_kept">kept: entered by hand</em>
                  </span>
                  <span>
                    Total {{ fmtEur(item.current?.total_cost) }} → <b>{{ fmtEur(item.proposed?.total_cost) }}</b>
                    <em v-if="item.cost_kept">energy cost kept: entered by hand</em>
                  </span>
                </div>
                <div v-else class="import-change">
                  Not seen in the vehicle history (e.g. the car was offline): tick to create the session from the billed data.
                </div>
              </div>
            </li>
          </ul>
          <div v-if="error" class="field-error">{{ error }}</div>

          <div class="modal-actions">
            <button v-if="accounts.length > 1" class="btn-cancel" @click="step = 'choose'">Back</button>
            <span class="modal-actions-spacer" />
            <button class="btn-cancel" @click="$emit('close')">Cancel</button>
            <button class="btn-save" :disabled="running || !chosen.length" @click="apply">
              {{ running ? 'Importing…' : `Import (${chosen.length})` }}
            </button>
          </div>
        </template>

        <template v-else>
          <p class="state">
            <strong>{{ result.applied }}</strong> session{{ result.applied === 1 ? '' : 's' }} updated<template v-if="result.created">,
            <strong>{{ result.created }}</strong> created</template>.
          </p>
          <div class="modal-actions">
            <span class="modal-actions-spacer" />
            <button class="btn-save" @click="$emit('close')">Done</button>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../composables/useApi'
import { parseUTC } from '../utils/maintenance'

const props = defineProps({
  vin: { type: String, required: true },
  year: { type: Number, required: true },
  month: { type: Number, required: true },
  monthLabel: { type: String, default: '' },
  // The connected charging provider accounts
  accounts: { type: Array, required: true },
})
const emit = defineEmits(['close', 'imported'])

const url = computed(() => `/api/vehicles/${props.vin}/charging-costs/import`)
const step = ref(props.accounts.length > 1 ? 'choose' : 'preview')
const accountId = ref(props.accounts[0]?.id ?? null)
const loading = ref(false)
const running = ref(false)
const error = ref('')
const items = ref([])
const selected = reactive({}) // provider:external id → ticked
const result = ref(null)

const keyOf = i => `${i.session.provider}:${i.session.external_id}`
const chosen = computed(() => items.value.filter(i => selected[keyOf(i)]))

const STATUS = {
  matched: 'New',
  uncertain: 'Check it',
  imported: 'Already imported',
  dismissed: 'Unlinked by you',
  unmatched: 'No matching session',
  elsewhere: 'Linked elsewhere',
}
const statusLabel = s => STATUS[s] || s
const fmtKwh = v => (v == null ? '—' : `${v.toFixed(2)} kWh`)
const fmtEur = v => (v == null ? '—' : `€${v.toFixed(2)}`)
const formatDateTime = ts => (ts
  ? parseUTC(ts).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  : '—')

const period = () => ({ year: props.year, month: props.month, account_id: accountId.value })

async function loadPreview() {
  step.value = 'preview'
  loading.value = true
  error.value = ''
  items.value = []
  for (const k of Object.keys(selected)) delete selected[k]
  try {
    const data = await api('POST', `${url.value}/preview`, period())
    items.value = data.items
    // Plausible new matches are ticked; the rest is opt-in
    for (const i of data.items) selected[keyOf(i)] = i.status === 'matched'
  } catch (e) {
    error.value = e.message || 'Failed to load the billed sessions'
  } finally {
    loading.value = false
  }
}

async function apply() {
  running.value = true
  error.value = ''
  const ids = unmatched => chosen.value.filter(i => unmatched === (i.status === 'unmatched')).map(i => i.session.external_id)
  try {
    result.value = await api('POST', `${url.value}/apply`, {
      ...period(),
      external_ids: ids(false),
      create_ids: ids(true),
    })
    emit('imported')
  } catch (e) {
    error.value = e.message || 'Import failed'
  } finally {
    running.value = false
  }
}

onMounted(() => {
  if (step.value === 'preview') loadPreview()
})
</script>

<style scoped>
.state { font-size: 13px; color: var(--muted); margin: 10px 0; }
.choices { display: flex; flex-direction: column; gap: 6px; margin: 4px 0 12px; }
.choice { display: flex; align-items: center; gap: 8px; font-size: 13px; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; cursor: pointer; overflow-wrap: anywhere; }
.imports { list-style: none; padding: 0; margin: 0 0 8px; display: flex; flex-direction: column; gap: 8px; max-height: 60vh; overflow-y: auto; }
.import { display: flex; gap: 10px; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
.import.unmatched { border-style: dashed; }
.import-check { padding-top: 2px; }
.import-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.import-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.import-where { color: var(--muted); font-size: 11px; }
.import-billed { color: var(--text); }
.fee { margin-left: 6px; color: #ffb74d; }
.import-change { display: flex; flex-direction: column; gap: 2px; color: var(--muted); }
.import-change em { margin-left: 6px; font-style: normal; font-size: 10px; text-transform: uppercase; color: var(--muted); border: 1px solid var(--border); border-radius: 4px; padding: 0 4px; }
.status-chip, .provider-chip { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 1px 6px; }
.provider-chip { border: 1px solid var(--accent); color: var(--accent); }
.status-chip.matched { background: var(--accent); color: var(--card); }
.status-chip.imported { border: 1px solid var(--border); color: var(--muted); }
.status-chip.unmatched, .status-chip.uncertain { border: 1px dashed #ffb74d; color: #ffb74d; }
.status-chip.dismissed, .status-chip.elsewhere { border: 1px solid var(--border); color: var(--muted); }
.import.elsewhere { opacity: 0.6; }
.import-warning { color: #ffb74d; }
</style>
