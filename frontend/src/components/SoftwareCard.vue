<template>
  <SectionCard title="Software" :icon="Cpu">
    <template #actions>
      <span v-if="badge" class="sw-badge" :class="badge.cls">{{ badge.label }}</span>
      <button class="sw-refresh" title="Check now" :disabled="entry.loading" @click="load(true)">
        <RefreshCw :size="13" :class="{ 'sw-spin': entry.loading }" />
      </button>
    </template>

    <div v-if="!data && entry.loading" class="sw-empty">Checking software…</div>
    <div v-else-if="!data && entry.error" class="sw-empty">{{ entry.error }}</div>

    <div v-else-if="data?.status === 'owner_only'" class="sw-empty">
      <Lock :size="15" class="sw-empty-icon" />
      <span>
        Leapmotor shows the software version and pending updates only to the account that <strong>owns</strong> the car.
        This car is shared with your account, so they're not available here.
      </span>
    </div>

    <template v-else-if="data">
      <InfoRow
        label="Installed version"
        :value="current?.version || 'Unknown'"
        :color="current?.version ? 'var(--text)' : 'var(--muted)'"
      />
      <InfoRow label="Last installed" :value="formatDay(current?.installed_at)" color="var(--sub)" />
      <InfoRow v-if="current?.notes.length" label="Release notes">
        <a href="#" class="sw-link" @click.prevent="openNotes(current, false)">View</a>
      </InfoRow>

      <div v-if="update" class="sw-update">
        <div class="sw-update-top">
          <Download :size="18" class="sw-update-icon" />
          <div>
            <div class="sw-update-ver">{{ update.version || 'New version' }}</div>
            <div class="sw-update-meta">
              Update waiting to be installed · {{ formatBytes(update.size_bytes) }} ·
              {{ update.packages.length }} package{{ update.packages.length === 1 ? '' : 's' }}
            </div>
          </div>
        </div>
        <div class="sw-actions">
          <button class="sw-btn" @click="openNotes(update, true)">Release notes</button>
          <button
            v-if="update.packages.some(p => p.downloadable)"
            class="sw-btn ghost"
            @click="openNotes(update, true, 'packages')"
          ><Download :size="13" /> Packages</button>
        </div>
      </div>

      <div class="sw-checked">Checked {{ checkedAgo }}</div>
    </template>

    <SoftwareNotesModal
      :visible="!!notesVersion"
      :version="notesVersion"
      :pending="notesPending"
      :vin="vin"
      :initial-tab="notesTab"
      @close="notesVersion = null"
    />
  </SectionCard>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Cpu, RefreshCw, Lock, Download } from 'lucide-vue-next'
import SectionCard from './SectionCard.vue'
import InfoRow from './InfoRow.vue'
import SoftwareNotesModal from './SoftwareNotesModal.vue'
import { softwareState, loadSoftware, formatBytes, formatDay } from '../composables/useSoftware'

const props = defineProps({
  vin: { type: String, required: true },
})

const entry = computed(() => softwareState(props.vin))
const data = computed(() => entry.value.data)
const current = computed(() => data.value?.current || null)
const update = computed(() => data.value?.update || null)

const badge = computed(() => {
  if (!data.value) return null
  if (data.value.status === 'owner_only') return { label: 'Owner only', cls: 'muted' }
  return update.value ? { label: 'Update', cls: 'warn' } : { label: 'Up to date', cls: 'ok' }
})

const checkedAgo = computed(() => {
  const ts = data.value?.checked_at
  if (!ts) return '—'
  const min = Math.round((Date.now() - new Date(ts).getTime()) / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  return `${Math.round(min / 60)} h ago`
})

const notesVersion = ref(null)
const notesPending = ref(false)
const notesTab = ref('notes')
function openNotes(version, pending, tab = 'notes') {
  notesPending.value = pending
  notesTab.value = tab
  notesVersion.value = version
}

function load(refresh = false) {
  loadSoftware(props.vin, { refresh })
}

// Load on mount and again after the cached answer was dropped (language change)
watch([() => props.vin, () => !data.value], ([, empty]) => { if (empty) load() }, { immediate: true })
</script>

<style scoped>
.sw-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 20px; }
.sw-badge.ok { color: #00e676; background: rgba(0,230,118,.12); }
.sw-badge.warn { color: #ffab40; background: rgba(255,171,64,.14); }
.sw-badge.muted { color: var(--sub); background: var(--btn-bg); }
.sw-refresh { border: none; background: none; color: var(--muted3); cursor: pointer; padding: 2px; display: flex; }
.sw-refresh:hover:not(:disabled) { color: var(--accent); }
.sw-spin { animation: sw-spin 1s linear infinite; }
@keyframes sw-spin { to { transform: rotate(360deg); } }
.sw-empty { display: flex; gap: 8px; font-size: 12px; color: var(--muted); line-height: 1.5; padding: 4px 0; }
.sw-empty strong { color: var(--sub); }
.sw-empty-icon { flex-shrink: 0; margin-top: 1px; }
.sw-link { color: var(--accent); text-decoration: none; }
.sw-update {
  margin-top: 12px; padding: 12px 14px; border-radius: 10px;
  border: 1px solid rgba(255,171,64,.35); background: rgba(255,171,64,.08);
}
.sw-update-top { display: flex; align-items: center; gap: 10px; }
.sw-update-icon { color: #ffab40; flex-shrink: 0; }
.sw-update-ver { font-family: var(--mono); font-size: 15px; font-weight: 700; color: #ffab40; }
.sw-update-meta { font-size: 12px; color: var(--sub); margin-top: 3px; }
.sw-btn {
  margin-top: 12px; display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: 1px solid rgba(255,171,64,.4); background: rgba(255,171,64,.14); color: #ffab40;
}
.sw-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.sw-actions .sw-btn { margin-top: 0; }
.sw-btn.ghost { background: none; }
.sw-checked { font-size: 11px; color: var(--muted3); margin-top: 10px; }
</style>
