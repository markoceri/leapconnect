import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../composables/useApi'
import { generateVehicleTheme, THEME_VARS } from '../utils/colorTheme'

export const useAppStore = defineStore('app', () => {
  // Screen: 'loading' | 'setup-user' | 'login' | 'setup-certs' | 'setup-account' | 'setup-services' | 'vehicles' | 'app'
  const screen = ref('loading')
  // Active sidebar tab: 'dashboard' | 'details' | 'history' | 'settings'
  const activeTab = ref('dashboard')

  const connected = ref(false)
  const vehicles = ref([])
  const selectedVin = ref(null)
  const vehicleData = ref({})
  const zonePresence = ref({}) // vin -> [zone names the vehicle is currently in]
  const hasPin = ref(sessionStorage.getItem('hasPin') === 'true')
  const loading = ref(false)
  const refreshing = ref(false)
  const picturePackages = ref({})
  const tempSetup = ref(null)
  const unreadMessages = ref(0)
  const displayName = ref('')
  const theme = ref('dark')
  const commandHistory = ref([])
  const showVehicleBar = ref(localStorage.getItem('showVehicleBar'))

  // Theme is a tri-state: 'dark' | 'light' | 'vehicle'. 'vehicle' is a full
  // standalone theme generated from the active vehicle's factory colour.
  function applyTheme(t) {
    theme.value = t
    localStorage.setItem('theme', t)
    if (t === 'vehicle') {
      const hex = currentVehicleColorHex()
      if (hex) {
        _applyVehicleVars(hex)
      } else {
        // No colour available yet — show dark until a palette/colour loads.
        _clearVehicleVars()
        document.documentElement.setAttribute('data-theme', 'dark')
      }
    } else {
      _clearVehicleVars()
      document.documentElement.setAttribute('data-theme', t)
    }
  }

  async function setTheme(t) {
    applyTheme(t)
    try {
      await api('PUT', '/api/preferences', { theme: t })
    } catch { /* ignore */ }
  }

  async function loadThemeFromPrefs() {
    try {
      const data = await api('GET', '/api/preferences')
      applyTheme(data.theme || 'dark')
      autoThemeFromVehicle.value = !!data.auto_theme_from_vehicle
    } catch {
      // Fallback to localStorage (e.g. on login page before auth)
      const saved = localStorage.getItem('theme')
      if (saved) applyTheme(saved)
    }
  }

  // --- Per-vehicle colour theme ---
  // The active vehicle's chosen/auto-detected factory colour drives a full
  // generated theme (every CSS token) when theme === 'vehicle'.
  const vehiclePalettes = ref({}) // vin -> { model_key, colors[], selected }
  const autoThemeFromVehicle = ref(false)
  const activeThemeHex = ref(null) // currently-applied vehicle colour, or null

  // The colour to theme around for the active vehicle: explicit choice first,
  // else the first palette entry.
  function currentVehicleColorHex() {
    const pal = vehiclePalettes.value[selectedVin.value]
    return pal?.selected?.hex || pal?.colors?.[0]?.hex || null
  }

  function _applyVehicleVars(hex) {
    const root = document.documentElement
    const { vars, base } = generateVehicleTheme(hex)
    for (const [name, value] of Object.entries(vars)) {
      root.style.setProperty(name, value)
    }
    root.setAttribute('data-theme', base) // keep map/chart light/dark logic working
    activeThemeHex.value = hex
    localStorage.setItem('vehicleThemeHex', hex)
  }

  function _clearVehicleVars() {
    const root = document.documentElement
    for (const name of THEME_VARS) root.style.removeProperty(name)
    activeThemeHex.value = null
    localStorage.removeItem('vehicleThemeHex')
  }

  // Re-apply the vehicle theme if it is the active mode for the selected car.
  function refreshVehicleTheme(vin) {
    if (theme.value === 'vehicle' && vin === selectedVin.value) applyTheme('vehicle')
  }

  async function loadVehiclePalette(vin) {
    if (!vin) return null
    try {
      const data = await api('GET', `/api/vehicles/${vin}/palette`)
      vehiclePalettes.value[vin] = data
      refreshVehicleTheme(vin)
      return data
    } catch {
      return null
    }
  }

  async function setVehicleColor(vin, colorKey) {
    const data = await api('PUT', `/api/vehicles/${vin}/color`, { color_key: colorKey })
    vehiclePalettes.value[vin] = data
    refreshVehicleTheme(vin)
    return data
  }

  async function detectVehicleColor(vin) {
    const res = await api('POST', `/api/vehicles/${vin}/color/detect`)
    await loadVehiclePalette(vin)
    return res
  }

  // For every vehicle without an explicit choice, auto-detect its colour.
  async function autoApplyVehicleColors() {
    for (const v of vehicles.value) {
      const pal = vehiclePalettes.value[v.vin] || (await loadVehiclePalette(v.vin))
      if (pal && !pal.selected) {
        try {
          await detectVehicleColor(v.vin)
        } catch {
          // best-effort
        }
      }
    }
  }

  async function setAutoTheme(enabled) {
    autoThemeFromVehicle.value = enabled
    try {
      await api('PUT', '/api/preferences', { auto_theme_from_vehicle: enabled })
    } catch {
      /* ignore */
    }
    // Enabling auto-detection also switches to the vehicle-colour theme so the
    // detected colour is actually shown.
    if (enabled) {
      await autoApplyVehicleColors()
      await setTheme('vehicle')
    } else if (theme.value === 'vehicle') {
      await setTheme('dark')
    }
  }

  // Load the active vehicle's accent on app entry; run auto-detection if on.
  function initAccent() {
    ;(async () => {
      if (selectedVin.value) await loadVehiclePalette(selectedVin.value)
      if (autoThemeFromVehicle.value) await autoApplyVehicleColors()
    })()
  }

  const selectedVehicle = computed(() =>
    vehicles.value.find((v) => v.vin === selectedVin.value) || null,
  )

  const currentData = computed(() =>
    selectedVin.value ? vehicleData.value[selectedVin.value] || null : null,
  )

  const currentStatus = computed(() => currentData.value?.status || null)

  async function login(credentials) {
    const result = await api('POST', '/api/cloud/session', credentials)
    connected.value = true
    vehicles.value = result.vehicles || []
    displayName.value = result.display_name || ''
    hasPin.value = false
    sessionStorage.removeItem('hasPin')
    if (vehicles.value.length === 1) {
      selectedVin.value = vehicles.value[0].vin
      screen.value = 'app'
    } else {
      screen.value = 'vehicles'
    }
    await loadThemeFromPrefs()
    initAccent()
    return result
  }

  async function reconnect() {
    try {
      const result = await api('PUT', '/api/cloud/session')
      connected.value = true
      vehicles.value = result.vehicles || []
      return result
    } catch {
      connected.value = false
      return null
    }
  }

  async function disconnect() {
    await api('DELETE', '/api/cloud/session')
    disconnectWebSocket()
    connected.value = false
  }

  const mqttStatus = ref({ enabled: false, connected: false, broker: '' })

  async function loadMqttStatus() {
    try {
      const data = await api('GET', '/api/mqtt')
      mqttStatus.value = { enabled: data.enabled, connected: data.connected, broker: data.broker || '' }
    } catch {
      // ignore
    }
  }

  const liveRefreshStatus = ref({ interval_seconds: 0, is_running: false })

  async function loadLiveRefreshStatus() {
    try {
      const data = await api('GET', '/api/live-refresh')
      liveRefreshStatus.value = { interval_seconds: data.interval_seconds, is_running: data.is_running }
    } catch {
      // ignore
    }
  }

  const abrpStatus = ref({ enabled: false, is_running: false })

  async function loadAbrpStatus() {
    try {
      const data = await api('GET', '/api/abrp')
      abrpStatus.value = { enabled: data.enabled, is_running: data.is_running }
    } catch {
      // ignore
    }
  }

  const notificationStatus = ref({ enabled: false, channel: null })

  async function loadNotificationStatus() {
    try {
      const channels = await api('GET', '/api/notifications/channels')
      const tg = channels.find(c => c.channel_type === 'telegram')
      if (tg) {
        notificationStatus.value = { enabled: tg.enabled, channel: 'Telegram' }
      } else {
        notificationStatus.value = { enabled: false, channel: null }
      }
    } catch {
      // ignore
    }
  }

  async function submitPin(pin, remember = false) {
    await api('PUT', '/api/cloud/pin', { pin })
    hasPin.value = true
    if (remember) {
      sessionStorage.setItem('hasPin', 'true')
    }
  }

  async function logout() {
    try {
      await api('DELETE', '/api/auth/session')
    } catch {
      // ignore
    }
    disconnectWebSocket()
    connected.value = false
    vehicles.value = []
    selectedVin.value = null
    vehicleData.value = {}
    hasPin.value = false
    sessionStorage.removeItem('hasPin')
    picturePackages.value = {}
    vehiclePalettes.value = {}
    if (theme.value === 'vehicle') {
      _clearVehicleVars()
      document.documentElement.setAttribute('data-theme', 'dark')
    }
    activeTab.value = 'dashboard'
    screen.value = 'login'
  }

  async function checkStatus() {
    try {
      // First check setup status
      const setup = await api('GET', '/api/setup/status')

      if (!setup.has_user) {
        // No LeapConnect user — first-time setup
        screen.value = 'setup-user'
        return false
      }

      if (!setup.authenticated) {
        // User exists but not logged in — show login screen
        screen.value = 'login'
        return false
      }

      if (!setup.has_certificates) {
        // User exists but no certificates
        screen.value = 'setup-certs'
        return false
      }

      if (!setup.has_account) {
        // Certs exist but no Leapmotor credentials
        screen.value = 'setup-account'
        return false
      }

      // Account exists — check connection
      if (setup.connected && setup.vehicles?.length > 0) {
        connected.value = true
        vehicles.value = setup.vehicles
        displayName.value = setup.display_name || ''
        if (vehicles.value.length === 1) {
          selectedVin.value = vehicles.value[0].vin
        }
        screen.value = 'app'
        await loadThemeFromPrefs()
        initAccent()
        return true
      }

      // Account exists but not connected — go to app in offline mode
      connected.value = false
      vehicles.value = setup.vehicles || []
      displayName.value = setup.display_name || ''
      screen.value = 'app'
      await loadThemeFromPrefs()
      return false
    } catch {
      // API not reachable
      screen.value = 'setup-user'
      return false
    }
  }

  async function loadVehicleData(vin) {
    loading.value = true
    try {
      const data = await api('GET', `/api/vehicles/${vin}/full`)
      data._fetchedAt = Date.now()
      vehicleData.value[vin] = data
      connectWebSocket(vin)
    } finally {
      loading.value = false
    }
  }

  async function loadZonePresence() {
    try {
      zonePresence.value = await api('GET', '/api/zones/presence')
    } catch {
      // presence is best-effort; ignore failures
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
        const data = await api('GET', `/api/vehicles/${selectedVin.value}/full`)
        data._fetchedAt = Date.now()
        vehicleData.value[selectedVin.value] = data
      } finally {
        refreshing.value = false
      }
    }
  }

  // Refresh with retries after a command — the car takes time to report new state
  let _pendingRetries = null
  async function refreshAfterCommand() {
    // Cancel any previous retry chain
    if (_pendingRetries) {
      clearTimeout(_pendingRetries)
      _pendingRetries = null
    }
    // Immediate refresh
    await refreshCurrent()
    // Then retry at 3s, 6s, 12s to catch delayed state updates
    const delays = [3000, 6000, 12000]
    for (const delay of delays) {
      _pendingRetries = setTimeout(async () => {
        if (selectedVin.value && connected.value) {
          try {
            const data = await api('GET', `/api/vehicles/${selectedVin.value}/full`)
            vehicleData.value[selectedVin.value] = data
          } catch {
            // ignore background refresh errors
          }
        }
      }, delay)
    }
  }

  // --- WebSocket real-time updates ---
  let _ws = null
  let _wsReconnectTimer = null
  const WS_RECONNECT_DELAY = 5000

  function _buildWsUrl(vin) {
    const loc = window.location
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:'
    const base = `${proto}//${loc.host}${loc.pathname.replace(/\/$/, '')}`
    return `${base}/ws/vehicle/${vin}`
  }

  function connectWebSocket(vin) {
    disconnectWebSocket()
    if (!vin) return

    const url = _buildWsUrl(vin)
    const ws = new WebSocket(url)

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'status_update' && msg.vin) {
          const existing = vehicleData.value[msg.vin]
          if (existing) {
            vehicleData.value[msg.vin] = {
              ...existing,
              status: msg.status,
              cache_age_seconds: msg.cache_age_seconds,
              _fetchedAt: Date.now(),
            }
          }
        }
      } catch {
        // ignore invalid messages
      }
    }

    ws.onclose = () => {
      _ws = null
      // Auto-reconnect if we're still in the app and have a selected vin
      if (screen.value === 'app' && selectedVin.value === vin && connected.value) {
        _wsReconnectTimer = setTimeout(() => connectWebSocket(vin), WS_RECONNECT_DELAY)
      }
    }

    ws.onerror = () => {
      // onclose will fire after this
    }

    _ws = ws
  }

  function disconnectWebSocket() {
    if (_wsReconnectTimer) {
      clearTimeout(_wsReconnectTimer)
      _wsReconnectTimer = null
    }
    if (_ws) {
      _ws.onclose = null // prevent auto-reconnect on intentional close
      _ws.close()
      _ws = null
    }
  }

  function selectVehicle(vin) {
    selectedVin.value = vin
    activeTab.value = 'dashboard'
    screen.value = 'app'
    connectWebSocket(vin)
    if (vehiclePalettes.value[vin]) refreshVehicleTheme(vin)
    else loadVehiclePalette(vin)
  }

  function goToVehicleSelector() {
    screen.value = 'vehicles'
  }

  async function execControl(vin, action, body = null) {
    const result = await api('POST', `/api/vehicles/${vin}/commands/${action}`, body)
    const entry = { action, body, response: result, timestamp: new Date().toISOString() }
    commandHistory.value = [entry, ...commandHistory.value].slice(0, 10)
    return result
  }

  async function setChargeSchedule(vin, body) {
    return await api('PUT', `/api/vehicles/${vin}/charge-schedule`, body)
  }

  async function setChargeLimit(vin, limit) {
    return await api('POST', `/api/vehicles/${vin}/commands/charge-limit`, { limit })
  }

  async function sendDestination(vin, { address, address_name, latitude, longitude }) {
    return await api('POST', `/api/vehicles/${vin}/commands/send-destination`, {
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
    zonePresence,
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
    disconnect,
    logout,
    checkStatus,
    loadVehicleData,
    loadZonePresence,
    refreshCurrent,
    refreshAfterCommand,
    selectVehicle,
    goToVehicleSelector,
    execControl,
    setChargeLimit,
    setChargeSchedule,
    sendDestination,
    submitPin,
    loadPicturePackage,
    unreadMessages,
    loadUnreadCount,
    displayName,
    theme,
    applyTheme,
    setTheme,
    vehiclePalettes,
    autoThemeFromVehicle,
    activeThemeHex,
    loadVehiclePalette,
    setVehicleColor,
    detectVehicleColor,
    setAutoTheme,
    showVehicleBar,
    mqttStatus,
    loadMqttStatus,
    liveRefreshStatus,
    loadLiveRefreshStatus,
    abrpStatus,
    loadAbrpStatus,
    notificationStatus,
    loadNotificationStatus,
    commandHistory,
    connectWebSocket,
    disconnectWebSocket,
  }
})
