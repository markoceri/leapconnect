<template>
  <div class="dashboard-tab">
    <!-- Hero -->
    <div class="hero">
      <!-- <div class="hero-glow" :class="{ charging: s.is_charging, ac: s.climate?.ac_switch }" /> -->
      <div class="hero-car">
        <DynamicCarImage :vin="vehicle.vin" :status="s" :refresh-key="carImageKey" />
        <div class="hero-badges">
          <span v-if="s.is_charging" class="badge badge-charging"><Zap :size="14" /></span>
          <span v-if="s.is_plugged" class="badge badge-plugged"><Plug :size="14" /></span>
          <span v-if="s.is_regening" class="badge badge-regen"><Zap :size="14" /></span>
          <span v-if="s.climate?.ac_switch" class="badge badge-ac"><Snowflake :size="14" /></span>
          <span v-if="s.doors?.is_locked" class="badge badge-lock"><Lock :size="14" /></span>
          <span v-if="s.doors?.bbcm_back_door_status" class="badge badge-trunk"><TrunkOpenIcon :size="14" /></span>
        </div>
      </div>
      <div class="hero-bottom">
        <div class="hero-info">
          <div class="hero-name">{{ vehicle.vehicle_nickname || vehicle.car_type || 'Leapmotor' }}</div>
          <div class="hero-vin">{{ vehicle.vin }}</div>
        </div>
        <div v-if="vehicleAddress" class="hero-location" @click="showLocationModal = true">
          <MapPin :size="12" class="hero-loc-icon" />
          <span class="hero-loc-text">{{ vehicleAddress }}</span>
        </div>
      </div>
    </div>

    <!-- Stats grid -->
    <div class="stats-row grid grid-cols-2 sm:grid-cols-3 lg:flex gap-2.5">
      <StatCard
        label="Battery" :value="s.battery?.soc ?? '—'" unit="%" :color="battColor"
        :sub="battSub"
        :icon="battIcon" :pulse="!!s.is_charging"
      />
      <StatCard
        label="Range" :value="s.battery?.expected_mileage ?? '—'" unit="km" color="var(--cyan)"
        :sub="s.battery?.dump_energy_kwh != null ? `${s.battery.dump_energy_kwh} kWh available` : ''"
      />
      <StatCard
        label="Speed" :value="s.driving?.speed ?? 0" unit="km/h" color="var(--text)"
        :sub="s.driving?.is_parked ? 'Parked' : 'Moving'"
      />
      <StatCard
        label="Odometer"
        :value="s.driving?.total_mileage != null ? s.driving.total_mileage.toLocaleString() : '—'"
        unit="km" color="var(--amber)"
      />
      <StatCard
        label="Outside Temp" :value="s.climate?.outdoor_temp ?? '—'" unit="°C" color="var(--purple)"
        :sub="s.climate?.ac_switch ? 'A/C on' : 'A/C off'"
      />
    </div>

    <!-- Battery bar -->
    <div class="battery-bar-container">
      <div class="battery-bar-fill" :style="{ width: (s.battery?.soc ?? 0) + '%', background: battColor, boxShadow: s.is_charging ? `0 0 8px ${battColor}` : 'none' }" />
    </div>

    <!-- Lock status + charging info row -->
    <div class="info-strip flex-col sm:flex-row">
      <div class="lock-widget" :style="{ borderColor: s.doors?.is_locked ? '#ffab4044' : '#00e67644' }">
        <div class="lock-label">Lock Status</div>
        <div class="lock-main">
          <span class="lock-icon"><component :is="s.doors?.is_locked ? Lock : Unlock" :size="18" /></span>
          <span class="lock-text" :style="{ color: s.doors?.is_locked ? '#ffab40' : '#00e676' }">
            {{ s.doors?.is_locked === true ? 'Locked' : s.doors?.is_locked === false ? 'Unlocked' : '—' }}
          </span>
        </div>
        <div class="lock-time">Updated {{ s.timestamps?.collect_time ? formatTime(s.timestamps.collect_time) : '—' }}</div>
      </div>

      <div v-if="s.is_charging" class="charging-widget">
        <div class="charging-title-row">
          <span class="lock-label">Charging</span>
          <span v-if="activeChargingTier" class="charging-tier-badge" :class="'tier-' + activeChargingTier.tier_id">
            <component :is="tierIconMap[activeChargingTier.tier_id] || Zap" :size="11" />
            {{ activeChargingTier.tier_label || activeChargingTier.tier_id }}
          </span>
        </div>
        <div class="charging-stats">
          <div class="charging-stat">
            <div class="charging-val" style="color:#00e676">{{ chargeTimeStr }}</div>
            <div class="charging-sub">Remaining</div>
          </div>
          <div class="charging-stat">
            <div class="charging-val" style="color:#ff9100">{{ chargingPowerDisplay }} kW</div>
            <div class="charging-sub">Power</div>
          </div>
          <div class="charging-stat">
            <div class="charging-val" style="color:#00d4ff">{{ Math.abs(s.battery?.battery_current ?? 0) }} A</div>
            <div class="charging-sub">Current</div>
          </div>
          <div class="charging-stat">
            <div class="charging-val" style="color:#7c6aff">{{ s.battery?.battery_voltage ?? '—' }} V</div>
            <div class="charging-sub">Voltage</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Remote Controls -->
    <div class="controls-card" :class="{ 'controls-collapsed': remoteSection.allHidden && !showHidden.remote }">
      <div class="controls-header" :class="{ 'controls-header-clickable': remoteSection.allHidden }" @click="remoteSection.allHidden && (showHidden.remote = !showHidden.remote)">
        <Shield :size="16" class="controls-icon" />
        <span class="controls-title">Remote Controls</span>
        <button v-if="remoteSection.hiddenCount && !remoteSection.allHidden" class="section-toggle" @click.stop="showHidden.remote = !showHidden.remote">
          <component :is="showHidden.remote ? EyeOff : Eye" :size="14" />
          <span>+{{ remoteSection.hiddenCount }}</span>
        </button>
        <span v-if="remoteSection.allHidden" class="section-collapsed-hint">
          <span class="section-collapsed-count">{{ remoteSection.hiddenCount }} unavailable</span>
          <ChevronDown :size="14" class="section-chevron" :class="{ 'section-chevron-open': showHidden.remote }" />
        </span>
      </div>
      <div v-if="!remoteSection.allHidden || showHidden.remote" class="controls-grid">
        <button
          v-for="c in remoteSection.visible"
          :key="c.action"
          class="ctrl-btn"
          :class="{ active: isActive(c.action), loading: loadingAction === c.action, 'ctrl-unavailable': c._unavailable }"
          :style="{ '--c': c.color }"
          @click="c.modal ? openModal(c.modal) : exec(c.action)"
        >
          <span class="ctrl-icon" :class="{ spinning: loadingAction === c.action }">
            <Loader v-if="loadingAction === c.action" :size="16" />
            <component v-else :is="c.icon" :size="16" />
          </span>
          <span class="ctrl-label">{{ c.label }}</span>
          <span v-if="isActive(c.action)" class="ctrl-active-dot" :style="{ background: c.color }" />
        </button>
      </div>
    </div>

    <!-- Charging Controls -->
    <div class="controls-card" :class="{ 'controls-collapsed': chargingSection.allHidden && !showHidden.charging }">
      <div class="controls-header" :class="{ 'controls-header-clickable': chargingSection.allHidden }" @click="chargingSection.allHidden && (showHidden.charging = !showHidden.charging)">
        <PlugZap :size="16" class="controls-icon" />
        <span class="controls-title">Charging</span>
        <button v-if="chargingSection.hiddenCount && !chargingSection.allHidden" class="section-toggle" @click.stop="showHidden.charging = !showHidden.charging">
          <component :is="showHidden.charging ? EyeOff : Eye" :size="14" />
          <span>+{{ chargingSection.hiddenCount }}</span>
        </button>
        <span v-if="chargingSection.allHidden" class="section-collapsed-hint">
          <span class="section-collapsed-count">{{ chargingSection.hiddenCount }} unavailable</span>
          <ChevronDown :size="14" class="section-chevron" :class="{ 'section-chevron-open': showHidden.charging }" />
        </span>
      </div>
      <div v-if="!chargingSection.allHidden || showHidden.charging" class="controls-grid">
        <button
          v-for="c in chargingSection.visible"
          :key="c.action"
          class="ctrl-btn"
          :class="{ loading: loadingAction === c.action, 'ctrl-unavailable': c._unavailable }"
          :style="{ '--c': c.color }"
          @click="c.modal ? openModal(c.modal) : exec(c.action)"
        >
          <span class="ctrl-icon" :class="{ spinning: loadingAction === c.action }">
            <Loader v-if="loadingAction === c.action" :size="16" />
            <component v-else :is="c.icon" :size="16" />
          </span>
          <span class="ctrl-label">{{ c.label }}</span>
        </button>
      </div>
    </div>

    <!-- Comfort Controls -->
    <div class="controls-card" :class="{ 'controls-collapsed': comfortSection.allHidden && !showHidden.comfort }">
      <div class="controls-header" :class="{ 'controls-header-clickable': comfortSection.allHidden }" @click="comfortSection.allHidden && (showHidden.comfort = !showHidden.comfort)">
        <Heater :size="16" class="controls-icon" />
        <span class="controls-title">Comfort</span>
        <button v-if="comfortSection.hiddenCount && !comfortSection.allHidden" class="section-toggle" @click.stop="showHidden.comfort = !showHidden.comfort">
          <component :is="showHidden.comfort ? EyeOff : Eye" :size="14" />
          <span>+{{ comfortSection.hiddenCount }}</span>
        </button>
        <span v-if="comfortSection.allHidden" class="section-collapsed-hint">
          <span class="section-collapsed-count">{{ comfortSection.hiddenCount }} unavailable</span>
          <ChevronDown :size="14" class="section-chevron" :class="{ 'section-chevron-open': showHidden.comfort }" />
        </span>
      </div>
      <div v-if="!comfortSection.allHidden || showHidden.comfort" class="controls-grid">
        <button
          v-for="c in comfortSection.visible"
          :key="c.action"
          class="ctrl-btn"
          :class="{ loading: loadingAction === c.action, 'ctrl-unavailable': c._unavailable }"
          :style="{ '--c': c.color }"
          @click="c.modal ? openModal(c.modal) : exec(c.action)"
        >
          <span class="ctrl-icon" :class="{ spinning: loadingAction === c.action }">
            <Loader v-if="loadingAction === c.action" :size="16" />
            <component v-else :is="c.icon" :size="16" />
          </span>
          <span class="ctrl-label">{{ c.label }}</span>
        </button>
      </div>
    </div>

    <!-- Security Controls -->
    <div class="controls-card" :class="{ 'controls-collapsed': securitySection.allHidden && !showHidden.security }">
      <div class="controls-header" :class="{ 'controls-header-clickable': securitySection.allHidden }" @click="securitySection.allHidden && (showHidden.security = !showHidden.security)">
        <ShieldCheck :size="16" class="controls-icon" />
        <span class="controls-title">Security</span>
        <button v-if="securitySection.hiddenCount && !securitySection.allHidden" class="section-toggle" @click.stop="showHidden.security = !showHidden.security">
          <component :is="showHidden.security ? EyeOff : Eye" :size="14" />
          <span>+{{ securitySection.hiddenCount }}</span>
        </button>
        <span v-if="securitySection.allHidden" class="section-collapsed-hint">
          <span class="section-collapsed-count">{{ securitySection.hiddenCount }} unavailable</span>
          <ChevronDown :size="14" class="section-chevron" :class="{ 'section-chevron-open': showHidden.security }" />
        </span>
      </div>
      <div v-if="!securitySection.allHidden || showHidden.security" class="controls-grid">
        <button
          v-for="c in securitySection.visible"
          :key="c.action"
          class="ctrl-btn"
          :class="{ loading: loadingAction === c.action, 'ctrl-unavailable': c._unavailable }"
          :style="{ '--c': c.color }"
          @click="exec(c.action)"
        >
          <span class="ctrl-icon" :class="{ spinning: loadingAction === c.action }">
            <Loader v-if="loadingAction === c.action" :size="16" />
            <component v-else :is="c.icon" :size="16" />
          </span>
          <span class="ctrl-label">{{ c.label }}</span>
        </button>
      </div>
    </div>

    <!-- Vehicle Controls -->
    <div class="controls-card" :class="{ 'controls-collapsed': vehicleSection.allHidden && !showHidden.vehicle }">
      <div class="controls-header" :class="{ 'controls-header-clickable': vehicleSection.allHidden }" @click="vehicleSection.allHidden && (showHidden.vehicle = !showHidden.vehicle)">
        <Car :size="16" class="controls-icon" />
        <span class="controls-title">Vehicle</span>
        <button v-if="vehicleSection.hiddenCount && !vehicleSection.allHidden" class="section-toggle" @click.stop="showHidden.vehicle = !showHidden.vehicle">
          <component :is="showHidden.vehicle ? EyeOff : Eye" :size="14" />
          <span>+{{ vehicleSection.hiddenCount }}</span>
        </button>
        <span v-if="vehicleSection.allHidden" class="section-collapsed-hint">
          <span class="section-collapsed-count">{{ vehicleSection.hiddenCount }} unavailable</span>
          <ChevronDown :size="14" class="section-chevron" :class="{ 'section-chevron-open': showHidden.vehicle }" />
        </span>
      </div>
      <div v-if="!vehicleSection.allHidden || showHidden.vehicle" class="controls-grid">
        <button
          v-for="c in vehicleSection.visible"
          :key="c.action"
          class="ctrl-btn"
          :class="{ loading: loadingAction === c.action, 'ctrl-unavailable': c._unavailable }"
          :style="{ '--c': c.color }"
          @click="c.modal ? openModal(c.modal) : exec(c.action)"
        >
          <span class="ctrl-icon" :class="{ spinning: loadingAction === c.action }">
            <Loader v-if="loadingAction === c.action" :size="16" />
            <component v-else :is="c.icon" :size="16" />
          </span>
          <span class="ctrl-label">{{ c.label }}</span>
        </button>
      </div>
    </div>

    <!-- Charge limit -->
    <div class="charge-limit-card" v-if="chargeLimitAvailable">
      <div class="charge-limit-header">
        <span class="charge-limit-title">Charge Limit</span>
        <span class="charge-limit-current">Current: {{ s.battery?.charge_soc_setting ?? '—' }}%</span>
      </div>
      <div class="charge-limit-row">
        <span class="charge-min">20%</span>
        <input type="range" min="20" max="100" step="5" v-model.number="pendingLimit" class="charge-slider" />
        <div class="charge-limit-right">
          <span class="charge-dot" />
          <span class="charge-val">{{ pendingLimit }}%</span>
          <button class="charge-set-btn" @click="doSetChargeLimit">Set</button>
        </div>
      </div>
    </div>

    <PinDialog
      ref="pinDialogRef"
      :visible="showPinDialog"
      @confirmed="onPinConfirmed"
      @cancelled="onPinCancelled"
    />

    <WindowControlModal
      :visible="showWindowModal"
      @close="showWindowModal = false"
      :on-exec="execWindow"
      :windows="s.windows"
    />

    <SunshadeControlModal
      :visible="showSunshadeModal"
      @close="showSunshadeModal = false"
      :on-exec="execSunshade"
      :sunshade="s.windows?.sun_shade"
      :is-locked="s.doors?.is_locked === true"
    />

    <ClimateControlModal
      :visible="showClimateModal"
      @close="showClimateModal = false"
      :on-exec="execClimate"
      :climate="s.climate"
    />

    <SeatControlModal
      :visible="showSeatModal"
      @close="showSeatModal = false"
      :on-exec="execSeat"
      :seat-comfort="s.seat_comfort"
    />

    <DestinationModal
      :visible="showDestinationModal"
      @close="showDestinationModal = false"
      :location="s.location"
      :vehicle="props.vehicle"
    />

    <SpeedLimitModal
      :visible="showSpeedLimitModal"
      @close="showSpeedLimitModal = false"
      :on-exec="execSpeedLimit"
    />

    <MediaControlModal
      :visible="showMediaModal"
      @close="showMediaModal = false"
      :on-exec="execMedia"
    />

    <FotaModal
      :visible="showFotaModal"
      @close="showFotaModal = false"
      :on-exec="execFota"
      :vin="props.vehicle?.vin"
    />

    <ChargeScheduleModal
      :visible="showChargeScheduleModal"
      @close="showChargeScheduleModal = false"
      :on-exec="execChargeSchedule"
      :charge-plan="s.battery?.charge_plan"
      :current-soc="s.battery?.charge_soc_setting"
      :vin="props.vehicle?.vin"
    />

    <ClimateScheduleModal
      :visible="showClimateScheduleModal"
      @close="showClimateScheduleModal = false"
      :vin="props.vehicle?.vin"
    />

    <!-- Location modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showLocationModal" class="loc-modal-overlay" @click.self="showLocationModal = false">
          <div class="loc-modal">
            <button class="loc-modal-close" @click="showLocationModal = false">&times;</button>
            <LocationCard :location="s.location" :vehicle="props.vehicle" />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, toValue } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import { api } from '../composables/useApi'
