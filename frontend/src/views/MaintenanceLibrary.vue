<template>
  <div class="mnt-library">
    <div v-if="loading" class="loading-row"><div class="spinner" /></div>

    <template v-else>
      <!-- Your plan — all tracked interventions -->
      <div class="card">
        <div class="card-header">
          <span><ClipboardList :size="16" class="card-icon" /> Your plan</span>
          <span class="muted-count">{{ plan.length }} interventions</span>
        </div>
        <div class="table-wrap">
          <table class="plan-table">
            <thead>
              <tr>
                <th>Service</th><th>Category</th><th>Interval</th><th>Priority</th>
                <th>Source</th><th>Last Done</th><th>Due</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in plan" :key="item.service_type">
                <td>{{ item.label }}</td>
                <td><span class="cat-badge">{{ item.category }}</span></td>
                <td>{{ formatInterval(item) }}</td>
                <td><span class="prio-badge" :class="'prio-' + item.priority">{{ item.priority }}</span></td>
                <td><span class="src-badge" :class="'src-' + item.source">{{ item.source }}</span></td>
                <td>{{ formatLastDone(item) }}</td>
                <td>{{ formatDue(item) }}</td>
                <td class="row-actions">
                  <div class="action-buttons">
                    <button class="icon-btn" title="Log service" @click="openLog(item)"><Check :size="14" /></button>
                    <button class="icon-btn" title="Edit" @click="editItem = item"><Pencil :size="14" /></button>
                    <button class="icon-btn icon-delete" title="Remove from plan" @click="askRemove(item)"><Trash2 :size="14" /></button>
                  </div>
                </td>
              </tr>
              <tr v-if="!plan.length"><td colspan="8" class="empty-row">No interventions in your plan yet</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Catalog extras (manual items not in plan) -->
      <div v-if="catalogAvailable.length" class="card">
        <div class="card-header">
          <span><BookOpen :size="16" class="card-icon" /> From the manual</span>
          <button class="text-btn" @click="importItems(catalogAvailable, 'catalog', null)">Add all</button>
        </div>
        <div class="chip-list">
          <button v-for="it in catalogAvailable" :key="it.service_type" class="add-chip" @click="importItems([it], 'catalog', null)">
            <Plus :size="13" /> {{ it.label }}
          </button>
        </div>
      </div>

      <!-- Local section -->
      <div class="card">
        <div class="card-header">
          <span><Wrench :size="16" class="card-icon" /> Local — your custom interventions</span>
          <div class="header-actions">
            <button class="text-btn" @click="showAddCustom = true"><Plus :size="14" /> Add</button>
            <button class="text-btn" @click="triggerFileImport"><Upload :size="14" /> Import file</button>
            <button class="text-btn" @click="showUrlImport = true"><Link :size="14" /> Import URL</button>
            <button class="text-btn" :disabled="!localItems.length" @click="exportLocal"><Download :size="14" /> Export</button>
          </div>
        </div>
        <div v-if="!localItems.length" class="empty-row">
          No custom interventions yet. Add your own to schedule maintenance the manual doesn't cover.
        </div>
        <div v-for="it in localItems" :key="it.service_type" class="lib-row">
          <div class="lib-info">
            <span class="lib-label">{{ it.label }}</span>
            <span class="lib-meta">{{ formatInterval(it) }} · {{ it.category }}</span>
          </div>
          <span class="prio-badge" :class="'prio-' + it.priority">{{ it.priority }}</span>
        </div>
        <input ref="fileInput" type="file" accept="application/json,.json" class="hidden-file" @change="onFileChosen" />
      </div>

      <!-- Remote section -->
      <div class="card">
        <div class="card-header">
          <span><Boxes :size="16" class="card-icon" /> Remote repositories</span>
          <button class="text-btn" @click="showAddRepo = true"><Plus :size="14" /> Add repo</button>
        </div>

        <div v-if="!repos.length && !standalonePacks.length" class="empty-row">
          No community repositories yet. Add a GitHub repo to browse and import extra maintenance packs.
          The factory schedule is always provided out of the box.
        </div>

        <!-- Per-repo -->
        <div v-for="repo in repos" :key="repo.id" class="repo-block">
          <div class="repo-head">
            <div class="repo-id">
              <span class="repo-name">{{ repo.name || repo.url }}</span>
              <a class="repo-url" :href="repo.url" target="_blank" rel="noopener">{{ repo.url }}</a>
            </div>
            <div class="repo-actions">
              <span v-if="repo.is_official" class="official-badge">Official</span>
              <span class="repo-status" :class="'st-' + repo.status">{{ repo.status }}</span>
              <button class="icon-btn" title="Refresh" :disabled="busyRepo === repo.id" @click="refreshRepo(repo)">
                <RefreshCw :size="14" :class="{ spinning: busyRepo === repo.id }" />
              </button>
              <button v-if="!repo.is_official" class="icon-btn icon-delete" title="Remove repository" @click="askRemoveRepo(repo)"><Trash2 :size="14" /></button>
            </div>
          </div>
          <div v-for="pack in packsForRepo(repo.id)" :key="pack.slug" class="pack-block">
            <PackCard :pack="pack" @import-pack="importPack" @import-item="importSingle" />
          </div>
          <div v-if="!packsForRepo(repo.id).length" class="empty-sub">No packs found in this repository.</div>
        </div>

        <!-- Standalone imported packs (file/URL) -->
        <div v-if="standalonePacks.length" class="repo-block">
          <div class="repo-head"><div class="repo-id"><span class="repo-name">Imported packs (file / URL)</span></div></div>
          <div v-for="pack in standalonePacks" :key="pack.slug" class="pack-block">
            <PackCard :pack="pack" @import-pack="importPack" @import-item="importSingle" />
          </div>
        </div>
      </div>
    </template>

    <!-- URL import inline modal -->
    <Teleport to="body">
      <div v-if="showUrlImport" class="modal-backdrop" @click.self="showUrlImport = false">
        <div class="mini-dialog">
          <h3>Import pack from URL</h3>
          <input v-model="importUrl" type="text" placeholder="https://raw.githubusercontent.com/.../pack.json" @keyup.enter="importFromUrl" />
          <div class="modal-actions">
            <button class="btn-cancel" @click="showUrlImport = false">Cancel</button>
            <button class="btn-save" :disabled="busy || !importUrl.trim()" @click="importFromUrl">{{ busy ? 'Fetching…' : 'Import' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Modals & dialogs -->
    <AddCustomItemModal :visible="showAddCustom" :vin="vin" @close="showAddCustom = false" @saved="onCustomSaved" />
    <AddRepoModal :visible="showAddRepo" @close="showAddRepo = false" @saved="onRepoAdded" />
    <ImportConflictDialog :visible="conflict.visible" :count="conflict.count" @resolve="resolveConflict" @cancel="conflict.visible = false" />
    <LogServiceModal :visible="logModal.visible" :vin="vin" :service-type="logModal.serviceType" :label="logModal.label"
      @close="logModal.visible = false" @saved="onChanged(); logModal.visible = false" />
    <EditPlanItemModal :vin="vin" :item="editItem" @close="editItem = null" @saved="onChanged(); editItem = null" />
    <ConfirmDialog :visible="removeTarget != null" title="Remove from plan?"
      :message="`Remove '${removeTarget?.label}' from your maintenance plan? Logged service records are kept.`"
      confirm-label="Remove" cancel-label="Cancel" variant="danger" icon="trash" :loading="removing"
      @confirm="confirmRemove" @cancel="removeTarget = null" />
    <ConfirmDialog :visible="removeRepoTarget != null" title="Remove repository?"
      :message="`Remove '${removeRepoTarget?.name || removeRepoTarget?.url}' and its cached packs? Already-imported plan items are kept.`"
      confirm-label="Remove" cancel-label="Cancel" variant="danger" icon="trash" :loading="removingRepo"
      @confirm="confirmRemoveRepo" @cancel="removeRepoTarget = null" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import {
  BookOpen, Boxes, Check, ClipboardList, Download, Link, Pencil, Plus,
  RefreshCw, Trash2, Upload, Wrench,
} from 'lucide-vue-next'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LogServiceModal from '../components/LogServiceModal.vue'
import EditPlanItemModal from '../components/EditPlanItemModal.vue'
import AddCustomItemModal from '../components/AddCustomItemModal.vue'
import AddRepoModal from '../components/AddRepoModal.vue'
import ImportConflictDialog from '../components/ImportConflictDialog.vue'
import PackCard from '../components/PackCard.vue'
import { formatInterval, formatLastDone, formatDue } from '../utils/maintenance'

const props = defineProps({ vin: { type: String, required: true } })
const emit = defineEmits(['changed'])
const { toast } = useToast()

const loading = ref(true)
const plan = ref([])
const library = ref({ catalog: [], local: [], repos: [], packs: [] })

const repos = computed(() => library.value.repos || [])
const localItems = computed(() => library.value.local || [])
const catalogAvailable = computed(() => (library.value.catalog || []).filter((i) => !i.in_plan))
const standalonePacks = computed(() => (library.value.packs || []).filter((p) => p.repo_id == null))
function packsForRepo(repoId) {
  return (library.value.packs || []).filter((p) => p.repo_id === repoId)
}

async function load() {
  loading.value = true
  try {
    const [planData, libData] = await Promise.all([
      api('GET', `/api/vehicles/${props.vin}/maintenance/plan`),
      api('GET', `/api/vehicles/${props.vin}/maintenance/library`),
    ])
    plan.value = planData
    library.value = libData
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function onChanged() {
  load()
  emit('changed')
}

// ---- Imports (with conflict handling) ----
const conflict = ref({ visible: false, count: 0, pending: null })

async function importItems(items, source, sourceRef) {
  const conflicting = items.filter((i) => i.in_plan)
  if (conflicting.length) {
    conflict.value = { visible: true, count: conflicting.length, pending: { items, source, sourceRef } }
    return
  }
  await doImport(items, source, sourceRef, 'skip')
}

async function resolveConflict(strategy) {
  const p = conflict.value.pending
  conflict.value.visible = false
  if (p) await doImport(p.items, p.source, p.sourceRef, strategy)
}

async function doImport(items, source, sourceRef, onConflict) {
  try {
    const payload = {
      items: items.map((i) => ({
        service_type: i.service_type, label: i.label, category: i.category,
        interval_km: i.interval_km, interval_months: i.interval_months,
        trigger_mode: i.trigger_mode, priority: i.priority, notes: i.notes,
      })),
      source, source_ref: sourceRef, on_conflict: onConflict,
    }
    const res = await api('POST', `/api/vehicles/${props.vin}/maintenance/plan/import`, payload)
    const n = res.imported.length + res.updated.length + res.variants.length
    const bits = []
    if (res.imported.length) bits.push(`${res.imported.length} added`)
    if (res.updated.length) bits.push(`${res.updated.length} updated`)
    if (res.variants.length) bits.push(`${res.variants.length} as variants`)
    if (res.skipped.length) bits.push(`${res.skipped.length} skipped`)
    toast(n ? `Imported: ${bits.join(', ')}` : `Nothing imported (${bits.join(', ')})`, n ? 'success' : 'info')
    onChanged()
  } catch (e) {
    toast(e.message, 'error')
  }
}

function importPack(pack) { importItems(pack.items, 'repo', pack.slug) }
function importSingle(item, pack) { importItems([item], 'repo', pack.slug) }

// ---- Local: add / export / import file / import URL ----
const showAddCustom = ref(false)
function onCustomSaved() { showAddCustom.value = false; onChanged() }

function exportLocal() {
  const a = document.createElement('a')
  a.href = `./api/vehicles/${props.vin}/maintenance/export`
  a.download = 'leapconnect-maintenance-local.json'
  document.body.appendChild(a); a.click(); a.remove()
}

const fileInput = ref(null)
function triggerFileImport() { fileInput.value?.click() }
async function onFileChosen(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`./api/maintenance/upload`, { method: 'POST', body: fd, credentials: 'include' })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
    toast(`Imported pack "${data.name}" with ${data.items.length} items`, 'success')
    onChanged()
  } catch (err) {
    toast(err.message, 'error')
  } finally {
    e.target.value = ''
  }
}

const showUrlImport = ref(false)
const importUrl = ref('')
const busy = ref(false)
async function importFromUrl() {
  if (!importUrl.value.trim()) return
  busy.value = true
  try {
    const data = await api('POST', '/api/maintenance/packs/import', { url: importUrl.value.trim() })
    toast(`Imported pack "${data.name}" with ${data.items.length} items`, 'success')
    showUrlImport.value = false
    importUrl.value = ''
    onChanged()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    busy.value = false
  }
}

// ---- Remote: repos ----
const showAddRepo = ref(false)
function onRepoAdded() { showAddRepo.value = false; onChanged() }

const busyRepo = ref(null)
async function refreshRepo(repo) {
  busyRepo.value = repo.id
  try {
    await api('POST', `/api/maintenance/repos/${repo.id}/refresh`)
    toast('Repository refreshed', 'success')
    onChanged()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    busyRepo.value = null
  }
}

const removeRepoTarget = ref(null)
const removingRepo = ref(false)
function askRemoveRepo(repo) { removeRepoTarget.value = repo }
async function confirmRemoveRepo() {
  removingRepo.value = true
  try {
    await api('DELETE', `/api/maintenance/repos/${removeRepoTarget.value.id}`)
    removeRepoTarget.value = null
    onChanged()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    removingRepo.value = false
  }
}

// ---- Plan table: log / edit / remove ----
const logModal = ref({ visible: false, serviceType: '', label: '' })
function openLog(item) { logModal.value = { visible: true, serviceType: item.service_type, label: item.label } }
const editItem = ref(null)

const removeTarget = ref(null)
const removing = ref(false)
function askRemove(item) { removeTarget.value = item }
async function confirmRemove() {
  removing.value = true
  try {
    await api('DELETE', `/api/vehicles/${props.vin}/maintenance/plan/${encodeURIComponent(removeTarget.value.service_type)}`)
    removeTarget.value = null
    onChanged()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    removing.value = false
  }
}

onMounted(load)
watch(() => props.vin, load)
</script>

<style scoped>
.mnt-library { display: flex; flex-direction: column; gap: 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 20px; }
.card-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  font-size: 14px; font-weight: 600; color: var(--heading); margin-bottom: 16px; flex-wrap: wrap;
}
.card-header > span { display: flex; align-items: center; gap: 8px; }
.card-icon { color: var(--muted); }
.muted-count { font-size: 12px; color: var(--muted); font-weight: 500; }
.header-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.text-btn {
  display: flex; align-items: center; gap: 4px; padding: 5px 10px; border-radius: 8px;
  border: 1px solid var(--btn-border); background: var(--btn-bg); color: var(--muted);
  cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.15s;
}
.text-btn:hover { border-color: var(--cyan); color: var(--cyan); }
.text-btn:disabled { opacity: 0.45; cursor: default; }

.table-wrap { overflow-x: auto; }
.plan-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.plan-table th { text-align: left; color: var(--muted); font-weight: 600; padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; }
.plan-table td { padding: 10px 10px; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: middle; }
.row-actions { white-space: nowrap; }
.action-buttons { display: flex; gap: 6px; justify-content: flex-end; }

.cat-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; background: var(--btn-bg); color: var(--muted); }
.prio-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; font-weight: 700; }
.prio-routine { background: rgba(0,230,118,0.09); color: var(--green); }
.prio-important { background: rgba(255,171,64,0.09); color: var(--amber); }
.prio-urgent { background: rgba(255,82,82,0.09); color: var(--red); }
.src-badge { font-size: 10px; padding: 2px 7px; border-radius: 8px; text-transform: uppercase; letter-spacing: 0.03em; background: var(--btn-bg); color: var(--muted); }
.src-local { color: var(--cyan); background: rgba(0,212,255,0.08); }
.src-repo { color: var(--amber); background: rgba(255,171,64,0.08); }

