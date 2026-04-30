<template>
  <div class="details-grid">
    <!-- Doors & Windows -->
    <SectionCard title="Doors & Windows" :icon="DoorOpen">
      <InfoRow label="Vehicle Lock" :value="doors.is_locked === true ? 'Locked' : doors.is_locked === false ? 'Unlocked' : '—'" :color="doors.is_locked === true ? '#00e676' : '#ffab40'" :dot="doors.is_locked != null" />
      <InfoRow label="Driver Door" :value="doorText(doors.driver_door)" :color="doorColor(doors.driver_door)" />
      <InfoRow label="Passenger Door" :value="doorText(doors.passenger_door)" :color="doorColor(doors.passenger_door)" />
      <InfoRow label="Left Rear" :value="doorText(doors.left_rear)" :color="doorColor(doors.left_rear)" />
      <InfoRow label="Right Rear" :value="doorText(doors.right_rear)" :color="doorColor(doors.right_rear)" />
      <InfoRow label="Trunk" :value="doorText(doors.trunk)" :color="doorColor(doors.trunk)" />
      <div class="section-divider" />
      <InfoRow label="LF Window" :value="winText(windows.left_front_percent)" :color="winColor(windows.left_front_percent)" />
      <InfoRow label="RF Window" :value="winText(windows.right_front_percent)" :color="winColor(windows.right_front_percent)" />
      <InfoRow label="LR Window" :value="winText(windows.left_rear_percent)" :color="winColor(windows.left_rear_percent)" />
      <InfoRow label="RR Window" :value="winText(windows.right_rear_percent)" :color="winColor(windows.right_rear_percent)" />
      <InfoRow label="Sun Shade" :value="sunShadeText" :color="windows.sun_shade > 0 ? '#ffab40' : '#5c6478'" />
    </SectionCard>

    <!-- Climate -->
    <SectionCard title="Climate" :icon="Thermometer">
      <InfoRow label="A/C" :value="climate.ac_switch ? 'On' : 'Off'" :color="climate.ac_switch ? '#00d4ff' : '#5c6478'" :dot="!!climate.ac_switch" />
      <InfoRow label="Set Temperature" :value="climate.ac_setting != null ? `${climate.ac_setting}°C` : '—'" color="#e2e6f0" />
      <InfoRow label="Outside Temperature" :value="climate.outdoor_temp != null ? `${climate.outdoor_temp}°C` : '—'" color="#8892a8" />
      <InfoRow label="Fan Volume" :value="climate.ac_air_volume ?? '—'" color="#e2e6f0" />
      <InfoRow label="Mode" :value="climateMode(climate.ac_cooling_and_heating)" :color="climate.ac_cooling_and_heating ? '#00d4ff' : '#5c6478'" />
      <InfoRow label="Air Circulation" :value="climate.ac_circle_mode != null ? (climate.ac_circle_mode ? 'Recirculate' : 'Fresh') : '—'" color="#8892a8" />
      <!-- Temperature slider visual -->
      <div v-if="climate.ac_setting != null" class="temp-slider-visual">
        <div class="temp-slider-label">Temperatura impostata</div>
        <div class="temp-slider-track">
          <div class="temp-slider-knob" :style="{ left: `${((climate.ac_setting - 16) / (30 - 16)) * 100}%` }" />
        </div>
        <div class="temp-slider-range"><span>16°C</span><span>30°C</span></div>
      </div>
    </SectionCard>

    <!-- Tire Pressure -->
    <SectionCard title="Tire Pressure" :icon="Circle">
      <div class="tire-grid">
        <div v-for="t in tireItems" :key="t.label" class="tire-item">
          <div class="tire-value" :style="{ color: tireColor(t.value) }">{{ t.value != null ? t.value.toFixed(1) : '—' }}</div>
          <div class="tire-label">{{ t.label }}</div>
        </div>
      </div>
      <div class="tire-note">Pressione in bar · Ottimale: 2.3 bar</div>
    </SectionCard>

    <!-- Battery & Charging -->
    <SectionCard title="Battery & Charging" :icon="Battery">
      <InfoRow label="State of Charge" :value="bat.soc != null ? `${bat.soc}%` : '—'" :color="bat.soc > 50 ? '#00e676' : bat.soc > 20 ? '#ffab40' : '#ff5252'" />
      <InfoRow label="Charging" :value="bat.is_charging === true ? 'Yes' : bat.is_charging === false ? 'No' : '—'" :color="bat.is_charging ? '#00e676' : '#5c6478'" :dot="!!bat.is_charging" />
      <InfoRow label="Time Remaining" :value="bat.is_charging ? `${bat.charge_remain_time ?? '—'} min` : '—'" color="#e2e6f0" />
      <InfoRow label="Charge Limit" :value="bat.charge_soc_setting != null ? `${bat.charge_soc_setting}%` : '—'" color="#e2e6f0" />
      <InfoRow label="Battery Voltage" :value="bat.battery_voltage != null ? `${bat.battery_voltage} V` : '—'" color="#8892a8" />
      <InfoRow label="Battery Current" :value="bat.battery_current != null ? `${bat.battery_current} A` : '—'" :color="bat.battery_current < 0 ? '#00e676' : '#ffab40'" />
      <InfoRow label="Battery Power" :value="bat.battery_power != null ? `${bat.battery_power} kW` : '—'" color="#ff9100" />
      <InfoRow label="Charging Power" :value="bat.charging_power_kw != null ? `${bat.charging_power_kw} kW` : '—'" color="#00e676" />
      <InfoRow label="Energy Available" :value="bat.dump_energy != null ? `${bat.dump_energy} kWh` : '—'" color="#00d4ff" />
      <div class="batt-bar">
        <div class="batt-bar-fill" :style="{ width: `${bat.soc ?? 0}%`, boxShadow: bat.is_charging ? '0 0 10px #00e67688' : 'none' }" />
      </div>
    </SectionCard>

    <!-- Location -->
    <SectionCard title="Location" :icon="MapPin">
      <template v-if="hasLocation">
        <div class="map-frame">
          <iframe :src="mapUrl" title="Posizione veicolo" loading="lazy" />
        </div>
        <div class="map-coords">
          <span class="map-coord">Lat: <span class="coord-val">{{ location.latitude.toFixed(6) }}</span></span>
          <span class="map-coord">Lng: <span class="coord-val">{{ location.longitude.toFixed(6) }}</span></span>
        </div>
      </template>
      <div v-else class="no-data">Location data unavailable</div>

      <!-- Send Destination -->
      <div class="send-dest-section">
        <div class="send-dest-title">Send Destination</div>
        <div class="send-dest-form">
          <input v-model="destAddress" class="dest-input" placeholder="Address" />
          <input v-model="destName" class="dest-input" placeholder="Name (optional)" />
          <div class="dest-coords-row">
            <input v-model.number="destLat" class="dest-input dest-coord" type="number" step="any" placeholder="Latitude" />
            <input v-model.number="destLng" class="dest-input dest-coord" type="number" step="any" placeholder="Longitude" />
          </div>
          <button class="dest-send-btn" :disabled="!canSendDest || sendingDest" @click="doSendDestination">
            <Loader v-if="sendingDest" :size="14" class="spinning" /> <span v-if="sendingDest">Sending...</span>
            <Navigation v-if="!sendingDest" :size="14" /> <span v-if="!sendingDest">Send to Vehicle</span>
          </button>
        </div>
      </div>
    </SectionCard>

    <!-- Connectivity -->
    <SectionCard title="Connectivity" :icon="Wifi">
      <InfoRow label="Bluetooth" :value="connectivity.bluetooth ? 'On' : connectivity.bluetooth === false ? 'Off' : '—'" :color="connectivity.bluetooth ? '#00d4ff' : '#5c6478'" :dot="!!connectivity.bluetooth" />
      <InfoRow label="Wi-Fi Hotspot" :value="connectivity.hotspot ? 'On' : connectivity.hotspot === false ? 'Off' : '—'" :color="connectivity.hotspot ? '#00e676' : '#5c6478'" :dot="!!connectivity.hotspot" />
      <InfoRow label="Ignition ON1" :value="ignition.on1 != null ? (ignition.on1 ? 'Yes' : 'No') : '—'" :color="ignition.on1 ? '#00e676' : '#5c6478'" />
      <InfoRow label="Ignition ON3" :value="ignition.on3 != null ? (ignition.on3 ? 'Yes' : 'No') : '—'" :color="ignition.on3 ? '#00e676' : '#5c6478'" />
      <InfoRow label="Gear Status" :value="driving.gear_status != null ? gearLabel(driving.gear_status) : '—'" color="#e2e6f0" />
      <InfoRow label="Last Update" :value="timestamps.collect_time ? formatTime(timestamps.collect_time) : '—'" color="#5c6478" />
    </SectionCard>

    <!-- Vehicle Info -->
    <SectionCard title="Vehicle Info" :icon="Info">
      <InfoRow label="VIN" color="#e2e6f0">
        <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
      </InfoRow>
      <InfoRow label="Model" :value="vehicle.car_type || '—'" color="#e2e6f0" />
      <InfoRow label="Nickname" :value="vehicle.nickname || '—'" color="#00d4ff" />
      <InfoRow label="Year" :value="vehicle.year || '—'" color="#e2e6f0" />
      <InfoRow label="Shared Vehicle" :value="vehicle.is_shared ? 'Yes' : 'No'" :color="vehicle.is_shared ? '#00e676' : '#5c6478'" />
    </SectionCard>

    <!-- Mileage & Energy -->
    <SectionCard title="Mileage & Energy" :icon="Zap">
      <InfoRow label="Total Mileage" :value="driving.total_mileage != null ? `${driving.total_mileage.toLocaleString()} km` : '—'" color="#ffab40" />
      <InfoRow label="Total Mileage (mi)" :value="driving.total_mileage != null ? `${(driving.total_mileage * 0.621371).toFixed(1)} mi` : '—'" color="#8892a8" />
      <InfoRow label="Energy Available" :value="bat.dump_energy != null ? `${bat.dump_energy} kWh` : '—'" color="#00d4ff" />
      <InfoRow v-if="mileage?.deliveryDays != null" label="Days Since Delivery" :value="mileage.deliveryDays" color="#e2e6f0" />
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import { gearLabel, formatTime, climateMode } from '../utils/formatters'
import SectionCard from '../components/SectionCard.vue'
import InfoRow from '../components/InfoRow.vue'
import {
  DoorOpen, Thermometer, Circle, Battery, MapPin,
  Wifi, Info, Zap, Loader, Navigation
} from 'lucide-vue-next'

