<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible && version" class="sn-overlay" @click.self="$emit('close')">
        <div class="sn-modal">
          <div class="sn-header">
            <Cpu :size="16" class="sn-header-icon" />
            <span class="sn-title">{{ pending ? 'Software update' : 'Installed software' }}</span>
            <button class="sn-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="sn-body">
            <div class="sn-ver-row">
              <span class="sn-ver" :class="{ pending }">{{ version.version || 'Unknown version' }}</span>
              <span class="sn-badge" :class="pending ? 'warn' : 'ok'">{{ pending ? 'Pending' : 'Installed' }}</span>
            </div>
            <div class="sn-meta">
              <template v-if="pending">
                {{ formatBytes(version.size_bytes) }} · {{ version.packages.length }} package{{ version.packages.length === 1 ? '' : 's' }}
              </template>
              <template v-else-if="version.installed_at">Installed on {{ formatDay(version.installed_at) }}</template>
            </div>

            <div v-if="version.packages.length" class="sn-tabs">
              <button :class="{ on: tab === 'notes' }" @click="tab = 'notes'">What's new</button>
              <button :class="{ on: tab === 'packages' }" @click="tab = 'packages'">Packages ({{ version.packages.length }})</button>
            </div>

            <div v-if="tab === 'notes'">
              <div v-if="!version.notes.length" class="sn-empty">No release notes for this version.</div>
              <div v-for="(note, i) in version.notes" :key="i" class="sn-note" dir="auto">
                <h4 v-if="note.title">{{ note.title }}</h4>
                <p>{{ note.content }}</p>
              </div>
              <div v-if="version.notes_language" class="sn-lang">
                Shown in {{ version.notes_language }}<template v-if="version.languages.length > 1"> · {{ version.languages.length }} languages available</template>
                · change it in Settings → Preferences
              </div>
            </div>

            <div v-else>
              <div v-if="canDownload" class="sn-dl">
                <div class="sn-dl-note">
                  <Lock :size="13" class="sn-dl-note-icon" />
                  <span>Leapmotor serves these files <strong>encrypted</strong> (<code>.encrypt</code>): they're an archive copy and can't be installed from here.</span>
                </div>
                <button class="sn-dl-all" @click="confirmAll = true">
                  <Download :size="14" /> Download all ({{ formatBytes(downloadSize) }})
                </button>
              </div>
              <div v-for="p in version.packages" :key="`${p.seq}-${p.product}-${p.ecu_id}`" class="sn-pkg">
                <span class="sn-pkg-name">{{ p.product || '—' }}</span>
                <span class="sn-pkg-size">{{ formatBytes(p.size_bytes) }}</span>
                <a
                  v-if="canDownload && p.downloadable"
                  class="sn-pkg-dl"
                  :href="packageUrl(p)"
                  :download="p.file_name"
                  :title="`Download ${p.file_name}`"
                ><Download :size="15" /></a>
                <span v-else-if="canDownload" />
                <span class="sn-pkg-detail">
                  {{ [p.component ? `${p.component}${p.ecu_id ? ` (${p.ecu_id})` : ''}` : p.ecu_id,
                      p.soft_version && `v${p.soft_version}`,
                      p.build_date && `built ${formatDay(p.build_date)}`].filter(Boolean).join(' · ') }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <ConfirmDialog
    :visible="confirmAll"
    title="Download the whole update?"
    :message="`This downloads ${formatBytes(downloadSize)} from Leapmotor through LeapConnect as one ZIP, with a manifest.json describing each package. The files are encrypted and can't be installed from here.`"
    confirm-label="Download"
    variant="info"
    icon="info"
    @confirm="downloadAll"
    @cancel="confirmAll = false"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Cpu, Download, Lock } from 'lucide-vue-next'
import ConfirmDialog from './ConfirmDialog.vue'
import { formatBytes, formatDay, packageDownloadUrl, updateDownloadUrl } from '../composables/useSoftware'

const props = defineProps({
  visible: Boolean,
  version: { type: Object, default: null },
  pending: Boolean,
  vin: { type: String, default: '' },
  initialTab: { type: String, default: 'notes' },
})

defineEmits(['close'])

