<template>
  <div v-if="shown.length" class="ongoing">
    <div v-for="o in shown" :key="`${o.provider}:${o.external_id}`" class="ongoing-item" :class="{ warn: !o.plausible }">
      <div class="ongoing-head">
        <span class="provider-chip" :title="o.account_username || ''">{{ o.provider_label }}</span>
        <strong>{{ o.station?.name || o.operator || 'Public charger' }}</strong>
        <span v-if="o.station?.max_power_kw" class="sub">{{ o.station.max_power_kw }} kW {{ o.station.is_dc == null ? '' : o.station.is_dc ? 'DC' : 'AC' }}</span>
        <span v-if="!o.charging_started_at" class="sub">· waiting for the energy to flow</span>
      </div>
      <div class="ongoing-facts">
        <span v-if="o.price_kwh != null">€{{ o.price_kwh.toFixed(2) }}/kWh</span>
        <span v-if="o.estimated_cost != null" :title="`${o.energy_kwh?.toFixed(1)} kWh so far × the tariff; fees and the final bill come when the session ends`">
          ≈ <b>€{{ o.estimated_cost.toFixed(2) }}</b> so far
        </span>
        <span v-if="o.pre_auth_amount" class="sub">€{{ o.pre_auth_amount.toFixed(0) }} held</span>
      </div>
      <div v-if="o.station?.address" class="sub">{{ o.station.address }}</div>
      <div v-for="p in o.problems" :key="p" class="warning">⚠ {{ p }} — maybe another vehicle's charge</div>
      <div v-if="o.linked_cost_id" class="warning">⚠ Already linked to another session</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../composables/useApi'

// The charging providers' sessions in progress for the vehicle's charge
const props = defineProps({
  vin: { type: String, required: true },
  // Show the sessions that don't fit the car's charge too (with the reason)
  showImplausible: { type: Boolean, default: true },
  // Refresh period while shown (the provider is read at most every 30 s)
  refreshMs: { type: Number, default: 60000 },
})

const sessions = ref([])
let timer = null

// One that fits the car's charge hides the ones that don't
const shown = computed(() => {
  const plausible = sessions.value.filter(o => o.plausible)
  if (plausible.length || !props.showImplausible) return plausible
  return sessions.value.filter(o => o.problems.every(p => p !== "the car isn't charging"))
})

async function load() {
  try {
    sessions.value = (await api('GET', `/api/vehicles/${props.vin}/charging-costs/ongoing`)).sessions
  } catch {
    sessions.value = [] // best-effort: no provider, or it's unreachable
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, props.refreshMs)
})
onBeforeUnmount(() => clearInterval(timer))
watch(() => props.vin, load)
</script>

<style scoped>
.ongoing { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
.ongoing-item { border: 1px solid var(--border); border-radius: 8px; padding: 7px 10px; display: flex; flex-direction: column; gap: 2px; font-size: 12px; }
.ongoing-item.warn { border-color: color-mix(in srgb, #ffb74d 60%, transparent); }
.ongoing-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.ongoing-facts { display: flex; gap: 4px 12px; flex-wrap: wrap; }
.provider-chip { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 1px 6px; border: 1px solid var(--accent); color: var(--accent); }
.sub { color: var(--muted); overflow-wrap: anywhere; }
.warning { color: #ffb74d; }
</style>
