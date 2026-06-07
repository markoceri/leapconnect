<template>
  <div class="pack-card" :class="{ dim: !pack.applies }">
    <div class="pack-head">
      <button class="pack-toggle" @click="expanded = !expanded">
        <component :is="expanded ? ChevronDown : ChevronRight" :size="15" />
        <span class="pack-name">{{ pack.name }}</span>
        <span class="pack-count">{{ pack.items.length }}</span>
      </button>
      <div class="pack-right">
        <span v-if="!pack.applies" class="compat-badge" title="Not listed for this vehicle's model">
          other model
        </span>
        <span v-if="pack.author" class="pack-author">by {{ pack.author }}</span>
        <button class="import-btn" :disabled="!importableCount" @click="$emit('import-pack', pack)">
          <Download :size="13" /> Import{{ importableCount ? ` (${importableCount})` : '' }}
        </button>
      </div>
    </div>
    <div v-if="expanded" class="pack-items">
      <div v-for="it in pack.items" :key="it.service_type" class="pack-item">
        <div class="pi-info">
          <span class="pi-label">{{ it.label }}</span>
          <span class="pi-meta">{{ interval(it) }} · {{ it.priority }}</span>
        </div>
        <span v-if="it.in_plan" class="in-plan-badge"><Check :size="12" /> in plan</span>
        <button v-else class="pi-add" title="Add to plan" @click="$emit('import-item', it, pack)">
          <Plus :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Check, ChevronDown, ChevronRight, Download, Plus } from 'lucide-vue-next'
import { formatInterval } from '../utils/maintenance'

const props = defineProps({
  pack: { type: Object, required: true },
})
defineEmits(['import-pack', 'import-item'])

const expanded = ref(false)
const importableCount = computed(() => props.pack.items.filter((i) => !i.in_plan).length)
const interval = (it) => formatInterval(it)
</script>

<style scoped>
.pack-card { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; background: var(--btn-bg); }
.pack-card.dim { opacity: 0.75; }
.pack-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.pack-toggle {
  display: flex; align-items: center; gap: 8px; background: none; border: none;
  color: var(--text); cursor: pointer; font-size: 13px; font-weight: 600; min-width: 0;
}
.pack-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pack-count { font-size: 11px; color: var(--muted); background: var(--card); border-radius: 8px; padding: 1px 7px; }
.pack-right { display: flex; align-items: center; gap: 8px; }
.compat-badge { font-size: 10px; color: var(--amber); background: rgba(255,171,64,0.08); border-radius: 8px; padding: 2px 7px; }
.pack-author { font-size: 11px; color: var(--muted); }
.import-btn {
  display: flex; align-items: center; gap: 4px; padding: 5px 10px; border-radius: 8px;
  border: 1px solid rgba(0,212,255,0.27); background: rgba(0,212,255,0.06); color: var(--cyan);
  cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.15s;
}
.import-btn:hover { background: rgba(0,212,255,0.13); }
.import-btn:disabled { opacity: 0.45; cursor: default; }

.pack-items { margin-top: 10px; display: flex; flex-direction: column; }
.pack-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 0; border-top: 1px solid var(--border); }
.pi-info { display: flex; flex-direction: column; min-width: 0; }
.pi-label { font-size: 13px; color: var(--text); }
.pi-meta { font-size: 11px; color: var(--muted); }
.in-plan-badge { display: flex; align-items: center; gap: 3px; font-size: 11px; color: var(--green); }
.pi-add {
  width: 26px; height: 26px; border-radius: 7px; border: 1px solid var(--btn-border);
  background: var(--card); color: var(--muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.pi-add:hover { border-color: var(--cyan); color: var(--cyan); }
</style>
