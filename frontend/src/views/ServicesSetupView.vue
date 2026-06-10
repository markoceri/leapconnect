<template>
  <div class="setup-screen">
    <div class="setup-container">
      <div class="setup-brand">
        <div class="setup-brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" />
          </svg>
        </div>
        <h1>LeapConnect</h1>
        <p>Services Setup</p>
      </div>

      <p class="setup-subtitle">
        Configure optional services. You can skip this step and change these settings later.
      </p>

      <!-- ─── Data Recording ─── -->
      <div class="service-card">
        <div class="service-header">
          <div class="service-icon history-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" />
            </svg>
          </div>
          <div class="service-info">
            <h3>Data Recording</h3>
            <p>Periodically save vehicle data (battery, mileage, location) to the local database for history charts.</p>
          </div>
          <button
            class="toggle-btn"
            :class="{ active: historyEnabled }"
            @click="historyEnabled = !historyEnabled"
          >
            <span class="toggle-track"><span class="toggle-thumb" /></span>
          </button>
        </div>
        <Transition name="expand">
          <div v-if="historyEnabled" class="service-options">
            <div class="option-row">
              <span class="option-label">Collection interval</span>
              <div class="option-control">
                <button class="step-btn" @click="historyInterval = Math.max(1, historyInterval - 5)">−</button>
                <span class="option-value">{{ historyInterval }} min</span>
                <button class="step-btn" @click="historyInterval = Math.min(1440, historyInterval + 5)">+</button>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- ─── Home Assistant ─── -->
      <div class="service-card">
        <div class="service-header">
          <div class="service-icon ha-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12.55a11 11 0 0 1 14.08 0" /><path d="M1.42 9a16 16 0 0 1 21.16 0" /><path d="M8.53 16.11a6 6 0 0 1 6.95 0" /><line x1="12" y1="20" x2="12.01" y2="20" />
            </svg>
          </div>
          <div class="service-info">
            <h3>Home Assistant</h3>
            <p>Publish vehicle sensors and controls to Home Assistant via MQTT auto-discovery.</p>
          </div>
          <button
            class="toggle-btn"
            :class="{ active: mqttEnabled }"
            @click="mqttEnabled = !mqttEnabled"
          >
            <span class="toggle-track"><span class="toggle-thumb" /></span>
          </button>
        </div>
        <Transition name="expand">
          <div v-if="mqttEnabled" class="service-options">
            <div class="form-group">
              <label>MQTT Broker Host</label>
              <input v-model="mqttForm.broker" type="text" placeholder="192.168.1.x or hostname" />
            </div>
            <div class="form-row">
              <div class="form-group" style="flex:1">
                <label>Port</label>
                <input v-model.number="mqttForm.port" type="number" placeholder="1883" />
              </div>
              <div class="form-group" style="flex:0 0 auto">
                <label>TLS</label>
                <button
                  class="toggle-btn small"
                  :class="{ active: mqttForm.use_tls }"
                  @click="mqttForm.use_tls = !mqttForm.use_tls"
                  style="margin-top:6px"
                >
                  <span class="toggle-track"><span class="toggle-thumb" /></span>
                </button>
              </div>
            </div>
            <div class="form-group">
              <label>Username <span class="optional">(optional)</span></label>
              <input v-model="mqttForm.username" type="text" placeholder="MQTT username" />
            </div>
            <div class="form-group">
              <label>Password <span class="optional">(optional)</span></label>
              <input v-model="mqttForm.password" type="password" placeholder="MQTT password" />
            </div>
            <div class="option-row">
              <span class="option-label">Polling interval</span>
              <div class="option-control">
                <button class="step-btn" @click="mqttInterval = Math.max(10, mqttInterval <= 60 ? mqttInterval - 10 : mqttInterval - 60)">−</button>
                <span class="option-value">{{ formatSeconds(mqttInterval) }}</span>
                <button class="step-btn" @click="mqttInterval = Math.min(3600, mqttInterval < 60 ? mqttInterval + 10 : mqttInterval + 60)">+</button>
              </div>
            </div>
            <div v-if="mqttTestResult" :class="mqttTestResult.ok ? 'setup-success' : 'setup-error'" style="margin-top:8px">
              {{ mqttTestResult.message }}
            </div>
            <button class="btn-test" :disabled="mqttTesting || !mqttForm.broker" @click="testMqtt">
              {{ mqttTesting ? 'Testing…' : 'Test Connection' }}
            </button>
          </div>
        </Transition>
      </div>

      <!-- ─── ABRP ─── -->
      <div class="service-card">
        <div class="service-header">
          <div class="service-icon abrp-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="3 11 22 2 13 21 11 13 3 11" />
            </svg>
          </div>
          <div class="service-info">
            <h3>ABRP</h3>
            <p>Send live telemetry to A Better Route Planner for real-time route planning and car model calibration.</p>
          </div>
          <button
            class="toggle-btn"
            :class="{ active: abrpEnabled }"
            @click="abrpEnabled = !abrpEnabled"
          >
            <span class="toggle-track"><span class="toggle-thumb" /></span>
          </button>
        </div>
        <Transition name="expand">
          <div v-if="abrpEnabled" class="service-options">
            <div class="form-group">
              <label>User Token</label>
              <input v-model="abrpForm.user_token" type="password" placeholder="Live data token from ABRP settings" />
            </div>
          </div>
        </Transition>
      </div>

      <!-- ─── Telegram Bot ─── -->
      <div class="service-card">
        <div class="service-header">
          <div class="service-icon telegram-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </div>
          <div class="service-info">
            <h3>Telegram Bot</h3>
            <p>Receive notifications and control your vehicle remotely via Telegram.</p>
          </div>
          <button
            class="toggle-btn"
            :class="{ active: telegramEnabled }"
            @click="telegramEnabled = !telegramEnabled"
          >
            <span class="toggle-track"><span class="toggle-thumb" /></span>
          </button>
        </div>
        <Transition name="expand">
          <div v-if="telegramEnabled" class="service-options">
            <p class="section-desc">
              Create a bot with <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a> on Telegram,
              then paste the token below. To find your Chat ID, send a message to your bot
              and visit <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code>.
            </p>
            <div class="form-group">
              <label>Bot Token</label>
              <input v-model="telegramForm.bot_token" :type="showTelegramSecrets ? 'text' : 'password'" placeholder="123456:ABC-DEF..." />
            </div>
            <div class="form-group">
              <label>Chat ID</label>
              <input v-model="telegramForm.chat_id" :type="showTelegramSecrets ? 'text' : 'password'" placeholder="-100123456789" />
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="telegramForm.bot_enabled" />
                <span>Enable bot commands</span>
              </label>
              <span class="field-hint">Allow /status, /lock, /climate and other commands from Telegram.</span>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="telegramForm.channel_enabled" />
                <span>Enable notifications</span>
              </label>
              <span class="field-hint">Send vehicle alerts (charging started, geofence, etc.) to this Telegram channel.</span>
            </div>
            <div v-if="telegramTestResult" :class="telegramTestResult.ok ? 'setup-success' : 'setup-error'" style="margin-top:8px">
              {{ telegramTestResult.message }}
            </div>
            <div class="channel-actions">
              <button class="btn-test" :disabled="telegramTesting || !telegramForm.bot_token || !telegramForm.chat_id" @click="testTelegram">
                {{ telegramTesting ? 'Testing…' : 'Test Connection' }}
              </button>
            </div>
          </div>
        </Transition>
      </div>

      <!-- ─── Actions ─── -->
      <div v-if="error" class="setup-error">{{ error }}</div>

      <button class="btn-primary" :disabled="submitting" @click="handleContinue">
        {{ submitting ? 'Saving…' : (historyEnabled || mqttEnabled || abrpEnabled || telegramEnabled) ? 'Save & Continue' : 'Skip & Continue' }}
      </button>
      <div class="theme-row">
        <div class="theme-pills">
          <button class="theme-pill" :class="{ active: store.theme === 'dark' }" @click="store.setTheme('dark')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            Dark
          </button>
          <button class="theme-pill" :class="{ active: store.theme === 'light' }" @click="store.setTheme('light')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
            Light
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useAppStore } from '../stores/appStore'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'

