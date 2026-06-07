<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('cancel')">
      <div class="modal-dialog">
        <h3>Some interventions already exist</h3>
        <p class="sub">
          {{ count }} of the selected interventions are already in your plan.
          How should they be imported?
        </p>
        <div class="choices">
          <button class="choice" @click="$emit('resolve', 'update')">
            <strong>Update existing</strong>
            <span>Overwrite intervals &amp; priority from the pack</span>
          </button>
          <button class="choice" @click="$emit('resolve', 'variant')">
            <strong>Keep both</strong>
            <span>Import duplicates as separate variants</span>
          </button>
          <button class="choice" @click="$emit('resolve', 'skip')">
            <strong>Skip existing</strong>
            <span>Only import interventions that are new</span>
          </button>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="$emit('cancel')">Cancel</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
})
defineEmits(['resolve', 'cancel'])
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0; background: #00000080; display: flex;
  align-items: center; justify-content: center; z-index: 2100;
}
.modal-dialog {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 24px; width: 90%; max-width: 420px;
}
.modal-dialog h3 { margin: 0 0 8px; color: var(--text); }
.sub { color: var(--muted); font-size: 13px; margin: 0 0 16px; line-height: 1.5; }
.choices { display: flex; flex-direction: column; gap: 10px; }
.choice {
  display: flex; flex-direction: column; gap: 2px; text-align: left;
  padding: 12px 14px; border-radius: 10px; border: 1px solid var(--btn-border);
  background: var(--btn-bg); color: var(--text); cursor: pointer; transition: all 0.15s;
}
.choice:hover { border-color: var(--cyan); }
.choice strong { font-size: 14px; }
.choice span { font-size: 12px; color: var(--muted); }
.modal-actions { display: flex; justify-content: flex-end; margin-top: 16px; }
.btn-cancel {
  padding: 8px 16px; border-radius: 8px; background: transparent; border: 1px solid var(--btn-border);
  color: var(--muted); cursor: pointer; font-size: 13px;
}
</style>
