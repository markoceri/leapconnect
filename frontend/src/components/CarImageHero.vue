<template>
  <div class="car-image-hero">
    <template v-if="imageUrl">
      <img :src="imageUrl" :alt="name" />
      <div class="car-image-overlay">
        <div>
          <div class="car-image-name">{{ name }}</div>
          <div class="car-image-vin">{{ vin }}</div>
        </div>
      </div>
    </template>
    <div v-else-if="loading" class="car-image-loading">
      <div class="spinner" style="width:20px;height:20px"></div>
      Loading vehicle image…
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  vin: { type: String, required: true },
  name: { type: String, default: 'Leapmotor' },
})

const imageUrl = ref(null)
const loading = ref(true)
let currentUrl = null

async function loadImage() {
  loading.value = true
  imageUrl.value = null
  if (currentUrl) {
    URL.revokeObjectURL(currentUrl)
    currentUrl = null
  }
  try {
    const res = await fetch(`/api/vehicles/${props.vin}/picture/image`)
    if (!res.ok) throw new Error()
    const blob = await res.blob()
    currentUrl = URL.createObjectURL(blob)
    imageUrl.value = currentUrl
  } catch {
    imageUrl.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.vin, loadImage, { immediate: true })

onBeforeUnmount(() => {
  if (currentUrl) URL.revokeObjectURL(currentUrl)
})
</script>

<style scoped>
.car-image-hero {
  position: relative;
  width: 100%;
  margin-bottom: 0.5rem;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  animation: fadeInUp 0.5s ease both;
}

.car-image-hero img {
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  display: block;
  margin: 0 auto;
  padding: 1.5rem 2rem;
  filter: drop-shadow(0 8px 32px rgba(0, 0, 0, 0.4));
}

.car-image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 1.2rem 1.6rem;
  background: linear-gradient(transparent, rgba(10, 12, 16, 0.85));
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.car-image-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.car-image-vin {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-tertiary);
  margin-top: 0.15rem;
}

.car-image-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 180px;
  color: var(--text-tertiary);
  font-size: 0.82rem;
  gap: 0.6rem;
}
</style>
