<template>
  <div class="section-card">
    <div v-if="title" class="section-header">
      <component v-if="icon" :is="icon" class="section-icon" :size="16" />
      <span class="section-title">{{ title }}</span>
    </div>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  icon: { type: [Object, Function], default: null },
})
</script>

<style scoped>
.section-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 16px;
}
@media (min-width: 640px) {
  .section-card { padding: 18px 20px; }
}
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.section-icon { color: var(--muted3); }
.section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--heading);
  letter-spacing: 0.02em;
}
</style>
