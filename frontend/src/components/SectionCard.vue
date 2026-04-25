<template>
  <div class="section-card">
    <div v-if="title" class="section-header">
      <span v-if="icon" class="section-icon">{{ icon }}</span>
      <span class="section-title">{{ title }}</span>
    </div>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  icon: { type: String, default: '' },
})
</script>

<style scoped>
.section-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.section-icon { font-size: 15px; }
.section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--heading);
  letter-spacing: 0.02em;
}
</style>
