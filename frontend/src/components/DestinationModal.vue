<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="dm-overlay" @click.self="$emit('close')">
        <div class="dm-modal">
          <div class="dm-header">
            <div class="dm-header-left">
              <Navigation :size="16" class="dm-header-icon" />
              <span class="dm-title">Send Destination</span>
            </div>
            <button class="dm-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="dm-body">
            <!-- Map -->
            <div ref="mapWrapper" class="dm-map-wrapper">
              <div ref="mapEl" class="dm-map-container" />
              <!-- Locate me button -->
              <button class="dm-locate-btn" @click="requestDeviceLocation" :disabled="locatingDevice" title="Find my location">
                <Crosshair :size="16" :class="{ spinning: locatingDevice }" />
              </button>
              <div class="dm-map-legend">
                <span class="dm-legend-item"><span class="dm-legend-dot vehicle" /> Vehicle</span>
                <span class="dm-legend-item"><span class="dm-legend-dot device" /> You</span>
                <span v-if="destination" class="dm-legend-item"><span class="dm-legend-dot dest" /> Dest.</span>
              </div>
            </div>

            <p class="dm-hint">Tap the map to select a destination, or enter it manually.</p>

            <!-- Form -->
            <div class="dm-form">
              <input v-model="destAddress" class="dm-input" placeholder="Address (optional)" />
              <input v-model="destName" class="dm-input" placeholder="Name (optional)" />
              <div class="dm-coords-row">
                <input v-model.number="destLat" class="dm-input dm-coord" type="number" step="any" placeholder="Latitude" />
                <input v-model.number="destLng" class="dm-input dm-coord" type="number" step="any" placeholder="Longitude" />
              </div>
              <button
                class="dm-send-btn"
                :disabled="!canSend || sending"
                @click="doSend"
              >
                <Loader v-if="sending" :size="14" class="spinning" />
                <Navigation v-else :size="14" />
                <span>{{ sending ? 'Sending...' : 'Send to Vehicle' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { accentHex } from '../utils/theme'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Navigation, Loader, Crosshair } from 'lucide-vue-next'

const props = defineProps({
  visible: { type: Boolean, default: false },
  location: { type: Object, default: () => ({}) },
  vehicle: { type: Object, required: true },
})

const emit = defineEmits(['close', 'sent'])

const store = useAppStore()
const { toast } = useToast()

const mapEl = ref(null)
const mapWrapper = ref(null)
let map = null
let tileLayer = null
let vehicleMarker = null
let deviceMarker = null
let destMarker = null

const destination = ref(null)
const destAddress = ref('')
const destName = ref('')
const destLat = ref(null)
const destLng = ref(null)
const sending = ref(false)
const locatingDevice = ref(false)

const vehicleLat = computed(() => props.location?.latitude || 0)
const vehicleLng = computed(() => props.location?.longitude || 0)
const hasVehicleLocation = computed(() => !!(props.location?.latitude && props.location?.longitude))

const canSend = computed(() =>
  destLat.value != null && destLng.value != null
)

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

const vehicleIcon = createIcon(accentHex(), '🚗')
const deviceIcon = createIcon('#00e676', '📍')
const destIcon = createIcon('#ff7043', '🎯')

function initMap() {
  if (!mapEl.value || map) return

  const center = hasVehicleLocation.value
    ? [vehicleLat.value, vehicleLng.value]
    : [45.4642, 9.1900]

  map = L.map(mapEl.value, {
    center,
    zoom: 14,
    zoomControl: false,
    attributionControl: false,
  })

  const isLight = document.documentElement.getAttribute('data-theme') === 'light'
  const tileUrl = isLight
    ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
  tileLayer = L.tileLayer(tileUrl, { maxZoom: 19, subdomains: 'abcd' }).addTo(map)

  L.control.zoom({ position: 'topright' }).addTo(map)

  if (hasVehicleLocation.value) {
    vehicleMarker = L.marker([vehicleLat.value, vehicleLng.value], { icon: vehicleIcon })
      .addTo(map)
      .bindPopup(`<b>Vehicle</b><br>${props.vehicle.vehicle_nickname || props.vehicle.car_type || 'Leapmotor'}`)
  }

  map.on('click', onMapClick)
}

function destroyMap() {
  if (map) {
    map.remove()
    map = null
    tileLayer = null
    vehicleMarker = null
    deviceMarker = null
    destMarker = null
  }
}

function onMapClick(e) {
  const { lat, lng } = e.latlng
  destLat.value = parseFloat(lat.toFixed(6))
  destLng.value = parseFloat(lng.toFixed(6))
  destination.value = { lat, lng }

  if (destMarker) {
    destMarker.setLatLng([lat, lng])
  } else {
    destMarker = L.marker([lat, lng], { icon: destIcon })
      .addTo(map)
      .bindPopup('Selected destination')
    destMarker.openPopup()
  }

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
    // User can type manually
  }
}

