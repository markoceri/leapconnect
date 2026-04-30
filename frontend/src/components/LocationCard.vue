<template>
  <div class="location-card">
    <div class="location-header">
      <MapPin :size="16" class="location-icon" />
      <span class="location-title">Location</span>
      <button class="expand-btn" @click="toggleFullscreen" :title="fullscreen ? 'Exit fullscreen' : 'Fullscreen map'">
        <Maximize2 v-if="!fullscreen" :size="14" />
        <Minimize2 v-else :size="14" />
      </button>
    </div>

    <!-- Map container -->
    <div
      ref="mapWrapper"
      class="map-wrapper"
      :class="{ fullscreen }"
    >
      <div ref="mapEl" class="map-container" />
      <!-- Fullscreen close button (inside map) -->
      <button v-if="fullscreen" class="fs-close-btn" @click="toggleFullscreen">
        <X :size="18" />
      </button>
      <!-- Legend overlay -->
      <div class="map-legend">
        <span class="legend-item"><span class="legend-dot vehicle" /> Vehicle</span>
        <span class="legend-item"><span class="legend-dot device" /> You</span>
        <span v-if="destination" class="legend-item"><span class="legend-dot dest" /> Dest.</span>
      </div>
    </div>

    <!-- Coordinates info -->
    <div class="coords-section">
      <div v-if="hasVehicleLocation" class="coord-row">
        <Car :size="14" class="coord-icon vehicle-color" />
        <span class="coord-label">Vehicle:</span>
        <span class="coord-value">{{ vehicleLat.toFixed(5) }}, {{ vehicleLng.toFixed(5) }}</span>
      </div>
      <div v-else class="coord-row muted">
        <Car :size="14" class="coord-icon" />
        <span class="coord-label">Vehicle: location unavailable</span>
      </div>
      <div v-if="deviceLocation" class="coord-row">
        <Smartphone :size="14" class="coord-icon device-color" />
        <span class="coord-label">You:</span>
        <span class="coord-value">{{ deviceLocation.lat.toFixed(5) }}, {{ deviceLocation.lng.toFixed(5) }}</span>
        <button class="locate-btn" @click="requestDeviceLocation">↻</button>
      </div>
      <div v-else class="coord-row muted">
        <Smartphone :size="14" class="coord-icon" />
        <span v-if="locatingDevice" class="coord-label">Locating...</span>
        <span v-else class="coord-label">{{ locationError || 'Device location unavailable' }}</span>
        <button class="locate-btn" @click="requestDeviceLocation" :disabled="locatingDevice">
          {{ locatingDevice ? '...' : 'Locate' }}
        </button>
      </div>
    </div>

    <!-- Send Destination -->
    <div class="dest-section">
      <div class="dest-header">
        <Navigation :size="14" class="dest-icon" />
        <span class="dest-title">Send Destination</span>
      </div>
      <p class="dest-hint">Tap the map to select a destination, or enter it manually.</p>
      <div class="dest-form">
        <input v-model="destAddress" class="dest-input" placeholder="Address" />
        <input v-model="destName" class="dest-input" placeholder="Name (optional)" />
        <div class="dest-coords-row">
          <input v-model.number="destLat" class="dest-input dest-coord" type="number" step="any" placeholder="Latitude" />
          <input v-model.number="destLng" class="dest-input dest-coord" type="number" step="any" placeholder="Longitude" />
        </div>
        <button class="dest-send-btn" :disabled="!canSendDest || sendingDest" @click="doSendDestination">
          <Loader v-if="sendingDest" :size="14" class="spinning" />
          <Navigation v-else :size="14" />
          <span>{{ sendingDest ? 'Sending...' : 'Send to Vehicle' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MapPin, Maximize2, Minimize2, X, Car, Smartphone, Navigation, Loader } from 'lucide-vue-next'

const props = defineProps({
  location: { type: Object, default: () => ({}) },
  vehicle: { type: Object, required: true },
})

const store = useAppStore()
const { toast } = useToast()

const mapEl = ref(null)
const mapWrapper = ref(null)
const fullscreen = ref(false)
let map = null
let vehicleMarker = null
let deviceMarker = null
let destMarker = null

const deviceLocation = ref(null)
const locatingDevice = ref(false)
const locationError = ref('')
const destination = ref(null)
const destAddress = ref('')
const destName = ref('')
const destLat = ref(null)
const destLng = ref(null)
const sendingDest = ref(false)

const vehicleLat = computed(() => props.location?.latitude || 0)
const vehicleLng = computed(() => props.location?.longitude || 0)
const hasVehicleLocation = computed(() => !!(props.location?.latitude && props.location?.longitude))

const canSendDest = computed(() =>
  destAddress.value.trim() && destLat.value != null && destLng.value != null
)

// --- Custom marker icons ---
function createIcon(color, emoji) {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      width:32px;height:32px;border-radius:50%;
      background:${color};border:2px solid ${color};
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 2px 8px ${color}88;font-size:14px;
    ">${emoji}</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
  })
}

