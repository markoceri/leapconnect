<template>
  <div class="dashboard">
    <TopBar @refresh="handleRefresh" @logout="handleLogout" />

    <VehicleTabs
      :vehicles="store.vehicles"
      :selected-vin="store.selectedVin"
      @select="handleSelectVehicle"
    />

    <div class="main-content">
      <div v-if="store.loading" class="loading-center">
        <div class="spinner"></div>
      </div>

      <div v-else-if="errorMsg" class="loading-center" style="color:var(--accent-red)">
        {{ errorMsg }}
      </div>

      <template v-else-if="data">
        <CarImageHero
          :vin="store.selectedVin"
          :name="vehicle.nickname || vehicle.car_type || 'Leapmotor'"
        />

        <HeroStrip
          :status="data.status"
          :mileage="mileageData"
        />

        <div class="dashboard-grid">
          <RemoteControls
            :vin="store.selectedVin"
            :has-pin="store.hasPin"
            :charge-soc-setting="data.status?.battery?.charge_soc_setting"
          />

          <DoorsWindows
            :doors="data.status?.doors || {}"
            :windows="data.status?.windows || {}"
          />

          <ClimateCard
            :climate="data.status?.climate || {}"
          />

          <TirePressure
            :tires="data.status?.tires || {}"
          />

          <BatteryCharging
            :bat="data.status?.battery || {}"
          />

          <LocationCard
            :location="data.status?.location || {}"
          />

          <ConnectivityCard
            :connectivity="data.status?.connectivity || {}"
            :ignition="data.status?.ignition || {}"
            :driving="data.status?.driving || {}"
            :timestamps="data.status?.timestamps || {}"
          />

          <VehicleInfo
            :vehicle="vehicle"
            :picture="pictureData"
          />

          <MileageEnergy
            :m="mileageData"
          />

          <RawData :data="data" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'
import TopBar from '../components/TopBar.vue'
import VehicleTabs from '../components/VehicleTabs.vue'
import CarImageHero from '../components/CarImageHero.vue'
import HeroStrip from '../components/HeroStrip.vue'
import RemoteControls from '../components/RemoteControls.vue'
import DoorsWindows from '../components/DoorsWindows.vue'
import ClimateCard from '../components/ClimateCard.vue'
import TirePressure from '../components/TirePressure.vue'
import BatteryCharging from '../components/BatteryCharging.vue'
import LocationCard from '../components/LocationCard.vue'
import ConnectivityCard from '../components/ConnectivityCard.vue'
import VehicleInfo from '../components/VehicleInfo.vue'
import MileageEnergy from '../components/MileageEnergy.vue'
import RawData from '../components/RawData.vue'

const emit = defineEmits(['logout'])
const store = useAppStore()
const { toast } = useToast()

const errorMsg = ref('')

const data = computed(() => store.currentData)
const vehicle = computed(() => data.value?.vehicle || {})
const mileageData = computed(() => (data.value?.mileage?.data) || {})
const pictureData = computed(() => (data.value?.picture?.data) || null)

// Auto-load data when selectedVin changes
watch(
  () => store.selectedVin,
  async (vin) => {
    if (vin && !store.vehicleData[vin]) {
      errorMsg.value = ''
      try {
        await store.loadVehicleData(vin)
      } catch (err) {
        errorMsg.value = err.message
        toast(err.message, 'error')
      }
    }
  },
  { immediate: true },
)

function handleSelectVehicle(vin) {
  store.selectVehicle(vin)
}

async function handleRefresh() {
  errorMsg.value = ''
  try {
    await store.refreshCurrent()
    toast('Data refreshed', 'success')
  } catch (err) {
    toast(err.message, 'error')
  }
}

function handleLogout() {
  store.logout()
  emit('logout')
}
</script>

<style scoped>
.dashboard {
  position: relative;
  z-index: 1;
  min-height: 100vh;
}

.main-content {
  padding: 0 2rem 2rem;
}

.loading-center {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60vh;
}

@media (max-width: 768px) {
  .main-content { padding: 0 1rem 1rem; }
}
</style>
