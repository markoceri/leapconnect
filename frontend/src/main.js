import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/main.css'
import { generateVehicleTheme } from './utils/colorTheme'

// Apply saved theme immediately to avoid flash
const savedTheme = localStorage.getItem('theme')
if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme)

// Re-apply the saved vehicle colour theme before mount to avoid a flash.
const savedThemeHex = localStorage.getItem('vehicleThemeHex')
if (savedTheme === 'vehicle' && savedThemeHex) {
  const { vars, base } = generateVehicleTheme(savedThemeHex)
  for (const [name, value] of Object.entries(vars)) {
    document.documentElement.style.setProperty(name, value)
  }
  document.documentElement.setAttribute('data-theme', base)
}

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
