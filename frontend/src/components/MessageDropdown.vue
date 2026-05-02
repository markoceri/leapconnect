<template>
  <div class="msg-dropdown-wrapper" ref="wrapperRef">
    <button class="msg-trigger" @click="toggle" :title="store.unreadMessages > 0 ? `${store.unreadMessages} unread messages` : 'Messages'">
      <Bell :size="14" />
      <span v-if="store.unreadMessages > 0" class="msg-badge">
        {{ store.unreadMessages > 99 ? '99+' : store.unreadMessages }}
      </span>
    </button>

    <Transition name="dropdown">
      <div v-if="open" class="msg-panel">
        <div class="msg-panel-header">
          <span class="msg-panel-title">Messages</span>
          <button class="msg-panel-close" @click="open = false">&times;</button>
        </div>

        <div v-if="loading && messages.length === 0" class="msg-panel-empty">
          <div class="spinner" />
        </div>

        <div v-else-if="messages.length === 0" class="msg-panel-empty">
          <MailX :size="24" />
          <span>No messages</span>
        </div>

        <div v-else class="msg-panel-list" @scroll="onScroll">
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="msg-item"
            :class="{ unread: !msg.is_read }"
            @click="goToMessages"
          >
            <span v-if="!msg.is_read" class="msg-dot" />
            <div class="msg-item-body">
              <div class="msg-item-top">
                <span class="msg-item-title">{{ msg.title || 'Notification' }}</span>
                <span class="msg-item-time">{{ formatTime(msg.send_time) }}</span>
              </div>
              <div class="msg-item-text">{{ msg.message || '' }}</div>
            </div>
          </div>
          <div v-if="loading" class="msg-panel-loading-more">
            <div class="spinner-sm" />
          </div>
        </div>

        <button class="msg-panel-viewall" @click="goToMessages">
          View all messages
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Bell, MailX } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { api } from '../composables/useApi'

const store = useAppStore()

const open = ref(false)
const messages = ref([])
const loading = ref(false)
const currentPage = ref(1)
const totalCount = ref(0)
const pageSize = 15
const wrapperRef = ref(null)

function toggle() {
  open.value = !open.value
  if (open.value && messages.value.length === 0) {
    loadMessages(1)
  }
}

async function loadMessages(page) {
  if (loading.value) return
  loading.value = true
  try {
    const data = await api('GET', `/api/messages?page_no=${page}&page_size=${pageSize}`)
    if (page === 1) {
      messages.value = data.messages || []
    } else {
      messages.value = [...messages.value, ...(data.messages || [])]
    }
    totalCount.value = data.count || 0
    currentPage.value = page
  } catch {
    // keep existing
  } finally {
    loading.value = false
  }
}

function onScroll(e) {
  const el = e.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 40) {
    const totalPages = Math.ceil(totalCount.value / pageSize)
    if (currentPage.value < totalPages && !loading.value) {
      loadMessages(currentPage.value + 1)
    }
  }
}

function goToMessages() {
  store.activeTab = 'messages'
  open.value = false
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now - d
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Now'
    if (diffMins < 60) return `${diffMins}m`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d`
    return d.toLocaleDateString()
  } catch {
    return ''
  }
}

function onClickOutside(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    open.value = false
  }
}

// Refresh messages when dropdown opens
watch(open, (val) => {
  if (val) {
    currentPage.value = 1
    loadMessages(1)
    store.loadUnreadCount()
  }
})

onMounted(() => {
  document.addEventListener('click', onClickOutside, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true)
})
</script>

<style scoped>
.msg-dropdown-wrapper {
  position: relative;
}

.msg-trigger {
  background: none;
  border: 1px solid #1c2240;
  border-radius: 8px;
  padding: 6px 8px;
  color: var(--label);
  cursor: pointer;
  display: flex;
  align-items: center;
  position: relative;
  transition: all 0.2s;
}
.msg-trigger:hover {
  background: #1c224044;
  color: var(--text);
}

.msg-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 10px;
  background: #ff5252;
  color: #fff;
  font-size: 9px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  box-shadow: 0 0 8px #ff525288;
  pointer-events: none;
  animation: badge-pop 0.3s ease;
}

@keyframes badge-pop {
  0% { transform: scale(0); }
  60% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

.msg-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 340px;
  max-height: 420px;
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: 12px;
  box-shadow: 0 8px 32px #00000066;
  display: flex;
  flex-direction: column;
  z-index: 2000;
  overflow: hidden;
}

@media (max-width: 400px) {
  .msg-panel {
    width: calc(100vw - 24px);
    right: -8px;
  }
}

.msg-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 10px;
  border-bottom: 1px solid var(--border2);
}

.msg-panel-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.msg-panel-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.msg-panel-close:hover {
  color: var(--text);
}

.msg-panel-list {
  flex: 1;
  overflow-y: auto;
  max-height: 320px;
  scrollbar-width: thin;
  scrollbar-color: #1c2240 transparent;
}

.msg-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid var(--border2);
}
.msg-item:last-child {
  border-bottom: none;
}
.msg-item:hover {
  background: #ffffff06;
}
.msg-item.unread {
  background: #00d4ff06;
}

.msg-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00d4ff;
  box-shadow: 0 0 6px #00d4ff88;
  flex-shrink: 0;
  margin-top: 6px;
}

.msg-item-body {
  flex: 1;
  min-width: 0;
}

.msg-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.msg-item-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.msg-item-time {
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.msg-item-text {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

.msg-panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--muted);
  font-size: 12px;
}

.msg-panel-loading-more {
  display: flex;
  justify-content: center;
  padding: 8px;
}

.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid #1c2240;
  border-top-color: #00d4ff;
  border-radius: 50%;
  animation: lm-spin 0.7s linear infinite;
}

.msg-panel-viewall {
  border: none;
  background: none;
  border-top: 1px solid var(--border2);
  padding: 10px;
  font-size: 12px;
  font-weight: 600;
  color: #00d4ff;
  cursor: pointer;
  text-align: center;
  transition: background 0.15s;
}
.msg-panel-viewall:hover {
  background: #00d4ff0a;
}

/* Dropdown transition */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
