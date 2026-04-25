<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(0,230,118,0.1);color:var(--accent-green)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="6" width="18" height="12" rx="2"/><line x1="23" y1="10" x2="23" y2="14"/></svg>
        </div>
        Battery & Charging
      </div>
    </div>
    <div class="card-body">
      <div class="data-row">
        <span class="data-label">State of Charge</span>
        <span class="data-value good">{{ bat.soc != null ? bat.soc + '%' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">
          <span class="status-dot" :class="bat.is_charging ? 'blue' : 'off'"></span>Charging
        </span>
        <span class="data-value">{{ bat.is_charging === true ? 'Yes' : bat.is_charging === false ? 'No' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Time Remaining</span>
        <span class="data-value">{{ bat.charge_remain_time != null ? bat.charge_remain_time + ' min' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Charge Limit</span>
        <span class="data-value">{{ bat.charge_soc_setting != null ? bat.charge_soc_setting + '%' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Battery Voltage</span>
        <span class="data-value">{{ bat.battery_voltage != null ? bat.battery_voltage + ' V' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Battery Current</span>
        <span class="data-value">{{ bat.battery_current != null ? bat.battery_current + ' A' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Energy Available</span>
        <span class="data-value">{{ bat.dump_energy != null ? bat.dump_energy + ' kWh' : '—' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  bat: { type: Object, default: () => ({}) },
})
</script>
