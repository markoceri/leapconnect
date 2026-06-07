<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-dialog">
        <h3>Add community repository</h3>
        <p class="sub">
          Paste a GitHub repository that publishes maintenance packs. It needs a
          <code>leapconnect-maintenance.json</code> manifest at its root, or a
          <code>packs/</code> directory of JSON files.
        </p>
        <div class="form-group">
          <label>GitHub repository URL</label>
          <input
            v-model="url"
            type="text"
            placeholder="https://github.com/owner/repo"
            @keyup.enter="submit"
          />
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="$emit('close')">Cancel</button>
          <button class="btn-save" :disabled="saving || !url.trim()" @click="submit">
            {{ saving ? 'Fetching…' : 'Add repository' }}
          </button>
        </div>
        <div v-if="errorMsg" class="field-error">{{ errorMsg }}</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../composables/useApi'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'saved'])

const url = ref('')
const saving = ref(false)
const errorMsg = ref('')

watch(() => props.visible, (v) => {
  if (v) { url.value = ''; errorMsg.value = '' }
})

async function submit() {
  if (!url.value.trim()) return
  saving.value = true
  errorMsg.value = ''
  try {
    await api('POST', '/api/maintenance/repos', { url: url.value.trim() })
    emit('saved')
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0; background: #00000080; display: flex;
  align-items: center; justify-content: center; z-index: 2000;
}
.modal-dialog {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 24px; width: 90%; max-width: 460px;
}
.modal-dialog h3 { margin: 0 0 8px; color: var(--text); }
.sub { color: var(--muted); font-size: 12px; margin: 0 0 16px; line-height: 1.5; }
.sub code { background: var(--btn-bg); padding: 1px 5px; border-radius: 4px; font-size: 11px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-group input {
  width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--input); color: var(--text); font-size: 14px;
}
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.btn-cancel {
  padding: 8px 16px; border-radius: 8px; background: var(--btn-bg); border: 1px solid var(--btn-border);
  color: var(--muted); cursor: pointer; font-size: 13px;
}
.btn-save {
  padding: 8px 16px; border-radius: 8px; background: var(--cyan); border: none;
  color: #000; cursor: pointer; font-size: 13px; font-weight: 600;
}
.btn-save:disabled { opacity: 0.5; cursor: default; }
.field-error { color: var(--red); font-size: 13px; margin-top: 8px; }
</style>
