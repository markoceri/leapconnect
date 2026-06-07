<template>
  <div class="maintenance-tab">
    <!-- Header -->
    <div class="mnt-header">
      <div class="header-title">
        <h2>Maintenance</h2>
        <p>Service tracker &amp; history</p>
      </div>
      <div v-if="!needsC10Confirmation && !loading" class="segmented">
        <button class="seg-btn" :class="{ active: view === 'overview' }" @click="view = 'overview'">
          <Gauge :size="15" /> Overview
        </button>
        <button class="seg-btn" :class="{ active: view === 'library' }" @click="view = 'library'">
          <ClipboardList :size="15" /> Interventions
        </button>
      </div>
    </div>

    <!-- C10 Variant Prompt -->
    <div v-if="needsC10Confirmation" class="variant-prompt">
      <div class="prompt-card">
        <h3>C10 Variant Required</h3>
        <p>Select your C10 model variant to load the correct service schedule:</p>
        <div class="variant-buttons">
          <button class="variant-btn" @click="confirmVariant('bev')">
            <Zap :size="20" />
            <span>Pure Electric (BEV)</span>
          </button>
          <button class="variant-btn" @click="confirmVariant('reev')">
            <Flame :size="20" />
            <span>Range Extender (REEV)</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-row"><div class="spinner" /></div>

    <!-- Content -->
    <template v-if="!loading && !needsC10Confirmation">
      <MaintenanceOverview
        v-if="view === 'overview'"
        :vin="vin"
        :overview="overview"
        @open-library="view = 'library'"
        @reload="loadOverview"
      />
      <MaintenanceLibrary
        v-else
        :vin="vin"
        @changed="loadOverview"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ClipboardList, Flame, Gauge, Zap } from 'lucide-vue-next'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import MaintenanceOverview from './MaintenanceOverview.vue'
import MaintenanceLibrary from './MaintenanceLibrary.vue'

const props = defineProps({
  vin: { type: String, required: true },
  status: { type: Object, default: () => ({}) },
  vehicle: { type: Object, default: () => ({}) },
})
const { toast } = useToast()

const loading = ref(true)
const view = ref('overview')
const needsC10Confirmation = ref(false)
const overview = ref({
  total_items: 0, upcoming_count: 0, overdue_count: 0, critical_count: 0,
  model_key: '', display_name: '', due_soon: [], plan: [], recent_records: [], next_item: null,
})

async function load() {
  loading.value = true
  try {
    const modelInfo = await api('GET', `/api/vehicles/${props.vin}/maintenance/model`)
    if (modelInfo.needs_confirmation) {
      needsC10Confirmation.value = true
      return
    }
    needsC10Confirmation.value = false
    await loadOverview()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  overview.value = await api('GET', `/api/vehicles/${props.vin}/maintenance/overview`)
}

async function confirmVariant(variant) {
  loading.value = true
  try {
    await api('POST', `/api/vehicles/${props.vin}/maintenance/model`, { variant })
    needsC10Confirmation.value = false
    await loadOverview()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.vin, load)
</script>

<style scoped>
.maintenance-tab {
  width: 100%;
}

.mnt-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 20px;
}
.mnt-header h2 { font-size: 20px; font-weight: 700; color: var(--text); margin: 0; }
.mnt-header p { font-size: 13px; color: var(--muted); margin: 4px 0 0; }

/* Segmented control */
.segmented {
  display: inline-flex; background: var(--btn-bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 3px;
}
.seg-btn {
  display: flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 8px;
  border: none; background: transparent; color: var(--muted); cursor: pointer;
  font-size: 13px; font-weight: 600; transition: all 0.15s;
}
.seg-btn.active { background: var(--card); color: var(--text); box-shadow: 0 1px 3px rgba(0,0,0,0.15); }

/* C10 variant prompt */
.variant-prompt { display: flex; justify-content: center; padding: 40px 0; }
.prompt-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 32px; max-width: 480px; text-align: center;
}
.prompt-card h3 { margin: 0 0 8px; color: var(--text); font-size: 18px; }
.prompt-card p { color: var(--muted); margin: 0 0 20px; }
.variant-buttons { display: flex; gap: 12px; justify-content: center; }
.variant-btn {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px 24px; border-radius: 12px; border: 1.5px solid var(--btn-border);
  background: var(--btn-bg); color: var(--text); cursor: pointer; font-size: 14px;
  transition: all 0.2s; min-width: 160px;
}
.variant-btn:hover { border-color: var(--cyan); background: var(--btn-hover); }

.loading-row { display: flex; justify-content: center; padding: 60px 0; }
.spinner {
  width: 32px; height: 32px; border-radius: 50%;
  border: 3px solid var(--border); border-top-color: var(--cyan);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
