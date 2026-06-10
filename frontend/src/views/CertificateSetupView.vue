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
        <div v-if="certsOnDisk" class="certs-found-banner">
          <div class="certs-found-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <div class="certs-found-text">
            <strong>Certificates already found</strong>
            <span>Valid certificate files were detected on the server. You can use them directly or upload new ones.</span>
          </div>
          <button class="btn-adopt" :disabled="adopting" @click="handleAdopt">
            {{ adopting ? 'Applying…' : 'Use existing certificates' }}
          </button>
          <div v-if="adoptError" class="setup-error">{{ adoptError }}</div>
          <div class="certs-found-divider"><span>or upload new ones</span></div>
        </div>

        <div v-if="!certsOnDisk" class="certs-found-banner" style="border-color:#00d4ff44">
          <div class="certs-found-icon" style="background:#00d4ff18;border-color:#00d4ff44">
            <Download :size="18" style="color:#00d4ff" />
          </div>
          <div class="certs-found-text">
            <strong>Download from GitHub</strong>
            <span>Automatically fetch the latest Leapmotor certificates from:</span>
            <a href="https://github.com/markoceri/leapmotor-certs" target="_blank" rel="noopener" class="cert-repo-link">github.com/markoceri/leapmotor-certs</a>
          </div>
          <button class="btn-adopt" style="background:#00d4ff22;border-color:#00d4ff44;color:#00d4ff" :disabled="downloadFromGH" @click="handleGitHubDownload">
            {{ downloadFromGH ? 'Downloading…' : 'Download from GitHub' }}
          </button>
          <div v-if="ghError" class="setup-error">{{ ghError }}</div>
          <div class="certs-found-divider"><span>or upload manually</span></div>
        </div>

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
import { ref, onMounted } from 'vue'
import { Download } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { api } from '../composables/useApi'

const store = useAppStore()
const submitting = ref(false)
const error = ref('')
const certFile = ref(null)
const keyFile = ref(null)
const certDragover = ref(false)
const keyDragover = ref(false)
const certsOnDisk = ref(false)
const adopting = ref(false)
const adoptError = ref('')
const downloadFromGH = ref(false)
const ghError = ref('')

onMounted(async () => {
  try {
    const status = await api('GET', '/api/setup/status')
    certsOnDisk.value = !!status.certs_found_on_disk
  } catch {
    // ignore — just don't show the banner
  }
})

async function handleAdopt() {
  adopting.value = true
  adoptError.value = ''
  try {
    await api('POST', '/api/setup/certificates/adopt')
    store.screen = 'setup-account'
  } catch (err) {
    adoptError.value = err.message
  } finally {
    adopting.value = false
  }
}

async function handleGitHubDownload() {
  downloadFromGH.value = true
  ghError.value = ''
  try {
    await api('POST', '/api/setup/certificates/fetch')
    store.screen = 'setup-account'
  } catch (err) {
    ghError.value = err.message
  } finally {
    downloadFromGH.value = false
  }
}

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

    const res = await fetch('./api/setup/certificates', {
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
  border: 1px dashed var(--btn-border);
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

.certs-found-banner {
  margin-bottom: 1.5rem;
}

.certs-found-icon {
  width: 36px;
  height: 36px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: #00e67618;
  border: 1px solid #00e67644;
  display: flex;
  align-items: center;
  justify-content: center;
}
.certs-found-icon svg { width: 18px; height: 18px; color: #00e676; }

.certs-found-text {
  text-align: center;
  margin-bottom: 14px;
}
.certs-found-text strong {
  display: block;
  font-size: 14px;
  color: var(--text);
  margin-bottom: 4px;
}
.certs-found-text span {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.5;
}

.btn-adopt {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #00e67622, #00e67644);
  border: 1px solid #00e67655;
  border-radius: 10px;
  color: #00e676;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.04em;
}
.btn-adopt:hover {
  background: linear-gradient(135deg, #00e67633, #00e67655);
}
.btn-adopt:disabled { opacity: 0.5; cursor: not-allowed; }

.certs-found-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
  color: var(--muted2);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.certs-found-divider::before,
.certs-found-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.cert-repo-link {
  display: block;
  color: #00d4ff;
  text-decoration: none;
  font-family: var(--mono);
  font-size: 12px;
  transition: color 0.15s;
  word-break: break-all;
}
.cert-repo-link:hover {
  color: #4de0ff;
  text-decoration: underline;
}
</style>