const vehicleIcon = createIcon('#00d4ff', '🚗')
const deviceIcon = createIcon('#00e676', '📍')
const destIcon = createIcon('#ff7043', '🎯')

// --- Map initialization ---
function initMap() {
  if (!mapEl.value || map) return

  const center = hasVehicleLocation.value
    ? [vehicleLat.value, vehicleLng.value]
    : [45.4642, 9.1900] // Default Milan

  map = L.map(mapEl.value, {
    center,
    zoom: 14,
    zoomControl: false,
    attributionControl: false,
  })

  // Dark tile layer
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd',
  }).addTo(map)

  // Zoom control in top-right
  L.control.zoom({ position: 'topright' }).addTo(map)

  // Vehicle marker
  if (hasVehicleLocation.value) {
    vehicleMarker = L.marker([vehicleLat.value, vehicleLng.value], { icon: vehicleIcon })
      .addTo(map)
      .bindPopup(`<b>Vehicle</b><br>${props.vehicle.nickname || props.vehicle.car_type || 'Leapmotor'}`)
  }

  // Map click handler for destination
  map.on('click', onMapClick)

  // Request device location automatically
  requestDeviceLocation()
}

function onMapClick(e) {
  const { lat, lng } = e.latlng
  destLat.value = parseFloat(lat.toFixed(6))
  destLng.value = parseFloat(lng.toFixed(6))
  destination.value = { lat, lng }

  // Place/move destination marker
  if (destMarker) {
    destMarker.setLatLng([lat, lng])
  } else {
    destMarker = L.marker([lat, lng], { icon: destIcon })
      .addTo(map)
      .bindPopup('Selected destination')
    destMarker.openPopup()
  }

  // Reverse geocode
  reverseGeocode(lat, lng)
}

async function reverseGeocode(lat, lng) {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
      { headers: { 'Accept-Language': 'en' } }
    )
    const data = await res.json()
    if (data.display_name) {
      destAddress.value = data.display_name
      destName.value = data.address?.road || data.address?.suburb || ''
    }
  } catch {
    // Geocoding failed, user can type manually
  }
}

function requestDeviceLocation() {
  if (!navigator.geolocation) {
    locationError.value = 'Geolocation not supported'
    toast('Geolocation is not supported by this browser', 'error')
    return
  }

  // Check if we're on a secure context (HTTPS or localhost)
  if (!window.isSecureContext) {
    locationError.value = 'Requires HTTPS'
    toast('Geolocation requires HTTPS. Try accessing via https:// or localhost', 'error')
    return
  }

  locatingDevice.value = true
  locationError.value = ''

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      locatingDevice.value = false
      const { latitude, longitude } = pos.coords
      deviceLocation.value = { lat: latitude, lng: longitude }
      if (map) {
        if (deviceMarker) {
          deviceMarker.setLatLng([latitude, longitude])
        } else {
          deviceMarker = L.marker([latitude, longitude], { icon: deviceIcon })
            .addTo(map)
            .bindPopup('<b>Your location</b>')
        }

        // Fit bounds to show both markers
        if (hasVehicleLocation.value) {
          const bounds = L.latLngBounds(
            [vehicleLat.value, vehicleLng.value],
            [latitude, longitude]
          )
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 })
        }
      }
    },
    (err) => {
      locatingDevice.value = false
      switch (err.code) {
        case err.PERMISSION_DENIED:
          locationError.value = 'Permission denied'
          toast('Location permission denied. Allow it in browser settings.', 'error')
          break
        case err.POSITION_UNAVAILABLE:
          locationError.value = 'Position unavailable'
          toast('Could not determine your position', 'error')
          break
        case err.TIMEOUT:
          locationError.value = 'Request timed out'
          toast('Location request timed out, try again', 'error')
          break
        default:
          locationError.value = 'Unknown error'
          toast('Could not get location', 'error')
      }
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
  )
}

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
  nextTick(() => {
    if (map) map.invalidateSize()
  })
}

// Watch for vehicle location changes
watch(() => props.location, (loc) => {
  if (map && loc?.latitude && loc?.longitude) {
    const pos = [loc.latitude, loc.longitude]
    if (vehicleMarker) {
      vehicleMarker.setLatLng(pos)
    } else {
      vehicleMarker = L.marker(pos, { icon: vehicleIcon })
        .addTo(map)
        .bindPopup(`<b>Vehicle</b><br>${props.vehicle.nickname || props.vehicle.car_type || 'Leapmotor'}`)
    }
    map.setView(pos, map.getZoom())
  }
}, { deep: true })

