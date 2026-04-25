<template>
  <div class="car-image" :class="{ 'glow-charging': charging, 'glow-ac': acOn }">
    <!-- Right side (far side) — rendered BELOW the body -->
    <img v-if="doors.rightRear && pkg['carpic_rightbehind_open.png']" :src="pkg['carpic_rightbehind_open.png']" class="layer" alt="" />
    <img v-if="!doors.rightRear && pkg['carpic_rightbehind_close.png']" :src="pkg['carpic_rightbehind_close.png']" class="layer" alt="" />
    <img v-if="doors.rightFront && pkg['carpic_rightfront_open.png']" :src="pkg['carpic_rightfront_open.png']" class="layer" alt="" />
    <img v-if="!doors.rightFront && pkg['carpic_rightfront_close.png']" :src="pkg['carpic_rightfront_close.png']" class="layer" alt="" />

    <!-- Base body -->
    <img v-if="pkg['carpic_body.png']" :src="pkg['carpic_body.png']" class="layer" alt="" />

    <!-- Hood -->
    <img v-if="hood && pkg['carpic_hood_open.png']" :src="pkg['carpic_hood_open.png']" class="layer" alt="" />
    <img v-if="!hood && pkg['carpic_hood_close.png']" :src="pkg['carpic_hood_close.png']" class="layer" alt="" />

    <!-- Left side (near side) — rendered ABOVE the body -->
    <img v-if="doors.leftRear && pkg['carpic_leftbehind_open.png']" :src="pkg['carpic_leftbehind_open.png']" class="layer" alt="" />
    <img v-if="!doors.leftRear && pkg['carpic_leftbehind_close.png']" :src="pkg['carpic_leftbehind_close.png']" class="layer" alt="" />
    <img v-if="doors.leftFront && pkg['carpic_leftfront_open.png']" :src="pkg['carpic_leftfront_open.png']" class="layer" alt="" />
    <img v-if="!doors.leftFront && pkg['carpic_leftfront_close.png']" :src="pkg['carpic_leftfront_close.png']" class="layer" alt="" />

    <!-- Tailgate (trunk) — only has an open image -->
    <img v-if="trunk && pkg['carpic_tailgate_open.png']" :src="pkg['carpic_tailgate_open.png']" class="layer" alt="" />

    <!-- Windows closed (glass visible when window is up) -->
    <img v-if="!windows.leftFrontOpen && pkg['carpic_leftfront_window_close.png']" :src="pkg['carpic_leftfront_window_close.png']" class="layer" alt="" />
    <img v-if="!windows.leftRearOpen && pkg['carpic_leftbehind_window_close.png']" :src="pkg['carpic_leftbehind_window_close.png']" class="layer" alt="" />

    <!-- Charging: open port + animated charge level -->
    <img v-if="charging && pkg['carpic_charge_open.png']" :src="pkg['carpic_charge_open.png']" class="layer" alt="" />
    <img v-if="charging && chargeFrame" :src="chargeFrame" class="layer" alt="" />

    <!-- Fallback: single image if package not loaded yet -->
    <img
      v-if="!hasPackage"
      :src="`/api/vehicles/${vin}/picture/image`"
      class="layer fallback"
      alt="Vehicle"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/appStore'

const props = defineProps({
  vin: { type: String, required: true },
  status: { type: Object, default: null },
})

const store = useAppStore()

const pkg = computed(() => store.picturePackages[props.vin] || {})
const hasPackage = computed(() => !!pkg.value['carpic_body.png'])

const s = computed(() => props.status || {})

// Door state: true = open
const doors = computed(() => ({
  leftFront: !!s.value.doors?.driver_door,
  leftRear: !!s.value.doors?.left_rear,
  rightFront: !!s.value.doors?.passenger_door,
  rightRear: !!s.value.doors?.right_rear,
}))

const trunk = computed(() => !!s.value.doors?.trunk)
const hood = computed(() => false) // no hood status from API
const charging = computed(() => !!s.value.battery?.is_charging)
const acOn = computed(() => !!s.value.climate?.ac_switch)

// Windows: open when percent > 0
const windows = computed(() => ({
  leftFrontOpen: (s.value.windows?.left_front_percent ?? 0) > 0,
  leftRearOpen: (s.value.windows?.left_rear_percent ?? 0) > 0,
}))

// Charging animation — cycle through charge1..15
const chargeFrameIndex = ref(1)
let chargeTimer = null
const CHARGE_FRAMES = 15

const chargeFrame = computed(() => {
  const key = `carpic_charge${chargeFrameIndex.value}.png`
  return pkg.value[key] || null
})

function startChargeAnimation() {
  if (chargeTimer) return
  chargeTimer = setInterval(() => {
    chargeFrameIndex.value = (chargeFrameIndex.value % CHARGE_FRAMES) + 1
  }, 200)
}

function stopChargeAnimation() {
  if (chargeTimer) {
    clearInterval(chargeTimer)
    chargeTimer = null
  }
  chargeFrameIndex.value = 1
}

// Watch charging state
onMounted(() => {
  if (charging.value) startChargeAnimation()
})
onUnmounted(() => stopChargeAnimation())

// React to charging changes
import { watch } from 'vue'
watch(charging, (val) => {
  if (val) startChargeAnimation()
  else stopChargeAnimation()
})
</script>

<style scoped>
.car-image {
  position: relative;
  width: 100%;
  max-width: 480px;
  aspect-ratio: 1125 / 525;
  filter: drop-shadow(0 8px 20px rgba(0, 0, 0, 0.6));
  transition: filter 0.6s ease;
}

.car-image.glow-charging {
  filter: drop-shadow(0 0 14px rgba(0, 230, 118, 0.6));
}

.car-image.glow-ac {
  filter: drop-shadow(0 0 14px rgba(0, 212, 255, 0.6));
}

.layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.fallback {
  position: relative;
}
</style>