const store = useAppStore()
const { toast } = useToast()

const submitting = ref(false)
const error = ref('')

// History / Data Recording
const historyEnabled = ref(false)
const historyInterval = ref(1)

// MQTT / Home Assistant
const mqttEnabled = ref(false)
const mqttInterval = ref(10)
const mqttTesting = ref(false)
const mqttTestResult = ref(null)
const mqttForm = reactive({
  broker: '',
  port: 1883,
  username: '',
  password: '',
  use_tls: false,
})

// ABRP
const abrpEnabled = ref(false)
const abrpForm = reactive({
  user_token: '',
})

// Telegram Bot
const telegramEnabled = ref(false)
const telegramTesting = ref(false)
const telegramTestResult = ref(null)
const showTelegramSecrets = ref(false)
const telegramForm = reactive({
  bot_token: '',
  chat_id: '',
  bot_enabled: true,
  channel_enabled: true,
})

function formatSeconds(s) {
  if (s < 60) return `${s} sec`
  const m = Math.round(s / 60)
  return `${m} min`
}

async function testMqtt() {
  mqttTesting.value = true
  mqttTestResult.value = null
  try {
    const data = await api('POST', '/api/mqtt/test', {
      broker: mqttForm.broker,
      port: mqttForm.port,
      username: mqttForm.username,
      password: mqttForm.password,
      use_tls: mqttForm.use_tls,
    })
    mqttTestResult.value = {
      ok: data.status === 'ok',
      message: data.message,
    }
  } catch (err) {
    mqttTestResult.value = { ok: false, message: err.message }
  } finally {
    mqttTesting.value = false
  }
}
async function testTelegram() {
  telegramTesting.value = true
  telegramTestResult.value = null
  try {
    // Create or update a temporary channel to test
    const data = await api('POST', '/api/notifications/channels', {
      channel_type: 'telegram',
      config: { bot_token: telegramForm.bot_token, chat_id: telegramForm.chat_id, bot_enabled: telegramForm.bot_enabled },
      enabled: telegramForm.channel_enabled,
    })
    // Test the channel
    const test = await api('POST', `/api/notifications/channels/${data.id}/test`)
    telegramTestResult.value = { ok: test.success, message: test.message || 'Test notification sent. Check Telegram.' }
    // Clean up the test channel
    await api('DELETE', `/api/notifications/channels/${data.id}`)
  } catch (err) {
    telegramTestResult.value = { ok: false, message: err.message }
  } finally {
    telegramTesting.value = false
  }
}
function proceedToApp() {
  if (store.vehicles.length === 1) {
    store.selectedVin = store.vehicles[0].vin
    store.screen = 'app'
  } else if (store.vehicles.length > 1) {
    store.screen = 'vehicles'
  } else {
    store.screen = 'app'
  }
}

