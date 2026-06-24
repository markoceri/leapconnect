<template>
  <div class="toggle" :class="{ on: modelValue }" @click="$emit('update:modelValue', !modelValue)">
    <div class="toggle-knob" />
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.toggle {
  width: 38px;
  height: 22px;
  border-radius: 11px;
  background: var(--toggle-bg);
  border: 1px solid var(--toggle-border);
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.toggle.on {
  background: rgba(var(--accent-rgb), 0.267);
  border-color: rgba(var(--accent-rgb), 0.4);
}
.toggle-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--toggle-knob);
  transition: left 0.2s;
}
.toggle.on .toggle-knob {
  left: 18px;
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent);
}
</style>
