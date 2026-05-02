<template>
  <div class="car-image">
    <img
      :src="displaySrc"
      class="car-img"
      alt="Vehicle"
      @load="onLoad"
      :class="{ visible: loaded }"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  vin: { type: String, required: true },
  status: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 },
})

const loaded = ref(false)

// --- Static image (non-charging or base) ---
const staticSrc = computed(() => {
  const ts = props.refreshKey || Date.now()
  return `/api/vehicles/${props.vin}/picture/dynamic?_t=${ts}`
})

// --- Charging animation ---
const charging = computed(() => !!props.status?.is_charging)
const chargeFrameUrls = ref([])   // Object URLs for frames 1-15
const chargeIndex = ref(0)
let chargeTimer = null
let preloadAbort = null

const displaySrc = computed(() => {
  if (charging.value && chargeFrameUrls.value.length === 15) {
    return chargeFrameUrls.value[chargeIndex.value]
  }
  return staticSrc.value
})

function onLoad() { loaded.value = true }
watch(staticSrc, () => { if (!charging.value) loaded.value = false })

async function preloadChargeFrames() {
  // Abort any previous preload
  revokeFrames()
  const controller = new AbortController()
  preloadAbort = controller

  const urls = []
  const ts = props.refreshKey || Date.now()
  try {
    // Fetch all 15 frames in parallel
    const fetches = []
    for (let i = 1; i <= 15; i++) {
      fetches.push(
        fetch(`/api/vehicles/${props.vin}/picture/dynamic?charge_frame=${i}&_t=${ts}`, {
          signal: controller.signal,
        }).then(r => r.blob())
      )
    }
    const blobs = await Promise.all(fetches)
    if (controller.signal.aborted) return
    for (const blob of blobs) {
      urls.push(URL.createObjectURL(blob))
    }
    chargeFrameUrls.value = urls
    startAnimation()
  } catch {
    // aborted or network error — ignore
  }
}

function revokeFrames() {
  if (preloadAbort) { preloadAbort.abort(); preloadAbort = null }
  stopAnimation()
  for (const url of chargeFrameUrls.value) URL.revokeObjectURL(url)
  chargeFrameUrls.value = []
  chargeIndex.value = 0
}

function startAnimation() {
  if (chargeTimer) return
  chargeTimer = setInterval(() => {
    chargeIndex.value = (chargeIndex.value + 1) % 15
  }, 200)
}

function stopAnimation() {
  if (chargeTimer) { clearInterval(chargeTimer); chargeTimer = null }
  chargeIndex.value = 0
}

watch(charging, (val) => {
  if (val) preloadChargeFrames()
  else revokeFrames()
})

onMounted(() => { if (charging.value) preloadChargeFrames() })
onUnmounted(() => revokeFrames())
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
