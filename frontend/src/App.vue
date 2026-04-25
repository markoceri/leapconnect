<template>
  <!-- Login -->
  <LoginView v-if="store.screen === 'login'" />

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
        <span class="navbar-title">Leapmotor Command Center</span>
      </div>
      <div class="navbar-right">
        <div class="connection-badge">
          <span class="connection-dot" />
          <span>CONNECTED</span>
        </div>
        <button class="nav-btn" @click="handleRefresh">
          <span :class="{ spinning: store.refreshing }">↻</span> Refresh
        </button>
        <button class="nav-btn" @click="handleLogout">⊣ Logout</button>
      </div>
    </div>

    <!-- Vehicle tabs -->
    <div class="vehicle-tabs-bar">
      <button
        v-for="v in store.vehicles"
        :key="v.vin"
        class="vtab"
        :class="{ active: store.selectedVin === v.vin }"
        @click="store.selectVehicle(v.vin)"
      >
        <div class="vtab-name">{{ v.nickname || v.car_type || 'Vehicle' }}</div>
        <div class="vtab-id">{{ v.vin.slice(-8) }}</div>
      </button>
      <button v-if="store.vehicles.length > 1" class="vtab vtab-add" @click="store.goToVehicleSelector()">+ Aggiungi</button>
    </div>

    <!-- Content area -->
    <div class="content-area">
      <!-- Sidebar -->
      <div class="sidebar">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="sidebar-btn"
          :class="{ active: store.activeTab === t.id }"
          :title="t.label"
          @click="store.activeTab = t.id"
        >
          {{ t.icon }}
          <div v-if="store.activeTab === t.id" class="sidebar-indicator" />
        </button>
      </div>

      <!-- Main scroll area -->
      <div class="main-scroll">
        <div v-if="store.loading" class="loading-center">
          <div class="spinner" />
        </div>
        <div v-else-if="errorMsg" class="loading-center error-text">{{ errorMsg }}</div>
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
          <HistoryTab
            v-else-if="store.activeTab === 'history'"
            :status="status"
          />
          <SettingsTab
            v-else-if="store.activeTab === 'settings'"
            :vehicle="vehicle"
            :raw-data="store.currentData"
          />
        </template>
      </div>
    </div>
  </div>

  <ToastContainer />
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAppStore } from './stores/appStore'
import { useToast } from './composables/useToast'
import LoginView from './views/LoginView.vue'
import VehicleSelectorView from './views/VehicleSelectorView.vue'
import DashboardTab from './views/DashboardTab.vue'
import DetailsTab from './views/DetailsTab.vue'
import HistoryTab from './views/HistoryTab.vue'
import SettingsTab from './views/SettingsTab.vue'
import ToastContainer from './components/ToastContainer.vue'

const store = useAppStore()
const { toast } = useToast()

const errorMsg = ref('')

const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: '⊞' },
  { id: 'details', label: 'Details', icon: '☰' },
  { id: 'history', label: 'History', icon: '📈' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
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
    toast('Dati aggiornati', 'success')
  } catch (err) {
    toast(err.message, 'error')
  }
}

function handleLogout() {
  store.logout()
}

onMounted(async () => {
  const restored = await store.checkStatus()
  if (restored) {
    toast('Session restored', 'success')
  }
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
}

/* Navbar */
.navbar {
  background: var(--bg2);
  border-bottom: 1px solid var(--border2);
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}
.navbar-left { display: flex; align-items: center; gap: 10px; }
.navbar-logo {
  width: 32px; height: 32px; border-radius: 8px;
  background: #00d4ff18; border: 1px solid #00d4ff44;
  display: flex; align-items: center; justify-content: center;
}
.navbar-title {
  font-size: 14px; font-weight: 700; color: var(--text);
  letter-spacing: -0.01em;
}
.navbar-right { display: flex; align-items: center; gap: 10px; }
.connection-badge {
  display: flex; align-items: center; gap: 6px;
  background: #00e67614; border: 1px solid #00e67644;
  border-radius: 20px; padding: 4px 12px;
  font-size: 11px; font-weight: 700; color: #00e676;
  letter-spacing: 0.06em;
}
.connection-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #00e676; display: inline-block;
  box-shadow: 0 0 6px #00e676;
  animation: lm-pulse 2s infinite;
}
.nav-btn {
  background: none; border: 1px solid #1c2240;
  border-radius: 8px; padding: 5px 12px;
  color: var(--label); font-size: 12px; cursor: pointer;
  display: flex; align-items: center; gap: 5px;
  transition: all 0.2s;
}
.nav-btn:hover { background: #1c224044; color: var(--text); }
.spinning { display: inline-block; animation: lm-spin 0.7s linear infinite; }

/* Vehicle tabs bar */
.vehicle-tabs-bar {
  background: var(--bg2);
  border-bottom: 1px solid var(--border2);
  padding: 0 24px;
  display: flex;
  gap: 2px;
}
.vtab {
  background: none; border: none;
  border-bottom: 2px solid transparent;
  padding: 10px 16px; cursor: pointer;
  transition: all 0.2s; color: var(--muted);
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

/* Sidebar */
.sidebar {
  width: 56px;
  background: var(--bg2);
  border-right: 1px solid var(--border2);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 16px;
  gap: 6px;
  flex-shrink: 0;
}
.sidebar-btn {
  width: 40px; height: 40px; border-radius: 10px;
  border: none; cursor: pointer; font-size: 16px;
  background: transparent; color: #3a4468;
  transition: all 0.2s; position: relative;
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
  padding: 20px 24px;
}
.loading-center {
  display: flex; align-items: center; justify-content: center;
  height: 60vh;
}
.error-text { color: var(--red); font-size: 14px; }
</style>
