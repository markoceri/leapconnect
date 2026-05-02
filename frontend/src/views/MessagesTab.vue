<template>
  <div class="messages-tab">
    <SectionCard title="Messages" :icon="Mail">
      <div class="messages-header">
        <div class="unread-badge" v-if="unreadCount > 0">
          {{ unreadCount }} unread
        </div>
        <button class="refresh-btn" :disabled="loadingMessages" @click="loadMessages(1)">
          <RefreshCw :size="14" :class="{ spinning: loadingMessages }" />
          <span>Refresh</span>
        </button>
      </div>

      <div v-if="loadingMessages && messages.length === 0" class="messages-loading">
        <div class="spinner" />
      </div>

      <div v-else-if="messages.length === 0" class="messages-empty">
        <MailX :size="32" />
        <span>No messages</span>
      </div>

      <div v-else class="messages-list">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-item"
          :class="{ unread: !msg.is_read }"
        >
          <div class="message-indicator">
            <span v-if="!msg.is_read" class="unread-dot" />
          </div>
          <div class="message-content">
            <div class="message-title-row">
              <span class="message-title">{{ msg.title || 'Notification' }}</span>
              <span class="message-time">{{ formatMsgTime(msg.send_time) }}</span>
            </div>
            <div class="message-body">{{ msg.message || '' }}</div>
            <div class="message-meta" v-if="msg.vin">
              <span class="message-vin">{{ msg.vin.slice(-8) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalCount > pageSize" class="pagination">
        <button class="page-btn" :disabled="currentPage <= 1" @click="loadMessages(currentPage - 1)">
          ← Prev
        </button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button class="page-btn" :disabled="currentPage >= totalPages" @click="loadMessages(currentPage + 1)">
          Next →
        </button>
      </div>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import SectionCard from '../components/SectionCard.vue'
import { api } from '../composables/useApi'
import { Mail, MailX, RefreshCw } from 'lucide-vue-next'

const messages = ref([])
const unreadCount = ref(0)
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = 20
const loadingMessages = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize)))

function formatMsgTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now - d
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d ago`
    return d.toLocaleDateString()
  } catch {
    return iso
  }
}

async function loadMessages(page = 1) {
  loadingMessages.value = true
  try {
    const data = await api('GET', `/api/messages?page_no=${page}&page_size=${pageSize}`)
    messages.value = data.messages || []
    totalCount.value = data.count || 0
    currentPage.value = page
  } catch {
    // keep existing data
  } finally {
    loadingMessages.value = false
  }
}

async function loadUnreadCount() {
  try {
    const data = await api('GET', '/api/messages/unread-count')
    unreadCount.value = data.unread || 0
  } catch {
    // ignore
  }
}

onMounted(() => {
  loadMessages(1)
  loadUnreadCount()
})
</script>

<style scoped>
.messages-tab {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.messages-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.unread-badge {
  background: #00d4ff18;
  border: 1px solid #00d4ff44;
  border-radius: 20px;
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 700;
  color: #00d4ff;
  letter-spacing: 0.04em;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  background: none;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 5px 12px;
  color: var(--label);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.refresh-btn:hover { background: #1c224044; color: var(--text); }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spinning { animation: lm-spin 0.7s linear infinite; }

.messages-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.messages-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--muted);
  font-size: 13px;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.message-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  background: var(--bg2);
  border: 1px solid transparent;
  transition: all 0.2s;
}
.message-item:hover {
  border-color: var(--border);
}
.message-item.unread {
  background: #00d4ff08;
  border-color: #00d4ff22;
}

.message-indicator {
  display: flex;
  align-items: flex-start;
  padding-top: 6px;
  width: 10px;
  flex-shrink: 0;
}

.unread-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00d4ff;
  box-shadow: 0 0 6px #00d4ff;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.message-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.message-time {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.message-body {
  font-size: 12px;
  color: var(--sub);
  line-height: 1.5;
  word-break: break-word;
}

.message-meta {
  margin-top: 6px;
  display: flex;
  gap: 8px;
}

.message-vin {
  font-size: 10px;
  color: var(--muted2);
  font-family: var(--mono);
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 4px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.page-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 5px 14px;
  color: var(--label);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.page-btn:hover:not(:disabled) { background: #1c224044; color: var(--text); }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.page-info {
  font-size: 12px;
  color: var(--muted);
  font-family: var(--mono);
}
</style>
