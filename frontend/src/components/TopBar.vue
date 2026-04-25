<template>
  <div class="topbar">
    <div class="topbar-left">
      <div class="topbar-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C1.4 11.3 1 12.1 1 13v3c0 .6.4 1 1 1h2" />
          <circle cx="7" cy="17" r="2" />
          <circle cx="17" cy="17" r="2" />
        </svg>
      </div>
      <span class="topbar-title">Leapmotor Command Center</span>
    </div>
    <div class="topbar-right">
      <div class="connection-badge">
        <span class="connection-dot"></span>
        Connected
      </div>
      <button class="btn-topbar" @click="$emit('refresh')">
        <svg style="width:12px;height:12px;display:inline;vertical-align:middle;margin-right:4px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M21 2v6h-6M3 12a9 9 0 0115.5-6.4L21 8M3 22v-6h6M21 12a9 9 0 01-15.5 6.4L3 16" />
        </svg>
        Refresh
      </button>
      <button class="btn-topbar btn-logout" @click="$emit('logout')">
        <svg style="width:12px;height:12px;display:inline;vertical-align:middle;margin-right:4px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
        </svg>
        Logout
      </button>
    </div>
  </div>
</template>

<script setup>
defineEmits(['refresh', 'logout'])
</script>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.8rem 2rem;
  background: rgba(10, 12, 16, 0.85);
  backdrop-filter: blur(20px) saturate(1.4);
  border-bottom: 1px solid var(--border-subtle);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.topbar-logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.topbar-logo svg { width: 18px; height: 18px; color: white; }

.topbar-title {
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.connection-badge {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.8rem;
  background: rgba(0, 230, 118, 0.08);
  border: 1px solid rgba(0, 230, 118, 0.15);
  border-radius: 100px;
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--accent-green);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.connection-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-green);
  animation: pulse 2s infinite;
}

.btn-topbar {
  padding: 0.4rem 0.9rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-family: var(--font-display);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
}
.btn-topbar:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary);
  border-color: var(--border-accent);
}
.btn-logout:hover {
  border-color: rgba(255, 61, 90, 0.4);
  color: var(--accent-red);
  background: rgba(255, 61, 90, 0.06);
}

@media (max-width: 768px) {
  .topbar { padding: 0.8rem 1rem; }
}
</style>