import { formatTime } from '../utils/formatters'
import StatCard from '../components/StatCard.vue'
import PinDialog from '../components/PinDialog.vue'
import DynamicCarImage from '../components/DynamicCarImage.vue'
import WindowControlModal from '../components/WindowControlModal.vue'
import SunshadeControlModal from '../components/SunshadeControlModal.vue'
import ClimateControlModal from '../components/ClimateControlModal.vue'
import TrunkOpenIcon from '../components/icons/TrunkOpenIcon.vue'
import SeatControlModal from '../components/SeatControlModal.vue'
import DestinationModal from '../components/DestinationModal.vue'
import SpeedLimitModal from '../components/SpeedLimitModal.vue'
import MediaControlModal from '../components/MediaControlModal.vue'
import FotaModal from '../components/FotaModal.vue'
import ChargeScheduleModal from '../components/ChargeScheduleModal.vue'
import ClimateScheduleModal from '../components/ClimateScheduleModal.vue'
import LocationCard from '../components/LocationCard.vue'
import {
  Zap, Snowflake, Lock, Unlock, Shield, Loader, Plug,
  Radio, ChevronUp, ChevronDown, Sun, Wind, Flame,
  Thermometer, ThermometerSnowflake, BatteryCharging, Columns2,
  ShieldCheck, ShieldOff, Power, PowerOff, Wifi, Car,
  CircleParking, Key, Eye, EyeOff, PlugZap,
  Heater, AirVent, Armchair, Navigation,
  Gauge, Music, Download, CalendarClock, MapPin, Home, Clock
} from 'lucide-vue-next'

