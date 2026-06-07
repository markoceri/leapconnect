<template>
  <div class="mnt-overview">
    <!-- Top: vehicle + status (left), KPIs + costs (right) -->
    <div class="overview-top">
      <!-- Hero: vehicle image + headline status -->
      <div class="hero-card">
        <div class="hero-image">
          <img :src="imageSrc" alt="Vehicle" @error="imageFailed = true" v-if="!imageFailed" />
          <div v-else class="image-fallback"><Car :size="64" /></div>
        </div>
        <div class="hero-info">
          <div class="hero-model">{{ overview.display_name }}</div>
          <div v-if="overview.current_km != null" class="hero-km">
            {{ overview.current_km.toLocaleString() }} km
          </div>
          <div class="hero-status" :class="heroStatusClass">
            <component :is="heroIcon" :size="18" />
            <span>{{ heroMessage }}</span>
          </div>
        </div>
      </div>

      <div class="overview-side">
        <!-- KPI summary -->
        <div class="summary-grid">
          <div class="summary-card" :class="{ warn: overview.overdue_count > 0 }">
            <div class="summary-value" :style="{ color: overview.overdue_count > 0 ? 'var(--red)' : 'var(--green)' }">
              {{ overview.overdue_count }}
            </div>
            <div class="summary-label">Overdue</div>
          </div>
          <div class="summary-card">
            <div class="summary-value" style="color: var(--amber)">{{ overview.upcoming_count }}</div>
            <div class="summary-label">Due soon</div>
          </div>
          <div class="summary-card">
            <div class="summary-value">{{ overview.total_items }}</div>
            <div class="summary-label">Tracked</div>
          </div>
        </div>

        <!-- Maintenance costs -->
        <div class="card">
          <div class="card-header"><span><Receipt :size="16" class="card-icon" /> Maintenance costs</span></div>
          <div v-if="!costs.services_count" class="empty-row">
            No costs logged yet — add a cost when you log a service.
          </div>
          <template v-else>
            <div class="cost-top">
              <div class="cost-total">
                <span class="cost-total-value">{{ formatEur(costs.total) }}</span>
                <span class="cost-total-label">total spent</span>
              </div>
              <div class="cost-substats">
                <div class="cost-sub"><span>{{ formatEur(costs.this_year) }}</span><small>this year</small></div>
                <div class="cost-sub"><span>{{ costs.services_count }}</span><small>services</small></div>
                <div class="cost-sub"><span>{{ formatEur(costs.avg) }}</span><small>avg / service</small></div>
              </div>
            </div>
            <div v-if="costs.by_category.length" class="cost-cats">
              <div v-for="c in costs.by_category" :key="c.category" class="cost-cat">
                <span class="cat-name">{{ c.category }}</span>
                <div class="cat-bar-wrap"><div class="cat-bar" :style="{ width: catWidth(c.total) }" /></div>
                <span class="cat-amount">{{ formatEur(c.total) }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Due soon shortlist -->
    <div class="card">
      <div class="card-header">
        <span><AlertTriangle :size="16" class="card-icon" /> Coming up</span>
        <button class="link-btn" @click="$emit('open-library')">
          All interventions <ChevronRight :size="14" />
        </button>
      </div>
      <div v-if="!overview.due_soon.length" class="empty-row">
        <CheckCircle2 :size="20" /> Nothing due soon — you're all set.
      </div>
      <div v-for="a in overview.due_soon" :key="a.service_type" class="due-row">
        <div class="due-status-dot" :class="'dot-' + a.status" />
        <div class="due-info">
          <span class="due-label">{{ a.label }}</span>
          <span class="due-remaining">{{ formatRemaining(a) }}</span>
        </div>
        <span class="prio-badge" :class="'prio-' + a.priority">{{ a.priority }}</span>
        <button class="log-btn" title="Log service" @click="openLog(a)">
          <Check :size="14" /> Log
        </button>
      </div>
    </div>

    <!-- Recent records -->
    <div class="card">
      <div class="card-header"><span><History :size="16" class="card-icon" /> Recent service records</span></div>
      <div v-if="!overview.recent_records.length" class="empty-row">No service records yet</div>
      <div v-for="r in overview.recent_records" :key="r.id" class="record-row">
        <div class="rec-info">
          <span class="rec-label">{{ r.label }}</span>
          <span class="rec-date">{{ formatDate(r.timestamp) }}</span>
        </div>
        <div class="rec-details">
          <span v-if="r.mileage_km != null">{{ r.mileage_km.toLocaleString() }} km</span>
          <span v-if="r.provider">{{ r.provider }}</span>
          <span v-if="r.cost != null" class="rec-cost">&euro;{{ r.cost.toFixed(2) }}</span>
        </div>
        <div class="rec-actions">
          <button class="icon-btn" title="Edit record" @click="openEditRecord(r)"><Pencil :size="14" /></button>
          <button class="icon-btn icon-delete" title="Delete record" @click="deleteTarget = r"><Trash2 :size="14" /></button>
        </div>
      </div>
    </div>

    <LogServiceModal
      :visible="logModal.visible"
      :vin="vin"
      :service-type="logModal.serviceType"
      :label="logModal.label"
      :record="logModal.record"
      @close="logModal.visible = false"
      @saved="onLogSaved"
    />
    <ConfirmDialog
      :visible="deleteTarget != null"
      title="Delete service record?"
      :message="`Delete the logged '${deleteTarget?.label}' service? This cannot be undone.`"
      confirm-label="Delete"
      cancel-label="Cancel"
      variant="danger"
      icon="trash"
      :loading="deleting"
      @confirm="confirmDeleteRecord"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { AlertTriangle, Car, Check, CheckCircle2, ChevronRight, History, Pencil, Receipt, Trash2 } from 'lucide-vue-next'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import LogServiceModal from '../components/LogServiceModal.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { formatDate, formatRemaining } from '../utils/maintenance'

const { toast } = useToast()

const props = defineProps({
  vin: { type: String, required: true },
  overview: { type: Object, required: true },
})
const emit = defineEmits(['open-library', 'reload'])

const imageFailed = ref(false)
const imageSrc = computed(() => `./api/vehicles/${props.vin}/picture/image`)

const costs = computed(() => props.overview.costs || { total: 0, this_year: 0, services_count: 0, avg: 0, by_category: [] })

const eurFmt = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'EUR' })
function formatEur(v) { return eurFmt.format(v || 0) }
function catWidth(v) {
  const max = Math.max(...costs.value.by_category.map((c) => c.total), 1)
  return `${Math.max((v / max) * 100, 4)}%`
}

