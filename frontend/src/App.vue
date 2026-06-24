<template>
  <!-- Loading -->
  <div v-if="store.screen === 'loading'" class="loading-screen">
    <div class="spinner" />
  </div>

  <!-- User Setup (first-time) -->
  <UserSetupView v-else-if="store.screen === 'setup-user'" />

  <!-- Login (returning user) -->
  <LoginView v-else-if="store.screen === 'login'" />

  <!-- Certificate Setup -->
  <CertificateSetupView v-else-if="store.screen === 'setup-certs'" />

  <!-- Account Setup (Leapmotor credentials) -->
  <AccountSetupView v-else-if="store.screen === 'setup-account'" />

  <!-- Services Setup (HA + History) -->
  <ServicesSetupView v-else-if="store.screen === 'setup-services'" />

  <!-- Vehicle Selector -->
  <VehicleSelectorView
    v-else-if="store.screen === 'vehicles'"
    :vehicles="store.vehicles"
    @select="onSelectVehicle"
  />

  <!-- Main App -->
  <div v-else class="app-shell">
    <!-- Top Navbar -->
    <div class="navbar">
      <div class="navbar-left">
        <div class="navbar-logo">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" style="stroke: var(--accent)" stroke-width="2">
            <path d="M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v9a2 2 0 01-2 2h-2" />
            <circle cx="9" cy="17" r="2" /><circle cx="17" cy="17" r="2" />
          </svg>
        </div>
        <span class="navbar-title hidden sm:inline">LeapConnect</span>
        <span class="navbar-title sm:hidden">LeapConnect</span>
      </div>
      <div class="navbar-right">
        <!-- Cloud connection badge (always visible) -->
        <div class="connection-badge" :class="{ offline: !store.connected }">
          <component :is="store.connected ? Cloud : CloudOff" :size="12" />
          <span class="connection-label">{{ store.connected ? 'CLOUD' : 'OFFLINE' }}</span>
        </div>
        <!-- Refresh / data age pill -->
        <button v-if="!store.connected" class="reconnect-btn" @click="handleReconnect">
          <RefreshCw :size="13" />
          <span class="reconnect-label">Reconnect</span>
        </button>
        <button v-else class="refresh-age-btn" :class="dataAgeClass" @click="handleRefresh">
          <RefreshCw :size="13" :class="{ spinning: store.refreshing }" />
          <span v-if="dataAgeLabel">{{ dataAgeLabel }}</span>
          <span v-else class="reconnect-label">Refresh</span>
        </button>
        <!-- Notifications -->
        <MessageDropdown />
        <!-- User menu (always visible) -->
        <div class="user-menu-wrap">
          <button class="user-avatar-btn" @click="toggleUserMenu">
            <span>{{ userInitials }}</span>
          </button>
          <Transition name="menu-fade">
            <div v-if="showUserMenu" class="user-menu-dropdown" @click.stop>
              <div class="user-menu-header">
                <span class="user-menu-name">{{ store.displayName || 'User' }}</span>
                <span class="user-menu-role">LeapConnect</span>
              </div>
              <!-- Services status -->
              <div class="user-menu-services">
                <div class="svc-row">
                  <span class="svc-dot" :class="store.liveRefreshStatus.is_running ? 'on' : 'off'" />
                  <span class="svc-label">Live Refresh</span>
                  <span class="svc-value" :class="store.liveRefreshStatus.is_running ? 'on' : ''">
                    {{ store.liveRefreshStatus.is_running ? `${store.liveRefreshStatus.interval_seconds}s` : 'Disabled' }}
                  </span>
                </div>
                <div class="svc-row">
                  <span class="svc-dot" :class="store.mqttStatus.connected ? 'on' : store.mqttStatus.enabled ? 'warn' : 'off'" />
                  <span class="svc-label">Home Assistant</span>
                  <span class="svc-value" :class="store.mqttStatus.connected ? 'on' : store.mqttStatus.enabled ? 'warn' : ''">
                    {{ store.mqttStatus.connected ? 'Online' : store.mqttStatus.enabled ? 'Offline' : 'Disabled' }}
                  </span>
                </div>
                <div class="svc-row">
                  <span class="svc-dot" :class="store.abrpStatus.is_running ? 'on' : store.abrpStatus.enabled ? 'warn' : 'off'" />
                  <span class="svc-label">ABRP</span>
                  <span class="svc-value" :class="store.abrpStatus.is_running ? 'on' : store.abrpStatus.enabled ? 'warn' : ''">
                    {{ store.abrpStatus.is_running ? 'Running' : store.abrpStatus.enabled ? 'Stopped' : 'Disabled' }}
                  </span>
                </div>
                <div class="svc-row">
                  <span class="svc-dot" :class="store.notificationStatus.enabled ? 'on' : 'off'" />
                  <span class="svc-label">Notifications</span>
                  <span class="svc-value" :class="store.notificationStatus.enabled ? 'on' : ''">
                    {{ store.notificationStatus.enabled ? store.notificationStatus.channel : 'Disabled' }}
                  </span>
                </div>
              </div>
              <div class="user-menu-divider" />
              <!-- Cloud action -->
              <button class="user-menu-item user-menu-action" @click="handleCloudToggle">
                <component :is="store.connected ? CloudOff : Cloud" :size="14" />
                <span>{{ store.connected ? 'Disconnect Leapmotor Cloud' : 'Connect Leapmotor Cloud' }}</span>
              </button>
              <!-- Theme toggle -->
              <button class="user-menu-item user-menu-action" @click="store.setTheme(store.theme === 'dark' ? 'light' : 'dark')">
                <component :is="store.theme === 'dark' ? Sun : Moon" :size="14" />
                <span>{{ store.theme === 'dark' ? 'Light Mode' : 'Dark Mode' }}</span>
              </button>
              <button class="user-menu-item user-menu-action" @click="toggleVehicleBar">
                <component :is="vehicleBarVisible ? PanelTopClose : PanelTop" :size="14" />
                <span>{{ vehicleBarVisible ? 'Hide Vehicle Bar' : 'Show Vehicle Bar' }}</span>
              </button>
              <div class="user-menu-divider" />
              <button class="user-menu-item user-menu-action user-menu-logout" @click="handleLogout">
                <LogOut :size="14" />
                <span>Logout</span>
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- Vehicle tabs — horizontal swipeable -->
    <div v-if="vehicleBarVisible" class="vehicle-tabs-bar">
      <div class="vehicle-tabs-scroll">
        <button
          v-for="v in store.vehicles"
          :key="v.vin"
          class="vtab"
          :class="{ active: store.selectedVin === v.vin }"
          @click="store.selectVehicle(v.vin)"
        >
          <div class="vtab-name">{{ v.vehicle_nickname || v.car_type || 'Vehicle' }}</div>
          <div class="vtab-id">{{ v.vin.slice(-8) }}</div>
        </button>
        <button v-if="store.vehicles.length > 1" class="vtab vtab-add" @click="store.goToVehicleSelector()">+ Add</button>
      </div>
    </div>

    <!-- Content area -->
    <div class="content-area">
      <!-- Sidebar (desktop only) -->
      <div class="sidebar hidden md:flex" :class="{ expanded: sidebarExpanded }">
        <div class="sidebar-nav">
          <button
            v-for="t in tabs"
            :key="t.id"
            class="sidebar-btn"
            :class="{ active: store.activeTab === t.id }"
            :title="sidebarExpanded ? '' : t.label"
            @click="store.activeTab = t.id"
          >
            <div class="sidebar-icon-wrap">
              <component :is="t.icon" :size="18" />
              <span v-if="t.id === 'messages' && store.unreadMessages > 0" class="tab-unread-dot" />
            </div>
            <span v-if="sidebarExpanded" class="sidebar-label">{{ t.label }}</span>
            <div v-if="store.activeTab === t.id" class="sidebar-indicator" />
          </button>
        </div>
        <button
          class="sidebar-toggle"
          :title="sidebarExpanded ? 'Collapse menu' : 'Expand menu'"
          @click="toggleSidebar"
        >
          <component :is="sidebarExpanded ? PanelLeftClose : PanelLeft" :size="18" />
          <span v-if="sidebarExpanded" class="sidebar-label">Collapse</span>
        </button>
      </div>

      <!-- Main scroll area -->
      <div class="main-scroll">
        <div v-if="store.loading" class="loading-center">
          <div class="spinner" />
        </div>
        <template v-else>
          <SettingsTab
            v-if="store.activeTab === 'settings'"
            :vehicle="vehicle"
            :raw-data="store.currentData"
          />
          <MessagesTab
            v-else-if="store.activeTab === 'messages'"
          />
          <HistoryTab
            v-else-if="store.activeTab === 'history'"
            :status="status"
            :vin="store.selectedVin"
          />
          <ChargingTab
            v-else-if="store.activeTab === 'charging'"
            :vin="store.selectedVin"
          />
          <TripsTab
            v-else-if="store.activeTab === 'trips'"
            :vin="store.selectedVin"
          />
          <MaintenanceTab
            v-else-if="store.activeTab === 'maintenance'"
            :vin="store.selectedVin"
            :status="status"
            :vehicle="vehicle"
          />
          <ZonesTab
            v-else-if="store.activeTab === 'zones'"
            :status="status"
          />
          <template v-else-if="store.currentData">
            <DashboardTab
              v-if="store.activeTab === 'dashboard'"
              :vehicle="vehicle"
              :status="status"
            />
            <DetailsTab
              v-else-if="store.activeTab === 'details'"
              :vehicle="vehicle"
              :status="status"
              :mileage="mileageData"
            />
          </template>
          <div v-else-if="errorMsg" class="loading-center error-text">{{ errorMsg }}</div>
          <div v-else-if="!store.connected" class="loading-center">
            <div class="offline-message">
              <p>Offline — live vehicle data is not available.</p>
              <p class="offline-hint">Use the History tab to view past data, or check Settings to update credentials.</p>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Bottom tab bar (mobile only) -->
    <div class="bottom-bar md:hidden">
      <button
        v-for="t in primaryTabs"
        :key="t.id"
        class="bottom-tab"
        :class="{ active: store.activeTab === t.id }"
        @click="store.activeTab = t.id"
      >
        <div class="bottom-icon-wrap">
          <component :is="t.icon" :size="20" />
        </div>
        <span class="bottom-tab-label">{{ t.label }}</span>
      </button>
      <button
        class="bottom-tab"
        :class="{ active: moreActive }"
        @click="showMoreSheet = true"
      >
        <div class="bottom-icon-wrap">
          <MoreHorizontal :size="20" />
          <span v-if="moreHasUnread" class="tab-unread-dot" />
        </div>
        <span class="bottom-tab-label">More</span>
      </button>
    </div>

    <!-- "More" bottom sheet (mobile only) -->
    <Transition name="sheet">
      <div v-if="showMoreSheet" class="more-sheet-overlay md:hidden" @click="showMoreSheet = false">
        <div class="more-sheet" @click.stop>
          <div class="more-sheet-grab" />
          <div class="more-sheet-title">More</div>
          <button
            v-for="t in moreTabs"
            :key="t.id"
            class="more-sheet-row"
            :class="{ active: store.activeTab === t.id }"
            @click="selectTab(t.id)"
          >
            <span class="more-sheet-icon">
              <component :is="t.icon" :size="20" />
            </span>
            <span class="more-sheet-label">{{ t.label }}</span>
            <span v-if="t.id === 'messages' && store.unreadMessages > 0" class="more-sheet-badge">
              {{ store.unreadMessages }}
            </span>
          </button>
        </div>
      </div>
    </Transition>
  </div>

  <ToastContainer />
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useAppStore } from './stores/appStore'
import { useToast } from './composables/useToast'
import { setOnUnauthorized } from './composables/useApi'
import CertificateSetupView from './views/CertificateSetupView.vue'
import AccountSetupView from './views/AccountSetupView.vue'
import ServicesSetupView from './views/ServicesSetupView.vue'
import UserSetupView from './views/UserSetupView.vue'
import LoginView from './views/LoginView.vue'
import VehicleSelectorView from './views/VehicleSelectorView.vue'
import DashboardTab from './views/DashboardTab.vue'
import DetailsTab from './views/DetailsTab.vue'
import HistoryTab from './views/HistoryTab.vue'
import ChargingTab from './views/ChargingTab.vue'
import TripsTab from './views/TripsTab.vue'
import MaintenanceTab from './views/MaintenanceTab.vue'
import MessagesTab from './views/MessagesTab.vue'
import SettingsTab from './views/SettingsTab.vue'
import ZonesTab from './views/ZonesTab.vue'
import ToastContainer from './components/ToastContainer.vue'
import MessageDropdown from './components/MessageDropdown.vue'
import { LayoutDashboard, List, TrendingUp, Mail, Settings, RefreshCw, LogOut, Cloud, CloudOff, Sun, Moon, PanelTop, PanelTopClose, PanelLeft, PanelLeftClose, MoreHorizontal, Bell, BatteryCharging, MapPin, MapPinned, Wrench } from 'lucide-vue-next'

