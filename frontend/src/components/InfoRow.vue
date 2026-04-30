<template>
  <div class="info-row">
    <span class="info-label">
      <span v-if="dot" class="info-dot" :style="{ background: color || '#00e676' }"></span>
      {{ label }}
    </span>
    <span class="info-value" :style="{ color: color || '#e2e6f0' }">
      <slot>{{ value }}</slot>
    </span>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: { type: [String, Number], default: '' },
  color: { type: String, default: '' },
  dot: Boolean,
})
</script>

<style scoped>
.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 0;
  border-bottom: 1px solid #181d2c;
  gap: 8px;
  min-width: 0;
}
.info-row:last-child { border-bottom: none; }
.info-label {
  font-size: 12.5px;
  color: var(--label);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.info-value {
  font-size: 12.5px;
  font-weight: 600;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.info-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}
</style>