const heroStatusClass = computed(() => {
  if (props.overview.overdue_count > 0) return 'status-overdue'
  if (props.overview.upcoming_count > 0) return 'status-soon'
  return 'status-ok'
})
const heroIcon = computed(() => {
  if (props.overview.overdue_count > 0) return AlertTriangle
  if (props.overview.upcoming_count > 0) return AlertTriangle
  return CheckCircle2
})
const heroMessage = computed(() => {
  const o = props.overview
  if (o.overdue_count > 0) return `${o.overdue_count} overdue, ${o.upcoming_count} due soon`
  if (o.upcoming_count > 0) return `${o.upcoming_count} due soon`
  return 'All up to date'
})

const logModal = ref({ visible: false, serviceType: '', label: '', record: null })
function openLog(a) {
  logModal.value = { visible: true, serviceType: a.service_type, label: a.label, record: null }
}
function openEditRecord(r) {
  logModal.value = { visible: true, serviceType: r.service_type, label: r.label, record: r }
}
function onLogSaved() {
  logModal.value.visible = false
  emit('reload')
}

// Delete a service record
const deleteTarget = ref(null)
const deleting = ref(false)
async function confirmDeleteRecord() {
  deleting.value = true
  try {
    await api('DELETE', `/api/vehicles/${props.vin}/maintenance/records/${deleteTarget.value.id}`)
    deleteTarget.value = null
    emit('reload')
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.mnt-overview { display: flex; flex-direction: column; gap: 16px; }

/* Top section: hero (left) + KPIs & costs (right) on desktop */
.overview-top {
  display: grid; grid-template-columns: 1fr; gap: 16px; align-items: start;
}
@media (min-width: 880px) {
  .overview-top { grid-template-columns: minmax(280px, 0.85fr) 1.15fr; }
}
.overview-side { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

/* Hero — vehicle image on top, status below (centered) */
.hero-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px; display: flex; flex-direction: column; gap: 14px;
  align-items: center; justify-content: center; text-align: center;
}
.hero-image { width: 100%; max-width: 380px; }
.hero-image img { width: 100%; height: auto; object-fit: contain; }
.image-fallback {
  width: 100%; aspect-ratio: 16/10; display: flex; align-items: center; justify-content: center;
  color: var(--muted); background: var(--btn-bg); border-radius: 12px;
}
.hero-info { display: flex; flex-direction: column; gap: 6px; align-items: center; }
.hero-model { font-size: 20px; font-weight: 700; color: var(--text); }
.hero-km { font-size: 14px; color: var(--muted); }
.hero-status { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; margin-top: 4px; }
.status-ok { color: var(--green); }
.status-soon { color: var(--amber); }
.status-overdue { color: var(--red); }

/* Summary */
.summary-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px;
}
.summary-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px; text-align: center;
}
.summary-card.warn { border-color: rgba(255,82,82,0.27); }
.summary-value { font-size: 28px; font-weight: 700; }
.summary-label { font-size: 12px; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.04em; }