const props = defineProps({
  vehicle: { type: Object, required: true },
  status: { type: Object, required: true },
  mileage: { type: Object, default: null },
})

const store = useAppStore()
const { toast } = useToast()

const doors = computed(() => props.status?.doors || {})
const windows = computed(() => props.status?.windows || {})
const climate = computed(() => props.status?.climate || {})
const bat = computed(() => props.status?.battery || {})
const location = computed(() => props.status?.location || {})
const connectivity = computed(() => props.status?.connectivity || {})
const ignition = computed(() => props.status?.ignition || {})
const driving = computed(() => props.status?.driving || {})
const timestamps = computed(() => props.status?.timestamps || {})

const tireItems = computed(() => {
  const t = props.status?.tires || {}
  return [
    { label: 'Front Left', value: t.front_left },
    { label: 'Front Right', value: t.front_right },
    { label: 'Rear Left', value: t.rear_left },
    { label: 'Rear Right', value: t.rear_right },
  ]
})

const hasLocation = computed(() => location.value.latitude && location.value.longitude)
const mapUrl = computed(() => {
  const lat = location.value.latitude
  const lng = location.value.longitude
  return `https://www.openstreetmap.org/export/embed.html?bbox=${lng - 0.01},${lat - 0.01},${lng + 0.01},${lat + 0.01}&layer=mapnik&marker=${lat},${lng}`
})

