<template>
  <div class="card card-half">
    <div class="card-header">
      <div class="card-title">
        <div class="card-title-icon" style="background:rgba(0,210,230,0.1);color:var(--accent)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
        </div>
        Location
      </div>
    </div>
    <div class="card-body">
      <template v-if="hasLocation">
        <div class="map-container">
          <iframe
            :src="mapUrl"
            loading="lazy"
          ></iframe>
        </div>
        <div class="map-coords">
          <div class="map-coord">Lat: <span>{{ location.latitude.toFixed(6) }}</span></div>
          <div class="map-coord">Lng: <span>{{ location.longitude.toFixed(6) }}</span></div>
        </div>
      </template>
      <div v-else class="no-location">Location data unavailable</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  location: { type: Object, default: () => ({}) },
})

const hasLocation = computed(() => props.location.latitude && props.location.longitude)

const mapUrl = computed(() => {
  const lat = props.location.latitude
  const lng = props.location.longitude
  return `https://www.openstreetmap.org/export/embed.html?bbox=${lng - 0.005},${lat - 0.003},${lng + 0.005},${lat + 0.003}&layer=mapnik&marker=${lat},${lng}`
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 260px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-elevated);
  position: relative;
}
.map-container iframe {
  width: 100%;
  height: 100%;
  border: none;
  filter: invert(0.9) hue-rotate(180deg) brightness(0.8) contrast(1.2);
}

.map-coords {
  display: flex;
  gap: 1.5rem;
  margin-top: 0.8rem;
}
.map-coord {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
}
.map-coord span { color: var(--text-accent); }

.no-location {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-tertiary);
  font-size: 0.85rem;
}
</style>