/* Maintenance costs card */
.cost-top { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.cost-total { display: flex; flex-direction: column; }
.cost-total-value { font-size: 30px; font-weight: 700; color: var(--text); }
.cost-total-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.cost-substats { display: flex; gap: 20px; }
.cost-sub { display: flex; flex-direction: column; align-items: flex-end; }
.cost-sub span { font-size: 16px; font-weight: 600; color: var(--text); }
.cost-sub small { font-size: 11px; color: var(--muted); }
.cost-cats { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
.cost-cat { display: grid; grid-template-columns: 90px 1fr auto; align-items: center; gap: 10px; }
.cat-name { font-size: 12px; color: var(--muted); text-transform: capitalize; }
.cat-bar-wrap { height: 8px; background: var(--btn-bg); border-radius: 6px; overflow: hidden; }
.cat-bar { height: 100%; background: var(--cyan); border-radius: 6px; }
.cat-amount { font-size: 12px; font-weight: 600; color: var(--text); }

/* Cards */
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 20px;
}
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 14px; font-weight: 600; color: var(--heading); margin-bottom: 12px;
}
.card-header span { display: flex; align-items: center; gap: 8px; }
.card-icon { color: var(--muted); }
.link-btn {
  display: flex; align-items: center; gap: 2px; background: none; border: none;
  color: var(--cyan); cursor: pointer; font-size: 13px; font-weight: 600;
}

/* Due rows */
.due-row {
  display: flex; align-items: center; gap: 12px; padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.due-row:last-child { border-bottom: none; }
.due-status-dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.dot-overdue { background: var(--red); }
.dot-due_soon { background: var(--amber); }
.due-info { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.due-label { font-size: 14px; font-weight: 600; color: var(--text); }
.due-remaining { font-size: 12px; color: var(--muted); }
.prio-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; font-weight: 700; }
.prio-routine { background: rgba(0,230,118,0.09); color: var(--green); }
.prio-important { background: rgba(255,171,64,0.09); color: var(--amber); }
.prio-urgent { background: rgba(255,82,82,0.09); color: var(--red); }
.log-btn {
  display: flex; align-items: center; gap: 4px; padding: 6px 12px; border-radius: 8px;
  border: 1px solid var(--btn-border); background: var(--btn-bg); color: var(--muted);
  cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.15s;
}
.log-btn:hover { border-color: var(--cyan); color: var(--cyan); }

/* Records */
.record-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; border-bottom: 1px solid var(--border); gap: 12px;
}
.record-row:last-child { border-bottom: none; }
.rec-info { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.rec-label { font-size: 14px; font-weight: 600; color: var(--text); }
.rec-date { font-size: 12px; color: var(--muted); }
.rec-details { display: flex; gap: 16px; font-size: 12px; color: var(--muted); }
.rec-cost { color: var(--green); font-weight: 600; }
.rec-actions { display: flex; gap: 6px; }
.icon-btn {
  width: 30px; height: 30px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.icon-btn:hover { border-color: var(--cyan); color: var(--cyan); }
.icon-delete:hover { border-color: var(--red); color: var(--red); }

.empty-row { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 20px; color: var(--muted); font-size: 13px; }
</style>