const store = useAppStore()
const { toast } = useToast()

const errorMsg = ref('')
const showUserMenu = ref(false)

const vehicleBarVisible = computed(() => {
  const saved = store.showVehicleBar
  if (saved === 'true') return true
  if (saved === 'false') return false
  // Default: show only if multiple vehicles
  return store.vehicles.length > 1
})

function toggleVehicleBar() {
  const newVal = !vehicleBarVisible.value
  store.showVehicleBar = newVal ? 'true' : 'false'
  localStorage.setItem('showVehicleBar', store.showVehicleBar)
}

const userInitials = computed(() => {
  const name = store.displayName || ''
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase() || '?'
})

// Ordered by usage hierarchy. On mobile the first PRIMARY_TAB_COUNT appear in
// the bottom bar; the rest are grouped under the "More" sheet. New tabs added
// to this list fall under "More" automatically.
const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'charging', label: 'Charging', icon: BatteryCharging },
  { id: 'trips', label: 'Trips', icon: MapPin },
  { id: 'maintenance', label: 'Maintenance', icon: Wrench },
  { id: 'zones', label: 'Zones', icon: MapPinned },
  { id: 'details', label: 'Details', icon: List },
  { id: 'history', label: 'History', icon: TrendingUp },
  { id: 'messages', label: 'Messages', icon: Mail },
  { id: 'settings', label: 'Settings', icon: Settings },
]

