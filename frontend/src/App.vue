<template>
  <!-- Loading -->
  <div v-if="store.screen === 'loading'" class="loading-screen">
    <div class="spinner" />
  </div>

  <!-- Certificate Setup -->
  <CertificateSetupView v-else-if="store.screen === 'setup-certs'" />

  <!-- Account Setup -->
  <AccountSetupView v-else-if="store.screen === 'setup-account'" />

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
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#00d4ff" stroke-width="2">
            <path d="M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v9a2 2 0 01-2 2h-2" />
            <circle cx="9" cy="17" r="2" /><circle cx="17" cy="17" r="2" />
          </svg>
        </div>
        <span class="navbar-title hidden sm:inline">LeapConnect</span>
        <span class="navbar-title sm:hidden">LeapConnect</span>
      </div>
      <div class="navbar-right">
        <div class="connection-badge hidden sm:flex" :class="{ offline: !store.connected }">
          <span class="connection-dot" :class="{ offline: !store.connected }" />
          <span>{{ store.connected ? 'CONNECTED' : 'OFFLINE' }}</span>
        </div>
        <div class="connection-dot sm:hidden" :class="{ offline: !store.connected }" style="width:8px;height:8px;border-radius:50%" />
        <button v-if="!store.connected" class="nav-btn" @click="handleReconnect">
          <RefreshCw :size="14" />
          <span class="hidden sm:inline">Reconnect</span>
        </button>
        <button v-else class="nav-btn" @click="handleRefresh">
          <RefreshCw :size="14" :class="{ spinning: store.refreshing }" />
          <span class="hidden sm:inline">Refresh</span>
        </button>
        <button class="nav-btn" @click="handleLogout">
          <LogOut :size="14" />
          <span class="hidden sm:inline">Logout</span>
        </button>
      </div>
    </div>

    <!-- Vehicle tabs — horizontal swipeable -->
    <div class="vehicle-tabs-bar">
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
      <div class="sidebar hidden md:flex">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="sidebar-btn"
          :class="{ active: store.activeTab === t.id }"
          :title="t.label"
          @click="store.activeTab = t.id"
        >
          <component :is="t.icon" :size="18" />
          <div v-if="store.activeTab === t.id" class="sidebar-indicator" />
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
        v-for="t in tabs"
        :key="t.id"
        class="bottom-tab"
        :class="{ active: store.activeTab === t.id }"
        @click="store.activeTab = t.id"
      >
        <component :is="t.icon" :size="20" />
        <span class="bottom-tab-label">{{ t.label }}</span>
      </button>
    </div>
  </div>

  <ToastContainer />
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAppStore } from './stores/appStore'
import { useToast } from './composables/useToast'
import CertificateSetupView from './views/CertificateSetupView.vue'
import AccountSetupView from './views/AccountSetupView.vue'
import VehicleSelectorView from './views/VehicleSelectorView.vue'
import DashboardTab from './views/DashboardTab.vue'
import DetailsTab from './views/DetailsTab.vue'
import HistoryTab from './views/HistoryTab.vue'
import MessagesTab from './views/MessagesTab.vue'
import SettingsTab from './views/SettingsTab.vue'
import ToastContainer from './components/ToastContainer.vue'
import { LayoutDashboard, List, TrendingUp, Mail, Settings, RefreshCw, LogOut } from 'lucide-vue-next'

const store = useAppStore()
const { toast } = useToast()

const errorMsg = ref('')

const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'details', label: 'Details', icon: List },
  { id: 'messages', label: 'Messages', icon: Mail },
  { id: 'history', label: 'History', icon: TrendingUp },
  { id: 'settings', label: 'Settings', icon: Settings },
]

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

function handleLogout() {
  store.logout()
}

onMounted(async () => {
  const restored = await store.checkStatus()
  if (restored) {
    toast('Session restored', 'success')
  } else if (store.screen === 'app' && !store.connected) {
    toast('Offline mode — live data not available', 'warning')
  }
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
  background: #00d4ff18; border: 1px solid #00d4ff44;
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
  border-radius: 20px; padding: 4px 12px;
  font-size: 11px; font-weight: 700; color: #00e676;
  letter-spacing: 0.06em;
}
.connection-badge.offline {
  background: #ff525214; border-color: #ff525244; color: #ff5252;
}
.connection-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #00e676; display: inline-block;
  box-shadow: 0 0 6px #00e676;
  animation: lm-pulse 2s infinite;
}
.connection-dot.offline {
  background: #ff5252; box-shadow: 0 0 6px #ff5252;
}
.nav-btn {
  background: none; border: 1px solid #1c2240;
  border-radius: 8px; padding: 6px 8px;
  color: var(--label); font-size: 12px; cursor: pointer;
  display: flex; align-items: center; gap: 5px;
  transition: all 0.2s;
}
@media (min-width: 640px) { .nav-btn { padding: 5px 12px; } }
.nav-btn:hover { background: #1c224044; color: var(--text); }
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
  border-bottom-color: #00d4ff;
  color: #00d4ff;
}
.vtab-name { font-size: 12px; font-weight: 700; }
.vtab-id { font-size: 10px; color: #2a3045; font-family: var(--mono); }
.vtab-add { font-size: 12px; color: #2a3045; align-self: center; margin-left: 4px; }

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
  align-items: center;
  padding-top: 16px;
  gap: 6px;
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar-btn {
  width: 40px; height: 40px; border-radius: 10px;
  border: none; cursor: pointer; font-size: 16px;
  background: transparent; color: #3a4468;
  transition: all 0.2s; position: relative;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sidebar-btn.active {
  background: #00d4ff18;
  color: #00d4ff;
}
.sidebar-btn:hover { color: #5c6478; }
.sidebar-indicator {
  position: absolute; left: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 20px;
  background: #00d4ff;
  border-radius: 0 2px 2px 0;
}

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
  color: #3a4468;
  transition: color 0.2s;
  padding: 6px 12px;
  -webkit-tap-highlight-color: transparent;
}
.bottom-tab.active { color: #00d4ff; }
.bottom-tab-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
</style>