function requestDeviceLocation() {
  if (!navigator.geolocation) {
    toast('Geolocation is not supported by this browser', 'error')
    return
  }
  if (!window.isSecureContext) {
    toast('Geolocation requires HTTPS', 'error')
    return
  }

  locatingDevice.value = true
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      locatingDevice.value = false
      const { latitude, longitude } = pos.coords
      if (map) {
        if (deviceMarker) {
          deviceMarker.setLatLng([latitude, longitude])
        } else {
          deviceMarker = L.marker([latitude, longitude], { icon: deviceIcon })
            .addTo(map)
            .bindPopup('<b>Your location</b>')
        }
        if (hasVehicleLocation.value) {
          const bounds = L.latLngBounds(
            [vehicleLat.value, vehicleLng.value],
            [latitude, longitude]
          )
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 })
        } else {
          map.setView([latitude, longitude], 14)
        }
      }
    },
    (err) => {
      locatingDevice.value = false
      if (err.code === err.PERMISSION_DENIED) {
        toast('Location permission denied', 'error')
      } else {
        toast('Could not get location', 'error')
      }
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
  )
}

async function doSend() {
  sending.value = true
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
    if (destMarker && map) {
      map.removeLayer(destMarker)
      destMarker = null
    }
    destination.value = null
    emit('sent')
    emit('close')
  } catch (err) {
    toast(`Send destination failed: ${err.message}`, 'error')
  } finally {
    sending.value = false
  }
}

// Init/destroy map when modal opens/closes
watch(() => props.visible, async (v) => {
  if (v) {
    destAddress.value = ''
    destName.value = ''
    destLat.value = null
    destLng.value = null
    destination.value = null
    await nextTick()
    initMap()
    // Leaflet needs a tick to measure container
    setTimeout(() => { if (map) map.invalidateSize() }, 100)
  } else {
    destroyMap()
  }
})

// Theme change
watch(() => store.theme, () => {
  if (!map || !tileLayer) return
  map.removeLayer(tileLayer)
  const isLight = document.documentElement.getAttribute('data-theme') === 'light'
  const tileUrl = isLight
    ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
  tileLayer = L.tileLayer(tileUrl, { maxZoom: 19, subdomains: 'abcd' }).addTo(map)
})

onBeforeUnmount(() => { destroyMap() })
</script>

<style scoped>
.dm-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(6px);
}
.dm-modal {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  width: 100%;
  max-width: 480px;
  margin: 0 12px;
  max-height: 90vh;
  max-height: 90dvh;
  overflow-y: auto;
  animation: dm-slideup 0.2s ease;
}
@keyframes dm-slideup {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.dm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 0;
}
.dm-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dm-header-icon { color: #ff7043; }
.dm-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--heading);
}
.dm-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 22px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.dm-close:hover { color: var(--text); }
.dm-body {
  padding: 14px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dm-map-wrapper {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  height: 220px;
}
@media (min-width: 640px) {
  .dm-map-wrapper { height: 260px; }
}
.dm-map-container {
  width: 100%;
  height: 100%;
}
.dm-locate-btn {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 1000;
  width: 32px;
  height: 32px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #00e676;
  transition: all 0.2s;
  box-shadow: var(--shadow-card);
}
.dm-locate-btn:hover:not(:disabled) {
  background: var(--elevated);
  color: #00ff88;
}
.dm-locate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.dm-locate-btn .spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.dm-map-legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 1000;
  display: flex;
  gap: 10px;
  background: var(--card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 11px;
  color: var(--sub);
}
.dm-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dm-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dm-legend-dot.vehicle { background: var(--accent); box-shadow: 0 0 4px var(--accent); }
.dm-legend-dot.device { background: #00e676; box-shadow: 0 0 4px #00e676; }
.dm-legend-dot.dest { background: #ff7043; box-shadow: 0 0 4px #ff7043; }
.dm-hint {
  font-size: 11px;
  color: var(--muted2);
  line-height: 1.4;
}
.dm-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dm-input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.dm-input:focus { border-color: var(--accent); }
.dm-input::placeholder { color: var(--muted2); }
.dm-coords-row { display: flex; gap: 8px; }
.dm-coord { flex: 1; }
.dm-send-btn {
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
.dm-send-btn:hover:not(:disabled) { background: linear-gradient(135deg, #ff704333, #ff704355); }
.dm-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Transitions */
.modal-enter-active, .modal-leave-active { transition: opacity 0.15s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