async function handleContinue() {
  error.value = ''
  submitting.value = true
  try {
    // Save scheduler (history recording) settings
    if (historyEnabled.value) {
      await api('PUT', '/api/scheduler', {
        enabled: true,
        interval_minutes: historyInterval.value,
      })
    }

    // Save MQTT settings
    if (mqttEnabled.value && mqttForm.broker) {
      await api('PUT', '/api/mqtt', {
        enabled: true,
        broker: mqttForm.broker,
        port: mqttForm.port,
        username: mqttForm.username,
        password: mqttForm.password || undefined,
        use_tls: mqttForm.use_tls,
      })
      // Also set the MQTT polling interval on the scheduler
      await api('PUT', '/api/scheduler', {
        mqtt_interval_seconds: mqttInterval.value,
      })
    }

    // Save ABRP settings
    if (abrpEnabled.value && abrpForm.user_token) {
      await api('PUT', '/api/abrp', {
        enabled: true,
        user_token: abrpForm.user_token,
      })
    }

    // Save Telegram bot channel
    if (telegramEnabled.value && telegramForm.bot_token && telegramForm.chat_id) {
      await api('POST', '/api/notifications/channels', {
        channel_type: 'telegram',
        config: {
          bot_token: telegramForm.bot_token,
          chat_id: telegramForm.chat_id,
          bot_enabled: telegramForm.bot_enabled,
        },
        enabled: telegramForm.channel_enabled,
      })
    }

    toast('Services configured', 'success')
    proceedToApp()
  } catch (err) {
    error.value = err.message
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.setup-screen {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  overflow-y: auto;
}

.setup-container {
  width: 100%;
  max-width: 520px;
  padding: 1.5rem;
  animation: lm-slideup 0.5s ease both;
}

/* ─── Theme row ─── */
.theme-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 1rem;
}
.theme-label {
  font-size: 12px;
  color: var(--muted);
  font-weight: 500;
}
.theme-pills {
  display: flex;
  gap: 4px;
}
.theme-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  background: var(--input);
  border: 1px solid var(--border);
  color: var(--label);
  cursor: pointer;
  transition: all 0.2s;
}
.theme-pill:hover:not(.active) {
  border-color: var(--muted);
  color: var(--text);
}
.theme-pill.active {
  background: #7c6aff22;
  border-color: #7c6aff66;
  color: #7c6aff;
}
.theme-pill svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}
@media (min-width: 640px) {
  .setup-container { padding: 2rem; }
}

.setup-brand {
  text-align: center;
  margin-bottom: 1.2rem;
}

