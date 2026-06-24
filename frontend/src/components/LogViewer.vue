<template>
  <div class="log-viewer">
    <div class="log-toolbar">
      <div class="log-filters">
        <select v-model="filterLevel" class="log-select">
          <option value="">All levels</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <input
          v-model="filterText"
          type="text"
          class="log-search"
          placeholder="Filter logs…"
        />
      </div>
      <div class="log-actions">
        <button class="log-action-btn" :class="{ active: autoScroll }" @click="autoScroll = !autoScroll" title="Auto-scroll">
          <ArrowDownToLine :size="13" />
        </button>
        <button class="log-action-btn" :class="{ active: copied }" @click="copyLogs" title="Copy logs">
          <Check v-if="copied" :size="13" />
          <Copy v-else :size="13" />
        </button>
        <button class="log-action-btn" @click="clearLogs" title="Clear">
          <X :size="13" />
        </button>
      </div>
    </div>
    <div ref="logContainer" class="log-entries" @scroll="onScroll">
      <div
        v-for="(entry, idx) in filteredEntries"
        :key="idx"
        class="log-entry"
        :class="'level-' + entry.level.toLowerCase()"
      >
        <span class="log-ts">{{ formatTs(entry.ts) }}</span>
        <span class="log-level">{{ entry.level }}</span>
        <span class="log-name">{{ entry.name }}</span>
        <span class="log-msg">{{ entry.message }}</span>
      </div>
      <div v-if="filteredEntries.length === 0" class="log-empty">
        No log entries{{ filterLevel || filterText ? ' matching filter' : '' }}
      </div>
    </div>
    <div class="log-status-bar">
      <span class="log-ws-status">
        <span class="ws-dot" :class="wsConnected ? 'connected' : 'disconnected'" />
        {{ wsConnected ? 'Live' : 'Disconnected' }}
      </span>
      <span class="log-count">{{ filteredEntries.length }} entries</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ArrowDownToLine, X, Copy, Check } from 'lucide-vue-next'
import { api } from '../composables/useApi'

const entries = ref([])
const filterLevel = ref('')
const filterText = ref('')
const autoScroll = ref(true)
const copied = ref(false)
const wsConnected = ref(false)
const logContainer = ref(null)

let ws = null

const filteredEntries = computed(() => {
  let result = entries.value
  if (filterLevel.value) {
    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    const minIdx = levels.indexOf(filterLevel.value)
    result = result.filter(e => levels.indexOf(e.level) >= minIdx)
  }
  if (filterText.value) {
    const q = filterText.value.toLowerCase()
    result = result.filter(e =>
      e.message.toLowerCase().includes(q) ||
      e.name.toLowerCase().includes(q)
    )
  }
  return result
})

function formatTs(ts) {
  if (!ts) return ''
  // Show only time part HH:MM:SS.mmm
  const d = new Date(ts)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
    '.' + String(d.getMilliseconds()).padStart(3, '0')
}

function clearLogs() {
  entries.value = []
}

function copyLogs() {
  const text = filteredEntries.value
    .map(e => `${e.ts} [${e.level}] ${e.name}: ${e.message}`)
    .join('\n')
  navigator.clipboard.writeText(text)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function onScroll() {
  if (!logContainer.value) return
  const el = logContainer.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  autoScroll.value = atBottom
}

function scrollToBottom() {
  if (!autoScroll.value || !logContainer.value) return
  nextTick(() => {
    const el = logContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(filteredEntries, () => {
  scrollToBottom()
})

async function loadInitialEntries() {
  try {
    const data = await api('GET', '/api/logs/entries?limit=500')
    entries.value = data.entries || []
    scrollToBottom()
  } catch { /* ignore */ }
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${location.host}/ws/logs`
  ws = new WebSocket(url)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => {
    wsConnected.value = false
    // Reconnect after 3 seconds
    setTimeout(() => { if (!ws || ws.readyState === WebSocket.CLOSED) connectWs() }, 3000)
  }
  ws.onmessage = (event) => {
    try {
      const entry = JSON.parse(event.data)
      entries.value.push(entry)
      // Cap at 2000 entries in the UI
      if (entries.value.length > 2000) {
        entries.value = entries.value.slice(-1500)
      }
    } catch { /* ignore */ }
  }
}

onMounted(() => {
  loadInitialEntries()
  connectWs()
})

onUnmounted(() => {
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
})
</script>

<style scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  height: 420px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--elevated, #0d1017);
}

.log-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  gap: 8px;
  flex-shrink: 0;
}

.log-filters {
  display: flex;
  gap: 6px;
  flex: 1;
}

.log-select {
  appearance: none;
  -webkit-appearance: none;
  padding: 4px 24px 4px 8px;
  background: var(--input, #161a26) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2388909a' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") no-repeat right 8px center;
  border: 1px solid var(--btn-border, #2a3040);
  border-radius: 6px;
  color: var(--text);
  font-size: 11px;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s;
}
.log-select:focus { border-color: rgba(var(--accent-rgb), 0.333); }
.log-select option {
  background: var(--card, #1a1e2e);
  color: var(--text);
}

.log-search {
  flex: 1;
  padding: 4px 8px;
  background: var(--input, #161a26);
  border: 1px solid var(--btn-border, #2a3040);
  border-radius: 6px;
  color: var(--text);
  font-size: 11px;
  outline: none;
  min-width: 80px;
}
.log-search::placeholder { color: var(--muted2); }
.log-search:focus { border-color: rgba(var(--accent-rgb), 0.333); }

.log-actions {
  display: flex;
  gap: 4px;
}

.log-action-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.log-action-btn:hover { color: var(--accent); border-color: rgba(var(--accent-rgb), 0.267); }
.log-action-btn.active { color: var(--accent); border-color: rgba(var(--accent-rgb), 0.333); background: rgba(var(--accent-rgb), 0.067); }

.log-entries {
  flex: 1;
  overflow-y: auto;
  font-family: var(--mono, 'JetBrains Mono', monospace);
  font-size: 11px;
  line-height: 1.6;
  padding: 6px 8px;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 1px 4px;
  border-radius: 3px;
  white-space: nowrap;
}
.log-entry:hover { background: #ffffff06; }

.log-ts {
  color: var(--muted2, #555);
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  width: 56px;
  font-weight: 600;
  text-align: center;
}
.level-debug .log-level { color: #888; }
.level-info .log-level { color: var(--accent); }
.level-warning .log-level { color: #ffab40; }
.level-error .log-level { color: #ff5252; }
.level-critical .log-level { color: #ff1744; font-weight: 700; }

.log-name {
  color: #7c6aff;
  flex-shrink: 0;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-msg {
  color: var(--sub, #ccc);
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-empty {
  color: var(--muted);
  text-align: center;
  padding: 40px 0;
  font-size: 12px;
}

.log-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 10px;
  border-top: 1px solid var(--border);
  font-size: 10px;
  color: var(--muted);
}

.log-ws-status {
  display: flex;
  align-items: center;
  gap: 5px;
}

.ws-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.ws-dot.connected { background: #00e676; box-shadow: 0 0 4px #00e67688; }
.ws-dot.disconnected { background: #5c6478; }

.log-count {
  font-family: var(--mono);
}
</style>
