<template>
  <div class="card card-full">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(255,255,255,0.05);color:var(--text-tertiary)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
        </div>
        Raw Data
      </div>
      <button class="raw-data-toggle" @click="open = !open">{ } Toggle JSON</button>
    </div>
    <div class="card-body" style="padding-top:0">
      <div v-if="open" class="raw-data-panel">
        <pre>{{ JSON.stringify(data, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  data: { type: Object, default: () => ({}) },
})

const open = ref(false)
</script>

<style scoped>
.raw-data-toggle {
  padding: 0.4rem 0.8rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  cursor: pointer;
  transition: var(--transition);
}
.raw-data-toggle:hover {
  color: var(--text-secondary);
  border-color: var(--border-accent);
}

.raw-data-panel {
  max-height: 400px;
  overflow: auto;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  padding: 1rem;
  margin-top: 1rem;
}
.raw-data-panel pre {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
