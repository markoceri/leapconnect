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

const store = useAppStore()
const { toast } = useToast()

const submitting = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
})

async function handleLogin() {
  error.value = ''
  submitting.value = true
  try {
    await store.login(form)
    toast('Connected successfully', 'success')
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
  background: var(--bg);
}

.login-container {
  width: 100%;
  max-width: 480px;
  padding: 2rem;
  animation: lm-slideup 0.5s ease both;
}

.login-brand {
  text-align: center;
  margin-bottom: 3rem;
}

.login-brand-icon {
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
.login-brand-icon svg { width: 22px; height: 22px; color: #00d4ff; }

.login-brand h1 {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}
.login-brand p {
  color: var(--muted);
  font-size: 13px;
  margin-top: 0.4rem;
}

.login-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 32px 28px;
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
.form-group small {
  display: block;
  margin-top: 0.3rem;
  font-size: 11px;
  color: var(--muted2);
}

.form-divider {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 1.5rem 0;
  color: var(--muted2);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.form-divider::before, .form-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.btn-login {
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
.btn-login:hover {
  background: linear-gradient(135deg, #00d4ff33, #00d4ff55);
}
.btn-login:disabled { opacity: 0.5; cursor: not-allowed; }

.login-error {
  margin-top: 1rem;
  padding: 9px 12px;
  background: #ff525210;
  border: 1px solid #ff525230;
  border-radius: 8px;
  color: var(--red);
  font-size: 12px;
}
</style>
