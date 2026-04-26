<template>
  <div class="vehicle-selector">
    <!-- Top bar -->
    <div class="vs-topbar">
      <div class="vs-brand">
        <div class="vs-logo">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#00d4ff" stroke-width="2">
            <path d="M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v9a2 2 0 01-2 2h-2" />
            <circle cx="9" cy="17" r="2" /><circle cx="17" cy="17" r="2" />
          </svg>
        </div>
        <span class="vs-brand-text">Leapmotor</span>
      </div>
    </div>

    <div class="vs-content">
      <div class="vs-header">
        <h1>I tuoi veicoli</h1>
        <p>Seleziona un veicolo per accedere al pannello di controllo</p>
      </div>

      <div class="vs-grid">
        <div
          v-for="v in vehicles"
          :key="v.vin"
          class="vs-card"
          @click="$emit('select', v.vin)"
        >
          <div class="vs-card-hero">
            <DynamicCarImage :vin="v.vin" :status="store.vehicleData[v.vin]?.status" />
          </div>
          <div class="vs-card-info">
            <div class="vs-card-top">
              <div>
                <div class="vs-card-name">{{ v.nickname || v.car_type || 'Leapmotor' }}</div>
                <div class="vs-card-vin">{{ v.vin }}</div>
              </div>
              <div class="vs-card-badge" :class="{ charging: getStatus(v.vin, 'battery', 'is_charging') }">
                {{ getStatus(v.vin, 'battery', 'is_charging') ? '⚡ Ricarica' : v.car_type || 'EV' }}
              </div>
            </div>
            <div class="vs-card-stats">
              <div class="vs-stat">
                <div class="vs-stat-value" :style="{ color: battColor(v.vin) }">
                  {{ getStatus(v.vin, 'battery', 'soc') ?? '—' }}{{ getStatus(v.vin, 'battery', 'soc') != null ? '%' : '' }}
                </div>
                <div class="vs-stat-label">Batteria</div>
              </div>
              <div class="vs-stat">
                <div class="vs-stat-value" style="color:#00d4ff">
                  {{ getStatus(v.vin, 'battery', 'expected_mileage') ?? '—' }}{{ getStatus(v.vin, 'battery', 'expected_mileage') != null ? ' km' : '' }}
                </div>
                <div class="vs-stat-label">Autonomia</div>
              </div>
              <div class="vs-stat">
                <div class="vs-stat-value" style="color:#8892a8">
                  {{ formatOdo(v.vin) }}
                </div>
                <div class="vs-stat-label">Odometro</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAppStore } from '../stores/appStore'
import DynamicCarImage from '../components/DynamicCarImage.vue'

defineProps({
  vehicles: { type: Array, required: true },
})
defineEmits(['select'])

const store = useAppStore()
function getStatus(vin, section, key) {
  const data = store.vehicleData[vin]
  if (!data?.status?.[section]) return null
  return data.status[section][key] ?? null
}

function battColor(vin) {
  const soc = getStatus(vin, 'battery', 'soc')
  if (soc == null) return '#8892a8'
  return soc > 50 ? '#00e676' : soc > 20 ? '#ffab40' : '#ff5252'
}

function formatOdo(vin) {
  const val = getStatus(vin, 'driving', 'total_mileage')
  if (val == null) return '—'
  return val.toLocaleString() + ' km'
}
</script>

<style scoped>
.vehicle-selector {
  min-height: 100vh;
  background: var(--bg);
  padding: 24px;
}
.vs-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 900px;
  margin: 0 auto 36px;
}
.vs-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.vs-logo {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: #00d4ff18;
  border: 1px solid #00d4ff44;
  display: flex;
  align-items: center;
  justify-content: center;
}
.vs-brand-text {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.vs-content {
  max-width: 900px;
  margin: 0 auto;
  animation: lm-slideup 0.4s ease;
}
.vs-header { margin-bottom: 28px; }
.vs-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 6px;
}
.vs-header p {
  font-size: 13px;
  color: var(--muted);
}
.vs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 18px;
}
.vs-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s;
}
.vs-card:hover {
  border-color: #00d4ff44;
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(0,212,255,0.08);
}
.vs-card-hero {
  background: linear-gradient(160deg, #0e1525, #12192a);
  padding: 24px 24px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: center;
}
.vs-card-info { padding: 16px 20px; }
.vs-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.vs-card-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.vs-card-vin {
  font-size: 11px;
  color: var(--muted2);
  margin-top: 2px;
  font-family: var(--mono);
}
.vs-card-badge {
  font-size: 11px;
  background: #1c2240;
  color: var(--muted3);
  border: 1px solid #1c2240;
  border-radius: 20px;
  padding: 3px 9px;
  font-weight: 600;
}
.vs-card-badge.charging {
  background: #00e67614;
  color: #00e676;
  border-color: #00e67644;
}
.vs-card-stats {
  display: flex;
  gap: 12px;
}
.vs-stat {
  flex: 1;
  text-align: center;
}
.vs-stat-value {
  font-size: 14px;
  font-weight: 700;
}
.vs-stat-label {
  font-size: 10px;
  color: var(--muted2);
  margin-top: 2px;
}
</style>
