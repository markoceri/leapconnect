import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  base: './',
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png'],
      manifest: {
        name: 'LeapConnect',
        short_name: 'LeapConnect',
        description: 'Companion app for your Leapmotor EV',
        theme_color: '#090b12',
        background_color: '#090b12',
        display: 'standalone',
        orientation: 'portrait',
        // Relative scope/start_url so the PWA also works when the app is served
        // under a dynamic prefix (e.g. Home Assistant ingress: /api/hassio_ingress/<token>/).
        // Both resolve against the manifest URL's directory.
        scope: '.',
        start_url: '.',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'pwa-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Precache the built app shell only. API responses are never part of the
        // build glob, and WebSockets bypass the SW, so both pass straight to the
        // network by default — no absolute /api or /ws rules, which would break
        // under Home Assistant ingress where the whole app lives under /api/...
        navigateFallback: 'index.html',
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8099',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:8099',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
