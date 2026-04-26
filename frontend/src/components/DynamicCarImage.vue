<template>
  <div class="car-image">
    <img
      :src="imgSrc"
      class="car-img"
      alt="Vehicle"
      @load="loaded = true"
      :class="{ visible: loaded }"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  vin: { type: String, required: true },
  /** Pass the vehicle status object so we know if it's charging. */
  status: { type: Object, default: null },
  /** Bump this to force a re-fetch (e.g. after a remote-control action). */
  refreshKey: { type: Number, default: 0 },
})

const loaded = ref(false)
const chargeFrame = ref(0)
let chargeTimer = null

const charging = computed(() => !!props.status?.battery?.is_charging)

const imgSrc = computed(() => {
  const params = new URLSearchParams()
  if (chargeFrame.value > 0) params.set('charge_frame', chargeFrame.value)
  params.set('_t', props.refreshKey || Date.now())
  return `/api/vehicles/${props.vin}/picture/dynamic?${params}`
})

// Reset loaded state when the source changes so the fade-in replays
watch(imgSrc, () => { loaded.value = false })

function startChargeAnimation() {
  if (chargeTimer) return
  chargeFrame.value = 1
  chargeTimer = setInterval(() => {
    chargeFrame.value = (chargeFrame.value % 15) + 1
  }, 200)
}

function stopChargeAnimation() {
  if (chargeTimer) {
    clearInterval(chargeTimer)
    chargeTimer = null
  }
  chargeFrame.value = 0
}

watch(charging, (val) => {
  if (val) startChargeAnimation()
  else stopChargeAnimation()
}, { immediate: true })

onMounted(() => { if (charging.value) startChargeAnimation() })
onUnmounted(() => stopChargeAnimation())
</script>

<style scoped>
.car-image {
  position: relative;
  width: 100%;
  max-width: 480px;
  aspect-ratio: 1125 / 525;
  filter: drop-shadow(0 8px 20px rgba(0, 0, 0, 0.6));
}

.car-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.car-img.visible {
  opacity: 1;
}
</style>
