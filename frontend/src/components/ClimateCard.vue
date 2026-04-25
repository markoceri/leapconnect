<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(255,107,53,0.1);color:var(--accent-warm)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a5 5 0 00-2 9.54V18a2 2 0 104 0v-6.46A5 5 0 0012 2z"/></svg>
        </div>
        Climate
      </div>
    </div>
    <div class="card-body">
      <div class="data-row">
        <span class="data-label">
          <span class="status-dot" :class="climate.ac_switch ? 'green' : 'off'"></span>A/C
        </span>
        <span class="data-value" :class="climate.ac_switch ? 'good' : ''">
          {{ climate.ac_switch ? 'On' : 'Off' }}
        </span>
      </div>
      <div class="data-row">
        <span class="data-label">Set Temperature</span>
        <span class="data-value">{{ climate.ac_setting != null ? climate.ac_setting + '°C' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Outside Temperature</span>
        <span class="data-value">{{ climate.outdoor_temp != null ? climate.outdoor_temp + '°C' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Fan Volume</span>
        <span class="data-value">{{ climate.ac_air_volume ?? '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Mode</span>
        <span class="data-value">{{ climate.ac_cooling_and_heating != null ? climateMode(climate.ac_cooling_and_heating) : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Air Circulation</span>
        <span class="data-value">{{ climate.ac_circle_mode != null ? (climate.ac_circle_mode ? 'Recirculate' : 'Fresh') : '—' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { climateMode } from '../utils/formatters'

defineProps({
  climate: { type: Object, default: () => ({}) },
})
</script>
