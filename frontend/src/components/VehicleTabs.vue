<template>
  <div class="vehicle-tabs">
    <button
      v-for="v in vehicles"
      :key="v.vin"
      class="vehicle-tab"
      :class="{ active: v.vin === selectedVin }"
      @click="$emit('select', v.vin)"
    >
      {{ v.nickname || v.car_type || 'Vehicle' }}
      <span class="tab-vin">{{ v.vin.slice(-8) }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  vehicles: { type: Array, required: true },
  selectedVin: { type: String, default: null },
})
defineEmits(['select'])
</script>

<style scoped>
.vehicle-tabs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 2rem 0;
}

.vehicle-tab {
  padding: 0.6rem 1.2rem;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-bottom: none;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  color: var(--text-secondary);
  font-family: var(--font-display);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
  position: relative;
}
.vehicle-tab:hover { color: var(--text-primary); background: var(--bg-card-hover); }

.vehicle-tab.active {
  background: var(--bg-card);
  color: var(--text-accent);
  border-color: var(--border-accent);
}
.vehicle-tab.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent);
}

.tab-vin {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-tertiary);
  display: block;
  margin-top: 0.1rem;
}

@media (max-width: 768px) {
  .vehicle-tabs { padding: 1rem 1rem 0; }
}
</style>
