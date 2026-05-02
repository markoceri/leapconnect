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
        <p>Create Your Account</p>
      </div>

      <div class="setup-card">
        <p class="setup-description">
          Welcome! Create a LeapConnect account to get started.
          This account is local to this application.
        </p>

        <form @submit.prevent="handleSubmit" autocomplete="off">
          <div class="form-group">
            <label>Display Name</label>
            <input v-model="form.display_name" type="text" placeholder="Your name" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <div class="password-wrapper">
              <input v-model="form.password" :type="showPassword ? 'text' : 'password'" placeholder="Choose a password" required />
              <button type="button" class="password-toggle" @click="showPassword = !showPassword" tabindex="-1">
                <svg v-if="!showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              </button>
            </div>
          </div>
          <div class="form-group">
            <label>Confirm Password</label>
            <div class="password-wrapper">
              <input v-model="form.confirm" :type="showPassword ? 'text' : 'password'" placeholder="Confirm password" required />
            </div>
          </div>

          <button type="submit" class="btn-primary" :disabled="submitting">
            {{ submitting ? 'Creating…' : 'Create Account' }}
          </button>
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

const store = useAppStore()
const submitting = ref(false)
const showPassword = ref(false)
const error = ref('')

const form = reactive({
  display_name: '',
  password: '',
  confirm: '',
})

async function handleSubmit() {
  error.value = ''
  if (form.password !== form.confirm) {
    error.value = 'Passwords do not match'
    return
  }
  if (form.password.length < 4) {
    error.value = 'Password must be at least 4 characters'
    return
  }
  submitting.value = true
  try {
    await api('POST', '/api/setup/user', {
      display_name: form.display_name,
      password: form.password,
    })
    store.screen = 'setup-certs'
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
  background: linear-gradient(135deg, #7c6aff22, #7c6aff44);
  border: 1px solid #7c6aff55;
  display: flex;
  align-items: center;
  justify-content: center;
}
.setup-brand-icon svg { width: 22px; height: 22px; color: #7c6aff; }

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
.form-group input:focus { border-color: #7c6aff55; }
.form-group input::placeholder { color: var(--muted2); }

.password-wrapper { position: relative; }
.password-wrapper input { padding-right: 44px; }

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
.password-toggle:hover svg { color: var(--text); }

.btn-primary {
  width: 100%;
  padding: 14px;
  margin-top: 6px;
  background: linear-gradient(135deg, #7c6aff22, #7c6aff44);
  border: 1px solid #7c6aff55;
  border-radius: 10px;
  color: #7c6aff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.04em;
}
.btn-primary:hover { background: linear-gradient(135deg, #7c6aff33, #7c6aff55); }
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
</style>
