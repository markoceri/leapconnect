import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../composables/useApi'

export const useAppStore = defineStore('app', () => {
  // Screen: 'login' | 'vehicles' | 'app'
  const screen = ref('login')
  // Active sidebar tab: 'dashboard' | 'details' | 'history' | 'settings'
  const activeTab = ref('dashboard')

  const connected = ref(false)
  const vehicles = ref([])
  const selectedVin = ref(null)
  const vehicleData = ref({})
  const hasPin = ref(false)
  const loading = ref(false)
  const refreshing = ref(false)
  const picturePackages = ref({})

  const selectedVehicle = computed(() =>
    vehicles.value.find((v) => v.vin === selectedVin.value) || null,
  )

  const currentData = computed(() =>
    selectedVin.value ? vehicleData.value[selectedVin.value] || null : null,
  )

  const currentStatus = computed(() => currentData.value?.status || null)

  async function login(credentials) {
    const result = await api('POST', '/api/login', credentials)
    connected.value = true
    vehicles.value = result.vehicles || []
    hasPin.value = false
    if (vehicles.value.length === 1) {
      selectedVin.value = vehicles.value[0].vin
      screen.value = 'app'
    } else {
      screen.value = 'vehicles'
    }
    return result
  }

  async function submitPin(pin) {
    await api('POST', '/api/set-pin', { pin })
    hasPin.value = true
  }

  async function logout() {
    try {
      await api('POST', '/api/logout')
    } catch {
      // ignore
    }
    connected.value = false
    vehicles.value = []
    selectedVin.value = null
    vehicleData.value = {}
    hasPin.value = false
    picturePackages.value = {}
    screen.value = 'login'
    activeTab.value = 'dashboard'
  }

  async function checkStatus() {
    try {
      const data = await api('GET', '/api/status')
      if (data.connected && data.vehicles?.length > 0) {
        connected.value = true
        vehicles.value = data.vehicles
        hasPin.value = data.has_pin
        if (data.vehicles.length === 1) {
          selectedVin.value = data.vehicles[0].vin
          screen.value = 'app'
        } else {
          screen.value = 'vehicles'
        }
        return true
      }
    } catch {
      // not connected
    }
    return false
  }

  async function loadVehicleData(vin) {
    loading.value = true
    try {
      const data = await api('GET', `/api/vehicles/${vin}/full`)
      vehicleData.value[vin] = data
    } finally {
      loading.value = false
    }
    // Load picture package in background (once)
    if (!picturePackages.value[vin]) {
      loadPicturePackage(vin)
    }
  }

  async function loadPicturePackage(vin) {
    try {
      const data = await api('GET', `/api/vehicles/${vin}/picture/package`)
      picturePackages.value[vin] = data
    } catch {
      // ignore — fallback to single image
    }
  }

  async function refreshCurrent() {
    if (selectedVin.value) {
      refreshing.value = true
      try {
        delete vehicleData.value[selectedVin.value]
        await loadVehicleData(selectedVin.value)
      } finally {
        refreshing.value = false
      }
    }
  }

  function selectVehicle(vin) {
    selectedVin.value = vin
    activeTab.value = 'dashboard'
    screen.value = 'app'
  }

  function goToVehicleSelector() {
    screen.value = 'vehicles'
  }

  async function execControl(vin, action) {
    return await api('POST', `/api/vehicles/${vin}/${action}`)
  }

  async function setChargeLimit(vin, limit) {
    return await api('POST', `/api/vehicles/${vin}/charge-limit`, { limit })
  }

  return {
    screen,
    activeTab,
    connected,
    vehicles,
    selectedVin,
    vehicleData,
    hasPin,
    loading,
    refreshing,
    picturePackages,
    selectedVehicle,
    currentData,
    currentStatus,
    login,
    logout,
    checkStatus,
    loadVehicleData,
    refreshCurrent,
    selectVehicle,
    goToVehicleSelector,
    execControl,
    setChargeLimit,
    submitPin,
    loadPicturePackage,
  }
})
