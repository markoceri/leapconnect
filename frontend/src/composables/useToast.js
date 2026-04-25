import { ref } from 'vue'

const toasts = ref([])
let nextId = 0

export function useToast() {
  function toast(message, type = 'info') {
    const id = ++nextId
    toasts.value.push({ id, message, type, removing: false })
    setTimeout(() => {
      const t = toasts.value.find((t) => t.id === id)
      if (t) t.removing = true
      setTimeout(() => {
        toasts.value = toasts.value.filter((t) => t.id !== id)
      }, 300)
    }, 4000)
  }

  return { toasts, toast }
}