const props = defineProps({
  vehicle: { type: Object, required: true },
  status: { type: Object, required: true },
})

const store = useAppStore()
const { toast } = useToast()
const loadingAction = ref(null)
const carImageKey = ref(Date.now())

// Charging tier tracking
const activeChargingTier = ref(null)
const chargingTiersLoaded = ref(false)
const availableTiers = ref([])
const tierIconMap = { home_grid: Home, home_solar: Sun, public_ac: Plug, public_dc: Zap }

const s = computed(() => props.status || {})

// --- Reverse geocoding for hero location ---
const vehicleAddress = ref('')
let _lastGeoKey = ''

async function reverseGeocode(lat, lng) {
  const key = `${lat.toFixed(4)},${lng.toFixed(4)}`
  if (key === _lastGeoKey) return
  _lastGeoKey = key
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=17&addressdetails=1`,
      { headers: { 'Accept-Language': 'it' } }
    )
    if (!res.ok) return
    const data = await res.json()
    const a = data.address || {}
    const road = a.road || a.pedestrian || a.footway || ''
    const city = a.city || a.town || a.village || a.municipality || ''
    const parts = [road, city].filter(Boolean)
    vehicleAddress.value = parts.length ? parts.join(', ') : data.display_name?.split(',').slice(0, 3).join(',') || ''
  } catch {
    // Silently ignore geocoding failures
  }
}

watch(
  () => [s.value.location?.latitude, s.value.location?.longitude],
  ([lat, lng]) => {
    if (lat && lng) reverseGeocode(lat, lng)
  },
  { immediate: true }
)

// Watch for charging start to show tier selection toast
let wasCharging = false
watch(
  () => s.value.is_charging,
  async (isCharging) => {
    if (isCharging && !wasCharging) {
      // Charging just started — show tier selection toast
      if (availableTiers.value.length > 0) {
        const tierNames = availableTiers.value.map(t => t.label).join(', ')
        toast(`Charging started — assign cost tier in History`, 'info')
      }
      // Load active session cost
      if (props.vehicle?.vin) {
        try {
          const costs = await api('GET', `/api/vehicles/${props.vehicle.vin}/charging-costs`)
          const active = costs.find(c => !c.end_ts)
          if (active) {
            activeChargingTier.value = active
          }
        } catch { /* ignore */ }
      }
    } else if (!isCharging && wasCharging) {
      activeChargingTier.value = null
    }
    wasCharging = !!isCharging
  },
  { immediate: true }
)

// Load charging tiers on mount
;(async () => {
  try {
    const data = await api('GET', '/api/charging-tiers')
    availableTiers.value = data.tiers || []
    chargingTiersLoaded.value = true
  } catch { /* ignore */ }
})()

const battColor = computed(() => {
  const soc = s.value.battery?.soc
  if (soc == null) return '#5c6478'
  return soc > 50 ? '#00e676' : soc > 20 ? '#ffab40' : '#ff5252'
})

const chargeTimeStr = computed(() => {
  const min = s.value.battery?.charge_remain_time
  if (min == null) return '—'
  return `${Math.floor(min / 60)}h ${min % 60}m`
})

const chargingPowerDisplay = computed(() => {
  const power = s.value.battery?.charging_power_kw
  if (power != null) return power
  return s.value.battery?.battery_power ?? '—'
})

const isSlowCharging = computed(() => {
  return s.value.is_charging && s.value.battery?.charge_state_label === 'CHARGING' && !s.value.battery?.dc_input_fast_charge
})

const battSub = computed(() => {
  if (s.value.is_charging) return isSlowCharging.value ? 'Slow charging (AC)' : 'Fast charging (DC)'
  if (s.value.is_plugged) return 'Plugged in'
  if (s.value.is_regening) return 'Regen'
  if (s.value.battery?.is_discharging) return 'Discharging'
  return 'Not charging'
})

const battIcon = computed(() => {
  if (!s.value.is_charging) return null
  return isSlowCharging.value ? Plug : Zap
})

const hasPin = computed(() => store.hasPin)

const showPinDialog = ref(false)
const pendingAction = ref(null)
const pinDialogRef = ref(null)
const showWindowModal = ref(false)
const showSunshadeModal = ref(false)
const showClimateModal = ref(false)
const showSeatModal = ref(false)
const showDestinationModal = ref(false)
const showSpeedLimitModal = ref(false)
const showMediaModal = ref(false)
const showFotaModal = ref(false)
const showChargeScheduleModal = ref(false)
const showClimateScheduleModal = ref(false)
const showLocationModal = ref(false)

const pendingLimit = ref(props.status?.battery?.charge_soc_setting ?? 80)

const isT03 = computed(() => /^t03$/i.test(props.vehicle?.car_type || ''))

const controls = computed(() => {
  const base = [
    { action: 'lock', icon: Lock, label: 'Lock', color: '#ffab40', right: 110 },
    { action: 'unlock', icon: Unlock, label: 'Unlock', color: '#00e676', right: 110 },
    { action: 'trunk/open', icon: TrunkOpenIcon, label: 'Open Trunk', color: '#00d4ff', right: 130 },
    { action: 'trunk/close', icon: ChevronDown, label: 'Close Trunk', color: '#5c6478', right: 130 },
    { action: 'find', icon: Radio, label: 'Find Car', color: '#00d4ff', right: 120 },
    { action: 'windows', icon: Columns2, label: 'Windows', color: '#7c6aff', modal: 'windows', right: 230 },
    { action: 'sunshade', icon: Sun, label: 'Sunshade', color: '#ffab40', modal: 'sunshade', right: 161 },
    { action: 'climate', icon: Thermometer, label: 'Climate', color: '#00d4ff', modal: 'climate', right: 170 },
    { action: 'ac-schedule', icon: CalendarClock, label: 'AC Schedule', color: '#7c6aff', modal: 'climateSchedule', right: 171 },
  ]
  return isT03.value ? base.filter(c => c.action !== 'trunk/close') : base
})

const chargingControls = [
  { action: 'charging/start', icon: PlugZap, label: 'Start Charge', color: '#00e676', right: 193 },
  { action: 'charging/stop', icon: PlugZap, label: 'Stop Charge', color: '#ff5252', right: 193 },
  { action: 'unlock-charger', icon: Plug, label: 'Unlock Charger', color: '#ffab40', right: 192 },
  { action: 'battery-preheat', icon: BatteryCharging, label: 'Battery Preheat', color: '#00e676', right: 190 },
  { action: 'battery-preheat-off', icon: BatteryCharging, label: 'Preheat Off', color: '#5c6478', right: 190 },
  { action: 'healthy-charging/on', icon: ShieldCheck, label: 'Healthy Charge On', color: '#00e676', right: 480 },
  { action: 'healthy-charging/off', icon: ShieldOff, label: 'Healthy Charge Off', color: '#ff5252', right: 480 },
  { action: 'charge-schedule', icon: CalendarClock, label: 'Schedule', color: '#00d4ff', modal: 'chargeSchedule', right: 340 },
]

const comfortControls = [
  { action: 'seats', icon: Armchair, label: 'Seats', color: '#ff9100', modal: 'seats', right: 301 },
  { action: 'steering-wheel-heat/on', icon: Heater, label: 'Wheel Heat On', color: '#ff9100', right: 320 },
  { action: 'steering-wheel-heat/off', icon: Heater, label: 'Wheel Heat Off', color: '#5c6478', right: 320 },
  { action: 'fuel-heating/on', icon: Flame, label: 'Fuel Heat On', color: '#ff9100', right: 380 },
  { action: 'fuel-heating/off', icon: Flame, label: 'Fuel Heat Off', color: '#5c6478', right: 380 },
  { action: 'sunroof/open', icon: Sun, label: 'Sunroof Open', color: '#00d4ff', right: 160 },
  { action: 'sunroof/close', icon: Sun, label: 'Sunroof Close', color: '#5c6478', right: 160 },
]

const securityControls = [
  { action: 'sentry-mode/on', icon: Eye, label: 'Sentry On', color: '#00e676', right: 220 },
  { action: 'sentry-mode/off', icon: EyeOff, label: 'Sentry Off', color: '#5c6478', right: 220 },
  { action: 'rearview-mirror-heat/on', icon: AirVent, label: 'Mirror Heat On', color: '#ff9100', right: 440 },
  { action: 'rearview-mirror-heat/off', icon: AirVent, label: 'Mirror Heat Off', color: '#5c6478', right: 440 },
]

const vehicleControls = [
  { action: 'on3/on', icon: Power, label: 'ON3 On', color: '#00e676', right: 410 },
  { action: 'on3/off', icon: PowerOff, label: 'ON3 Off', color: '#ff5252', right: 410 },
  { action: 'ble-key-restart', icon: Key, label: 'BLE Restart', color: '#7c6aff', right: 430 },
  { action: 'hotspot', icon: Wifi, label: 'Hotspot', color: '#00d4ff', right: 140 },
  { action: 'send-destination', icon: Navigation, label: 'Send Destination', color: '#ff7043', modal: 'destination', right: 180 },
  { action: 'speed-limit', icon: Gauge, label: 'Speed Limit', color: '#ff9100', modal: 'speedLimit', right: 510 },
  { action: 'autopark', icon: CircleParking, label: 'Autopark', color: '#7c6aff', right: 150 },
  { action: 'piloted-parking', icon: CircleParking, label: 'Piloted Park', color: '#00d4ff', right: 350 },
  { action: 'prepare-car', icon: Car, label: 'Prepare Car', color: '#00e676', right: 360 },
  { action: 'media', icon: Music, label: 'Media', color: '#7c6aff', modal: 'media', right: 270 },
  { action: 'fota', icon: Download, label: 'Firmware', color: '#ff5252', modal: 'fota', right: 390 },
]

// --- Permission gating ---
// Ability code → Right codes enabled by that ability (from leapmotor-api ABILITY_TO_RIGHTS)
const ABILITY_TO_RIGHTS = {
  1: [110], 2: [120], 3: [130], 4: [150], 6: [170], 9: [171],
  10: [190], 11: [161], 12: [230], 14: [301], 15: [320], 17: [170, 171],
  18: [460], 24: [130], 25: [160], 30: [180], 34: [510], 35: [340],
  36: [230], 38: [360, 361], 40: [380], 42: [370], 43: [370],
  48: [192], 50: [220], 52: [180],
}
const RIGHTS_WITH_ABILITY = new Set(Object.values(ABILITY_TO_RIGHTS).flat())

const userRights = computed(() => {
  const r = props.vehicle?.rights
  if (!r) return new Set()
  return new Set(r.split(',').map(Number).filter(n => !isNaN(n)))
})

const hwRights = computed(() => {
  const abilities = props.vehicle?.abilities || []
  const rights = new Set()
  for (const a of abilities) {
    const mapped = ABILITY_TO_RIGHTS[Number(a)]
    if (mapped) mapped.forEach(r => rights.add(r))
  }
  return rights
})

function isControlAvailable(ctrl) {
  const right = ctrl.right
  if (right == null) return true
  if (!userRights.value.has(right)) return false
  if (RIGHTS_WITH_ABILITY.has(right) && !hwRights.value.has(right)) return false
  return true
}

const showHidden = ref({ remote: false, charging: false, comfort: false, security: false, vehicle: false })

function sectionData(list, key) {
  return computed(() => {
    const mapped = toValue(list).map(c => ({ ...c, _unavailable: !isControlAvailable(c) }))
    const hiddenCount = mapped.filter(c => c._unavailable).length
    const availableCount = mapped.length - hiddenCount
    const allHidden = availableCount === 0
    const visible = mapped.filter(c => !c._unavailable || showHidden.value[key])
    return { visible, hiddenCount, allHidden }
  })
}

const remoteSection = sectionData(controls, 'remote')
const chargingSection = sectionData(chargingControls, 'charging')
const comfortSection = sectionData(comfortControls, 'comfort')
const securitySection = sectionData(securityControls, 'security')
const vehicleSection = sectionData(vehicleControls, 'vehicle')

const chargeLimitAvailable = computed(() => {
  if (!userRights.value.has(340)) return false
  if (RIGHTS_WITH_ABILITY.has(340) && !hwRights.value.has(340)) return false
  return true
})

function isActive(action) {
  if (action === 'lock') return s.value.doors?.is_locked
  if (action === 'unlock') return s.value.doors?.is_locked === false
  if (action === 'ac' || action === 'climate') return s.value.climate?.ac_switch
  if (action === 'trunk/open') return s.value.doors?.bbcm_back_door_status
  return false
}

async function requirePin() {
  if (hasPin.value) return true
  return new Promise((resolve) => {
    pendingAction.value = { resolve }
    showPinDialog.value = true
  })
}

async function onPinConfirmed({ pin, remember }) {
  try {
    await store.submitPin(pin, remember)
    showPinDialog.value = false
    if (pendingAction.value?.resolve) {
      pendingAction.value.resolve(true)
      pendingAction.value = null
    }
  } catch (err) {
    pinDialogRef.value?.setError(err.message || 'Invalid PIN')
  }
}

function onPinCancelled() {
  showPinDialog.value = false
  if (pendingAction.value?.resolve) {
    pendingAction.value.resolve(false)
    pendingAction.value = null
  }
}

async function exec(action, body = null) {
  const ok = await requirePin()
  if (!ok) return
  loadingAction.value = action
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast(`${action} executed successfully`, 'success')
    await store.refreshAfterCommand()
    carImageKey.value = Date.now()
  } catch (err) {
    toast(`${action} failed: ${err.message}`, 'error')
  } finally {
    loadingAction.value = null
  }
}

async function execWindow({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Windows command sent', 'success')
    await store.refreshAfterCommand()
    carImageKey.value = Date.now()
  } catch (err) {
    toast(`Windows: ${err.message}`, 'error')
  }
}

async function execSunshade({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Sunshade command sent', 'success')
    await store.refreshAfterCommand()
    carImageKey.value = Date.now()
  } catch (err) {
    toast(`Sunshade: ${err.message}`, 'error')
  }
}

async function execClimate({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Climate command sent', 'success')
    await store.refreshAfterCommand()
    carImageKey.value = Date.now()
  } catch (err) {
    toast(`Climate: ${err.message}`, 'error')
  }
}

async function execSeat({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Seat command sent', 'success')
    await store.refreshAfterCommand()
  } catch (err) {
    toast(`Seat: ${err.message}`, 'error')
  }
}

function openModal(type) {
  if (type === 'windows') showWindowModal.value = true
  else if (type === 'sunshade') showSunshadeModal.value = true
  else if (type === 'climate') showClimateModal.value = true
  else if (type === 'seats') showSeatModal.value = true
  else if (type === 'destination') showDestinationModal.value = true
  else if (type === 'speedLimit') showSpeedLimitModal.value = true
  else if (type === 'media') showMediaModal.value = true
  else if (type === 'fota') showFotaModal.value = true
  else if (type === 'chargeSchedule') showChargeScheduleModal.value = true
  else if (type === 'climateSchedule') showClimateScheduleModal.value = true
}

async function execSpeedLimit({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Speed limit set', 'success')
    await store.refreshAfterCommand()
  } catch (err) {
    toast(`Speed limit: ${err.message}`, 'error')
  }
}

async function execMedia({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast(`${action} command sent`, 'success')
  } catch (err) {
    toast(`Media: ${err.message}`, 'error')
  }
}

async function execFota({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Firmware command sent', 'success')
  } catch (err) {
    toast(`FOTA: ${err.message}`, 'error')
  }
}

async function execChargeSchedule({ action, body }) {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.execControl(props.vehicle.vin, action, body)
    toast('Charge schedule updated', 'success')
    await store.refreshAfterCommand()
  } catch (err) {
    toast(`Schedule: ${err.message}`, 'error')
  }
}

async function execClimateSchedule() {
  // Climate schedule is now managed locally by ClimateScheduleModal
  showClimateScheduleModal.value = true
}

async function doSetChargeLimit() {
  const ok = await requirePin()
  if (!ok) return
  try {
    await store.setChargeLimit(props.vehicle.vin, pendingLimit.value)
    toast(`Charge limit set to ${pendingLimit.value}%`, 'success')
  } catch (err) {
    toast(`Failed: ${err.message}`, 'error')
  }
}
</script>

<style scoped>
.dashboard-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Hero */
.hero {
  background: var(--hero-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 16px 14px;
  position: relative;
  overflow: hidden;
}
@media (min-width: 640px) {
  .hero { border-radius: 16px; padding: 28px 28px 20px; }
}
.hero-glow {
  position: absolute;
  top: -60px;
  right: -60px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0,212,255,0.025) 0%, transparent 70%);
  pointer-events: none;
}
.hero-glow.charging { background: radial-gradient(circle, rgba(0,230,118,0.04) 0%, transparent 70%); }
.hero-glow.ac { background: radial-gradient(circle, rgba(0,212,255,0.04) 0%, transparent 70%); }
.hero-car { display: flex; flex-direction: column; align-items: center; margin-bottom: 8px; }
.hero-badges {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  backdrop-filter: blur(6px);
}
.badge-charging { background: rgba(0,230,118,0.15); border: 1px solid rgba(0,230,118,0.5); }
.badge-plugged { background: rgba(255,171,64,0.15); border: 1px solid rgba(255,171,64,0.5); }
.badge-regen { background: rgba(0,212,255,0.15); border: 1px solid rgba(0,212,255,0.5); }
.badge-ac { background: rgba(0,212,255,0.12); border: 1px solid rgba(0,212,255,0.45); }
.badge-lock { background: rgba(255,171,64,0.15); border: 1px solid rgba(255,171,64,0.5); }
.badge-trunk { background: rgba(255,171,64,0.15); border: 1px solid rgba(255,171,64,0.5); }
.hero-bottom {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-top: 4px; gap: 12px;
}
.hero-info { min-width: 0; }
.hero-name { font-size: 18px; font-weight: 700; color: var(--text); }
.hero-vin { font-size: 11px; color: var(--muted2); font-family: var(--mono); margin-top: 2px; }
.hero-location {
  display: flex; align-items: center; gap: 4px;
  cursor: pointer; flex-shrink: 1; min-width: 0;
  padding: 4px 10px; border-radius: 8px;
  background: rgba(255,255,255,0.04);
  transition: background .2s;
}
.hero-location:hover { background: rgba(255,255,255,0.08); }
.hero-loc-icon { color: var(--muted); flex-shrink: 0; }
.hero-loc-text {
  font-size: 11px; color: var(--muted); line-height: 1.3;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  text-align: right;
}

/* Location modal */
.loc-modal-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.loc-modal {
  position: relative;
  width: 94vw; max-width: 600px; max-height: 90vh;
  overflow-y: auto;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4);
}
.loc-modal .location-card {
  border-radius: 16px;
}
.loc-modal-close {
  position: absolute; top: 8px; right: 12px; z-index: 10;
  background: rgba(0,0,0,.4); border: none; color: #fff;
  font-size: 22px; width: 32px; height: 32px; border-radius: 50%;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  line-height: 1; transition: background .2s;
}
.loc-modal-close:hover { background: rgba(0,0,0,.6); }

/* Stats row */
.stats-row { /* responsive via Tailwind classes */ }

/* Battery bar */
.battery-bar-container {
  height: 4px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.battery-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}

/* Lock + Charging strip */
.info-strip { display: flex; gap: 10px; }
.lock-widget {
  background: var(--card);
  border: 1px solid;
  border-radius: 12px;
  padding: 14px 18px;
  min-width: 160px;
}
.lock-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--muted3);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.lock-main { display: flex; align-items: center; gap: 8px; }
.lock-icon { font-size: 22px; }
.lock-text { font-size: 18px; font-weight: 700; }
.lock-time { font-size: 10px; color: var(--muted2); margin-top: 6px; }

.charging-widget {
  background: var(--card);
  border: 1px solid #00e67633;
  border-radius: 12px;
  padding: 14px 18px;
  flex: 1;
}
.charging-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.charging-tier-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 500;
  flex-shrink: 0;
}
.charging-tier-badge.tier-home_grid { background: rgba(102,187,106,0.15); color: #66bb6a; }
.charging-tier-badge.tier-home_solar { background: rgba(253,216,53,0.15); color: #fdd835; }
.charging-tier-badge.tier-public_ac { background: rgba(66,165,245,0.15); color: #42a5f5; }
.charging-tier-badge.tier-public_dc { background: rgba(124,106,255,0.15); color: #7c6aff; }
.charging-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
@media (min-width: 640px) {
  .charging-stats { display: flex; gap: 16px; }
}
.charging-stat {}
.charging-val { font-size: 20px; font-weight: 700; }
.charging-sub { font-size: 11px; color: var(--muted); }

/* Controls card */
.controls-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px 16px;
}
.controls-collapsed {
  padding: 12px 16px;
  opacity: 0.6;
}
.controls-collapsed:hover { opacity: 0.85; }
.controls-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.controls-collapsed .controls-header { margin-bottom: 0; }
.controls-header-clickable { cursor: pointer; }
.controls-icon { font-size: 14px; }
.controls-title { font-size: 13px; font-weight: 700; color: var(--heading); }
.controls-warn { font-size: 11px; color: #ffab40; margin-left: auto; }

.section-toggle {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted);
  font-size: 0.7rem;
  padding: 2px 8px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.section-toggle:hover {
  color: var(--text);
  border-color: var(--text-secondary, var(--muted));
}

.section-collapsed-hint {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
}
.section-collapsed-count {
  font-size: 0.7rem;
  color: var(--muted);
}
.section-chevron {
  color: var(--muted);
  transition: transform 0.2s;
}
.section-chevron-open {
  transform: rotate(180deg);
}

.controls-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
@media (min-width: 640px) {
  .controls-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (min-width: 1024px) {
  .controls-grid { grid-template-columns: repeat(6, 1fr); }
}

.ctrl-btn {
  background: var(--elevated);
  border: 1px solid var(--btn-border);
  border-radius: 12px;
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.15s;
  min-width: 0;
  position: relative;
}
.ctrl-btn:hover {
  transform: scale(1.03);
}
.ctrl-btn:active {
  transform: scale(0.95);
}
.ctrl-btn.active {
  background: color-mix(in srgb, var(--c) 10%, transparent);
  border-color: color-mix(in srgb, var(--c) 33%, transparent);
}
.ctrl-btn.loading { cursor: wait; opacity: 0.7; }
.ctrl-btn.ctrl-unavailable { opacity: 0.35; filter: grayscale(0.6); }

.ctrl-icon {
  font-size: 20px;
  color: var(--c);
}
.ctrl-icon.spinning { animation: lm-spin 0.7s linear infinite; }
.ctrl-label {
  font-size: 10px;
  color: var(--label);
  font-weight: 500;
  text-align: center;
  line-height: 1.3;
  letter-spacing: 0.02em;
}
.ctrl-btn.active .ctrl-label { color: var(--c); }

.ctrl-active-dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
  animation: lm-pulse 2s infinite;
}

/* Charge limit */
.charge-limit-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 20px;
}
.charge-limit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.charge-limit-title { font-size: 13px; font-weight: 600; color: var(--heading); }
.charge-limit-current { font-size: 12px; color: var(--muted); }

.charge-limit-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.charge-min { font-size: 11px; color: var(--muted2); }
.charge-slider { flex: 1; }
.charge-limit-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.charge-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
}
.charge-val { font-size: 15px; font-weight: 700; color: var(--text); }
.charge-set-btn {
  background: var(--btn-bg);
  border: 1px solid var(--btn-border);
  border-radius: 7px;
  padding: 5px 12px;
  color: var(--sub);
  font-size: 12px;
  cursor: pointer;
  font-weight: 600;
}
.charge-set-btn:hover { background: var(--btn-hover); }


</style>
