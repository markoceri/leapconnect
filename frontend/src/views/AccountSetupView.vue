<template>
  <div class="setup-screen">
    <div class="setup-container">
      <div class="setup-brand">
        <div class="setup-brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <h1>LeapConnect</h1>
        <p>Leapmotor Account</p>
      </div>

      <div class="setup-card">
        <p class="setup-description">
          Enter your Leapmotor account credentials.
          They will be saved locally and used to automatically connect to the servers
          and collect vehicle data.
        </p>

        <div class="setup-hint">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="hint-icon">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span>Consider creating a <strong>shared/secondary account</strong> in the Leapmotor app and sharing the vehicle with it. This avoids conflicts with your primary account sessions (e.g. being logged out from the phone app or temporary account locks on Leapmotor's servers).</span>
        </div>

        <form @submit.prevent="handleSubmit" autocomplete="off">
          <div class="form-group">
            <label>Email</label>
            <input v-model="form.username" type="email" placeholder="your@email.com" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <div class="password-wrapper">
              <input v-model="form.password" :type="showPassword ? 'text' : 'password'" placeholder="Leapmotor account password" required />
              <button type="button" class="password-toggle" @click="showPassword = !showPassword" tabindex="-1">
                <svg v-if="!showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              </button>
            </div>
          </div>

          <div class="setup-buttons">
            <button type="button" class="btn-primary" :disabled="testingConnection || submitting" @click="testConnection">
              <svg v-if="testingConnection" class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.2" />
                <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round" />
              </svg>
              {{ testingConnection ? 'Testing…' : 'Test Connection' }}
            </button>
            <button type="submit" class="btn-primary" :disabled="submitting || testingConnection">
              {{ submitting ? 'Saving…' : 'Save & Connect' }}
            </button>
          </div>

          <div v-if="testSuccess" class="setup-success">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5" /></svg>
            Connection successful — {{ testVehicles }} vehicle(s) found.
          </div>
          <div v-if="testError" class="setup-error">{{ testError }}</div>
          <div v-if="warning" class="setup-warning">
            <strong>Credentials saved.</strong> {{ warning }}
          </div>
          <div v-if="error" class="setup-error">{{ error }}</div>
        </form>
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
const testingConnection = ref(false)
const showPassword = ref(false)
const error = ref('')
const warning = ref('')
const testSuccess = ref(false)
const testError = ref('')
const testVehicles = ref(0)

const form = reactive({
  username: '',
  password: '',
})

async function testConnection() {
  testError.value = ''
  testSuccess.value = false
  testingConnection.value = true
  try {
    const result = await api('POST', '/api/setup/account/test', {
      username: form.username,
      password: form.password,
    })

    if (result.connected) {
      testSuccess.value = true
      testVehicles.value = result.vehicles?.length || 0
      toast('Connection successful', 'success')
    } else {
      testError.value = result.connection_error || 'Connection failed'
    }
  } catch (err) {
    testError.value = err.message
  } finally {
    testingConnection.value = false
  }
}

async function handleSubmit() {
  error.value = ''
  warning.value = ''
  submitting.value = true
  try {
    const payload = {
      username: form.username,
      password: form.password,
    }

    const result = await api('POST', '/api/setup/account', payload)

    if (result.connected) {
      store.connected = true
      store.vehicles = result.vehicles || []
      toast('Connected successfully', 'success')
      store.screen = 'setup-services'
    } else {
      // Credentials saved but connection failed — proceed to services setup in offline mode
      warning.value = result.connection_error || 'Could not connect to servers. The app will work in offline mode.'
      store.connected = false
      // After a short delay, proceed to services setup anyway
      setTimeout(() => {
        store.screen = 'setup-services'
      }, 3000)
    }
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
}

.setup-container {
  width: 100%;
  max-width: 480px;
  padding: 1.5rem;
  animation: lm-slideup 0.5s ease both;
}
@media (min-width: 640px) {
  .setup-container { padding: 2rem; }
}

.setup-brand {
  text-align: center;
  margin-bottom: 2rem;
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

.setup-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 24px 20px;
}
@media (min-width: 640px) {
  .setup-card { padding: 32px 28px; }
}

.setup-description {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
  margin-bottom: 1rem;
}

.setup-hint {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: #ffab4012;
  border: 1px solid #ffab4030;
  border-radius: 10px;
  margin-bottom: 1.5rem;
  font-size: 12px;
  line-height: 1.5;
  color: #e8d0a0;
}
.setup-hint .hint-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: #ffab40;
  margin-top: 1px;
}
.setup-hint strong {
  color: #ffab40;
  font-weight: 600;
}

[data-theme="light"] .setup-hint {
  background: #ffab4015;
  border-color: #ffab4050;
  color: #5a3a10;
}
[data-theme="light"] .setup-hint strong {
  color: #b8700a;
}
.setup-hint strong {
  color: #ffab40;
  font-weight: 600;
}

.form-group { margin-bottom: 1.1rem; }

.form-group label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 7px;
}

.password-wrapper {
  position: relative;
}

.password-wrapper input {
  padding-right: 44px;
}

.password-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.password-toggle svg {
  width: 18px;
  height: 18px;
  color: var(--muted);
  transition: color 0.2s;
}
.password-toggle:hover svg {
  color: var(--text);
}

.form-group input {
  width: 100%;
  padding: 13px 16px;
  background: var(--input);
  border: 1px solid var(--btn-border);
  border-radius: 10px;
  color: var(--text);
  font-size: 14px;
  transition: border-color 0.2s;
  outline: none;
}
.form-group input:focus {
  border-color: #00d4ff55;
}
.form-group input::placeholder {
  color: var(--muted2);
}

.btn-primary {
  flex: 1;
  padding: 14px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 10px;
  color: #00d4ff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.btn-primary:hover {
  background: linear-gradient(135deg, #00d4ff33, #00d4ff55);
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.setup-buttons {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}

.spinner {
  width: 16px;
  height: 16px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.setup-success {
  margin-top: 1rem;
  padding: 9px 12px;
  background: #00e67610;
  border: 1px solid #00e67630;
  border-radius: 8px;
  color: #00e676;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.setup-success svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.setup-error {
  margin-top: 1rem;
  padding: 9px 12px;
  background: #ff525210;
  border: 1px solid #ff525230;
  border-radius: 8px;
  color: var(--red);
  font-size: 12px;
}

.setup-warning {
  margin-top: 1rem;
  padding: 9px 12px;
  background: #ff980010;
  border: 1px solid #ff980030;
  border-radius: 8px;
  color: #ff9800;
  font-size: 12px;
  line-height: 1.4;
}
</style>
