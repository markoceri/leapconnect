<template>
  <LoginView v-if="!store.connected" @logged-in="onLoggedIn" />
  <DashboardView v-else @logout="onLogout" />
  <ToastContainer />
</template>

<script setup>
import { onMounted } from 'vue'
import { useAppStore } from './stores/appStore'
import { useToast } from './composables/useToast'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import ToastContainer from './components/ToastContainer.vue'

const store = useAppStore()
const { toast } = useToast()

async function onLoggedIn() {
  // store.connected is already set by the store
}

function onLogout() {
  // store.connected is already false
}

onMounted(async () => {
  const restored = await store.checkStatus()
  if (restored) {
    toast('Session restored', 'success')
  }
})
</script>