async function doSendDestination() {
  sendingDest.value = true
  try {
    await store.sendDestination(props.vehicle.vin, {
      address: destAddress.value.trim(),
      address_name: destName.value.trim() || destAddress.value.trim(),
      latitude: destLat.value,
      longitude: destLng.value,
    })
    toast('Destination sent to vehicle', 'success')
    destAddress.value = ''
    destName.value = ''
    destLat.value = null
    destLng.value = null
    if (destMarker) {
      map.removeLayer(destMarker)
      destMarker = null
    }
    destination.value = null
  } catch (err) {
    toast(`Send destination failed: ${err.message}`, 'error')
  } finally {
    sendingDest.value = false
  }
}

onMounted(() => { nextTick(initMap) })
onBeforeUnmount(() => {
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<style scoped>
.location-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  overflow: hidden;
}
@media (min-width: 640px) {
  .location-card { padding: 18px 20px; }
}

.location-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.location-icon { color: var(--muted3); }
.location-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--heading);
  flex: 1;
}
.expand-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px;
  color: var(--muted3);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
}
.expand-btn:hover { color: var(--cyan); border-color: #00d4ff44; }

/* Map */
.map-wrapper {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  height: 220px;
  transition: all 0.3s ease;
  z-index: 0;
}
@media (min-width: 640px) {
  .map-wrapper { height: 260px; }
}
.map-wrapper.fullscreen {
  position: fixed;
  inset: 0;
  z-index: 5000;
  border-radius: 0;
  border: none;
  height: 100vh;
  height: 100dvh;
}
.map-container {
  width: 100%;
  height: 100%;
}
.fs-close-btn {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 5001;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.fs-close-btn:hover { border-color: #00d4ff44; }

.map-legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 1000;
  display: flex;
  gap: 10px;
  background: rgba(13, 16, 24, 0.85);
  backdrop-filter: blur(6px);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 11px;
  color: var(--sub);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.legend-dot.vehicle { background: #00d4ff; box-shadow: 0 0 4px #00d4ff; }
.legend-dot.device { background: #00e676; box-shadow: 0 0 4px #00e676; }
.legend-dot.dest { background: #ff7043; box-shadow: 0 0 4px #ff7043; }

/* Coordinates */
.coords-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.coord-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--sub);
}
.coord-row.muted { color: var(--muted2); }
.coord-icon { flex-shrink: 0; }
.vehicle-color { color: #00d4ff; }
.device-color { color: #00e676; }
.coord-label { font-weight: 500; }
.coord-value { font-family: var(--mono); color: var(--text); font-size: 11px; }
.locate-btn {
  margin-left: auto;
  background: none;
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 2px 8px;
  font-size: 10px;
  color: var(--cyan);
  cursor: pointer;
  transition: all 0.2s;
}
.locate-btn:hover { border-color: #00d4ff44; }

/* Destination */
.dest-section {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
.dest-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.dest-icon { color: #ff7043; }
.dest-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--heading);
}
.dest-hint {
  font-size: 11px;
  color: var(--muted2);
  margin-bottom: 10px;
  line-height: 1.4;
}
.dest-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dest-input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.dest-input:focus { border-color: #00d4ff; }
.dest-input::placeholder { color: var(--muted2); }
.dest-coords-row { display: flex; gap: 8px; }
.dest-coord { flex: 1; }
.dest-send-btn {
  margin-top: 4px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #ff704322, #ff704344);
  border: 1px solid #ff704355;
  border-radius: 8px;
  color: #ff7043;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.dest-send-btn:hover:not(:disabled) { background: linear-gradient(135deg, #ff704333, #ff704355); }
.dest-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>

<style>
/* Global leaflet overrides for dark theme */
.leaflet-container {
  background: #0d1018 !important;
  font-family: var(--font) !important;
}
.leaflet-control-zoom a {
  background: #111420 !important;
  color: #e2e6f0 !important;
  border-color: #1c2135 !important;
}
.leaflet-control-zoom a:hover {
  background: #1c2240 !important;
}
.leaflet-popup-content-wrapper {
  background: #111420 !important;
  color: #e2e6f0 !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
}
.leaflet-popup-tip {
  background: #111420 !important;
}
.leaflet-popup-close-button {
  color: #5c6478 !important;
}
.custom-marker {
  background: none !important;
  border: none !important;
}
</style>