const sunShadeText = computed(() => {
  const v = windows.value.sun_shade
  if (v === 0) return '0'
  if (v === 1) return 'Open'
  if (v === 2) return 'Tilted'
  return v ?? '—'
})

function doorText(val) {
  if (val === true) return 'Open'
  if (val === false) return 'Closed'
  return '—'
}
function doorColor(val) {
  if (val === true) return '#ffab40'
  if (val === false) return '#00e676'
  return '#5c6478'
}
function winText(val) {
  return val != null ? `${val}%` : '—'
}
function winColor(val) {
  return val > 0 ? '#ffab40' : '#5c6478'
}
function tireColor(val) {
  if (val == null) return '#e2e6f0'
  return val < 2.0 ? '#ff5252' : val < 2.2 ? '#ffab40' : '#e2e6f0'
}

// --- Send Destination ---
const destAddress = ref('')
const destName = ref('')
const destLat = ref(null)
const destLng = ref(null)
const sendingDest = ref(false)

const canSendDest = computed(() =>
  destAddress.value.trim() && destLat.value != null && destLng.value != null
)

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
  } catch (err) {
    toast(`Send destination failed: ${err.message}`, 'error')
  } finally {
    sendingDest.value = false
  }
}
</script>

<style scoped>
.details-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
@media (min-width: 768px) {
  .details-grid { grid-template-columns: 1fr 1fr; }
}
.section-divider { height: 10px; }

