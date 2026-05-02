<template>
  <div class="setup-screen">
    <div class="setup-container">
      <div class="setup-brand">
        <div class="setup-brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h1>LeapConnect</h1>
        <p>Certificate Setup</p>
      </div>

      <div class="setup-card">
        <p class="setup-description">
          To communicate with Leapmotor servers, TLS certificates are required.
          Upload your certificate and private key files below.
        </p>

        <form @submit.prevent="handleSubmit" autocomplete="off">
          <div class="form-group">
            <label>App Certificate (.crt / .pem)</label>
            <div
              class="file-upload"
              :class="{ filled: certFile, dragover: certDragover }"
              @click="$refs.certInput.click()"
              @dragover.prevent="certDragover = true"
              @dragleave.prevent="certDragover = false"
              @drop.prevent="onCertDrop"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>{{ certFile ? certFile.name : 'Drop file here or click to choose…' }}</span>
            </div>
            <input ref="certInput" type="file" accept=".crt,.pem,.cer" hidden @change="onCertChange" />
          </div>

          <div class="form-group">
            <label>Private Key (.key / .pem)</label>
            <div
              class="file-upload"
              :class="{ filled: keyFile, dragover: keyDragover }"
              @click="$refs.keyInput.click()"
              @dragover.prevent="keyDragover = true"
              @dragleave.prevent="keyDragover = false"
              @drop.prevent="onKeyDrop"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>{{ keyFile ? keyFile.name : 'Drop file here or click to choose…' }}</span>
            </div>
            <input ref="keyInput" type="file" accept=".key,.pem" hidden @change="onKeyChange" />
          </div>

          <button type="submit" class="btn-primary" :disabled="submitting || !certFile || !keyFile">
            {{ submitting ? 'Uploading…' : 'Upload & Continue' }}
          </button>
          <div v-if="error" class="setup-error">{{ error }}</div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAppStore } from '../stores/appStore'

const store = useAppStore()
const submitting = ref(false)
const error = ref('')
const certFile = ref(null)
const keyFile = ref(null)
const certDragover = ref(false)
const keyDragover = ref(false)

function onCertChange(e) {
  certFile.value = e.target.files[0] || null
}

function onKeyChange(e) {
  keyFile.value = e.target.files[0] || null
}

function onCertDrop(e) {
  certDragover.value = false
  const file = e.dataTransfer.files[0]
  if (file) certFile.value = file
}

function onKeyDrop(e) {
  keyDragover.value = false
  const file = e.dataTransfer.files[0]
  if (file) keyFile.value = file
}

async function handleSubmit() {
  if (!certFile.value || !keyFile.value) return
  error.value = ''
  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('cert_file', certFile.value)
    formData.append('key_file', keyFile.value)

    const res = await fetch('/api/setup/certificates', {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)

    store.screen = 'setup-account'
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
  background: linear-gradient(135deg, #ff980022, #ff980044);
  border: 1px solid #ff980055;
  display: flex;
  align-items: center;
  justify-content: center;
}
.setup-brand-icon svg { width: 22px; height: 22px; color: #ff9800; }

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

.file-upload {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 16px;
  background: var(--input);
  border: 1px dashed #1c2240;
  border-radius: 10px;
  color: var(--muted2);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.file-upload:hover,
.file-upload.dragover {
  border-color: #00d4ff55;
  background: #00d4ff08;
}
.file-upload.filled {
  border-style: solid;
  border-color: #00d4ff44;
  color: var(--text);
}
.file-upload svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
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
</style>
