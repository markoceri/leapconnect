<template>
  <svg viewBox="0 0 500 205" xmlns="http://www.w3.org/2000/svg" :style="svgStyle">
    <defs>
      <linearGradient id="cBody" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="bodyTopColor" />
        <stop offset="100%" stop-color="#090d15" />
      </linearGradient>
      <linearGradient id="cRoof" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="roofTopColor" />
        <stop offset="100%" :stop-color="color" />
      </linearGradient>
    </defs>
    <!-- Ground shadow -->
    <ellipse cx="255" cy="196" rx="200" ry="10" fill="rgba(0,0,0,0.45)" />
    <!-- Main body -->
    <path d="M 48 157 C 46 142 50 122 62 112 L 82 80 Q 106 60 142 54 L 166 36 Q 190 22 220 20 L 300 20 Q 340 20 364 38 L 383 70 Q 430 82 453 117 L 460 150 Q 462 164 450 168 L 408 168 A 34 15 0 0 0 342 168 L 200 168 A 34 15 0 0 0 134 168 L 60 160 Z" fill="url(#cBody)" :stroke="color" stroke-width="0.5" />
    <!-- Roof -->
    <path d="M 168 36 Q 190 22 220 20 L 300 20 Q 340 20 363 38 L 383 70 L 148 72 Z" fill="url(#cRoof)" />
    <!-- Windshield -->
    <path d="M 152 53 L 168 36 Q 190 22 220 20 L 224 68 L 148 72 Z" fill="rgba(120,185,230,0.18)" stroke="rgba(140,200,240,0.35)" stroke-width="1" />
    <!-- Side windows -->
    <path d="M 227 20 L 296 20 L 291 68 L 228 68 Z" fill="rgba(120,185,230,0.16)" stroke="rgba(140,200,240,0.28)" stroke-width="1" />
    <!-- Rear quarter window -->
    <path d="M 299 20 Q 336 20 360 38 L 367 68 L 295 68 Z" fill="rgba(120,185,230,0.13)" stroke="rgba(140,200,240,0.22)" stroke-width="1" />
    <!-- Window sill line -->
    <line x1="149" y1="72" x2="368" y2="70" stroke="rgba(180,210,230,0.18)" stroke-width="1" />
    <!-- Door lines -->
    <line x1="228" y1="20" x2="226" y2="168" stroke="rgba(0,0,0,0.5)" stroke-width="1.5" />
    <line x1="297" y1="20" x2="294" y2="168" stroke="rgba(0,0,0,0.5)" stroke-width="1.5" />
    <!-- Door handles -->
    <rect x="237" y="120" width="22" height="6" rx="3" fill="#253545" stroke="#2d4255" stroke-width="1" />
    <rect x="305" y="120" width="22" height="6" rx="3" fill="#253545" stroke="#2d4255" stroke-width="1" />
    <!-- Rocker panel -->
    <path d="M 136 163 L 340 163 L 338 170 L 138 170 Z" fill="rgba(0,0,0,0.35)" />
    <!-- Headlight -->
    <ellipse cx="452" cy="128" rx="14" ry="9" fill="rgba(255,255,200,0.04)" stroke="rgba(255,255,200,0.65)" stroke-width="1.5" />
    <ellipse cx="452" cy="128" rx="8" ry="5.5" fill="rgba(255,255,200,0.95)" />
    <path d="M 449 116 Q 461 120 461 128" stroke="rgba(255,255,200,0.75)" stroke-width="2.5" fill="none" stroke-linecap="round" />
    <!-- Taillight -->
    <rect x="51" y="115" width="14" height="32" rx="3" fill="rgba(255,50,50,0.06)" stroke="rgba(255,60,40,0.75)" stroke-width="1.5" />
    <rect x="53" y="119" width="10" height="10" rx="1.5" fill="rgba(255,55,40,0.9)" />
    <rect x="53" y="133" width="10" height="7" rx="1" fill="rgba(255,100,40,0.6)" />
    <!-- Front plate -->
    <rect x="446" y="156" width="18" height="8" rx="2" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.22)" stroke-width="1" />
    <!-- Rear badge -->
    <rect x="53" y="151" width="13" height="6" rx="2" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.18)" stroke-width="1" />
    <!-- Trunk open line -->
    <path v-if="trunkOpen" d="M 52 112 L 50 75 Q 58 58 80 54 L 82 80" fill="none" stroke="#ffab40" stroke-width="2" stroke-dasharray="5,3" />
    <!-- Wheels -->
    <g v-for="cx in [375, 138]" :key="cx">
      <circle :cx="cx" cy="170" r="30" fill="#070b12" />
      <circle :cx="cx" cy="170" r="24" fill="#0d1220" />
      <circle :cx="cx" cy="170" r="19" fill="#070b12" stroke="#1a2232" stroke-width="1.5" />
      <line v-for="(a, i) in spokes" :key="i"
        :x1="cx + 9 * Math.cos(a * Math.PI / 180)" :y1="170 + 9 * Math.sin(a * Math.PI / 180)"
        :x2="cx + 18 * Math.cos(a * Math.PI / 180)" :y2="170 + 18 * Math.sin(a * Math.PI / 180)"
        stroke="#1e2840" stroke-width="3.5" stroke-linecap="round" />
      <circle :cx="cx" cy="170" r="5" fill="#1e2840" />
      <circle :cx="cx" cy="170" r="2" fill="#0d1220" />
    </g>
    <!-- Charging badge -->
    <g v-if="charging">
      <circle cx="95" cy="107" r="17" fill="rgba(0,230,118,0.12)" stroke="rgba(0,230,118,0.55)" stroke-width="1.5" />
      <text x="95" y="113" text-anchor="middle" fill="#00e676" font-size="16">⚡</text>
    </g>
    <!-- AC badge -->
    <g v-if="acOn">
      <circle cx="418" cy="92" r="15" fill="rgba(0,212,255,0.1)" stroke="rgba(0,212,255,0.45)" stroke-width="1.5" />
      <text x="418" y="98" text-anchor="middle" fill="#00d4ff" font-size="14">❄</text>
    </g>
    <!-- Lock indicator -->
    <g v-if="locked" opacity="0.7">
      <circle cx="258" cy="155" r="9" fill="rgba(255,171,64,0.15)" stroke="rgba(255,171,64,0.5)" stroke-width="1" />
      <text x="258" y="160" text-anchor="middle" fill="#ffab40" font-size="10">🔒</text>
    </g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  locked: { type: Boolean, default: false },
  charging: { type: Boolean, default: false },
  acOn: { type: Boolean, default: false },
  trunkOpen: { type: Boolean, default: false },
  color: { type: String, default: '#1e2d3f' },
})

const spokes = [0, 51.4, 102.8, 154.3, 205.7, 257.1, 308.6]

const glow = computed(() =>
  props.charging ? '#00e676' : props.acOn ? '#00d4ff' : null
)

const svgStyle = computed(() => ({
  width: '100%',
  maxWidth: '480px',
  filter: glow.value
    ? `drop-shadow(0 0 14px ${glow.value}99)`
    : 'drop-shadow(0 8px 20px rgba(0,0,0,0.6))',
  transition: 'filter 0.6s ease',
}))

const bodyTopColor = computed(() =>
  props.charging ? '#1a3028' : props.acOn ? '#1a2838' : props.color
)
const roofTopColor = computed(() =>
  props.charging ? '#1e3530' : props.acOn ? '#1e2d3c' : '#182030'
)
</script>
