<template>
  <div class="login-screen">
    <div class="login-container">
      <div class="login-brand">
        <div class="login-brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C1.4 11.3 1 12.1 1 13v3c0 .6.4 1 1 1h2" />
            <circle cx="7" cy="17" r="2" />
            <circle cx="17" cy="17" r="2" />
          </svg>
        </div>
        <h1>Leapmotor</h1>
        <p>Vehicle Command Center</p>
      </div>

      <div class="login-card">
        <form @submit.prevent="handleLogin" autocomplete="off">
          <div class="form-group">
            <label>Email</label>
            <input v-model="form.username" type="email" placeholder="your@email.com" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input v-model="form.password" type="password" placeholder="Account password" required />
          </div>

          <div class="form-divider">Certificates</div>

          <div class="form-group">
            <label>App Certificate Path</label>
            <input v-model="form.app_cert_path" type="text" placeholder="/path/to/app-cert.pem" required />
          </div>
          <div class="form-group">
            <label>App Key Path</label>
            <input v-model="form.app_key_path" type="text" placeholder="/path/to/app-key.pem" required />
          </div>

          <div class="form-divider">Optional</div>

          <div class="form-group">
            <label>Vehicle PIN</label>
            <input v-model="form.operation_password" type="password" placeholder="Required for remote control" />
            <small>Without a PIN, only read-only data is available</small>
          </div>
          <div class="form-group">
            <label>P12 Password</label>
            <input v-model="form.account_p12_password" type="password" placeholder="Auto-derived if empty" />
            <small>Account certificate password (usually auto-detected)</small>
          </div>

          <button type="submit" class="btn-login" :disabled="submitting">
            {{ submitting ? 'Connecting…' : 'Connect to Leapmotor' }}
          </button>
          <div v-if="error" class="login-error visible">{{ error }}</div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useAppStore } from '../stores/appStore'
import { useToast } from '../composables/useToast'

const emit = defineEmits(['logged-in'])
const store = useAppStore()
const { toast } = useToast()

const submitting = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
  app_cert_path: '',
  app_key_path: '',
  operation_password: '',
  account_p12_password: '',
})

async function handleLogin() {
  error.value = ''
  submitting.value = true
  try {
    await store.login(form)
    toast('Connected successfully', 'success')
    emit('logged-in')
  } catch (err) {
    error.value = err.message
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-screen {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
}

.login-container {
  width: 100%;
  max-width: 480px;
  padding: 2rem;
  animation: loginReveal 0.8s ease both;
}

@keyframes loginReveal {
  from { opacity: 0; transform: translateY(30px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.login-brand {
  text-align: center;
  margin-bottom: 3rem;
}

.login-brand-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 1.2rem;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(0, 210, 230, 0.2);
}
.login-brand-icon svg { width: 32px; height: 32px; color: white; }

.login-brand h1 {
  font-size: 1.8rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.login-brand p {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-top: 0.4rem;
  font-weight: 300;
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 2rem;
  box-shadow: var(--shadow-card);
}

.form-group { margin-bottom: 1.2rem; }

.form-group label {
  display: block;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.5rem;
}

.form-group input {
  width: 100%;
  padding: 0.75rem 1rem;
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  transition: var(--transition);
  outline: none;
}
.form-group input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.form-group input::placeholder {
  color: var(--text-tertiary);
  font-family: var(--font-display);
}
.form-group small {
  display: block;
  margin-top: 0.3rem;
  font-size: 0.72rem;
  color: var(--text-tertiary);
}

.form-divider {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 1.5rem 0;
  color: var(--text-tertiary);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.form-divider::before, .form-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-default);
}

.btn-login {
  width: 100%;
  padding: 0.85rem;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  color: #fff;
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 600;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition);
  margin-top: 0.5rem;
}
.btn-login:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(0, 210, 230, 0.25);
}
.btn-login:active { transform: translateY(0); }
.btn-login:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.login-error {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 61, 90, 0.08);
  border: 1px solid rgba(255, 61, 90, 0.2);
  border-radius: var(--radius-sm);
  color: var(--accent-red);
  font-size: 0.82rem;
}
</style>
