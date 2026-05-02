import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../composables/useApi'

export const useAppStore = defineStore('app', () => {
  // Screen: 'loading' | 'setup-certs' | 'setup-account' | 'vehicles' | 'app'
  const screen = ref('loading')
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
  const tempSetup = ref(null)
  const unreadMessages = ref(0)

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

  async function reconnect() {
    try {
      const result = await api('POST', '/api/reconnect')
      connected.value = true
      vehicles.value = result.vehicles || []
      return result
    } catch {
      connected.value = false
      return null
    }
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
    activeTab.value = 'dashboard'
    // Stay in app — just disconnected, not wiping setup
    screen.value = 'app'
  }

  async function checkStatus() {
    try {
      // First check setup status
      const setup = await api('GET', '/api/setup/status')

      if (!setup.has_account) {
        // No account configured — check if certificates are set
        const certs = await api('GET', '/api/setup/certificates')
        if (!certs.cert_exists || !certs.key_exists) {
          screen.value = 'setup-certs'
        } else {
          screen.value = 'setup-account'
        }
        return false
      }

      // Account exists — check connection
      if (setup.connected && setup.vehicles?.length > 0) {
        connected.value = true
        vehicles.value = setup.vehicles
        if (vehicles.value.length === 1) {
          selectedVin.value = vehicles.value[0].vin
        }
        screen.value = 'app'
        return true
      }

      // Account exists but not connected — go to app in offline mode
      connected.value = false
      vehicles.value = setup.vehicles || []
      screen.value = 'app'
      return false
    } catch {
      // API not reachable
      screen.value = 'setup-certs'
      return false
    }
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

  async function sendDestination(vin, { address, address_name, latitude, longitude }) {
    return await api('POST', `/api/vehicles/${vin}/send-destination`, {
      address, address_name, latitude, longitude,
    })
  }

  async function loadUnreadCount() {
    try {
      const data = await api('GET', '/api/messages/unread-count')
      unreadMessages.value = data.unread || 0
    } catch {
      // ignore
    }
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
    tempSetup,
    selectedVehicle,
    currentData,
    currentStatus,
    login,
    reconnect,
    logout,
    checkStatus,
    loadVehicleData,
    refreshCurrent,
    selectVehicle,
    goToVehicleSelector,
    execControl,
    setChargeLimit,
    sendDestination,
    submitPin,
    loadPicturePackage,
    unreadMessages,
    loadUnreadCount,
  }
})
