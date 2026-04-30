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

        <form @submit.prevent="handleSubmit" autocomplete="off">
          <div class="form-group">
            <label>Email</label>
            <input v-model="form.username" type="email" placeholder="your@email.com" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input v-model="form.password" type="password" placeholder="Leapmotor account password" required />
          </div>

          <button type="submit" class="btn-primary" :disabled="submitting">
            {{ submitting ? 'Saving…' : 'Save & Connect' }}
          </button>

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
const error = ref('')
const warning = ref('')

const form = reactive({
  username: '',
  password: '',
})

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
      if (store.vehicles.length === 1) {
        store.selectedVin = store.vehicles[0].vin
        store.screen = 'app'
      } else if (store.vehicles.length > 1) {
        store.screen = 'vehicles'
      } else {
        store.screen = 'app'
      }
    } else {
      // Credentials saved but connection failed — go to app in offline mode
      warning.value = result.connection_error || 'Could not connect to servers. The app will work in offline mode.'
      store.connected = false
      // After a short delay, proceed to app anyway
      setTimeout(() => {
        store.screen = 'app'
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
  margin-bottom: 1.5rem;
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

.form-group input {
  width: 100%;
  padding: 13px 16px;
  background: var(--input);
  border: 1px solid #1c2240;
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
  width: 100%;
  padding: 14px;
  margin-top: 6px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 10px;
  color: #00d4ff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.04em;
}
.btn-primary:hover {
  background: linear-gradient(135deg, #00d4ff33, #00d4ff55);
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

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
