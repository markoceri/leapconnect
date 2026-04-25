import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../composables/useApi'

export const useAppStore = defineStore('app', () => {
  const connected = ref(false)
  const vehicles = ref([])
  const selectedVin = ref(null)
  const vehicleData = ref({})
  const hasPin = ref(false)
  const loading = ref(false)

  const selectedVehicle = computed(() =>
    vehicles.value.find((v) => v.vin === selectedVin.value) || null,
  )

  const currentData = computed(() =>
    selectedVin.value ? vehicleData.value[selectedVin.value] || null : null,
  )

  async function login(credentials) {
    const result = await api('POST', '/api/login', credentials)
    connected.value = true
    vehicles.value = result.vehicles || []
    hasPin.value = !!credentials.operation_password
    if (vehicles.value.length > 0) {
      selectedVin.value = vehicles.value[0].vin
    }
    return result
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
  }

  async function checkStatus() {
    try {
      const data = await api('GET', '/api/status')
      if (data.connected && data.vehicles?.length > 0) {
        connected.value = true
        vehicles.value = data.vehicles
        hasPin.value = data.has_pin
        selectedVin.value = data.vehicles[0].vin
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
  }

  async function refreshCurrent() {
    if (selectedVin.value) {
      delete vehicleData.value[selectedVin.value]
      await loadVehicleData(selectedVin.value)
    }
  }

  function selectVehicle(vin) {
    selectedVin.value = vin
  }

  async function execControl(vin, action) {
    return await api('POST', `/api/vehicles/${vin}/${action}`)
  }

  async function setChargeLimit(vin, limit) {
    return await api('POST', `/api/vehicles/${vin}/charge-limit`, { limit })
  }

  return {
    connected,
    vehicles,
    selectedVin,
    vehicleData,
    hasPin,
    loading,
    selectedVehicle,
    currentData,
    login,
    logout,
    checkStatus,
    loadVehicleData,
    refreshCurrent,
    selectVehicle,
    execControl,
    setChargeLimit,
  }
})
