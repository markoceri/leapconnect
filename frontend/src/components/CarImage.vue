<template>
  <div class="car-image">
    <!-- Composed layers: always in DOM, hidden until painted -->
    <div class="layers-container" :class="{ visible: layersPainted }">
      <!-- Right side (far side) — rendered BELOW the body -->
      <img v-if="doors.rightRear && pkg['carpic_rightbehind_open.png']" :src="pkg['carpic_rightbehind_open.png']" class="layer" alt="" />
      <img v-if="!doors.rightRear && pkg['carpic_rightbehind_close.png']" :src="pkg['carpic_rightbehind_close.png']" class="layer" alt="" />
      <img v-if="doors.rightFront && pkg['carpic_rightfront_open.png']" :src="pkg['carpic_rightfront_open.png']" class="layer" alt="" />
      <img v-if="!doors.rightFront && pkg['carpic_rightfront_close.png']" :src="pkg['carpic_rightfront_close.png']" class="layer" alt="" />

      <!-- Base body -->
      <img
        v-if="pkg['carpic_body.png']"
        :src="pkg['carpic_body.png']"
        class="layer"
        alt=""
        @load="onBodyLoaded"
      />

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
    </div>

    <!-- Tripsum placeholder: sits ON TOP, hides only after layers are painted -->
    <img
      v-if="!layersPainted"
      :src="tripsum || `/api/vehicles/${vin}/picture/image`"
      class="layer placeholder"
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
const hasStatus = computed(() => !!s.value.doors)
const tripsum = computed(() => pkg.value['carpic_for_tripsum.png'] || null)

const layersPainted = ref(false)
const bodyDecoded = ref(false)

function onBodyLoaded() {
  // Body image decoded by browser — safe to show layers and hide tripsum
  bodyDecoded.value = true
  if (hasStatus.value) {
    layersPainted.value = true
  }
}

const s = computed(() => props.status || {})

// Door state: true = open
const doors = computed(() => ({
  leftFront: !!s.value.doors?.lbcm_driver_door_status,
  leftRear: !!s.value.doors?.lbcm_left_rear_door_status,
  rightFront: !!s.value.doors?.rbcm_driver_door_status,
  rightRear: !!s.value.doors?.rbcm_right_rear_door_status,
}))

const trunk = computed(() => !!s.value.doors?.bbcm_back_door_status)
const hood = computed(() => false) // no hood status from API
const charging = computed(() => !!s.value.battery?.is_charging)
const acOn = computed(() => !!s.value.climate?.ac_switch)

// Windows: open when percent > 0
const windows = computed(() => ({
  leftFrontOpen: (s.value.windows?.left_front_window_percent ?? 0) > 0,
  leftRearOpen: (s.value.windows?.left_rear_window_percent ?? 0) > 0,
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

// If status arrives after body was already decoded, flip painted
watch(hasStatus, (val) => {
  if (val && bodyDecoded.value) layersPainted.value = true
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

.layers-container {
  position: absolute;
  inset: 0;
  opacity: 0;
}

.layers-container.visible {
  opacity: 1;
}

.layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.placeholder {
  z-index: 10;
}
</style>