const PRIMARY_TAB_COUNT = 4
const primaryTabs = tabs.slice(0, PRIMARY_TAB_COUNT)
const moreTabs = tabs.slice(PRIMARY_TAB_COUNT)
const moreActive = computed(() => moreTabs.some((t) => store.activeTab === t.id))
const moreHasUnread = computed(() => store.unreadMessages > 0 && moreTabs.some((t) => t.id === 'messages'))

// Desktop sidebar expand/collapse — collapsed by default, persisted
const sidebarExpanded = ref(localStorage.getItem('sidebarExpanded') === 'true')
function toggleSidebar() {
  sidebarExpanded.value = !sidebarExpanded.value
  localStorage.setItem('sidebarExpanded', String(sidebarExpanded.value))
}

// Mobile "More" bottom sheet
const showMoreSheet = ref(false)
function selectTab(id) {
  store.activeTab = id
  showMoreSheet.value = false
}

const vehicle = computed(() => store.currentData?.vehicle || {})
const status = computed(() => store.currentData?.status || {})
const mileageData = computed(() => store.currentData?.mileage?.data || {})

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

function onSelectVehicle(vin) {
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

async function handleReconnect() {
  try {
    const result = await store.reconnect()
    if (result) {
      toast('Connected successfully', 'success')
    } else {
      toast('Connection failed', 'error')
    }
  } catch (err) {
    toast(err.message || 'Connection failed', 'error')
  }
}

async function handleCloudToggle() {
  if (store.connected) {
    if (!confirm('Disconnect from Leapmotor Cloud? Live data will stop until you reconnect.')) return
    try {
      await store.disconnect()
      toast('Disconnected from Cloud', 'warning')
    } catch (err) {
      toast(err.message || 'Disconnect failed', 'error')
    }
  } else {
    await handleReconnect()
  }
  showUserMenu.value = false
}

function handleLogout() {
  store.logout()
}

function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
  if (showUserMenu.value) {
    store.loadMqttStatus()
    store.loadLiveRefreshStatus()
    store.loadAbrpStatus()
    store.loadNotificationStatus()
  }
}

