<template>
  <div class="stat-card">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-main">
      <span class="stat-value" :style="{ color }">{{ value }}</span>
      <span class="stat-unit" :style="{ color }">{{ unit }}</span>
    </div>
    <div v-if="sub" class="stat-sub">
      <component v-if="icon" :is="icon" :size="12" class="stat-icon" :class="{ pulse }" />
      {{ sub }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  unit: { type: String, default: '' },
  sub: { type: String, default: '' },
  color: { type: String, default: '#00d4ff' },
  icon: { type: [Object, Function], default: null },
  pulse: Boolean,
})
</script>

<style scoped>
.stat-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
  flex: 1;
  min-width: 0;
}
.stat-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--muted3);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.stat-main {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}
.stat-unit {
  font-size: 13px;
  opacity: 0.8;
  font-weight: 500;
}
.stat-sub {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--muted3);
}
.stat-icon {
  color: var(--green);
}
.stat-icon.pulse {
  animation: lm-pulse 1.5s infinite;
}
</style>