.chip-list { display: flex; flex-wrap: wrap; gap: 8px; }
.add-chip {
  display: flex; align-items: center; gap: 5px; padding: 6px 12px; border-radius: 16px;
  border: 1px dashed var(--btn-border); background: transparent; color: var(--muted);
  cursor: pointer; font-size: 12px; transition: all 0.15s;
}
.add-chip:hover { border-color: var(--cyan); color: var(--cyan); border-style: solid; }

.lib-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); gap: 12px; }
.lib-row:last-child { border-bottom: none; }
.lib-info { display: flex; flex-direction: column; }
.lib-label { font-size: 14px; font-weight: 600; color: var(--text); }
.lib-meta { font-size: 12px; color: var(--muted); }

.repo-block { border-top: 1px solid var(--border); padding-top: 14px; margin-top: 14px; }
.repo-block:first-of-type { border-top: none; padding-top: 0; margin-top: 0; }
.repo-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.repo-id { display: flex; flex-direction: column; min-width: 0; }
.repo-name { font-size: 14px; font-weight: 600; color: var(--text); }
.repo-url { font-size: 11px; color: var(--muted); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.repo-url:hover { color: var(--cyan); }
.repo-actions { display: flex; align-items: center; gap: 6px; }
.official-badge { font-size: 10px; padding: 2px 7px; border-radius: 8px; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 700; color: var(--cyan); background: rgba(0,212,255,0.08); }
.repo-status { font-size: 10px; padding: 2px 7px; border-radius: 8px; text-transform: uppercase; background: var(--btn-bg); color: var(--muted); }
.st-ok { color: var(--green); background: rgba(0,230,118,0.08); }
.st-error { color: var(--red); background: rgba(255,82,82,0.08); }
.pack-block { margin-top: 10px; }
.empty-sub { font-size: 12px; color: var(--muted); padding: 6px 0; }

.icon-btn {
  width: 30px; height: 30px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.icon-btn:hover { border-color: var(--cyan); color: var(--cyan); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.icon-delete:hover { border-color: var(--red); color: var(--red); }
.spinning { animation: spin 0.8s linear infinite; }

.repo-empty { display: flex; flex-direction: column; gap: 12px; }
.empty-note { margin: 0; color: var(--muted); font-size: 13px; }
.suggested {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 14px; border: 1px dashed var(--btn-border); border-radius: 10px;
}
.sug-info { display: flex; flex-direction: column; min-width: 0; }
.sug-name { font-size: 13px; font-weight: 600; color: var(--text); }
.sug-url { font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.hidden-file { display: none; }
.empty-row { padding: 20px; text-align: center; color: var(--muted); font-size: 13px; }
.loading-row { display: flex; justify-content: center; padding: 60px 0; }
.spinner { width: 32px; height: 32px; border-radius: 50%; border: 3px solid var(--border); border-top-color: var(--cyan); animation: spin 0.8s linear infinite; }

/* Mini dialog (URL import) */
.modal-backdrop { position: fixed; inset: 0; background: #00000080; display: flex; align-items: center; justify-content: center; z-index: 2000; }
.mini-dialog { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; width: 90%; max-width: 460px; }
.mini-dialog h3 { margin: 0 0 14px; color: var(--text); font-size: 16px; }
.mini-dialog input { width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--input); color: var(--text); font-size: 14px; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }
.btn-cancel { padding: 8px 16px; border-radius: 8px; background: var(--btn-bg); border: 1px solid var(--btn-border); color: var(--muted); cursor: pointer; font-size: 13px; }
.btn-save { padding: 8px 16px; border-radius: 8px; background: var(--cyan); border: none; color: #000; cursor: pointer; font-size: 13px; font-weight: 600; }
.btn-save:disabled { opacity: 0.5; cursor: default; }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