// --- Data age indicator ---
const dataAgeTick = ref(0)
let dataAgeInterval = null

const dataAgeSeconds = computed(() => {
  dataAgeTick.value // reactive dependency for ticking
  const data = store.currentData
  if (!data || data.cache_age_seconds == null) return null
  // cache_age_seconds is the age at fetch time; add elapsed since fetch
  const fetchedAt = data._fetchedAt || 0
  const elapsed = fetchedAt ? (Date.now() - fetchedAt) / 1000 : 0
  return Math.round(data.cache_age_seconds + elapsed)
})

const dataAgeLabel = computed(() => {
  const s = dataAgeSeconds.value
  if (s == null) return ''
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ago`
})

const dataAgeClass = computed(() => {
  const s = dataAgeSeconds.value
  if (s == null) return ''
  if (s < 120) return 'fresh'
  if (s < 600) return 'stale'
  return 'old'
})

let unreadInterval = null

function onClickOutsideMenu(e) {
  const wrap = document.querySelector('.user-menu-wrap')
  if (wrap && !wrap.contains(e.target)) showUserMenu.value = false
}

onMounted(async () => {
  document.addEventListener('click', onClickOutsideMenu)
  setOnUnauthorized(() => { store.screen = 'login' })
  const restored = await store.checkStatus()
  if (restored) {
    toast('Session restored', 'success')
  } else if (store.screen === 'app' && !store.connected) {
    toast('Offline mode — live data not available', 'warning')
  }
  // Load unread count and poll every 60s (only when authenticated)
  if (store.screen === 'app') {
    store.loadUnreadCount()
    store.loadMqttStatus()
    store.loadLiveRefreshStatus()
    store.loadAbrpStatus()
    store.loadNotificationStatus()
    unreadInterval = setInterval(() => store.loadUnreadCount(), 60000)
  }
  // Tick data age every 10s
  dataAgeInterval = setInterval(() => { dataAgeTick.value++ }, 10000)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutsideMenu)
  if (unreadInterval) clearInterval(unreadInterval)
  if (dataAgeInterval) clearInterval(dataAgeInterval)
  store.disconnectWebSocket()
})
</script>

<style scoped>
.loading-screen {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
}

.app-shell {
  height: 100vh;
  height: 100dvh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Navbar */
.navbar {
  background: var(--bg2);
  border-bottom: 1px solid var(--border2);
  padding: 0 16px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 1000;
}
@media (min-width: 640px) {
  .navbar { padding: 0 24px; height: 56px; }
}
.navbar-left { display: flex; align-items: center; gap: 8px; }
@media (min-width: 640px) { .navbar-left { gap: 10px; } }
.navbar-logo {
  width: 32px; height: 32px; border-radius: 8px;
  background: rgba(var(--accent-rgb), 0.094); border: 1px solid rgba(var(--accent-rgb), 0.267);
  display: flex; align-items: center; justify-content: center;
}
.navbar-title {
  font-size: 13px; font-weight: 700; color: var(--text);
  letter-spacing: -0.01em;
}
@media (min-width: 640px) { .navbar-title { font-size: 14px; } }
.navbar-right { display: flex; align-items: center; gap: 8px; }
@media (min-width: 640px) { .navbar-right { gap: 10px; } }
.connection-badge {
  display: flex; align-items: center; gap: 6px;
  background: #00e67614; border: 1px solid #00e67644;
  border-radius: 20px; padding: 4px 10px;
  font-size: 11px; font-weight: 700; color: #00e676;
  letter-spacing: 0.06em;
}
@media (min-width: 640px) { .connection-badge { padding: 4px 12px; } }
.connection-badge.offline {
  background: #ff525214; border-color: #ff525244; color: #ff5252;
}
/* User menu */
.user-menu-wrap { position: relative; }
.user-avatar-btn {
  width: 32px; height: 32px; border-radius: 50%;
  background: #00e67618; border: 1.5px solid #00e67644;
  color: #00e676; font-size: 11px; font-weight: 700;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  position: relative; transition: all 0.2s;
}
.user-avatar-btn.offline {
  background: #ff525214; border-color: #ff525244; color: #ff5252;
}

.user-menu-dropdown {
  position: absolute; top: 44px; right: 0;
  background: var(--bg2); border: 1px solid var(--border2);
  border-radius: 14px; min-width: 220px;
  box-shadow: var(--shadow-menu); z-index: 1100;
  overflow: hidden; backdrop-filter: blur(12px);
}
.user-menu-header {
  padding: 14px 16px 10px;
}
.user-menu-name {
  display: block; font-size: 14px; font-weight: 700; color: var(--text);
}
.user-menu-services {
  padding: 6px 16px 10px;
}
.svc-row {
  display: flex; align-items: center; gap: 8px; font-size: 11px;
}
.svc-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.svc-dot.on { background: #00e676; box-shadow: 0 0 6px #00e67688; }
.svc-dot.warn { background: #ffab40; box-shadow: 0 0 6px #ffab4088; }
.svc-dot.off { background: #444; }
.svc-label { color: var(--label); }
.svc-value { margin-left: auto; font-weight: 600; color: var(--muted); }
.svc-value.on { color: #00e676; }
.svc-value.warn { color: #ffab40; }
.user-menu-item {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 16px; font-size: 12px; color: var(--label);
  width: 100%; background: none; border: none; cursor: default;
  transition: background 0.15s, color 0.15s;
}
.user-menu-action {
  cursor: pointer;
}
.user-menu-action:hover { background: var(--elevated); color: var(--text); }
.user-menu-divider { height: 1px; background: var(--border2); margin: 4px 12px; }
.user-menu-logout { color: #ff5252; }
.user-menu-logout:hover { color: #ff5252; background: #ff525210; }

.menu-fade-enter-active, .menu-fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.menu-fade-enter-from, .menu-fade-leave-to { opacity: 0; transform: translateY(-4px); }
.refresh-age-btn {
  display: flex; align-items: center; gap: 5px;
  border-radius: 20px; padding: 4px 12px;
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--elevated); border: 1px solid var(--border); color: var(--label);
}
.refresh-age-btn:hover { filter: brightness(1.3); }
.refresh-age-btn.fresh {
  background: #00e67614; border-color: #00e67644; color: #00e676;
}
.refresh-age-btn.stale {
  background: #ffab4014; border-color: #ffab4044; color: #ffab40;
}
.refresh-age-btn.old {
  background: #ff525214; border-color: #ff525244; color: #ff5252;
}
.reconnect-btn {
  display: flex; align-items: center; gap: 5px;
  border-radius: 20px; padding: 4px 12px;
  font-size: 11px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
  background: #ff525214; border: 1px solid #ff525244; color: #ff5252;
}
.reconnect-btn:hover { filter: brightness(1.3); }
.reconnect-label { display: none; }
@media (min-width: 640px) { .reconnect-label { display: inline; } }
.user-menu-role {
  display: block; font-size: 11px; color: var(--label); margin-top: 2px;
}
.connection-label { display: inline; }
.spinning { display: inline-block; animation: lm-spin 0.7s linear infinite; }

/* Vehicle tabs bar — horizontal scrollable */
.vehicle-tabs-bar {
  background: var(--bg2);
  border-bottom: 1px solid var(--border2);
  flex-shrink: 0;
}
.vehicle-tabs-scroll {
  display: flex;
  gap: 2px;
  padding: 0 16px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.vehicle-tabs-scroll::-webkit-scrollbar { display: none; }
@media (min-width: 640px) {
  .vehicle-tabs-scroll { padding: 0 24px; }
}
.vtab {
  background: none; border: none;
  border-bottom: 2px solid transparent;
  padding: 10px 16px; cursor: pointer;
  transition: all 0.2s; color: var(--muted);
  white-space: nowrap;
  flex-shrink: 0;
}
.vtab:hover { color: var(--text); }
.vtab.active {
  border-bottom-color: var(--accent);
  color: var(--accent);
}
.vtab-name { font-size: 12px; font-weight: 700; }
.vtab-id { font-size: 10px; color: var(--muted); font-family: var(--mono); }
.vtab-add { font-size: 12px; color: var(--muted); align-self: center; margin-left: 4px; }

/* Content area */
.content-area {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Sidebar (desktop only, hidden via Tailwind on mobile) */
.sidebar {
  width: 56px;
  background: var(--bg2);
  border-right: 1px solid var(--border2);
  flex-direction: column;
  padding: 16px 8px 12px;
  flex-shrink: 0;
  overflow: hidden;
  transition: width 0.22s ease;
}
.sidebar.expanded { width: 200px; }
.sidebar-nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
}
.sidebar-nav::-webkit-scrollbar { display: none; }
.sidebar.expanded .sidebar-nav { align-items: stretch; }
.sidebar-btn {
  width: 40px; height: 40px; border-radius: 10px;
  border: none; cursor: pointer; font-size: 16px;
  background: transparent; color: var(--muted2);
  transition: background 0.2s, color 0.2s; position: relative;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sidebar.expanded .sidebar-btn {
  width: 100%; justify-content: flex-start;
  gap: 13px; padding: 0 11px;
}
.sidebar-btn.active {
  background: rgba(var(--accent-rgb), 0.094);
  color: var(--accent);
}
.sidebar-btn:hover { color: #5c6478; }
.sidebar-label {
  font-size: 13px; font-weight: 600; white-space: nowrap;
}
.sidebar-indicator {
  position: absolute; left: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 20px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}
.sidebar.expanded .sidebar-indicator { left: -11px; }
.sidebar-toggle {
  margin-top: 8px;
  height: 40px; border-radius: 10px;
  border: none; cursor: pointer;
  background: transparent; color: var(--muted3);
  transition: background 0.2s, color 0.2s;
  display: flex; align-items: center; justify-content: center;
  gap: 13px; flex-shrink: 0; align-self: center; width: 40px;
}
.sidebar.expanded .sidebar-toggle {
  align-self: stretch; width: 100%;
  justify-content: flex-start; padding: 0 11px;
}
.sidebar-toggle:hover { color: var(--text); background: var(--elevated); }

/* Main scroll */
.main-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: calc(100px + env(safe-area-inset-bottom, 0px)); /* space for bottom bar on mobile */
  position: relative;
  z-index: 0;
}
@media (min-width: 768px) {
  .main-scroll {
    padding: 20px 24px;
    padding-bottom: 20px;
  }
}
.loading-center {
  display: flex; align-items: center; justify-content: center;
  height: 60vh;
}
.error-text { color: var(--red); font-size: 14px; }
.offline-message {
  text-align: center;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}
.offline-hint {
  font-size: 12px;
  color: var(--muted2);
  margin-top: 0.5rem;
}

/* Bottom tab bar (mobile only, hidden via Tailwind on desktop) */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: var(--bg2);
  border-top: 1px solid var(--border2);
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 10px 0;
  padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  backdrop-filter: blur(12px);
}
@media (min-width: 768px) {
  .bottom-bar { display: none; }
}
.bottom-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--muted2);
  transition: color 0.2s;
  padding: 6px 12px;
  -webkit-tap-highlight-color: transparent;
}
.bottom-tab.active { color: var(--accent); }
.bottom-tab-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

/* "More" bottom sheet (mobile only) */
.more-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.more-sheet {
  background: var(--bg2);
  border-top: 1px solid var(--border);
  border-radius: 20px 20px 0 0;
  padding: 8px 0 calc(14px + env(safe-area-inset-bottom, 0px));
  box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.4);
}
.more-sheet-grab {
  width: 38px; height: 4px; border-radius: 3px;
  background: var(--muted2); margin: 6px auto 8px;
}
.more-sheet-title {
  font-size: 11px; font-weight: 600; color: var(--label);
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 4px 20px 8px;
}
.more-sheet-row {
  display: flex; align-items: center; gap: 14px;
  width: 100%; padding: 14px 20px;
  background: none; border: none; cursor: pointer;
  color: var(--text); font-size: 15px; font-weight: 500;
  -webkit-tap-highlight-color: transparent;
}
.more-sheet-row:active { background: var(--elevated); }
.more-sheet-icon { color: var(--muted3); display: inline-flex; flex-shrink: 0; }
.more-sheet-row.active { color: var(--accent); }
.more-sheet-row.active .more-sheet-icon { color: var(--accent); }
.more-sheet-label { flex: 1; text-align: left; }
.more-sheet-badge {
  background: #ff5252; color: #fff;
  font-size: 10px; font-weight: 700;
  min-width: 18px; height: 18px; border-radius: 9px;
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0 5px;
}
.sheet-enter-active, .sheet-leave-active { transition: opacity 0.25s ease; }
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-active .more-sheet, .sheet-leave-active .more-sheet {
  transition: transform 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.sheet-enter-from .more-sheet, .sheet-leave-to .more-sheet {
  transform: translateY(100%);
}

/* Unread dot on sidebar/bottom tabs */
.sidebar-icon-wrap,
.bottom-icon-wrap {
  position: relative;
  display: inline-flex;
}
.tab-unread-dot {
  position: absolute;
  top: -3px;
  right: -4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff5252;
  box-shadow: 0 0 6px #ff525288;
  pointer-events: none;
}
</style>