.setup-brand-icon {
  width: 44px;
  height: 44px;
  margin: 0 auto 1.2rem;
  border-radius: 12px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  display: flex;
  align-items: center;
  justify-content: center;
}
.setup-brand-icon svg { width: 22px; height: 22px; color: #00d4ff; }

.setup-brand h1 {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}
.setup-brand p {
  color: var(--muted);
  font-size: 13px;
  margin-top: 0.4rem;
}

.setup-subtitle {
  text-align: center;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
  margin-bottom: 1.5rem;
}

/* ─── Service cards ─── */
.service-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
}

.service-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.service-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.service-icon svg { width: 18px; height: 18px; }
.history-icon { background: #7c6aff22; border: 1px solid #7c6aff44; }
.history-icon svg { color: #7c6aff; }
.ha-icon { background: #00d4ff22; border: 1px solid #00d4ff44; }
.ha-icon svg { color: #00d4ff; }
.abrp-icon { background: #4caf5022; border: 1px solid #4caf5044; }
.abrp-icon svg { color: #4caf50; }
.telegram-icon { background: #039be522; border: 1px solid #039be544; }
.telegram-icon svg { color: #039be5; }

.service-info {
  flex: 1;
  min-width: 0;
}
.service-info h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}
.service-info p {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.4;
}

/* ─── Toggle button ─── */
.toggle-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 0 0;
  flex-shrink: 0;
}
.toggle-track {
  display: block;
  width: 40px;
  height: 22px;
  border-radius: 12px;
  background: var(--btn-bg);
  position: relative;
  transition: background 0.25s;
}
.toggle-btn.active .toggle-track {
  background: #00d4ff;
}
.toggle-thumb {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #e2e6f0;
  position: absolute;
  top: 3px;
  left: 3px;
  transition: transform 0.25s;
}
.toggle-btn.active .toggle-thumb {
  transform: translateX(18px);
  background: #fff;
}
.toggle-btn.small .toggle-track {
  width: 34px;
  height: 18px;
}
.toggle-btn.small .toggle-thumb {
  width: 12px;
  height: 12px;
  top: 3px;
  left: 3px;
}
.toggle-btn.small.active .toggle-thumb {
  transform: translateX(16px);
}

/* ─── Expandable options ─── */
.service-options {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
  padding-top: 0;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.option-label {
  font-size: 12px;
  color: var(--label);
  font-weight: 500;
}

.option-control {
  display: flex;
  align-items: center;
  gap: 6px;
}

.step-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.step-btn:hover { background: var(--border); }

.option-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  min-width: 56px;
  text-align: center;
}

/* ─── Form fields ─── */
.form-group {
  margin-bottom: 10px;
}
.form-group label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 5px;
}
.form-group .optional {
  text-transform: none;
  letter-spacing: normal;
  opacity: 0.6;
}
.form-group input {
  width: 100%;
  padding: 10px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus {
  border-color: #00d4ff;
}
.form-group input::placeholder {
  color: var(--muted);
  opacity: 0.5;
}

.form-row {
  display: flex;
  gap: 10px;
}

/* ─── Buttons ─── */
.btn-primary {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #00d4ff, #0099cc);
  color: #000;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
  transition: opacity 0.2s;
}
.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-test {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: transparent;
  color: var(--label);
  font-size: 12px;
  cursor: pointer;
  margin-top: 10px;
  transition: all 0.2s;
}
.btn-test:hover { background: var(--border); color: var(--text); }
.btn-test:disabled { opacity: 0.5; cursor: not-allowed; }

/* ─── Messages ─── */
.setup-error {
  background: #ff525218;
  border: 1px solid #ff525244;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 12px;
  color: #ff5252;
  margin-top: 8px;
}
.setup-success {
  background: #00e67618;
  border: 1px solid #00e67644;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 12px;
  color: #00e676;
}

/* ─── Section description ─── */
.section-desc {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.5;
  margin-bottom: 0.8rem;
}
.section-desc a {
  color: var(--cyan);
  text-decoration: none;
}
.section-desc a:hover { text-decoration: underline; }
.section-desc code {
  background: var(--bg);
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 11px;
  word-break: break-all;
}

/* ─── Checkbox label ─── */
.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: 8px;
  text-transform: none !important;
  letter-spacing: normal !important;
  font-size: 13px !important;
  color: var(--text) !important;
  font-weight: 500 !important;
  cursor: pointer;
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--cyan);
  cursor: pointer;
  flex-shrink: 0;
}

/* ─── Field hint ─── */
.field-hint {
  display: block;
  font-size: 11px;
  color: var(--muted2);
  margin-top: 3px;
  margin-left: 24px;
}

/* ─── Channel actions ─── */
.channel-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.channel-actions .btn-test {
  flex: 1;
  margin-top: 0;
}
</style>
