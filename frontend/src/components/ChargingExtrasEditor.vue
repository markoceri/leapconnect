<template>
  <div class="extras">
    <div v-for="(extra, i) in modelValue" :key="i" class="extra-card" :class="{ excluded: !extra.included }">
      <div class="extra-head">
        <input v-model="extra.label" class="extra-label" type="text" maxlength="64" placeholder="Label" />
        <select v-model="extra.kind" class="extra-kind">
          <option v-for="k in EXTRA_KINDS" :key="k.id" :value="k.id">{{ k.label }}</option>
        </select>
        <span class="extra-amount" :title="extra.included ? 'Counted in the charging cost' : 'Not counted in the charging cost'">
          {{ formatAmount(extraCost(extra, context)) }}
        </span>
        <button class="extra-remove" title="Remove" @click="remove(i)"><X :size="14" /></button>
      </div>

      <div class="extra-fields">
        <label v-if="extra.kind === 'fixed'" class="field">
          <span>Amount (€) — negative for a discount</span>
          <input v-model.number="extra.amount" type="number" step="0.01" />
        </label>
        <label v-else-if="extra.kind === 'per_kwh'" class="field">
          <span>Rate (€/kWh)</span>
          <input v-model.number="extra.rate" type="number" step="0.001" min="0" />
        </label>
        <label v-else-if="extra.kind === 'percent'" class="field">
          <span>Rate (% of the energy cost)</span>
          <input v-model.number="extra.rate" type="number" step="0.1" min="0" />
        </label>
        <template v-else>
          <label class="field">
            <span>Rate</span>
            <span class="field-pair">
              <input v-model.number="extra.rate" type="number" step="0.01" min="0" />
              <select v-model="extra.time_unit">
                <option value="minute">€/min</option>
                <option value="hour">€/h</option>
              </select>
            </span>
          </label>
          <label class="field">
            <span>Billed</span>
            <select v-model="extra.billing">
              <option value="exact">by the minute</option>
              <option value="started">per started {{ extra.time_unit === 'minute' ? 'minute' : 'hour' }}</option>
            </select>
          </label>
          <label class="field">
            <span>From</span>
            <span class="field-pair">
              <select v-model="extra.start_ref" :disabled="extra.end_ref === 'manual'">
                <option v-for="r in START_REFS" :key="r.id" :value="r.id">{{ r.label }}</option>
              </select>
              <span class="field-plus">+</span>
              <input
                v-model.number="extra.start_offset_min"
                class="field-min"
                type="number"
                step="1"
                min="0"
                :disabled="extra.end_ref === 'manual'"
                title="Minutes after it (e.g. a grace period)"
              />
              <span class="field-unit">min</span>
            </span>
          </label>
          <label class="field">
            <span>Until</span>
            <span class="field-pair">
              <select v-model="extra.end_ref">
                <option v-for="r in END_REFS" :key="r.id" :value="r.id">{{ r.label }}</option>
              </select>
              <template v-if="extra.end_ref === 'manual'">
                <input v-model.number="extra.duration_min" class="field-min" type="number" step="1" min="0" />
                <span class="field-unit">min</span>
              </template>
            </span>
          </label>
          <label class="field">
            <span>Cap (€, optional)</span>
            <input v-model.number="extra.cap" type="number" step="0.01" min="0" placeholder="No cap" />
          </label>
          <div class="extra-window">{{ windowText(extra) }}</div>
        </template>
      </div>

      <div class="extra-included">
        <ToggleSwitch v-model="extra.included" />
        <span @click="extra.included = !extra.included">Counts in the charging cost</span>
      </div>
    </div>

    <select class="extra-add" :value="''" @change="add($event)">
      <option value="" disabled>+ Add an extra cost…</option>
      <option v-for="p in EXTRA_PRESETS" :key="p.id" :value="p.id">{{ p.label }}</option>
    </select>
  </div>
</template>

<script setup>
import { X } from 'lucide-vue-next'
import ToggleSwitch from './ToggleSwitch.vue'
import { EXTRA_KINDS, EXTRA_PRESETS, START_REFS, END_REFS, extraCost, extraWindow } from '../utils/chargingExtras'

const props = defineProps({
  // The session's extras, edited in place
  modelValue: { type: Array, required: true },
  // { energyKwh, energyCost, startTs, endTs, unplugTs, departureTs } (Dates)
  context: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue'])

function add(event) {
  const preset = EXTRA_PRESETS.find(p => p.id === event.target.value)
  event.target.value = ''
  if (preset) emit('update:modelValue', [...props.modelValue, preset.make()])
}

function remove(i) {
  emit('update:modelValue', props.modelValue.filter((_, j) => j !== i))
}

function formatAmount(v) {
  if (v == null) return '—'
  return `${v < 0 ? '−' : ''}€${Math.abs(v).toFixed(2)}`
}

const time = d => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

function windowText(extra) {
  const { begin, finish, minutes } = extraWindow(extra, props.context)
  if (extra.end_ref === 'manual') return minutes == null ? 'Set the duration' : `${minutes} min`
  if (!begin) return 'The charge has no end yet'
  if (!finish) {
    const what = extra.end_ref === 'unplug' ? 'unplug' : 'departure'
    return `From ${time(begin)} — no ${what} seen yet: computed once it happens, or set a duration`
  }
  return `${time(begin)} → ${time(finish)} · ${minutes} min`
}
</script>

<style scoped>
.extras { display: flex; flex-direction: column; gap: 8px; }
.extra-card { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; background: var(--btn-bg); }
.extra-card.excluded { opacity: 0.7; }
.extra-head { display: flex; gap: 6px; align-items: center; }
.extra-head input, .extra-head select, .extra-fields input, .extra-fields select {
  background: var(--input); border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; color: var(--text); font-size: 12px; min-width: 0;
}
.extra-label { flex: 1; }
.extra-kind { flex: 0 0 auto; }
.extra-amount { min-width: 64px; text-align: right; font-weight: 600; color: #ffd54f; font-size: 13px; }
.excluded .extra-amount { color: var(--muted); text-decoration: line-through; }
.extra-remove { background: none; border: none; color: var(--muted); cursor: pointer; padding: 4px; display: flex; }
.extra-remove:hover { color: var(--red); }
.extra-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; margin-top: 8px; }
.field { display: flex; flex-direction: column; gap: 3px; font-size: 11px; color: var(--muted); }
.field > input, .field > select { width: 100%; }
.field-pair { display: flex; gap: 4px; align-items: center; }
.field-pair > input, .field-pair > select { flex: 1; }
.field-pair > .field-min { flex: 0 0 56px; }
.field-plus, .field-unit { font-size: 11px; color: var(--muted); }
.extra-window { grid-column: 1 / -1; font-size: 11px; color: var(--muted); }
.extra-included { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 12px; color: var(--muted); }
.extra-included span { cursor: pointer; }
.extra-add { background: var(--input); border: 1px dashed var(--border); border-radius: 8px; padding: 7px 10px; color: var(--muted); font-size: 12px; cursor: pointer; }
@media (max-width: 600px) {
  .extra-fields { grid-template-columns: 1fr; }
}
</style>
