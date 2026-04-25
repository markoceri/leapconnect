<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(255,196,0,0.1);color:var(--accent-yellow)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
        </div>
        Tire Pressure
      </div>
    </div>
    <div class="card-body">
      <div class="tire-visual">
        <div class="tire-cell">
          <div class="tire-value">{{ fmt(tires.front_left) }}</div>
          <div class="tire-label">Front Left</div>
        </div>
        <div class="tire-car-icon"></div>
        <div class="tire-cell">
          <div class="tire-value">{{ fmt(tires.front_right) }}</div>
          <div class="tire-label">Front Right</div>
        </div>
        <div class="tire-cell">
          <div class="tire-value">{{ fmt(tires.rear_left) }}</div>
          <div class="tire-label">Rear Left</div>
        </div>
        <div class="tire-cell">
          <div class="tire-value">{{ fmt(tires.rear_right) }}</div>
          <div class="tire-label">Rear Right</div>
        </div>
      </div>
      <div class="tire-unit-label">Pressure in bar</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  tires: { type: Object, default: () => ({}) },
})

function fmt(val) {
  return val != null ? val.toFixed(1) : '—'
}
</script>

<style scoped>
.tire-visual {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  grid-template-rows: auto auto;
  gap: 0.8rem 2rem;
  align-items: center;
  justify-items: center;
  padding: 1rem 0;
}

.tire-cell { text-align: center; }

.tire-value {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.tire-label {
  font-size: 0.65rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 0.2rem;
}

.tire-car-icon {
  grid-row: span 2;
  width: 60px;
  height: 100px;
  border: 2px solid var(--border-default);
  border-radius: 12px 12px 8px 8px;
  position: relative;
  opacity: 0.4;
}
.tire-car-icon::before {
  content: '';
  position: absolute;
  top: 15%;
  left: 10%;
  right: 10%;
  bottom: 30%;
  border: 1px solid var(--border-default);
  border-radius: 6px 6px 4px 4px;
}

.tire-unit-label {
  text-align: center;
  font-size: 0.7rem;
  color: var(--text-tertiary);
  margin-top: 0.5rem;
}
</style>