const tab = ref('notes')
watch(() => props.visible, v => { if (v) tab.value = props.initialTab })

// Only the pending update can be downloaded: the cloud links its packages.
const downloadable = computed(() => (props.version?.packages || []).filter(p => p.downloadable))
const canDownload = computed(() => props.pending && !!props.vin && downloadable.value.length > 0)
const downloadSize = computed(() => downloadable.value.reduce((sum, p) => sum + (p.size_bytes || 0), 0))

function packageUrl(p) {
  return packageDownloadUrl(props.vin, p.seq)
}

const confirmAll = ref(false)
function downloadAll() {
  confirmAll.value = false
  const a = document.createElement('a')
  a.href = updateDownloadUrl(props.vin)
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}
</script>

<style scoped>
.sn-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.sn-modal {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  width: 92vw; max-width: 520px; max-height: 85vh;
  display: flex; flex-direction: column;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
}
.sn-header {
  display: flex; align-items: center; gap: 8px;
  padding: 16px 20px; border-bottom: 1px solid var(--divider);
}
.sn-header-icon { color: var(--muted3); }
.sn-title { flex: 1; font-size: 15px; font-weight: 600; color: var(--text); }
.sn-close { background: none; border: none; color: var(--muted); font-size: 22px; cursor: pointer; padding: 0 4px; line-height: 1; }
.sn-body { padding: 18px 20px; overflow: auto; }
.sn-ver-row { display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }
.sn-ver { font-family: var(--mono); font-size: 18px; font-weight: 700; color: var(--text); }
.sn-ver.pending { color: #ffab40; }
.sn-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 20px; }
.sn-badge.warn { color: #ffab40; background: rgba(255,171,64,.14); }
.sn-badge.ok { color: #00e676; background: rgba(0,230,118,.12); }
.sn-meta { font-size: 12px; color: var(--sub); margin-bottom: 14px; }
.sn-tabs { display: flex; gap: 6px; margin-bottom: 12px; }
.sn-tabs button {
  border: 1px solid var(--border); background: none; color: var(--sub);
  border-radius: 8px; padding: 5px 10px; font-size: 12px; cursor: pointer;
}
.sn-tabs button.on { color: var(--accent); border-color: rgba(var(--accent-rgb), .4); background: rgba(var(--accent-rgb), .1); }
.sn-empty { font-size: 12px; color: var(--muted); padding: 8px 0; }
.sn-note { padding: 10px 0; border-bottom: 1px solid var(--divider); }
.sn-note:last-of-type { border-bottom: none; }
.sn-note h4 { margin: 0 0 4px; font-size: 13px; color: var(--text); }
.sn-note p { margin: 0; font-size: 12.5px; color: var(--sub); line-height: 1.55; white-space: pre-line; }
.sn-lang { font-size: 11px; color: var(--muted3); margin-top: 12px; }
.sn-dl { margin-bottom: 6px; }
.sn-dl-note { display: flex; gap: 7px; font-size: 11.5px; color: var(--muted); line-height: 1.5; }
.sn-dl-note strong { color: var(--sub); }
.sn-dl-note code { font-family: var(--mono); font-size: 11px; }
.sn-dl-note-icon { flex-shrink: 0; margin-top: 2px; }
.sn-dl-all {
  margin: 10px 0 4px; display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: 1px solid rgba(var(--accent-rgb), .4); background: rgba(var(--accent-rgb), .1); color: var(--accent);
}
.sn-pkg {
  display: grid; grid-template-columns: 1fr auto; gap: 2px 10px;
  padding: 9px 0; border-bottom: 1px solid var(--divider); font-size: 12px;
}
.sn-pkg:last-child { border-bottom: none; }
.sn-pkg-name { font-family: var(--mono); color: var(--text); overflow-wrap: anywhere; }
.sn-pkg-size { text-align: right; color: var(--sub); }
.sn-pkg-detail { grid-column: 1 / -1; color: var(--muted3); font-size: 11px; }
.sn-dl ~ .sn-pkg { grid-template-columns: 1fr auto 22px; }
.sn-pkg-dl { color: var(--muted3); display: flex; justify-content: flex-end; }
.sn-pkg-dl:hover { color: var(--accent); }
</style>
