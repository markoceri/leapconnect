<template>
  <div class="settings-tab">
    <!-- Account -->
    <SectionCard title="Account" icon="👤">
      <div class="account-row">
        <div class="account-avatar">{{ initials }}</div>
        <div>
          <div class="account-name">{{ displayName }}</div>
          <div class="account-email">{{ email }}</div>
        </div>
      </div>
      <InfoRow label="Versione app" value="v2.4.1" color="#5c6478" />
    </SectionCard>

    <!-- Vehicle -->
    <SectionCard title="Veicolo" icon="🚗">
      <InfoRow label="Modello" :value="`${vehicle.year || ''} Leapmotor ${vehicle.car_type || ''}`" color="#e2e6f0" />
      <InfoRow label="VIN" color="#e2e6f0">
        <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
      </InfoRow>
      <InfoRow label="Nickname" :value="vehicle.nickname || '—'" color="#00d4ff" />
    </SectionCard>

    <!-- Notifications -->
    <SectionCard title="Notifiche" icon="🔔">
      <div v-for="n in notifications" :key="n.key" class="notif-row">
        <span class="notif-label">{{ n.label }}</span>
        <ToggleSwitch v-model="n.enabled" />
      </div>
    </SectionCard>

    <!-- Preferences -->
    <SectionCard title="Preferenze" icon="🎛">
      <InfoRow label="Unità distanza" value="km" color="#e2e6f0" />
      <InfoRow label="Unità pressione" value="bar" color="#e2e6f0" />
      <InfoRow label="Tema" value="Dark" color="#7c6aff" />
      <InfoRow label="Lingua" value="Italiano" color="#e2e6f0" />
    </SectionCard>

    <!-- Raw Data toggle -->
    <SectionCard title="Dati grezzi" icon="{ }">
      <button class="raw-toggle" @click="showRaw = !showRaw">
        {{ showRaw ? 'Nascondi' : 'Mostra' }} JSON completo
      </button>
      <div v-if="showRaw" class="raw-panel">
        <pre>{{ JSON.stringify(rawData, null, 2) }}</pre>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import SectionCard from '../components/SectionCard.vue'
import InfoRow from '../components/InfoRow.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'

const props = defineProps({
  vehicle: { type: Object, required: true },
  rawData: { type: Object, default: () => ({}) },
})

const showRaw = ref(false)

const email = computed(() => {
  // We don't have user email from the API, show placeholder
  return '—'
})
const displayName = computed(() => props.vehicle.nickname || 'User')
const initials = computed(() => {
  const n = displayName.value
  return n.substring(0, 2).toUpperCase()
})

const notifications = reactive([
  { label: 'Carica completata', key: 'notifCharge', enabled: true },
  { label: 'Batteria scarica (<20%)', key: 'notifLow', enabled: true },
  { label: 'Pressione pneumatici', key: 'notifTire', enabled: true },
  { label: 'Aggiornamenti software', key: 'notifOTA', enabled: false },
])
</script>

<style scoped>
.settings-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 640px;
}

.account-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0 16px;
}
.account-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #00d4ff22;
  border: 2px solid #00d4ff55;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #00d4ff;
}
.account-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.account-email {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.notif-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #181d2c;
}
.notif-row:last-child { border-bottom: none; }
.notif-label { font-size: 13px; color: var(--sub); }

.raw-toggle {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--muted);
  font-size: 12px;
  font-family: var(--mono);
  cursor: pointer;
  transition: all 0.2s;
}
.raw-toggle:hover { color: var(--sub); border-color: #00d4ff44; }

.raw-panel {
  max-height: 400px;
  overflow: auto;
  background: #0d1018;
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
}
.raw-panel pre {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted3);
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
