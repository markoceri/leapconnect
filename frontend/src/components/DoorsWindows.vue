<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(179,136,255,0.1);color:var(--accent-purple)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
        </div>
        Doors & Windows
      </div>
    </div>
    <div class="card-body">
      <div class="data-row">
        <span class="data-label">
          <span class="status-dot" :class="locked === true ? 'green' : locked === false ? 'red' : 'off'"></span>
          Vehicle Lock
        </span>
        <span class="data-value" :class="locked === true ? 'good' : locked === false ? 'bad' : ''">
          {{ locked === true ? 'Locked' : locked === false ? 'Unlocked' : '—' }}
        </span>
      </div>
      <div v-for="door in doorItems" :key="door.label" class="data-row">
        <span class="data-label">{{ door.label }}</span>
        <span class="data-value" :class="doorState(door.value).cls">{{ doorState(door.value).text }}</span>
      </div>

      <div class="windows-section">
        <div v-for="win in windowItems" :key="win.label" class="data-row">
          <span class="data-label">{{ win.label }}</span>
          <span class="data-value">{{ win.value != null ? win.value + '%' : '—' }}</span>
        </div>
        <div class="data-row">
          <span class="data-label">Sun Shade</span>
          <span class="data-value">{{ windows.sun_shade ?? '—' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { doorState } from '../utils/formatters'

const props = defineProps({
  doors: { type: Object, default: () => ({}) },
  windows: { type: Object, default: () => ({}) },
})

const locked = computed(() => props.doors.is_locked ?? null)

const doorItems = computed(() => [
  { label: 'Driver Door', value: props.doors.driver_door },
  { label: 'Passenger Door', value: props.doors.passenger_door },
  { label: 'Left Rear', value: props.doors.left_rear },
  { label: 'Right Rear', value: props.doors.right_rear },
  { label: 'Trunk', value: props.doors.trunk },
])

const windowItems = computed(() => [
  { label: 'LF Window', value: props.windows.left_front_percent },
  { label: 'RF Window', value: props.windows.right_front_percent },
  { label: 'LR Window', value: props.windows.left_rear_percent },
  { label: 'RR Window', value: props.windows.right_rear_percent },
])
</script>

<style scoped>
.windows-section {
  margin-top: 1rem;
  padding-top: 0.8rem;
  border-top: 1px solid var(--border-subtle);
}
</style>
