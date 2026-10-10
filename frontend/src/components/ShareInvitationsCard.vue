<template>
  <SectionCard title="Shared Cars" :icon="Users">
    <p class="si-desc">
      When an owner shares a car with your Leapmotor account from the official app, the car stays hidden until you accept the invitation.
    </p>

    <div v-if="!store.connected" class="si-empty">Connect to the Leapmotor cloud to see invitations.</div>
    <div v-else-if="loading" class="si-empty">
      <RefreshCw :size="13" class="si-spin" /> Checking invitations…
    </div>
    <template v-else>
      <div v-if="invitations.length === 0" class="si-empty">No pending invitations.</div>
      <div v-for="inv in invitations" :key="inv.vin" class="si-item">
        <div class="si-info">
          <div class="si-car">{{ inv.car_alias || `Leapmotor ${inv.car_type || ''}`.trim() }}</div>
          <div class="si-meta">
            From {{ inv.owner_nickname || inv.owner_email || 'the owner' }}
            <template v-if="inv.share_time"> · {{ formatDate(inv.share_time) }}</template>
            <template v-if="inv.expire_time"> · until {{ formatDate(inv.expire_time) }}</template>
          </div>
          <div class="si-vin">{{ inv.vin }}</div>
        </div>
        <div class="si-actions">
          <button class="si-btn si-reject" :disabled="!!busyVin" @click="pendingReject = inv">Reject</button>
          <button class="si-btn si-accept" :disabled="!!busyVin" @click="answer(inv, true)">
            <RefreshCw v-if="busyVin === inv.vin" :size="12" class="si-spin" />
            Accept
          </button>
        </div>
      </div>
      <div v-if="error" class="field-error">{{ error }}</div>
      <div v-if="success" class="field-success">{{ success }}</div>
      <button class="si-refresh" :disabled="loading || !!busyVin" @click="load">
        <RefreshCw :size="12" /> Check again
      </button>
    </template>

    <ConfirmDialog
      :visible="!!pendingReject"
      title="Reject invitation"
      :message="`The car won't be shared with your account. The owner can share it again from the official app.`"
      confirm-label="Reject"
      cancel-label="Cancel"
      variant="danger"
      @confirm="confirmReject"
      @cancel="pendingReject = null"
    />
  </SectionCard>
</template>

<script setup>
import { ref, watch } from 'vue'
import SectionCard from './SectionCard.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import { api } from '../composables/useApi'
import { useAppStore } from '../stores/appStore'
import { Users, RefreshCw } from 'lucide-vue-next'

const store = useAppStore()

const invitations = ref([])
const loading = ref(false)
const busyVin = ref(null)
const pendingReject = ref(null)
const error = ref('')
const success = ref('')

function formatDate(ms) {
  return new Date(ms).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

async function load() {
  if (!store.connected) return
  loading.value = true
  error.value = ''
  try {
    const res = await api('GET', '/api/share-invitations')
    invitations.value = res.invitations || []
  } catch (e) {
    error.value = e.message || 'Failed to load invitations'
  } finally {
    loading.value = false
  }
}

async function answer(inv, accept) {
  busyVin.value = inv.vin
  error.value = ''
  success.value = ''
  try {
    const res = await api('POST', `/api/share-invitations/${inv.vin}/${accept ? 'accept' : 'reject'}`)
    store.vehicles = res.vehicles || store.vehicles
    invitations.value = invitations.value.filter(i => i.vin !== inv.vin)
    success.value = accept
      ? 'Invitation accepted: the car is now in your vehicle list.'
      : 'Invitation rejected.'
  } catch (e) {
    error.value = e.message || 'Failed to answer the invitation'
  } finally {
    busyVin.value = null
  }
}

function confirmReject() {
  const inv = pendingReject.value
  pendingReject.value = null
  if (inv) answer(inv, false)
}

watch(() => store.connected, connected => { if (connected) load() }, { immediate: true })
</script>

<style scoped>
.si-desc { font-size: 12px; color: var(--muted); margin: 0 0 12px; line-height: 1.4; }
.si-empty { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); padding: 8px 0; }
.si-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--divider); flex-wrap: wrap; }
.si-info { flex: 1; min-width: 0; }
.si-car { font-size: 13px; font-weight: 600; color: var(--text); }
.si-meta { font-size: 12px; color: var(--sub); margin-top: 2px; }
.si-vin { font-size: 11px; color: var(--muted); font-family: monospace; margin-top: 2px; overflow-wrap: anywhere; }
.si-actions { display: flex; gap: 8px; }
.si-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text); }
.si-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.si-accept { border-color: rgba(var(--accent-rgb), 0.333); background: rgba(var(--accent-rgb), 0.133); color: var(--accent); }
.si-reject:hover:not(:disabled) { border-color: #ff5252; color: #ff5252; }
.si-refresh { display: inline-flex; align-items: center; gap: 6px; margin-top: 12px; padding: 0; border: none; background: none; color: var(--muted); font-size: 12px; cursor: pointer; }
.si-refresh:hover:not(:disabled) { color: var(--accent); }
.si-spin { animation: si-spin 1s linear infinite; }
@keyframes si-spin { to { transform: rotate(360deg); } }
.field-error { margin-top: 0.6rem; font-size: 12px; color: #ff5252; }
.field-success { margin-top: 0.6rem; font-size: 12px; color: #00e676; }
</style>
