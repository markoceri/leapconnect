<template>
  <button
    class="ctrl-btn"
    :class="[cssClass, { executing, success: result === 'success', error: result === 'error' }]"
    :title="disabled ? 'PIN required' : ''"
    @click="$emit('click')"
  >
    <div class="ctrl-icon">
      <component :is="iconComponent" />
    </div>
    {{ label }}
  </button>
</template>

<script setup>
import { ref, computed, h } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  cssClass: { type: String, default: '' },
  icon: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

defineEmits(['click'])

const executing = ref(false)
const result = ref(null)

const icons = {
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>',
  unlock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 019.9-1"/>',
  'trunk-open': '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
  'trunk-close': '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><line x1="9" y1="22" x2="9" y2="12"/><line x1="15" y1="22" x2="15" y2="12"/>',
  find: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  'window-open': '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 014-4h14"/>',
  'window-close': '<polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 01-4 4H3"/>',
  'sun-open': '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>',
  'sun-close': '<path d="M17 18a5 5 0 00-10 0"/><line x1="12" y1="9" x2="12" y2="2"/><line x1="4.22" y1="10.22" x2="5.64" y2="11.64"/><line x1="1" y1="18" x2="3" y2="18"/><line x1="21" y1="18" x2="23" y2="18"/><line x1="18.36" y1="11.64" x2="19.78" y2="10.22"/><line x1="23" y1="22" x2="1" y2="22"/><line x1="8" y1="18" x2="8" y2="22"/><line x1="16" y1="18" x2="16" y2="22"/>',
  ac: '<path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M19.07 4.93L4.93 19.07"/>',
  cool: '<path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14"/>',
  heat: '<path d="M12 2a5 5 0 00-2 9.54V18a2 2 0 104 0v-6.46A5 5 0 0012 2z"/>',
  defrost: '<path d="M2 12h20"/><path d="M12 2v20"/><path d="M20 16l-4-4 4-4"/><path d="M4 8l4 4-4 4"/>',
  battery: '<rect x="1" y="6" width="18" height="12" rx="2"/><line x1="23" y1="10" x2="23" y2="14"/><line x1="6" y1="10" x2="6" y2="14"/><line x1="10" y1="10" x2="10" y2="14"/>',
}

const iconComponent = computed(() => {
  const svgContent = icons[props.icon] || icons.find || ''
  return {
    render() {
      return h('svg', {
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '2',
        innerHTML: svgContent,
      })
    },
  }
})
</script>

<style scoped>
.ctrl-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 1.2rem 0.8rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
  position: relative;
  overflow: hidden;
}
.ctrl-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-accent);
  color: var(--text-primary);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}
.ctrl-btn:active { transform: translateY(0); }

.ctrl-btn.executing { pointer-events: none; border-color: var(--accent); }
.ctrl-btn.executing .ctrl-icon { animation: spin 1s linear infinite; }

.ctrl-btn.success {
  border-color: var(--accent-green);
  background: rgba(0, 230, 118, 0.05);
}
.ctrl-btn.error {
  border-color: var(--accent-red);
  background: rgba(255, 61, 90, 0.05);
}

.ctrl-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
}
.ctrl-icon svg { width: 20px; height: 20px; }

.ctrl-btn.lock .ctrl-icon { background: rgba(179, 136, 255, 0.12); color: var(--accent-purple); }
.ctrl-btn.unlock .ctrl-icon { background: rgba(0, 230, 118, 0.12); color: var(--accent-green); }
.ctrl-btn.trunk .ctrl-icon { background: rgba(0, 210, 230, 0.12); color: var(--accent); }
.ctrl-btn.find .ctrl-icon { background: rgba(255, 196, 0, 0.12); color: var(--accent-yellow); }
.ctrl-btn.window .ctrl-icon { background: rgba(0, 210, 230, 0.12); color: var(--accent); }
.ctrl-btn.climate .ctrl-icon { background: rgba(255, 107, 53, 0.12); color: var(--accent-warm); }
.ctrl-btn.sunshade .ctrl-icon { background: rgba(255, 196, 0, 0.12); color: var(--accent-yellow); }
.ctrl-btn.battery-ctl .ctrl-icon { background: rgba(0, 230, 118, 0.12); color: var(--accent-green); }
</style>
