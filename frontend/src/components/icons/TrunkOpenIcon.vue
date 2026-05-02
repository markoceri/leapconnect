<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <!-- Car body 3/4 view, front-left -->
    <!-- Roof / cabin -->
    <path d="M5 13l3-5h6l1.5 2" />
    <!-- Body lower line -->
    <path d="M2 17h20" />
    <!-- Front fender -->
    <path d="M2 17v-3a1 1 0 0 1 1-1h2" />
    <!-- Rear fender -->
    <path d="M22 17v-3a1 1 0 0 0-1-1h-1.5" />
    <!-- Undercarriage -->
    <path d="M5 13v4M19.5 10v7" />
    <!-- Wheels -->
    <circle cx="6.5" cy="17.5" r="2" />
    <circle cx="18" cy="17.5" r="2" />
    <!-- Trunk lid open (lifted from rear) -->
    <path d="M15.5 10l4-6" />
    <path d="M14 8l5.5-4" />
    <!-- Open arrow indicator -->
    <path d="M18 5l1.5-2.5M18.5 2l1 2.5-2.5.5" />
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 24 },
  strokeWidth: { type: [Number, String], default: 2 },
})
</script>