/* Tire */
.tire-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 12px 0;
}
.tire-item { text-align: center; }
.tire-value { font-size: 22px; font-weight: 700; }
.tire-label {
  font-size: 10px;
  color: var(--muted);
  margin-top: 3px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.tire-note {
  text-align: center;
  font-size: 11px;
  color: var(--muted2);
  margin-top: 8px;
  padding: 8px;
  background: #0d1018;
  border-radius: 8px;
}

/* Battery bar */
.batt-bar {
  margin-top: 12px;
  height: 6px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.batt-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #00d4ff, #00e676);
  border-radius: 4px;
  transition: width 0.6s;
}

/* Map */
.map-frame {
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 10px;
  border: 1px solid var(--border);
}
.map-frame iframe {
  width: 100%;
  height: 200px;
  border: none;
  display: block;
  filter: invert(0.85) hue-rotate(180deg) saturate(0.8);
}
.map-coords {
  display: flex;
  gap: 16px;
  font-size: 12px;
}
.map-coord { color: var(--muted); }
.coord-val { color: #00d4ff; font-family: var(--mono); }

/* Temp slider visual */
.temp-slider-visual { margin-top: 14px; padding-top: 12px; }
.temp-slider-label {
  font-size: 10px;
  color: var(--muted2);
  margin-bottom: 8px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.temp-slider-track {
  position: relative;
  height: 4px;
  background: var(--border);
  border-radius: 4px;
}
.temp-slider-knob {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #00d4ff;
  border-radius: 50%;
  top: -4px;
  transition: left 0.4s;
  box-shadow: 0 0 8px #00d4ff;
}
.temp-slider-range {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 10px;
  color: var(--muted2);
}

.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  color: var(--muted);
  font-size: 13px;
}

/* Send Destination */
.send-dest-section {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.send-dest-title {
  font-size: 11px;
  color: var(--muted2);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.send-dest-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dest-input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--fg);
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}
.dest-input:focus { border-color: #00d4ff; }
.dest-coords-row { display: flex; gap: 8px; }
.dest-coord { flex: 1; }
.dest-send-btn {
  margin-top: 4px;
  padding: 8px 14px;
  background: linear-gradient(135deg, #00d4ff22, #00e67622);
  border: 1px solid #00d4ff44;
  border-radius: 8px;
  color: #00d4ff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.dest-send-btn:hover:not(:disabled) { background: linear-gradient(135deg, #00d4ff33, #00e67633); }
.dest-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }


</style>
