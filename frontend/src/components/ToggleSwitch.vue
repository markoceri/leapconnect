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
  background: #1c2240;
  border: 1px solid #2a3050;
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.toggle.on {
  background: #00d4ff44;
  border-color: #00d4ff66;
}
.toggle-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #3a4468;
  transition: left 0.2s;
}
.toggle.on .toggle-knob {
  left: 18px;
  background: #00d4ff;
  box-shadow: 0 0 6px #00d4ff;
}
</style>
