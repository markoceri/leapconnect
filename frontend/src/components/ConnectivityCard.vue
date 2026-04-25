<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(0,210,230,0.1);color:var(--accent)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12.55a11 11 0 0114.08 0"/><path d="M1.42 9a16 16 0 0121.16 0"/><path d="M8.53 16.11a6 6 0 016.95 0"/><circle cx="12" cy="20" r="1"/></svg>
        </div>
        Connectivity
      </div>
    </div>
    <div class="card-body">
      <div class="data-row">
        <span class="data-label">
          <span class="status-dot" :class="connectivity.bluetooth ? 'blue' : 'off'"></span>Bluetooth
        </span>
        <span class="data-value">{{ connectivity.bluetooth ? 'On' : connectivity.bluetooth === false ? 'Off' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">
          <span class="status-dot" :class="connectivity.hotspot ? 'green' : 'off'"></span>Wi-Fi Hotspot
        </span>
        <span class="data-value">{{ connectivity.hotspot ? 'On' : connectivity.hotspot === false ? 'Off' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Ignition ON1</span>
        <span class="data-value">{{ ignition.on1 != null ? (ignition.on1 ? 'Yes' : 'No') : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Ignition ON3</span>
        <span class="data-value">{{ ignition.on3 != null ? (ignition.on3 ? 'Yes' : 'No') : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Gear Status</span>
        <span class="data-value">{{ driving.gear_status != null ? gearLabel(driving.gear_status) : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Last Update</span>
        <span class="data-value" style="font-size:0.72rem">
          {{ timestamps.collect_time ? formatTime(timestamps.collect_time) : '—' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { gearLabel, formatTime } from '../utils/formatters'

defineProps({
  connectivity: { type: Object, default: () => ({}) },
  ignition: { type: Object, default: () => ({}) },
  driving: { type: Object, default: () => ({}) },
  timestamps: { type: Object, default: () => ({}) },
})
</script>
