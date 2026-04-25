<template>
  <div class="hero-strip">
    <div class="hero-stat battery">
      <div class="hero-stat-label">Battery</div>
      <div class="hero-stat-value">
        {{ soc ?? '—' }}<span v-if="soc != null" class="unit">%</span>
      </div>
      <div class="hero-stat-sub">
        {{ bat.is_charging ? '⚡ Charging' : bat.charge_remain_time ? `${bat.charge_remain_time} min remaining` : 'Not charging' }}
      </div>
      <div v-if="soc != null" class="hero-progress">
        <div class="hero-progress-fill" :style="{ width: soc + '%' }"></div>
      </div>
    </div>

    <div class="hero-stat range">
      <div class="hero-stat-label">Range</div>
      <div class="hero-stat-value">
        {{ range ?? '—' }}<span v-if="range != null" class="unit">km</span>
      </div>
      <div class="hero-stat-sub">
        {{ bat.dump_energy != null ? `${bat.dump_energy} kWh available` : '' }}
      </div>
    </div>

    <div class="hero-stat speed">
      <div class="hero-stat-label">Speed</div>
      <div class="hero-stat-value">{{ speed }}<span class="unit">km/h</span></div>
      <div class="hero-stat-sub">{{ drv.is_parked ? 'Parked' : 'Moving' }}</div>
    </div>

    <div class="hero-stat mileage">
      <div class="hero-stat-label">Odometer</div>
      <div class="hero-stat-value">
        {{ typeof mileageVal === 'number' ? mileageVal.toLocaleString() : mileageVal }}
        <span v-if="typeof mileageVal === 'number'" class="unit">km</span>
      </div>
      <div class="hero-stat-sub">
        {{ mileage?.deliveryDays ? `${mileage.deliveryDays} days since delivery` : '' }}
      </div>
    </div>

    <div class="hero-stat temp">
      <div class="hero-stat-label">Outside Temp</div>
      <div class="hero-stat-value">
        {{ outTemp ?? '—' }}<span v-if="outTemp != null" class="unit">°C</span>
      </div>
      <div class="hero-stat-sub">{{ clm.ac_switch ? 'A/C active' : 'A/C off' }}</div>
    </div>

    <div class="hero-stat lock">
      <div class="hero-stat-label">Lock Status</div>
      <div class="hero-stat-value">
        {{ locked === true ? '🔒 Locked' : locked === false ? '🔓 Open' : '—' }}
      </div>
      <div class="hero-stat-sub">
        {{ ts.collect_time ? 'Updated ' + formatTime(ts.collect_time) : '' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatTime } from '../utils/formatters'

const props = defineProps({
  status: { type: Object, default: () => ({}) },
  mileage: { type: Object, default: null },
})

const bat = computed(() => props.status?.battery || {})
const drv = computed(() => props.status?.driving || {})
const clm = computed(() => props.status?.climate || {})
const drs = computed(() => props.status?.doors || {})
const ts = computed(() => props.status?.timestamps || {})

const soc = computed(() => bat.value.soc ?? null)
const range = computed(() => bat.value.expected_mileage ?? null)
const speed = computed(() => drv.value.speed ?? 0)
const mileageVal = computed(() => drv.value.total_mileage ?? props.mileage?.totalmileage ?? '—')
const outTemp = computed(() => clm.value.outdoor_temp ?? null)
const locked = computed(() => drs.value.is_locked ?? null)
</script>

<style scoped>
.hero-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  padding: 1.5rem 0;
  animation: fadeInUp 0.5s ease both;
}

.hero-stat {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 1.2rem 1.4rem;
  position: relative;
  overflow: hidden;
  transition: var(--transition);
}
.hero-stat:hover {
  border-color: var(--border-accent);
  box-shadow: var(--shadow-glow);
}

.hero-stat-label {
  font-size: 0.7rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
  margin-bottom: 0.5rem;
}

.hero-stat-value {
  font-size: 1.8rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.hero-stat-value .unit {
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 0.15rem;
}

.hero-stat-sub {
  font-size: 0.72rem;
  color: var(--text-secondary);
  margin-top: 0.3rem;
}

.hero-stat.battery .hero-stat-value { color: var(--accent-green); }
.hero-stat.range .hero-stat-value { color: var(--accent); }
.hero-stat.speed .hero-stat-value { color: var(--text-primary); }
.hero-stat.temp .hero-stat-value { color: var(--accent-warm); }
.hero-stat.lock .hero-stat-value { color: var(--accent-purple); }
.hero-stat.mileage .hero-stat-value { color: var(--accent-yellow); }

.hero-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(255, 255, 255, 0.03);
}
.hero-progress-fill {
  height: 100%;
  border-radius: 0 2px 0 0;
  transition: width 1s ease;
}
.hero-stat.battery .hero-progress-fill { background: var(--accent-green); }
.hero-stat.range .hero-progress-fill { background: var(--accent); }
</style>
