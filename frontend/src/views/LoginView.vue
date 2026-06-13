<template>
  <div class="login-screen">
    <div class="login-container">
      <div class="login-brand">
        <div class="login-brand-icon">
          <Car :size="22" />
        </div>
        <h1>LeapConnect</h1>
        <p>Vehicle Dashboard</p>
      </div>

      <div class="login-card">
        <form @submit.prevent="handleLogin" autocomplete="off">
          <div class="form-group">
            <label>Password</label>
            <div class="password-wrapper">
              <input v-model="form.password" :type="showPassword ? 'text' : 'password'" placeholder="Enter your password" required autofocus />
              <button type="button" class="password-toggle" @click="showPassword = !showPassword" tabindex="-1">
                <Eye v-if="!showPassword" :size="18" />
                <EyeOff v-else :size="18" />
              </button>
            </div>
          </div>

          <button type="submit" class="btn-login" :disabled="submitting">
            {{ submitting ? 'Signing in…' : 'Sign In' }}
          </button>
          <div v-if="error" class="login-error visible">{{ error }}</div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Car, Eye, EyeOff } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { api } from '../composables/useApi'

const store = useAppStore()

const submitting = ref(false)
const error = ref('')

const showPassword = ref(false)
const form = reactive({
  password: '',
})

async function handleLogin() {
  error.value = ''
  submitting.value = true
  try {
    await api('POST', '/api/auth/session', { password: form.password })
    // Re-check status — session cookie is now set
    await store.checkStatus()
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
  padding: 1.5rem;
  animation: lm-slideup 0.5s ease both;
}

@media (min-width: 640px) {
  .login-container { padding: 2rem; }
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
  background: linear-gradient(135deg, color-mix(in srgb, var(--cyan) 13%, transparent), color-mix(in srgb, var(--cyan) 27%, transparent));
  border: 1px solid color-mix(in srgb, var(--cyan) 33%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cyan);
}

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
  padding: 24px 20px;
}
@media (min-width: 640px) {
  .login-card { padding: 32px 28px; }
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
  border: 1px solid var(--btn-border);
  border-radius: 10px;
  color: var(--text);
  font-size: 14px;
  transition: border-color 0.2s;
  outline: none;
}
.form-group input:focus {
  border-color: color-mix(in srgb, var(--cyan) 33%, transparent);
}
.form-group input::placeholder {
  color: var(--muted2);
}

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
  color: var(--muted);
  transition: color 0.2s;
}
.password-toggle:hover svg { color: var(--text); }

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
  background: linear-gradient(135deg, color-mix(in srgb, var(--cyan) 13%, transparent), color-mix(in srgb, var(--cyan) 27%, transparent));
  border: 1px solid color-mix(in srgb, var(--cyan) 33%, transparent);
  border-radius: 10px;
  color: var(--cyan);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.04em;
}
.btn-login:hover {
  background: linear-gradient(135deg, color-mix(in srgb, var(--cyan) 20%, transparent), color-mix(in srgb, var(--cyan) 33%, transparent));
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
