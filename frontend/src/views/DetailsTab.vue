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
      <InfoRow label="Discharging" :value="bat.is_discharging === true ? 'Yes' : bat.is_discharging === false ? 'No' : '—'" :color="bat.is_discharging ? '#ffab40' : '#5c6478'" />
      <InfoRow label="Regen Braking" :value="props.status?.is_regening === true ? 'Yes' : props.status?.is_regening === false ? 'No' : '—'" :color="props.status?.is_regening ? '#00d4ff' : '#5c6478'" />
      <InfoRow label="Charge State" :value="bat.charge_state_label || '—'" :color="bat.charge_state != null && bat.charge_state > 0 ? '#00e676' : '#5c6478'" />
      <InfoRow label="Time Remaining" :value="bat.is_charging ? `${bat.charge_remain_time ?? '—'} min` : '—'" color="#e2e6f0" />
      <InfoRow label="Charge Limit" :value="bat.charge_soc_setting != null ? `${bat.charge_soc_setting}%` : '—'" color="#e2e6f0" />
      <InfoRow label="Battery Voltage" :value="bat.battery_voltage != null ? `${bat.battery_voltage} V` : '—'" color="#8892a8" />
      <InfoRow label="Battery Current" :value="bat.battery_current != null ? `${bat.battery_current} A` : '—'" :color="bat.battery_current < 0 ? '#00e676' : '#ffab40'" />
      <InfoRow label="Battery Power" :value="bat.battery_power != null ? `${bat.battery_power} kW` : '—'" color="#ff9100" />
      <InfoRow label="Charging Power" :value="bat.charging_power_kw != null ? `${bat.charging_power_kw} kW` : '—'" color="#00e676" />
      <InfoRow label="Discharging Power" :value="bat.discharging_power_kw != null ? `${bat.discharging_power_kw} kW` : '—'" color="#ffab40" />
      <InfoRow label="Energy Available" :value="bat.dump_energy != null ? `${bat.dump_energy} kWh` : '—'" color="#00d4ff" />
      <div class="batt-bar">
        <div class="batt-bar-fill" :style="{ width: `${bat.soc ?? 0}%`, boxShadow: bat.is_charging ? '0 0 10px #00e67688' : 'none' }" />
      </div>
    </SectionCard>

    <!-- Location -->
    <LocationCard :location="location" :vehicle="vehicle" />

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
      <InfoRow label="Plate Number" :value="vehicle.plate_number || '—'" color="#e2e6f0" />
      <InfoRow label="Color" :value="vehicle.out_color || '—'" color="#e2e6f0" />
      <InfoRow label="Year" :value="vehicle.year || '—'" color="#e2e6f0" />
      <InfoRow label="Seat Layout" :value="vehicle.seat_layout || '—'" color="#8892a8" />
      <InfoRow label="Rudder" :value="vehicle.rudder || '—'" color="#8892a8" />
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
import { computed } from 'vue'
import { gearLabel, formatTime, climateMode } from '../utils/formatters'
import SectionCard from '../components/SectionCard.vue'
import InfoRow from '../components/InfoRow.vue'
import LocationCard from '../components/LocationCard.vue'
import {
  DoorOpen, Thermometer, Circle, Battery,
  Wifi, Info, Zap
} from 'lucide-vue-next'

const props = defineProps({
  vehicle: { type: Object, required: true },
  status: { type: Object, required: true },
  mileage: { type: Object, default: null },
})

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
</script>

<style scoped>
.details-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  max-width: 100%;
  overflow: hidden;
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


</style>
