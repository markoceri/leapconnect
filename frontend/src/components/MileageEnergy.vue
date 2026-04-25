<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(255,196,0,0.1);color:var(--accent-yellow)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        Mileage & Energy
      </div>
    </div>
    <div class="card-body">
      <div class="data-row">
        <span class="data-label">Total Mileage</span>
        <span class="data-value">{{ m.totalmileage != null ? m.totalmileage.toLocaleString() + ' km' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Total Mileage (mi)</span>
        <span class="data-value">{{ m.totalmileageMile != null ? parseFloat(m.totalmileageMile).toLocaleString() + ' mi' : '—' }}</span>
      </div>
      <div class="data-row">
        <span class="data-label">Days Since Delivery</span>
        <span class="data-value">{{ m.deliveryDays ?? '—' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  m: { type: Object, default: () => ({}) },
})
</script>
