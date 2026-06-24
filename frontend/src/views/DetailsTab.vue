<template>
  <div class="details-grid">
    <!-- Doors & Windows -->
    <SectionCard title="Doors & Windows" :icon="DoorOpen">
      <InfoRow label="Vehicle Lock" :value="doors.is_locked === true ? 'Locked' : doors.is_locked === false ? 'Unlocked' : '—'" :color="doors.is_locked === true ? '#00e676' : '#ffab40'" :dot="doors.is_locked != null" />
      <InfoRow label="Driver Door" :value="doorText(doors.lbcm_driver_door_status)" :color="doorColor(doors.lbcm_driver_door_status)" />
      <InfoRow label="Passenger Door" :value="doorText(doors.rbcm_driver_door_status)" :color="doorColor(doors.rbcm_driver_door_status)" />
      <InfoRow label="Left Rear" :value="doorText(doors.lbcm_left_rear_door_status)" :color="doorColor(doors.lbcm_left_rear_door_status)" />
      <InfoRow label="Right Rear" :value="doorText(doors.rbcm_right_rear_door_status)" :color="doorColor(doors.rbcm_right_rear_door_status)" />
      <InfoRow label="Trunk" :value="doorText(doors.bbcm_back_door_status)" :color="doorColor(doors.bbcm_back_door_status)" />
      <div class="section-divider" />
      <InfoRow label="LF Window" :value="winText(windows.left_front_window_percent)" :color="winColor(windows.left_front_window_percent)" />
      <InfoRow label="RF Window" :value="winText(windows.right_front_window_percent)" :color="winColor(windows.right_front_window_percent)" />
      <InfoRow label="LR Window" :value="winText(windows.left_rear_window_percent)" :color="winColor(windows.left_rear_window_percent)" />
      <InfoRow label="RR Window" :value="winText(windows.right_rear_window_percent)" :color="winColor(windows.right_rear_window_percent)" />
      <InfoRow label="Sun Shade" :value="sunShadeText" :color="windows.sun_shade > 0 ? '#ffab40' : 'var(--muted)'" />
    </SectionCard>

    <!-- Climate -->
    <SectionCard title="Climate" :icon="Thermometer">
      <InfoRow label="A/C" :value="climate.ac_switch ? 'On' : 'Off'" :color="climate.ac_switch ? 'var(--accent)' : 'var(--muted)'" :dot="!!climate.ac_switch" />
      <InfoRow label="Set Temperature" :value="climate.ac_setting != null ? `${climate.ac_setting}°C` : '—'" color="var(--text)" />
      <InfoRow v-if="climate.ac_setting_right != null" label="Right Temp" :value="`${climate.ac_setting_right}°C`" color="var(--text)" />
      <InfoRow v-if="climate.interior_temp != null" label="Interior Temp" :value="`${climate.interior_temp}°C`" color="var(--sub)" />
      <InfoRow label="Outside Temperature" :value="climate.outdoor_temp != null ? `${climate.outdoor_temp}°C` : '—'" color="var(--sub)" />
      <InfoRow label="Fan Volume" :value="climate.ac_air_volume ?? '—'" color="var(--text)" />
      <InfoRow label="Mode" :value="climateMode(climate.ac_cooling_and_heating)" :color="climate.ac_cooling_and_heating ? 'var(--accent)' : 'var(--muted)'" />
      <InfoRow label="Air Circulation" :value="climate.ac_circle_mode != null ? (climate.ac_circle_mode ? 'Recirculate' : 'Fresh') : '—'" color="var(--sub)" />
      <InfoRow v-if="climate.recirculation_mode != null" label="Recirculation" :value="climate.recirculation_mode === 0 ? 'Fresh Air' : 'Recirculation'" color="var(--sub)" />
      <InfoRow v-if="climate.windshield_defrost != null" label="Windshield Defrost" :value="climate.windshield_defrost > 0 ? 'Active' : 'Off'" :color="climate.windshield_defrost > 0 ? '#ff9100' : 'var(--muted)'" />
      <InfoRow v-if="climate.rear_window_heating != null" label="Rear Window Heat" :value="climate.rear_window_heating ? 'On' : 'Off'" :color="climate.rear_window_heating ? '#ff9100' : 'var(--muted)'" />
      <InfoRow v-if="climate.ac_operate_mode != null" label="Operate Mode" :value="climate.ac_operate_mode === 0 ? 'Auto' : 'Manual'" color="var(--sub)" />
      <InfoRow v-if="climate.climate_mode != null" label="Climate Mode" :value="climate.climate_mode === 0 ? 'Off' : climate.climate_mode === 1 ? 'Fast Cool' : climate.climate_mode === 3 ? 'Fast Heat' : `${climate.climate_mode}`" color="var(--sub)" />
      <!-- Temperature slider visual -->
      <div v-if="climate.ac_setting != null" class="temp-slider-visual">
        <div class="temp-slider-label">Set Temperature</div>
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
      <div class="tire-note">Pressure in bar · Optimal: 2.3 bar</div>
    </SectionCard>

    <!-- Battery & Charging -->
    <SectionCard title="Battery & Charging" :icon="Battery">
      <InfoRow label="State of Charge" :value="bat.soc != null ? `${bat.soc}%` : '—'" :color="bat.soc > 50 ? '#00e676' : bat.soc > 20 ? '#ffab40' : '#ff5252'" />
      <InfoRow label="Charging" :value="props.status?.is_charging === true ? 'Yes' : props.status?.is_charging === false ? 'No' : '—'" :color="props.status?.is_charging ? '#00e676' : 'var(--muted)'" :dot="!!props.status?.is_charging" />
      <InfoRow label="Plugged In" :value="props.status?.is_plugged === true ? 'Yes' : props.status?.is_plugged === false ? 'No' : '—'" :color="props.status?.is_plugged ? '#ffab40' : 'var(--muted)'" :dot="!!props.status?.is_plugged" />
      <InfoRow label="Discharging" :value="bat.is_discharging === true ? 'Yes' : bat.is_discharging === false ? 'No' : '—'" :color="bat.is_discharging ? '#ffab40' : 'var(--muted)'" />
      <InfoRow label="Regen Braking" :value="props.status?.is_regening === true ? 'Yes' : props.status?.is_regening === false ? 'No' : '—'" :color="props.status?.is_regening ? 'var(--accent)' : 'var(--muted)'" />
      <InfoRow label="Charge State" :value="bat.charge_state_label || '—'" :color="bat.charge_state != null && bat.charge_state > 0 ? '#00e676' : 'var(--muted)'" />
      <InfoRow label="Time Remaining" :value="props.status?.is_charging ? `${bat.charge_remain_time ?? '—'} min` : '—'" color="var(--text)" />
      <InfoRow label="Charge Limit" :value="bat.charge_soc_setting != null ? `${bat.charge_soc_setting}%` : '—'" color="var(--text)" />
      <InfoRow label="Battery Voltage" :value="bat.battery_voltage != null ? `${bat.battery_voltage} V` : '—'" color="var(--sub)" />
      <InfoRow label="Battery Current" :value="bat.battery_current != null ? `${bat.battery_current} A` : '—'" :color="bat.battery_current < 0 ? '#00e676' : '#ffab40'" />
      <InfoRow label="Battery Power" :value="bat.battery_power != null ? `${bat.battery_power} kW` : '—'" color="#ff9100" />
      <InfoRow label="Charging Power" :value="bat.charging_power_kw != null ? `${bat.charging_power_kw} kW` : '—'" color="#00e676" />
      <InfoRow label="Discharging Power" :value="bat.discharging_power_kw != null ? `${bat.discharging_power_kw} kW` : '—'" color="#ffab40" />
      <InfoRow label="Energy Available" :value="bat.dump_energy_kwh != null ? `${bat.dump_energy_kwh} kWh` : '—'" color="var(--accent)" />
      <InfoRow v-if="bat.precise_soc != null" label="Precise SoC" :value="`${bat.precise_soc}%`" color="var(--sub)" />
      <InfoRow v-if="bat.min_battery_temp != null" label="Min Battery Temp" :value="`${bat.min_battery_temp}°C`" color="var(--sub)" />
      <InfoRow v-if="bat.healthy_charge_enabled != null" label="Healthy Charge" :value="bat.healthy_charge_enabled ? 'Enabled' : 'Disabled'" :color="bat.healthy_charge_enabled ? '#00e676' : 'var(--muted)'" />
      <InfoRow v-if="bat.charge_completed != null" label="Charge Completed" :value="bat.charge_completed ? 'Yes' : 'No'" color="var(--sub)" />
      <div class="batt-bar">
        <div class="batt-bar-fill" :style="{ width: `${bat.soc ?? 0}%`, boxShadow: props.status?.is_charging ? '0 0 10px #00e67688' : 'none' }" />
      </div>
    </SectionCard>

    <!-- Charge Plan -->
    <SectionCard title="Charge Plan" :icon="BatteryCharging">
      <InfoRow label="Charge Limit" :value="chargePlan.soc_setting != null ? `${chargePlan.soc_setting}%` : '—'" color="var(--text)" />
      <InfoRow label="Scheduled" :value="chargePlan.enabled === 1 ? 'Enabled' : chargePlan.enabled === 0 ? 'Disabled' : '—'" :color="chargePlan.enabled === 1 ? '#00e676' : 'var(--muted)'" />
      <InfoRow label="Start Time" :value="chargePlan.start || '—'" color="var(--sub)" />
      <InfoRow label="End Time" :value="chargePlan.end || '—'" color="var(--sub)" />
      <InfoRow label="Cycles" :value="chargePlan.cycles || '—'" color="var(--sub)" />
      <InfoRow label="Recharge" :value="chargePlan.recharge != null ? (chargePlan.recharge ? 'Yes' : 'No') : '—'" color="var(--sub)" />
    </SectionCard>

    <!-- Seat Comfort -->
    <SectionCard title="Seat Comfort" :icon="Armchair">
      <InfoRow label="Driver Heat" :value="seatComfort.driver_seat_heating != null ? `Level ${seatComfort.driver_seat_heating}` : '—'" :color="seatComfort.driver_seat_heating > 0 ? '#ff9100' : 'var(--muted)'" />
      <InfoRow label="Driver Ventilation" :value="seatComfort.driver_seat_ventilation != null ? `Level ${seatComfort.driver_seat_ventilation}` : '—'" :color="seatComfort.driver_seat_ventilation > 0 ? 'var(--accent)' : 'var(--muted)'" />
      <InfoRow label="Passenger Heat" :value="seatComfort.passenger_seat_heating != null ? `Level ${seatComfort.passenger_seat_heating}` : '—'" :color="seatComfort.passenger_seat_heating > 0 ? '#ff9100' : 'var(--muted)'" />
      <InfoRow label="Passenger Ventilation" :value="seatComfort.passenger_seat_ventilation != null ? `Level ${seatComfort.passenger_seat_ventilation}` : '—'" :color="seatComfort.passenger_seat_ventilation > 0 ? 'var(--accent)' : 'var(--muted)'" />
      <InfoRow label="Steering Wheel Heat" :value="seatComfort.steering_wheel_heating != null ? (seatComfort.steering_wheel_heating ? 'On' : 'Off') : '—'" :color="seatComfort.steering_wheel_heating ? '#ff9100' : 'var(--muted)'" />
      <InfoRow v-if="seatComfort.steering_wheel_heater_minutes != null" label="SW Heat Remaining" :value="`${seatComfort.steering_wheel_heater_minutes} min`" color="var(--sub)" />
    </SectionCard>

    <!-- Security -->
    <SectionCard title="Security" :icon="ShieldCheck">
      <InfoRow label="Security Active" :value="security.is_security_active === true ? 'Yes' : security.is_security_active === false ? 'No' : '—'" :color="security.is_security_active ? '#00e676' : 'var(--muted)'" :dot="!!security.is_security_active" />
      <InfoRow label="Sentry Mode" :value="security.sentry_mode != null ? (security.sentry_mode ? 'On' : 'Off') : '—'" :color="security.sentry_mode ? '#00e676' : 'var(--muted)'" />
      <InfoRow label="Left Mirror Heat" :value="security.left_mirror_heating != null ? (security.left_mirror_heating ? 'On' : 'Off') : '—'" :color="security.left_mirror_heating ? '#ff9100' : 'var(--muted)'" />
      <InfoRow label="Right Mirror Heat" :value="security.right_mirror_heating != null ? (security.right_mirror_heating ? 'On' : 'Off') : '—'" :color="security.right_mirror_heating ? '#ff9100' : 'var(--muted)'" />
      <InfoRow label="Roof Opening" :value="security.roof_opening != null ? `${security.roof_opening}` : '—'" color="var(--sub)" />
    </SectionCard>

    <!-- Location -->
    <LocationCard :location="location" :vehicle="vehicle" />

    <!-- Connectivity -->
    <SectionCard title="Connectivity" :icon="Wifi">
      <InfoRow label="Bluetooth" :value="connectivity.bluetooth_state ? 'On' : connectivity.bluetooth_state === false ? 'Off' : '—'" :color="connectivity.bluetooth_state ? 'var(--accent)' : 'var(--muted)'" :dot="!!connectivity.bluetooth_state" />
      <InfoRow label="Wi-Fi Hotspot" :value="connectivity.hotspot_state ? 'On' : connectivity.hotspot_state === false ? 'Off' : '—'" :color="connectivity.hotspot_state ? '#00e676' : 'var(--muted)'" :dot="!!connectivity.hotspot_state" />
      <InfoRow label="Ignition ON1" :value="ignition.bcm_key_position_on1 != null ? (ignition.bcm_key_position_on1 ? 'Yes' : 'No') : '—'" :color="ignition.bcm_key_position_on1 ? '#00e676' : 'var(--muted)'" />
      <InfoRow v-if="ignition.bcm_key_position_on2 != null" label="Ignition ON2" :value="ignition.bcm_key_position_on2 ? 'Yes' : 'No'" :color="ignition.bcm_key_position_on2 ? '#00e676' : 'var(--muted)'" />
      <InfoRow label="Ignition ON3" :value="ignition.bcm_key_position_on3 != null ? (ignition.bcm_key_position_on3 ? 'Yes' : 'No') : '—'" :color="ignition.bcm_key_position_on3 ? '#00e676' : 'var(--muted)'" />
      <InfoRow label="Gear Status" :value="driving.gear_status != null ? gearLabel(driving.gear_status) : '—'" color="var(--text)" />
      <InfoRow v-if="driving.speed_limit != null" label="Speed Limit" :value="`${driving.speed_limit} km/h`" :color="driving.speed_limit_active ? '#ff5252' : 'var(--sub)'" />
      <InfoRow v-if="driving.parking_brake_state != null" label="Parking Brake" :value="driving.parking_brake_state ? 'Engaged' : 'Released'" :color="driving.parking_brake_state ? '#ffab40' : 'var(--muted)'" />
      <InfoRow v-if="driving.live_remaining_range != null" label="Live Range" :value="`${driving.live_remaining_range} km`" color="var(--sub)" />
      <InfoRow label="Last Update" :value="timestamps.collect_time ? formatTime(timestamps.collect_time) : '—'" color="#5c6478" />
    </SectionCard>

    <!-- Vehicle Info -->
    <SectionCard title="Vehicle Info" :icon="Info">
      <InfoRow label="VIN" color="var(--text)">
        <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
      </InfoRow>
      <InfoRow label="Model" :value="vehicle.car_type || '—'" color="var(--text)" />
      <InfoRow label="Nickname" :value="vehicle.vehicle_nickname || '—'" color="var(--accent)" />
      <InfoRow label="Plate Number" :value="vehicle.plate_number || '—'" color="var(--text)" />
      <InfoRow label="Color" :value="vehicle.out_color || '—'" color="var(--text)" />
      <InfoRow label="Year" :value="vehicle.year || '—'" color="var(--text)" />
      <InfoRow label="Seat Layout" :value="vehicle.seat_layout || '—'" color="var(--sub)" />
      <InfoRow label="Rudder" :value="vehicle.rudder || '—'" color="var(--sub)" />
      <InfoRow label="Shared Vehicle" :value="vehicle.is_shared ? 'Yes' : 'No'" :color="vehicle.is_shared ? '#00e676' : 'var(--muted)'" />
    </SectionCard>

    <!-- Mileage & Energy -->
    <SectionCard title="Mileage & Energy" :icon="Zap">
      <InfoRow label="Total Mileage" :value="driving.total_mileage != null ? `${driving.total_mileage.toLocaleString()} km` : '—'" color="#ffab40" />
      <InfoRow label="Total Mileage (mi)" :value="driving.total_mileage != null ? `${(driving.total_mileage * 0.621371).toFixed(1)} mi` : '—'" color="var(--sub)" />
      <InfoRow label="Energy Available" :value="bat.dump_energy_kwh != null ? `${bat.dump_energy_kwh} kWh` : '—'" color="var(--accent)" />
      <InfoRow v-if="mileage?.deliveryDays != null" label="Days Since Delivery" :value="mileage.deliveryDays" color="var(--text)" />
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
  DoorOpen, Thermometer, Circle, Battery, BatteryCharging,
  Wifi, Info, Zap, Armchair, ShieldCheck
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
const seatComfort = computed(() => props.status?.seat_comfort || {})
const security = computed(() => props.status?.security || {})
const chargePlan = computed(() => props.status?.battery?.charge_plan || {})

const tireItems = computed(() => {
  const t = props.status?.tires || {}
  return [
    { label: 'Front Left', value: t.front_left_bar },
    { label: 'Front Right', value: t.front_right_bar },
    { label: 'Rear Left', value: t.rear_left_bar },
    { label: 'Rear Right', value: t.rear_right_bar },
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
  return val > 0 ? '#ffab40' : 'var(--muted)'
}
function tireColor(val) {
  if (val == null) return 'var(--text)'
  return val < 2.0 ? '#ff5252' : val < 2.2 ? '#ffab40' : 'var(--text)'
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
  background: var(--elevated);
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
  background: linear-gradient(90deg, var(--accent), #00e676);
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
  background: var(--accent);
  border-radius: 50%;
  top: -4px;
  transition: left 0.4s;
  box-shadow: 0 0 8px var(--accent);
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
