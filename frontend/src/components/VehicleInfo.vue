<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(179,136,255,0.1);color:var(--accent-purple)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        </div>
        Vehicle Info
      </div>
    </div>
    <div class="card-body">
      <div class="data-row">
        <span class="data-label">VIN</span>
        <span class="data-value" style="font-size:0.72rem">{{ vehicle.vin || '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Model</span>
        <span class="data-value">{{ vehicle.car_type || '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Nickname</span>
        <span class="data-value">{{ vehicle.nickname || '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Year</span>
        <span class="data-value">{{ vehicle.year || '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Shared Vehicle</span>
        <span class="data-value">{{ vehicle.is_shared ? 'Yes' : 'No' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Abilities</span>
        <span class="data-value abilities">{{ (vehicle.abilities || []).join(', ') || '—' }}</span>
      </div>
      <div v-if="picture?.shareBindUrl" class="data-row">
        <span class="data-label">Car Picture</span>
        <span class="data-value">
          <a :href="picture.shareBindUrl" target="_blank" rel="noopener" class="link">View →</a>
        </span>
      </div>
      <div v-if="picture?.key" class="data-row">
        <span class="data-label">Picture Package</span>
        <span class="data-value">
          <a :href="`/api/vehicles/${vehicle.vin}/picture/download?key=${encodeURIComponent(picture.key)}`" class="link">Download ZIP →</a>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  vehicle: { type: Object, default: () => ({}) },
  picture: { type: Object, default: null },
})
</script>

<style scoped>
.abilities {
  font-size: 0.68rem;
  max-width: 200px;
  text-align: right;
  word-break: break-word;
}
.link {
  color: var(--text-accent);
  text-decoration: none;
}
</style>
