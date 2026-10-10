<template>
  <div class="charging-tab">
    <div class="charging-header">
      <div class="header-title">
        <h2>Charging</h2>
        <p>Energy, sessions &amp; costs</p>
      </div>
      <div class="month-nav">
        <button class="toolbar-btn" @click="prevMonth"><ChevronLeft :size="16" /></button>
        <span class="month-label">{{ monthLabel }}</span>
        <button class="toolbar-btn" :disabled="isCurrentMonth" @click="nextMonth"><ChevronRight :size="16" /></button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-center">
      <div class="spinner" />
    </div>

    <template v-else>
    <!-- KPI cards -->
    <div v-if="kpiCards.length" class="summary-grid">
      <div v-for="s in kpiCards" :key="s.label" class="summary-card">
        <div class="summary-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="summary-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- Charts row: three charts side by side on desktop -->
    <div class="charts-grid charts-grid-3">
      <div class="chart-card">
        <div class="chart-header"><Zap :size="16" class="chart-icon" /> Energy per session (kWh)</div>
        <div class="chart-area"><canvas ref="energyCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><TrendingUp :size="16" class="chart-icon" /> Daily cost (€)</div>
        <div class="chart-area"><canvas ref="costCanvas" /></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><PieChart :size="16" class="chart-icon" /> Energy by tier</div>
        <div class="chart-area"><canvas ref="pieCanvas" /></div>
      </div>
    </div>

    <!-- Time-of-use visualization -->
    <div v-if="homePricingMode === 'time_of_use' && timeBands.length" class="chart-card wide tou-card">
      <div class="chart-header"><Clock :size="16" class="chart-icon" /> Time-of-use bands — energy distribution</div>
      <div class="tou-bands">
        <div v-for="band in timeBandsWithEnergy" :key="band.id" class="tou-band-row">
          <span class="tou-color" :style="{ background: band.color || '#888' }" />
          <span class="tou-name">{{ band.name }}</span>
          <span class="tou-price">€{{ band.price_kwh.toFixed(3) }}/kWh</span>
          <div class="tou-bar-track">
            <div class="tou-bar-fill" :style="{ width: band.pct + '%', background: band.color || '#888' }" />
          </div>
          <span class="tou-energy">{{ band.energy.toFixed(1) }} kWh</span>
          <span class="tou-cost">€{{ band.cost.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Monthly summary -->
    <div class="chart-card wide">
      <div class="chart-header"><CalendarDays :size="16" class="chart-icon" /> Monthly summary</div>
      <div class="monthly-table-wrap">
        <table class="monthly-table">
          <thead>
            <tr>
              <th>Month</th>
              <th>Sessions</th>
              <th>Energy (kWh)</th>
              <th>Home grid</th>
              <th v-if="hasSolarPanels">Solar</th>
              <th>Public</th>
              <th>Cost (€)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in monthlySummary" :key="m.month">
              <td>{{ m.month }}</td>
              <td>{{ m.sessions }}</td>
              <td>{{ m.energy.toFixed(1) }}</td>
              <td>{{ m.homeGrid.toFixed(1) }}</td>
              <td v-if="hasSolarPanels">{{ m.solar.toFixed(1) }}</td>
              <td>{{ m.public.toFixed(1) }}</td>
              <td>€{{ m.cost.toFixed(2) }}</td>
            </tr>
            <tr v-if="!monthlySummary.length">
              <td :colspan="hasSolarPanels ? 7 : 6" class="empty-row">No data available</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Session list -->
    <div class="chart-card wide">
      <div class="chart-header">
        <List :size="16" class="chart-icon" /> Charging sessions
        <span class="chart-header-spacer" />
        <button
          v-if="missingCosts.total"
          class="btn-bulk"
          @click="openBulkDialog"
          title="Calculate the cost of every session in this month that doesn't have one"
        >
          <Calculator :size="14" /> Calculate missing costs ({{ missingCosts.total }})
        </button>
        <button
          v-if="filteredSessions.length > 1"
          class="btn-bulk"
          :class="{ active: mergeMode }"
          @click="toggleMergeMode"
          title="Join a charge that was interrupted and resumed in place (plug out/in, car unlocked…)"
        >
          <Combine :size="14" /> {{ mergeMode ? 'Cancel merge' : 'Merge sessions' }}
        </button>
      </div>
      <p v-if="mergeMode" class="merge-hint">
        Click the <strong>first</strong> and the <strong>last</strong> session to merge: every session in between is
        included. To merge across months, pick one session, change month and pick the other. Sessions in progress
        can't be merged.
      </p>
      <div class="session-list" :class="{ 'merge-active': mergeMode }">
        <div class="session-head">
          <span>Date</span>
          <span>Time</span>
          <span>Battery</span>
          <span>Energy</span>
          <span>Peak</span>
          <span>Tier</span>
          <span>Zone</span>
          <span>Cost</span>
          <span class="head-edit" />
        </div>
        <div
          v-for="s in filteredSessions"
          :key="s.id || s.start_ts"
          class="session-row"
          :class="mergeMode && {
            'merge-pickable': !!s.end_ts,
            'merge-disabled': !s.end_ts,
            'merge-endpoint': mergeRowState(s) === 'endpoint',
            'merge-included': mergeRowState(s) === 'included',
          }"
          @click="mergeMode && pickMergeRow(s)"
        >
          <span class="cell cell-date" data-label="Date">
            <span class="date-line">
              {{ formatDate(s.start_ts) }}
              <span v-if="s.parts > 1" class="merged-badge" :title="`Merged session: ${s.parts} charging runs`">
                <Layers :size="11" />×{{ s.parts }}
              </span>
              <span
                v-if="s.duplicate_of_id"
                class="duplicate-badge"
                :title="`No charging data of its own and it lies within the session of ${formatDate(s.duplicate_of_start_ts)} ${formatTimeRange(s.duplicate_of_start_ts, s.duplicate_of_end_ts)}, which already counts this charge`"
              >
                <CopyX :size="11" /> Possible duplicate
              </span>
            </span>
          </span>
          <span class="cell cell-time" data-label="Time">{{ formatTimeRange(s.start_ts, s.end_ts) }}</span>
          <span class="cell cell-soc" data-label="Battery">{{ formatSocRange(s) }}</span>
          <span class="cell cell-energy" data-label="Energy">{{ s.energy_kwh != null ? s.energy_kwh.toFixed(1) + ' kWh' : '—' }}</span>
          <span class="cell cell-peak" data-label="Peak">{{ s.peak_power_kw != null ? s.peak_power_kw.toFixed(1) + ' kW' : '—' }}</span>
          <span class="cell cell-tier" data-label="Tier">
            <span v-if="s.tier_label" class="tier-badge" :class="'tier-' + s.tier_id">{{ s.tier_label }}</span>
            <span v-else class="tier-badge tier-none">No tier</span>
          </span>
          <span class="cell cell-zone" data-label="Zone">{{ s.zone_name || '—' }}</span>
          <span class="cell cell-cost" data-label="Cost">
            <span v-if="s.cost != null">€{{ s.cost.toFixed(2) }}</span>
            <span v-else class="cost-none">—</span>
          </span>
          <span class="cell cell-edit">
            <span v-if="mergeMode && mergeRowState(s)" class="merge-chip" :class="'merge-chip-' + mergeRowState(s)">
              {{ mergeRowState(s) === 'endpoint' ? 'Selected' : 'Included' }}
            </span>
            <button v-else-if="!mergeMode" class="edit-btn" @click="editSession(s)" title="Session details">
              <Pencil :size="14" />
            </button>
          </span>
        </div>
        <div v-if="!filteredSessions.length" class="empty-row">No charging sessions in this period</div>
      </div>
      <div v-if="mergeMode && mergeFirst" class="merge-bar">
        <span v-if="!mergeLast">
          First: <strong>{{ formatDate(mergeFirst.start_ts) }} {{ formatTimeRange(mergeFirst.start_ts, mergeFirst.end_ts) }}</strong>
          <template v-if="!mergeFirstInView"> ({{ monthName(mergeFirst.start_ts) }})</template>
          — now click the last session{{ mergeFirstInView ? '' : ' (here, or in another month)' }}
        </span>
        <span v-else-if="mergeAcrossMonths">
          From <strong>{{ formatDate(mergeLow.start_ts) }} {{ formatTime(mergeLow.start_ts) }}</strong>
          ({{ monthName(mergeLow.start_ts) }}) to
          <strong>{{ formatDate(mergeHigh.start_ts) }} {{ formatTime(mergeHigh.start_ts) }}</strong>
          ({{ monthName(mergeHigh.start_ts) }}) — the review lists every session involved
        </span>
        <span v-else>
          <strong>{{ mergeRange.length }}</strong> sessions
          <template v-if="mergeIncludedCount">({{ mergeIncludedCount }} included in between)</template>
          · {{ formatDate(mergeLow.start_ts) }} {{ formatTimeRange(mergeLow.start_ts, mergeHigh.end_ts) }}
          · {{ mergeRangeEnergy.toFixed(1) }} kWh
        </span>
        <span class="chart-header-spacer" />
        <button class="btn-save" :disabled="!mergeLast" @click="openMergeDialog">Review merge</button>
      </div>
    </div>

    <!-- Charging by location -->
    <div v-if="costByLocation.length" class="chart-card wide">
      <div class="chart-header"><MapPin :size="16" class="chart-icon" /> Charging by location</div>
      <div class="location-list">
        <div v-for="loc in costByLocation" :key="loc.zone" class="location-row">
          <span class="loc-name">{{ loc.zone }}</span>
          <span class="loc-stat">{{ loc.sessions }} session{{ loc.sessions === 1 ? '' : 's' }}</span>
          <span class="loc-stat">{{ loc.energy.toFixed(1) }} kWh</span>
          <span class="loc-cost">€{{ loc.cost.toFixed(2) }}</span>
        </div>
      </div>
    </div>
    </template>

    <!-- Session detail & edit dialog -->
    <Teleport to="body">
      <div v-if="editingSession" class="modal-backdrop" @click.self="closeSession">
        <div class="modal-dialog session-modal">
          <div class="modal-header">
            <h3>Charging Detail</h3>
            <button class="close-btn" @click="closeSession">✕</button>
          </div>
          <p class="edit-date">
            {{ formatDate(editingSession.start_ts) }}
            <span v-if="editingSession.parts > 1" class="merged-badge" :title="`Merged session: ${editingSession.parts} charging runs`">
              <Layers :size="11" />×{{ editingSession.parts }}
            </span>
            <span v-if="editingSession.duplicate_of_id" class="duplicate-badge"><CopyX :size="11" /> Possible duplicate</span>
          </p>
          <div v-if="editingSession.duplicate_of_id" class="duplicate-note">
            <CopyX :size="14" />
            <span>
              This record has no charging data of its own and lies within the session of
              <strong>{{ formatDate(editingSession.duplicate_of_start_ts) }}
              {{ formatTimeRange(editingSession.duplicate_of_start_ts, editingSession.duplicate_of_end_ts) }}</strong>,
              which already counts this charge: it's most likely a duplicate, counted twice in the totals.
              Delete it to fix them.
            </span>
          </div>
          <p v-if="editingSession.parts > 1" class="merged-note">
            <Layers :size="13" /> Merged from {{ editingSession.parts }} charging runs. Delete it to split it back into
            separate sessions.
          </p>

          <div class="session-detail-stats">
            <div class="detail-stat">
              <span class="stat-label">Time</span>
              <span class="stat-value">{{ formatTimeRange(editingSession.start_ts, editingSession.end_ts) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Duration</span>
              <span class="stat-value" style="color: #7c6aff">{{ sessionDuration(editingSession) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Energy</span>
              <span class="stat-value" style="color: #00e676">{{ editingSession.energy_kwh != null ? editingSession.energy_kwh.toFixed(1) + ' kWh' : '—' }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">SOC</span>
              <span class="stat-value" style="color: #66bb6a">{{ formatSocRange(editingSession) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">SOC added</span>
              <span class="stat-value" style="color: #42a5f5">{{ formatSocDelta(editingSession) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Peak power</span>
              <span class="stat-value" style="color: #ff7043">{{ editingSession.peak_power_kw != null ? editingSession.peak_power_kw.toFixed(1) + ' kW' : '—' }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Avg power</span>
              <span class="stat-value" style="color: #ffab40">{{ sessionAvgPower(editingSession) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Cost</span>
              <span class="stat-value" style="color: #ffd54f">{{ editingSession.cost != null ? '€' + editingSession.cost.toFixed(2) : '—' }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Price</span>
              <span class="stat-value" style="color: #fdd835">{{ sessionUnitPrice(editingSession) }}</span>
            </div>
            <div class="detail-stat">
              <span class="stat-label">Charge type</span>
              <span class="stat-value">{{ editingSession.parts ? (editingSession.is_dc ? 'DC' : 'AC') : '—' }}</span>
            </div>
          </div>

          <template v-if="editingSession.latitude != null && editingSession.longitude != null">
            <div ref="sessionMapEl" class="session-map" />
            <a class="map-link" :href="mapsUrl(editingSession)" target="_blank" rel="noopener">
              <MapPin :size="13" /> Open in Google Maps
            </a>
          </template>
          <div v-else class="map-empty">No GPS position recorded for this session</div>

          <div class="session-edit">
            <div class="session-edit-title"><Pencil :size="13" /> Edit session</div>
            <div class="session-edit-grid">
              <div class="form-group">
                <label>Tier</label>
                <select v-model="editForm.tier_id">
                  <option v-for="t in availableTiers" :key="t.id" :value="t.id">{{ t.label }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>Zone</label>
                <select v-model="editForm.zone_name">
                  <option :value="''">No zone</option>
                  <option v-for="z in availableZones" :key="z.id" :value="z.name">{{ z.name }}</option>
                  <option v-if="editForm.zone_name && !availableZones.some(z => z.name === editForm.zone_name)" :value="editForm.zone_name">{{ editForm.zone_name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>Energy (kWh)</label>
                <div class="input-with-action">
                  <input v-model.number="editForm.energy_kwh" type="number" step="0.1" min="0" />
                  <button
                    v-if="editingSession.id"
                    class="btn-recalc"
                    :disabled="recalculatingId === editingSession.id"
                    @click="recalcSession(editingSession)"
                    title="Recalculate energy &amp; cost from current data"
                  >
                    <RotateCw :size="14" :class="{ spinning: recalculatingId === editingSession.id }" />
                  </button>
                </div>
              </div>
              <div class="form-group">
                <label>Cost override (€) — leave empty for auto</label>
                <input v-model.number="editForm.cost" type="number" step="0.01" min="0" placeholder="Auto-calculate" />
              </div>
              <div class="form-group span-2">
                <label>Note</label>
                <input v-model="editForm.note" type="text" placeholder="Optional note" />
              </div>
            </div>
          </div>

          <div class="modal-actions">
            <button
              v-if="editingSession.id"
              class="btn-delete"
              :disabled="saving"
              @click="deleteSession(editingSession)"
              title="Delete this session's cost record"
            >
              <Trash2 :size="14" /> Delete
            </button>
            <span class="modal-actions-spacer" />
            <button class="btn-cancel" @click="closeSession">Cancel</button>
            <button class="btn-save" :disabled="saving" @click="saveSession">{{ saving ? 'Saving…' : 'Save' }}</button>
          </div>
          <div v-if="editError" class="field-error">{{ editError }}</div>
        </div>
      </div>
    </Teleport>

    <!-- Merge sessions dialog -->
    <Teleport to="body">
      <div v-if="mergeOpen" class="modal-backdrop" @click.self="closeMergeDialog">
        <div class="modal-dialog modal-wide">
          <h3>Merge charging sessions</h3>
          <p class="edit-date">
            For a charge interrupted and resumed in place. The sessions become one, priced only for the time it was
            charging.
          </p>

          <div v-if="mergePreview" class="merge-sessions">
            <div
              v-for="ps in mergePreview.sessions"
              :key="ps.start_ts"
              class="merge-session"
              :class="{ 'is-included': !ps.selected, 'has-problem': ps.problem }"
            >
              <div class="merge-session-line">
                <span class="merge-chip" :class="ps.selected ? 'merge-chip-endpoint' : 'merge-chip-included'">
                  {{ ps.selected ? 'Selected' : 'Included' }}
                </span>
                <span class="merge-session-time">{{ formatDate(ps.start_ts) }} {{ formatTimeRange(ps.start_ts, ps.end_ts) }}</span>
                <span v-if="ps.parts > 1" class="merged-badge"><Layers :size="11" />×{{ ps.parts }}</span>
                <span class="chart-header-spacer" />
                <span class="merge-session-energy">{{ ps.energy_kwh != null ? ps.energy_kwh.toFixed(1) + ' kWh' : '—' }}</span>
              </div>
              <div v-if="ps.problem" class="merge-session-problem">
                <AlertTriangle :size="12" />
                <span>{{ ps.problem_message }}</span>
                <button
                  v-if="ps.problem === 'duplicate' && ps.id"
                  class="btn-link-danger"
                  :disabled="mergeSaving"
                  @click="deleteDuplicateFromMerge(ps)"
                >Delete it</button>
              </div>
            </div>
            <p v-if="mergePreview.sessions.some(ps => !ps.selected)" class="form-hint">
              <strong>Included</strong> sessions weren't clicked but lie between the selected ones, so they are part of
              the merge too.
            </p>
          </div>

          <div v-if="mergePreview && mergePreview.runs.length" class="merge-timeline" aria-hidden="true">
            <div
              v-for="(r, i) in mergePreview.runs"
              :key="'r' + i"
              class="merge-run"
              :style="timelineStyle(r.start_ts, r.end_ts)"
              :title="`${formatTimeRange(r.start_ts, r.end_ts)} · ${r.energy_kwh != null ? r.energy_kwh.toFixed(1) + ' kWh' : '—'}`"
            />
            <div
              v-for="(g, i) in mergePreview.gaps"
              :key="'g' + i"
              class="merge-gap-bar"
              :class="{ bad: !gapOk(g) }"
              :style="timelineStyle(g.start_ts, g.end_ts)"
            />
          </div>

          <div v-if="mergePreview && mergePreview.gaps.length" class="merge-gaps">
            <div v-for="(g, i) in mergePreview.gaps" :key="i" class="merge-gap" :class="{ bad: !gapOk(g) }">
              <span class="merge-gap-title">Pause {{ formatTimeRange(g.start_ts, g.end_ts) }} · {{ formatMinutes(g.minutes) }}</span>
              <span class="merge-checks">
                <span :class="checkClass(g.within_max_gap)">{{ checkMark(g.within_max_gap) }} ≤ {{ formatMinutes(mergePreview.max_gap_minutes) }}</span>
                <span :class="checkClass(g.same_odometer)">{{ checkMark(g.same_odometer) }} Same odometer</span>
                <span :class="checkClass(g.same_place)">{{ checkMark(g.same_place) }} Same place</span>
              </span>
            </div>
          </div>

          <div class="merge-form">
            <div class="form-group">
              <label>Max pause between sessions (min)</label>
              <input v-model.number="mergeMaxGap" type="number" min="1" max="720" step="5" />
            </div>
            <div class="form-group">
              <label>Tier</label>
              <select v-model="mergeTier">
                <option v-for="t in availableTiers" :key="t.id" :value="t.id">{{ t.label }}</option>
              </select>
            </div>
          </div>

          <div v-if="mergePreview && !mergePreview.reason" class="merge-result">
            <span>Result: <strong>{{ mergePreview.energy_kwh != null ? mergePreview.energy_kwh.toFixed(1) + ' kWh' : '—' }}</strong></span>
            <span v-if="mergePreview.cost != null">≈ <strong>€{{ mergePreview.cost.toFixed(2) }}</strong></span>
            <span v-if="mergePreview.zone_name">in {{ mergePreview.zone_name }}</span>
          </div>
          <div v-if="mergePreview && mergePreview.reason" class="field-error">Can't merge: {{ mergePreview.message }}</div>
          <div v-if="mergeError" class="field-error">{{ mergeError }}</div>

          <div class="modal-actions">
            <span class="modal-actions-spacer" />
            <button class="btn-cancel" :disabled="mergeSaving" @click="closeMergeDialog">Cancel</button>
            <button
              class="btn-save"
              :disabled="mergeSaving || mergeLoading || !mergePreview || !!mergePreview.reason"
              @click="runMerge"
            >{{ mergeSaving ? 'Merging…' : 'Merge' }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Calculate missing costs dialog -->
    <Teleport to="body">
      <div v-if="bulkOpen" class="modal-backdrop" @click.self="closeBulkDialog">
        <div class="modal-dialog">
          <h3>Calculate missing costs</h3>
          <p class="edit-date">{{ monthLabel }}</p>

          <template v-if="!bulkResult">
            <ul class="bulk-summary">
              <li v-if="missingCosts.stored.length">
                <strong>{{ missingCosts.stored.length }}</strong> session{{ missingCosts.stored.length === 1 ? '' : 's' }}
                with a tier — energy and cost re-measured
              </li>
              <li v-if="missingCosts.detected.length">
                <strong>{{ missingCosts.detected.length }}</strong> session{{ missingCosts.detected.length === 1 ? '' : 's' }}
                without a tier — tier inferred from the charge location
              </li>
            </ul>

            <div v-if="missingCosts.detected.length" class="form-group">
              <label>Tier when it can't be inferred</label>
              <select v-model="bulkFallbackTier">
                <option :value="null">Skip — assign it manually later</option>
                <option v-for="t in availableTiers" :key="t.id" :value="t.id">{{ t.label }}</option>
              </select>
              <p class="form-hint">
                A DC fast charge is priced as Public DC; a charge inside a zone with a charging tier uses that
                tier. Anything else (outside every zone, or no GPS fix) gets this tier, or is skipped.
              </p>
            </div>

            <div v-if="missingCosts.orphans.length" class="form-group">
              <label class="check-label">
                <input v-model="bulkCloseOrphans" type="checkbox" />
                Also close {{ missingCosts.orphans.length }} unfinished session{{ missingCosts.orphans.length === 1 ? '' : 's' }}
              </label>
              <p class="form-hint">
                These sessions were recorded when charging started, but the app never saw the charge stop (e.g. the
                backend was offline), so they still look "ongoing" and have no cost. The vehicle history shows the
                charge actually ended: enabling this sets the end time from the history, then measures energy and
                cost. Leave it off if you think a charge is genuinely still in progress.
              </p>
            </div>

            <div class="modal-actions">
              <span class="modal-actions-spacer" />
              <button class="btn-cancel" @click="closeBulkDialog">Cancel</button>
              <button class="btn-save" :disabled="bulkRunning || !bulkSelection.length" @click="runBulkCalculation">
                {{ bulkRunning ? 'Calculating…' : `Calculate (${bulkSelection.length})` }}
              </button>
            </div>
            <div v-if="bulkError" class="field-error">{{ bulkError }}</div>
          </template>

          <template v-else>
            <p class="bulk-result">
              <strong>{{ bulkResult.calculated }}</strong> session{{ bulkResult.calculated === 1 ? '' : 's' }} costed.
            </p>
            <div v-if="bulkResult.skipped.length">
              <p class="bulk-result">{{ bulkResult.skipped.length }} skipped:</p>
              <ul class="bulk-skipped">
                <li v-for="sk in bulkResult.skipped" :key="sk.start_ts">
                  <span>{{ formatDate(sk.start_ts) }} {{ formatTime(sk.start_ts) }}</span>
                  <span class="skip-reason">{{ skipReasonLabel(sk.reason) }}</span>
                </li>
              </ul>
              <p class="form-hint">Use the edit button on those rows to set the tier or energy manually.</p>
            </div>
            <div class="modal-actions">
              <span class="modal-actions-spacer" />
              <button class="btn-save" @click="closeBulkDialog">Done</button>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { api } from '../composables/useApi'
import { addBaseLayer } from '../utils/mapTiles'
import { accentHex } from '../utils/theme'
import { parseUTC } from '../utils/maintenance'
import { Zap, TrendingUp, PieChart, Clock, CalendarDays, ChevronLeft, ChevronRight, List, Pencil, MapPin, RotateCw, Calculator, Trash2, Combine, Layers, CopyX, AlertTriangle } from 'lucide-vue-next'

Chart.register(...registerables)

const props = defineProps({
  vin: { type: String, required: true },
})

// State
const selectedMonth = ref(new Date())
const sessionCosts = ref([])
const monthSessions = ref([])
const monthTimeZone = ref('UTC')  // time zone the backend computes months in
const availableTiers = ref([])
const availableZones = ref([])
const timeBands = ref([])
const homePricingMode = ref('flat')
const hasSolarPanels = ref(false)
const editingSession = ref(null)
const editForm = ref({})
const editError = ref('')
const saving = ref(false)
const recalculatingId = ref(null)
const loading = ref(true)
const bulkOpen = ref(false)
const bulkFallbackTier = ref(null)
const bulkCloseOrphans = ref(false)
const bulkRunning = ref(false)
const bulkResult = ref(null)
const bulkError = ref('')

// Charts
const energyCanvas = ref(null)
const costCanvas = ref(null)
const pieCanvas = ref(null)
let charts = []
let resizeTimeout

// Month navigation
const monthLabel = computed(() => {
  const d = selectedMonth.value
  return d.toLocaleString('en-US', { month: 'long', year: 'numeric' })
})
const isCurrentMonth = computed(() => {
  const now = new Date()
  const d = selectedMonth.value
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
})
function prevMonth() {
  const d = new Date(selectedMonth.value)
  d.setMonth(d.getMonth() - 1)
  selectedMonth.value = d
}
function nextMonth() {
  const d = new Date(selectedMonth.value)
  d.setMonth(d.getMonth() + 1)
  selectedMonth.value = d
}

// Sessions of the selected month, from the backend: detected from the vehicle
// history and paired with the cost records (same list the month-end job uses)
const filteredSessions = computed(() => monthSessions.value)

// KPI cards
const kpiCards = computed(() => {
  const sessions = filteredSessions.value
  if (!sessions.length) return []

  const totalEnergy = sessions.reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const totalCost = sessions.reduce((s, c) => s + (c.cost || 0), 0)
  const homeGrid = sessions.filter(c => c.tier_id === 'home_grid').reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const solar = sessions.filter(c => c.tier_id === 'home_solar').reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const pub = sessions.filter(c => c.tier_id === 'public_ac' || c.tier_id === 'public_dc').reduce((s, c) => s + (c.energy_kwh || 0), 0)
  const homeCost = sessions.filter(c => c.tier_id === 'home_grid' || c.tier_id === 'home_solar').reduce((s, c) => s + (c.cost || 0), 0)
  const pubCost = sessions.filter(c => c.tier_id === 'public_ac' || c.tier_id === 'public_dc').reduce((s, c) => s + (c.cost || 0), 0)

  const cards = [
    { label: 'Sessions', value: sessions.length, color: '#7c6aff' },
    { label: 'Total energy', value: `${totalEnergy.toFixed(1)} kWh`, color: '#00e676' },
    { label: 'Home grid', value: `${homeGrid.toFixed(1)} kWh`, color: '#66bb6a' },
  ]
  if (hasSolarPanels.value) {
    cards.push({ label: 'Solar', value: `${solar.toFixed(1)} kWh`, color: '#fdd835' })
  }
  cards.push(
    { label: 'Public', value: `${pub.toFixed(1)} kWh`, color: '#42a5f5' },
    { label: 'Total cost', value: `€${totalCost.toFixed(2)}`, color: '#ffd54f' },
    { label: 'Home cost', value: `€${homeCost.toFixed(2)}`, color: '#a5d6a7' },
    { label: 'Public cost', value: `€${pubCost.toFixed(2)}`, color: '#90caf9' },
  )
  return cards
})

// Monthly summary (last 6 months)
const monthlySummary = computed(() => {
  const all = sessionCosts.value
  if (!all.length) return []
  const months = {}
  // Months in the same time zone the backend uses for the session list
  const monthOf = new Intl.DateTimeFormat('en-CA', { timeZone: monthTimeZone.value, year: 'numeric', month: '2-digit' })
  for (const s of all) {
    const key = monthOf.format(parseUTC(s.start_ts))
    if (!months[key]) months[key] = { month: key, sessions: 0, energy: 0, homeGrid: 0, solar: 0, public: 0, cost: 0 }
    months[key].sessions++
    months[key].energy += s.energy_kwh || 0
    months[key].cost += s.cost || 0
    if (s.tier_id === 'home_grid') months[key].homeGrid += s.energy_kwh || 0
    else if (s.tier_id === 'home_solar') months[key].solar += s.energy_kwh || 0
    else months[key].public += s.energy_kwh || 0
  }
  return Object.values(months).sort((a, b) => b.month.localeCompare(a.month)).slice(0, 12)
})

// Charging energy/cost grouped by the zone the session happened in
const costByLocation = computed(() => {
  const groups = {}
  for (const s of filteredSessions.value) {
    const key = s.zone_name || 'Unknown location'
    if (!groups[key]) groups[key] = { zone: key, sessions: 0, energy: 0, cost: 0 }
    groups[key].sessions++
    groups[key].energy += s.energy_kwh || 0
    groups[key].cost += s.cost || 0
  }
  return Object.values(groups).sort((a, b) => b.energy - a.energy)
})

// Time-of-use bands with energy distribution
const timeBandsWithEnergy = computed(() => {
  if (!timeBands.value.length) return []
  const sessions = filteredSessions.value
  const bandEnergy = {}
  for (const b of timeBands.value) bandEnergy[b.id] = { energy: 0, cost: 0 }
  for (const s of sessions) {
    if (s.time_band_id && bandEnergy[s.time_band_id]) {
      bandEnergy[s.time_band_id].energy += s.energy_kwh || 0
      bandEnergy[s.time_band_id].cost += s.cost || 0
    }
  }
  const maxE = Math.max(1, ...Object.values(bandEnergy).map(b => b.energy))
  return timeBands.value.map(b => ({
    ...b,
    energy: bandEnergy[b.id]?.energy || 0,
    cost: bandEnergy[b.id]?.cost || 0,
    pct: ((bandEnergy[b.id]?.energy || 0) / maxE) * 100,
  }))
})

// Formatting
function formatDate(ts) {
  if (!ts) return '—'
  return parseUTC(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
function formatTime(ts) {
  return parseUTC(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}
function formatTimeRange(start, end) {
  const s = start ? formatTime(start) : ''
  const e = end ? formatTime(end) : 'ongoing'
  return `${s} – ${e}`
}

// Session detail & edit dialog
const sessionMapEl = ref(null)
let sessionMap = null

function destroySessionMap() {
  sessionMap?.remove()
  sessionMap = null
}

async function renderSessionMap(session) {
  destroySessionMap()
  if (session.latitude == null || session.longitude == null) return
  await nextTick()
  if (!sessionMapEl.value) return
  const pos = [session.latitude, session.longitude]
  sessionMap = L.map(sessionMapEl.value, { zoomControl: true, attributionControl: false }).setView(pos, 16)
  addBaseLayer(sessionMap)
  L.circleMarker(pos, { radius: 9, color: '#fff', fillColor: accentHex(), fillOpacity: 1, weight: 2 })
    .bindTooltip(session.zone_name || 'Charging location')
    .addTo(sessionMap)
}

function closeSession() {
  destroySessionMap()
  editingSession.value = null
}

function formatSocRange(s) {
  if (s.start_soc == null && s.end_soc == null) return '—'
  return `${s.start_soc ?? '?'}% → ${s.end_soc ?? '?'}%`
}
function formatSocDelta(s) {
  if (s.start_soc == null || s.end_soc == null) return '—'
  const d = s.end_soc - s.start_soc
  return `${d >= 0 ? '+' : ''}${d}%`
}
function sessionHours(s) {
  if (!s.start_ts) return null
  const end = s.end_ts ? parseUTC(s.end_ts) : new Date()
  return (end - parseUTC(s.start_ts)) / 3600000
}
function sessionDuration(s) {
  const h = sessionHours(s)
  if (h == null || h < 0) return '—'
  const mins = Math.round(h * 60)
  return mins >= 60 ? `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, '0')}m` : `${mins} min`
}
// Over the whole window: for a merged session it includes the pauses
function sessionAvgPower(s) {
  const h = sessionHours(s)
  if (s.energy_kwh == null || !s.end_ts || !h || h <= 0) return '—'
  return `${(s.energy_kwh / h).toFixed(1)} kW`
}
function sessionUnitPrice(s) {
  if (s.cost == null || !s.energy_kwh) return '—'
  return `€${(s.cost / s.energy_kwh).toFixed(3)}/kWh`
}
function mapsUrl(s) {
  return `https://www.google.com/maps/search/?api=1&query=${s.latitude},${s.longitude}`
}

// Edit session
function editSession(session) {
  editingSession.value = session
  editForm.value = {
    tier_id: session.tier_id || (availableTiers.value[0]?.id || 'home_grid'),
    zone_name: session.zone_name || '',
    energy_kwh: session.energy_kwh,
    cost: session.cost,
    note: session.note || '',
  }
  editError.value = ''
  renderSessionMap(session)
}

async function saveSession() {
  saving.value = true
  editError.value = ''
  try {
    const s = editingSession.value
    const body = {
      tier_id: editForm.value.tier_id,
      zone_name: editForm.value.zone_name ?? '',
      energy_kwh: editForm.value.energy_kwh || undefined,
      peak_power_kw: s.peak_power_kw ?? undefined,
      note: editForm.value.note || undefined,
    }
    if (s.id) {
      // Update existing
      await api('PUT', `/api/vehicles/${props.vin}/charging-costs/${s.id}`, body)
    } else {
      // Create new for a session without cost record
      body.start_ts = s.start_ts
      body.end_ts = s.end_ts || undefined
      await api('POST', `/api/vehicles/${props.vin}/charging-costs`, body)
    }
    await loadData()
    closeSession()
  } catch (e) {
    editError.value = e.message || 'Failed to save'
  } finally {
    saving.value = false
  }
}

// Merge sessions — a range is picked in the list (first + last session, all
// the ones in between included), reviewed in a dialog with the backend preview
const mergeMode = ref(false)
const mergeFirst = ref(null)  // the clicked sessions; kept across month changes
const mergeLast = ref(null)
const mergeOpen = ref(false)
const mergePreview = ref(null)
const mergeLoading = ref(false)
const mergeSaving = ref(false)
const mergeError = ref('')
const mergeMaxGap = ref(120)
const mergeTier = ref(null)

function resetMerge() {
  mergeFirst.value = null
  mergeLast.value = null
}

function toggleMergeMode() {
  mergeMode.value = !mergeMode.value
  resetMerge()
}

function pickMergeRow(s) {
  if (!s.end_ts) return  // in progress
  if (!mergeFirst.value || mergeLast.value) {
    mergeFirst.value = s
    mergeLast.value = null
  } else if (s.start_ts === mergeFirst.value.start_ts) {
    mergeFirst.value = null
  } else {
    mergeLast.value = s
  }
}

const startMs = s => parseUTC(s.start_ts).getTime()
// Picked endpoints in time order (they may be clicked in either order)
const mergeLow = computed(() => {
  const a = mergeFirst.value
  const b = mergeLast.value
  if (!a || !b) return a
  return startMs(a) <= startMs(b) ? a : b
})
const mergeHigh = computed(() => {
  const a = mergeFirst.value
  const b = mergeLast.value
  if (!a || !b) return a
  return startMs(a) <= startMs(b) ? b : a
})

function inView(sel) {
  return !!sel && filteredSessions.value.some(s => s.start_ts === sel.start_ts)
}
const mergeFirstInView = computed(() => inView(mergeFirst.value))
const mergeAcrossMonths = computed(() => !!mergeLast.value && (!inView(mergeFirst.value) || !inView(mergeLast.value)))

// Sessions of this month inside the picked range (by time, so an endpoint
// picked in another month still includes the sessions between it and here)
const mergeRange = computed(() => {
  if (!mergeLow.value) return []
  const lo = startMs(mergeLow.value)
  const hi = startMs(mergeHigh.value)
  return filteredSessions.value.filter(s => startMs(s) >= lo && startMs(s) <= hi)
})
const mergeIncludedCount = computed(() => mergeRange.value.filter(s => mergeRowState(s) === 'included').length)
const mergeRangeEnergy = computed(() => mergeRange.value.reduce((sum, s) => sum + (s.energy_kwh || 0), 0))

function mergeRowState(s) {
  if (!mergeMode.value || !mergeFirst.value) return null
  if (s.start_ts === mergeFirst.value.start_ts || s.start_ts === mergeLast.value?.start_ts) return 'endpoint'
  if (!mergeLast.value) return null
  return mergeRange.value.includes(s) ? 'included' : null
}

function monthName(ts) {
  return parseUTC(ts).toLocaleString('en-GB', { month: 'long' })
}

function mergeStarts() {
  return [mergeFirst.value.start_ts, mergeLast.value.start_ts]
}

async function loadMergePreview() {
  if (!mergeFirst.value || !mergeLast.value) return
  mergeLoading.value = true
  mergeError.value = ''
  try {
    const preview = await api('POST', `/api/vehicles/${props.vin}/charging-costs/merge/preview`, {
      start_ts: mergeStarts(),
      max_gap_minutes: mergeMaxGap.value,
      tier_id: mergeTier.value || undefined,
    })
    mergePreview.value = preview
    if (!mergeTier.value && preview.tier_id) mergeTier.value = preview.tier_id
  } catch (e) {
    mergeError.value = e.message || 'Preview failed'
  } finally {
    mergeLoading.value = false
  }
}

function openMergeDialog() {
  mergePreview.value = null
  mergeTier.value = null
  mergeError.value = ''
  mergeOpen.value = true
  loadMergePreview()
}

function closeMergeDialog() {
  if (mergeSaving.value) return
  mergeOpen.value = false
}

let mergePreviewTimer
watch([mergeMaxGap, mergeTier], () => {
  if (!mergeOpen.value) return
  clearTimeout(mergePreviewTimer)
  if (!(mergeMaxGap.value >= 1 && mergeMaxGap.value <= 720)) {
    mergeError.value = 'Max pause must be between 1 and 720 minutes'
    return
  }
  mergePreviewTimer = setTimeout(loadMergePreview, 350)
})

async function runMerge() {
  mergeSaving.value = true
  mergeError.value = ''
  try {
    await api('POST', `/api/vehicles/${props.vin}/charging-costs/merge`, {
      start_ts: mergeStarts(),
      max_gap_minutes: mergeMaxGap.value,
      tier_id: mergeTier.value || undefined,
    })
    mergeOpen.value = false
    mergeMode.value = false
    resetMerge()
    await loadData()
  } catch (e) {
    mergeError.value = e.message || 'Merge failed'
  } finally {
    mergeSaving.value = false
  }
}

// Delete a duplicate spotted in the merge review; the rest of the selection
// is re-checked (or the dialog closes when nothing is left to merge)
async function deleteDuplicateFromMerge(ps) {
  if (!confirm('Delete this duplicate record? The session it duplicates already counts its charge.')) return
  mergeSaving.value = true
  mergeError.value = ''
  try {
    await api('DELETE', `/api/vehicles/${props.vin}/charging-costs/${ps.id}`)
    if (mergeLast.value?.start_ts === ps.start_ts) mergeLast.value = null
    if (mergeFirst.value?.start_ts === ps.start_ts) {
      mergeFirst.value = mergeLast.value
      mergeLast.value = null
    }
    await loadData()
    if (mergeFirst.value && mergeLast.value) {
      await loadMergePreview()
    } else {
      mergeOpen.value = false
    }
  } catch (e) {
    mergeError.value = e.message || 'Delete failed'
  } finally {
    mergeSaving.value = false
  }
}

function gapOk(g) {
  return g.within_max_gap && g.same_odometer !== false && g.same_place !== false
}
function checkMark(v) { return v === true ? '✓' : v === false ? '✗' : '?' }
function checkClass(v) { return v === true ? 'check-ok' : v === false ? 'check-bad' : 'check-unknown' }
function formatMinutes(min) {
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

// Position of a span on the merge timeline (first run start → last run end)
function timelineStyle(start, end) {
  const runs = mergePreview.value?.runs || []
  if (!runs.length) return {}
  const t0 = parseUTC(runs[0].start_ts).getTime()
  const t1 = parseUTC(runs[runs.length - 1].end_ts || runs[runs.length - 1].start_ts).getTime()
  const span = Math.max(t1 - t0, 1)
  const a = (parseUTC(start).getTime() - t0) / span * 100
  const b = (parseUTC(end || start).getTime() - t0) / span * 100
  return { left: `${a}%`, width: `${Math.max(b - a, 0.8)}%` }
}

// Delete a stored session record (e.g. a duplicate). A session that is also
// visible in the snapshots stays listed, back without a cost.
async function deleteSession(session) {
  if (!session.id) return
  const message = session.parts > 1
    ? `Delete this merged session? It will split back into its ${session.parts} charging runs, without costs.`
    : 'Delete this charging session record? Its cost and notes will be lost.'
  if (!confirm(message)) return
  saving.value = true
  editError.value = ''
  try {
    await api('DELETE', `/api/vehicles/${props.vin}/charging-costs/${session.id}`)
    await loadData()
    closeSession()
  } catch (e) {
    editError.value = e.message || 'Failed to delete'
  } finally {
    saving.value = false
  }
}

// Recalculate a stored session's total energy & cost from current data
async function recalcSession(session) {
  if (!session.id || recalculatingId.value) return
  recalculatingId.value = session.id
  try {
    await api('POST', `/api/vehicles/${props.vin}/charging-costs/${session.id}/recalculate`)
    await loadData()
    const fresh = monthSessions.value.find(s => s.id === session.id)
    if (fresh) editSession(fresh)
    else closeSession()
  } catch { /* ignore */ } finally {
    recalculatingId.value = null
  }
}

// Calculate missing costs (current month only)
const missingCosts = computed(() => {
  const stored = []    // record with a tier, finished, no cost
  const detected = []  // snapshot-only session, finished — tier to infer
  const orphans = []   // open record, but the history shows the charge ended
  for (const s of filteredSessions.value) {
    if (s.cost != null || s.duplicate_of_id) continue
    if (s.id && s.end_ts) stored.push(s)
    else if (!s.id && s.end_ts) detected.push(s)
    else if (s.id && !s.end_ts && s.detected_end_ts) orphans.push(s)
  }
  return { stored, detected, orphans, total: stored.length + detected.length + orphans.length }
})

const bulkSelection = computed(() => {
  const { stored, detected, orphans } = missingCosts.value
  const items = [...stored, ...detected].map(s => ({ start_ts: s.start_ts, end_ts: s.end_ts, cost_id: s.id ?? null }))
  if (bulkCloseOrphans.value) {
    for (const s of orphans) items.push({ start_ts: s.start_ts, end_ts: s.detected_end_ts, cost_id: s.id })
  }
  return items
})

function openBulkDialog() {
  bulkFallbackTier.value = null
  bulkCloseOrphans.value = false
  bulkResult.value = null
  bulkError.value = ''
  bulkOpen.value = true
}

function closeBulkDialog() {
  if (bulkRunning.value) return
  bulkOpen.value = false
  bulkResult.value = null
}

async function runBulkCalculation() {
  bulkRunning.value = true
  bulkError.value = ''
  try {
    bulkResult.value = await api('POST', `/api/vehicles/${props.vin}/charging-costs/calculate-missing`, {
      sessions: bulkSelection.value,
      fallback_tier_id: bulkFallbackTier.value,
      close_orphans: bulkCloseOrphans.value,
    })
    await loadData()
  } catch (e) {
    bulkError.value = e.message || 'Failed to calculate costs'
  } finally {
    bulkRunning.value = false
  }
}

function skipReasonLabel(reason) {
  return {
    no_tier: 'tier not inferable',
    no_energy: 'energy not measurable',
    ongoing: 'still in progress',
    not_found: 'session no longer exists',
  }[reason] || reason
}

// Data loading
async function loadData() {
  loading.value = true
  try {
    const y = selectedMonth.value.getFullYear()
    const m = selectedMonth.value.getMonth()

    const [tiersData, costs, prefs, monthData, zonesData] = await Promise.all([
      api('GET', '/api/charging/tiers'),
      api('GET', `/api/vehicles/${props.vin}/charging-costs`),
      api('GET', '/api/preferences'),
      api('GET', `/api/vehicles/${props.vin}/charging-sessions?year=${y}&month=${m + 1}`),
      api('GET', `/api/zones?vin=${props.vin}`),
    ])
    availableZones.value = zonesData || []
    availableTiers.value = tiersData.tiers || []
    timeBands.value = tiersData.time_bands || []
    homePricingMode.value = tiersData.home_pricing_mode || 'flat'
    sessionCosts.value = costs || []
    hasSolarPanels.value = prefs.has_solar_panels ?? false
    monthSessions.value = monthData?.sessions || []
    monthTimeZone.value = monthData?.timezone || 'UTC'
  } catch { /* ignore */ }
  loading.value = false
  await nextTick()
  renderCharts()
}

// Charts
function destroyCharts() {
  charts.forEach(c => c.destroy())
  charts = []
}

function getChartColors() {
  const s = getComputedStyle(document.documentElement)
  return {
    grid: s.getPropertyValue('--chart-grid').trim() || '#1c2135',
    tick: s.getPropertyValue('--chart-tick').trim() || '#4a5468',
    label: s.getPropertyValue('--label').trim() || '#6a748a',
  }
}

function renderCharts() {
  destroyCharts()
  const sessions = [...filteredSessions.value].reverse() // chronological order (oldest first)
  const cc = getChartColors()

  // Energy per session bar chart
  if (energyCanvas.value && sessions.length) {
    const ctx = energyCanvas.value.getContext('2d')
    const tierColors = { home_grid: '#66bb6a', home_solar: '#fdd835', public_ac: '#42a5f5', public_dc: '#7c6aff' }
    charts.push(new Chart(ctx, {
      type: 'bar',
      data: {
        labels: sessions.map(s => formatDate(s.start_ts)),
        datasets: [{
          data: sessions.map(s => s.energy_kwh || 0),
          backgroundColor: sessions.map(s => tierColors[s.tier_id] || '#888'),
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: (ctx) => {
                const s = sessions[ctx.dataIndex]
                if (s.peak_power_kw != null) return `Peak: ${s.peak_power_kw.toFixed(1)} kW`
                return ''
              },
            },
          },
        },
        scales: {
          x: { ticks: { color: cc.tick, font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: cc.tick }, grid: { color: cc.grid } },
        },
      },
    }))
  }

  // Daily cost line chart
  if (costCanvas.value && sessions.length) {
    const ctx = costCanvas.value.getContext('2d')
    // Aggregate by day
    const daily = {}
    for (const s of sessions) {
      const day = parseUTC(s.start_ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
      daily[day] = (daily[day] || 0) + (s.cost || 0)
    }
    const labels = Object.keys(daily)
    const data = labels.map(l => daily[l])
    charts.push(new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data,
          borderColor: '#ffd54f',
          backgroundColor: 'rgba(255,213,79,0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: cc.tick, font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: cc.tick, callback: v => `€${v.toFixed(2)}` }, grid: { color: cc.grid } },
        },
      },
    }))
  }

  // Tier pie chart
  if (pieCanvas.value && sessions.length) {
    const ctx = pieCanvas.value.getContext('2d')
    const tierEnergy = {}
    for (const s of sessions) {
      const tid = s.tier_id || 'unknown'
      tierEnergy[tid] = (tierEnergy[tid] || 0) + (s.energy_kwh || 0)
    }
    const tierColors = { home_grid: '#66bb6a', home_solar: '#fdd835', public_ac: '#42a5f5', public_dc: '#7c6aff', unknown: '#888' }
    const tierLabels = { home_grid: 'Home Grid', home_solar: 'Solar', public_ac: 'Public AC', public_dc: 'Public DC', unknown: 'Unknown' }
    const keys = Object.keys(tierEnergy).filter(k => tierEnergy[k] > 0)
    charts.push(new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: keys.map(k => tierLabels[k] || k),
        datasets: [{
          data: keys.map(k => tierEnergy[k]),
          backgroundColor: keys.map(k => tierColors[k] || '#888'),
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: cc.label, font: { size: 11 } } },
        },
      },
    }))
  }
}

// Resize handler with debounce
function handleResize() {
  clearTimeout(resizeTimeout)
  resizeTimeout = setTimeout(() => {
    renderCharts()
  }, 300)
}

// Lifecycle
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  clearTimeout(resizeTimeout)
  destroySessionMap()
})
watch(() => props.vin, loadData)
watch(selectedMonth, loadData)
</script>

<style scoped>
.charging-tab { width: 100%; }
.loading-center { display: flex; justify-content: center; padding: 48px; }
.charging-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.header-title h2 { font-size: 20px; font-weight: 700; color: var(--text); margin: 0; }
.header-title p { font-size: 12px; color: var(--muted); margin: 2px 0 0; }
.month-nav { display: flex; align-items: center; gap: 8px; }
.month-label { font-size: 14px; font-weight: 600; color: var(--text); min-width: 130px; text-align: center; }
.toolbar-btn { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 6px; color: var(--text); cursor: pointer; display: flex; align-items: center; transition: all 0.15s; }
.toolbar-btn:disabled { opacity: 0.4; cursor: default; }
.toolbar-btn:hover:not(:disabled) { background: var(--btn-bg); color: var(--cyan); border-color: var(--cyan); }

/* KPI — aligned with the Data History tab */
.summary-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }
@media (min-width: 768px) {
  .summary-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
}
.summary-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; text-align: center; }
.summary-value { font-size: 20px; font-weight: 700; }
.summary-label { font-size: 10px; color: var(--muted); margin-top: 4px; }

/* Charts */
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; margin-bottom: 12px; }
.charts-grid-3 { grid-template-columns: 1fr; }
@media (min-width: 640px) {
  .charts-grid-3 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
}
.chart-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }
.chart-card.wide { grid-column: 1 / -1; }
.charts-grid + .chart-card.wide,
.chart-card.wide + .chart-card.wide { margin-top: 12px; }
.chart-header { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 10px; }
.chart-icon { opacity: 0.7; }
.chart-header-spacer { flex: 1; }
.btn-bulk { display: inline-flex; align-items: center; gap: 6px; background: var(--btn-bg); border: 1px solid var(--btn-border); border-radius: 8px; padding: 5px 10px; color: var(--text); cursor: pointer; font-size: 12px; font-weight: 500; }
.btn-bulk:hover { border-color: var(--text); }
.chart-area { height: 200px; position: relative; }

/* TOU bands */
.tou-card { margin-bottom: 12px; }
.tou-bands { display: flex; flex-direction: column; gap: 8px; }
.tou-band-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.tou-color { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.tou-name { min-width: 50px; color: var(--text); font-weight: 500; }
.tou-price { min-width: 80px; color: var(--muted); }
.tou-bar-track { flex: 1; height: 8px; background: var(--bg); border-radius: 4px; overflow: hidden; }
.tou-bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.tou-energy { min-width: 60px; text-align: right; color: var(--text); }
.tou-cost { min-width: 50px; text-align: right; color: var(--muted); }

/* Charging by location */
.location-list { display: flex; flex-direction: column; }
.location-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.location-row:last-child { border-bottom: none; }
.loc-name { flex: 1; color: var(--text); font-weight: 500; }
.loc-stat { color: var(--muted); min-width: 70px; text-align: right; }
.loc-cost { color: var(--text); min-width: 60px; text-align: right; font-weight: 600; }

/* Monthly summary */
.monthly-table-wrap { overflow-x: auto; }
.monthly-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.monthly-table th { text-align: left; color: var(--muted); font-weight: 600; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.monthly-table td { padding: 6px 8px; color: var(--text); border-bottom: 1px solid var(--border); }
.empty-row { color: var(--muted); text-align: center; padding: 20px; }

/* Session list */
.session-list { display: flex; flex-direction: column; }
/* Desktop: aligned table with header */
.session-head, .session-row {
  display: grid;
  grid-template-columns: 1.1fr 1.3fr 1.1fr 0.9fr 0.8fr 1.1fr 1fr 0.9fr 40px;
  gap: 12px; align-items: center;
}
/* Merge mode: the last column holds the Selected/Included chip instead of the edit button */
@media (min-width: 641px) {
  .merge-active .session-head, .merge-active .session-row {
    grid-template-columns: 1.1fr 1.3fr 1.1fr 0.9fr 0.8fr 1.1fr 1fr 0.9fr 72px;
  }
}
.session-head { padding: 0 0 8px; border-bottom: 1px solid var(--border); }
.session-head span { font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); font-weight: 600; }
.session-row { padding: 10px 0; border-bottom: 1px solid var(--border); }
.session-row:last-child { border-bottom: none; }
.cell { font-size: 13px; color: var(--text); min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.cell-date { font-weight: 500; }
.cell-time { font-size: 12px; color: var(--muted); }
.cell-energy { font-weight: 600; color: var(--green); }
.cell-peak { font-size: 12px; color: var(--amber); }
.cell-soc { font-size: 12px; white-space: nowrap; }
.cell-cost { font-weight: 600; color: var(--amber); }
.cell-edit { display: flex; justify-content: flex-end; }
.cost-none { color: var(--muted); }
.tier-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 500; }
.tier-home_grid { background: rgba(102,187,106,0.15); color: #66bb6a; }
.tier-home_solar { background: rgba(253,216,53,0.15); color: #fdd835; }
.tier-public_ac { background: rgba(66,165,245,0.15); color: #42a5f5; }
.tier-public_dc { background: rgba(124,106,255,0.15); color: #7c6aff; }
.tier-none { background: rgba(136,136,136,0.1); color: #888; }
.edit-btn { background: none; border: 1px solid var(--border); border-radius: 6px; padding: 4px 6px; color: var(--muted); cursor: pointer; display: flex; align-items: center; }
.edit-btn:hover { color: var(--text); border-color: var(--text); }
.edit-btn:disabled { cursor: default; opacity: 0.6; }
.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Merged sessions & merge mode */
.date-line { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.merged-badge { display: inline-flex; align-items: center; gap: 2px; font-size: 10px; font-weight: 600; color: var(--accent); background: color-mix(in srgb, var(--accent) 14%, transparent); border-radius: 4px; padding: 1px 5px; }
.merged-note { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; color: var(--muted); background: var(--btn-bg); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; margin: -6px 0 14px; line-height: 1.4; }
.duplicate-badge { display: inline-flex; align-items: center; gap: 3px; font-size: 10px; font-weight: 600; color: var(--red); background: color-mix(in srgb, var(--red) 12%, transparent); border-radius: 4px; padding: 1px 5px; white-space: nowrap; }
.duplicate-note { display: flex; gap: 8px; align-items: flex-start; font-size: 12px; color: var(--text); background: color-mix(in srgb, var(--red) 10%, transparent); border: 1px solid color-mix(in srgb, var(--red) 40%, transparent); border-radius: 8px; padding: 8px 10px; margin: -6px 0 14px; line-height: 1.45; }
.duplicate-note svg { color: var(--red); flex-shrink: 0; margin-top: 2px; }
.btn-bulk.active { border-color: var(--accent); color: var(--accent); }
.merge-hint { font-size: 12px; color: var(--muted); margin: -2px 0 10px; line-height: 1.45; }
.session-row.merge-pickable { cursor: pointer; }
.session-row.merge-pickable:hover { background: var(--btn-bg); }
.session-row.merge-disabled { opacity: 0.45; cursor: not-allowed; }
.session-row.merge-endpoint, .session-row.merge-included { box-shadow: inset 3px 0 0 var(--accent); }
.session-row.merge-endpoint { background: color-mix(in srgb, var(--accent) 12%, transparent); }
.session-row.merge-included { background: color-mix(in srgb, var(--accent) 6%, transparent); }
.merge-chip { font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 6px; white-space: nowrap; }
.merge-chip-endpoint { background: var(--accent); color: var(--card); }
.merge-chip-included { border: 1px dashed var(--accent); color: var(--accent); }
.merge-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 10px; padding: 10px 12px; border: 1px solid var(--accent); border-radius: 10px; font-size: 12px; color: var(--text); }
.modal-dialog.modal-wide { max-width: 560px; max-height: 90vh; overflow-y: auto; }
.merge-sessions { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.merge-session { display: flex; flex-direction: column; gap: 4px; font-size: 12px; padding: 6px 8px; border: 1px solid var(--border); border-radius: 8px; }
.merge-session-line { display: flex; align-items: center; gap: 8px; }
.merge-session.has-problem { border: 1px solid var(--red); background: color-mix(in srgb, var(--red) 8%, transparent); }
.merge-session-problem { display: flex; align-items: center; gap: 6px; color: var(--red); font-size: 11px; line-height: 1.4; }
.merge-session-problem svg { flex-shrink: 0; }
.btn-link-danger { margin-left: auto; background: none; border: 1px solid var(--red); color: var(--red); border-radius: 6px; padding: 2px 8px; font-size: 11px; cursor: pointer; white-space: nowrap; }
.btn-link-danger:disabled { opacity: 0.6; cursor: default; }
.merge-session.is-included { border-style: dashed; border-color: var(--accent); }
.merge-session-time { color: var(--text); }
.merge-session-energy { font-weight: 600; color: var(--green); }
.merge-timeline { position: relative; height: 14px; border-radius: 7px; background: var(--btn-bg); margin: 4px 0 10px; overflow: hidden; }
.merge-run { position: absolute; top: 0; bottom: 0; background: var(--green); border-radius: 7px; }
.merge-gap-bar { position: absolute; top: 5px; bottom: 5px; background: var(--muted); opacity: 0.35; }
.merge-gap-bar.bad { background: var(--red); opacity: 0.8; }
.merge-gaps { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.merge-gap { display: flex; flex-direction: column; gap: 4px; font-size: 12px; padding: 6px 8px; border-left: 3px solid var(--green); background: var(--btn-bg); border-radius: 0 8px 8px 0; }
.merge-gap.bad { border-left-color: var(--red); }
.merge-gap-title { color: var(--text); }
.merge-checks { display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; }
.check-ok { color: var(--green); }
.check-bad { color: var(--red); font-weight: 600; }
.check-unknown { color: var(--muted); }
.merge-form { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.merge-result { display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; color: var(--text); margin-top: 4px; }

/* Mobile: each session becomes a compact labelled card */
@media (max-width: 640px) {
  .session-head { display: none; }
  .session-row {
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 8px 12px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 8px;
  }
  .session-row:last-child { border-bottom: 1px solid var(--border); }
  .cell { display: flex; flex-direction: column; font-size: 13px; }
  .cell[data-label]::before {
    content: attr(data-label);
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--muted); margin-bottom: 2px; font-weight: 600;
  }
  .cell-date { grid-column: 1; grid-row: 1; }
  .cell-time { grid-column: 2; grid-row: 1; }
  .cell-soc { grid-column: 3; grid-row: 1; }
  .cell-energy { grid-column: 1; grid-row: 2; }
  .cell-peak { grid-column: 2; grid-row: 2; }
  .cell-cost { grid-column: 3; grid-row: 2; }
  .cell-tier { grid-column: 4; grid-row: 2; display: flex; align-items: center; width: fit-content; }
  .tier-badge { display: inline-block; }
  .cell-edit { grid-column: 4; grid-row: 1; justify-self: flex-end; }
}

/* Modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.modal-dialog { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; width: 90%; max-width: 380px; }
.modal-dialog h3 { font-size: 16px; font-weight: 700; color: var(--text); margin: 0 0 4px; }
.edit-date { font-size: 12px; color: var(--muted); margin-bottom: 16px; }

/* Session detail (same look as the trip detail) */
.modal-dialog.session-modal { max-width: 700px; width: 100%; max-height: 85vh; overflow-y: auto; }
.modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.modal-header h3 { margin: 0; }
.close-btn { background: none; border: none; color: var(--muted); font-size: 18px; cursor: pointer; }
.close-btn:hover { color: var(--text); }
.session-modal .edit-date { display: flex; align-items: center; gap: 6px; }
.session-detail-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 16px; }
.detail-stat { background: var(--bg2); border-radius: 8px; padding: 10px 12px; }
.stat-label { display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px; }
.stat-value { font-size: 14px; font-weight: 600; color: var(--text); }
.session-edit { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border); }
.session-edit-title { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin-bottom: 10px; }
.session-edit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.session-edit-grid .span-2 { grid-column: 1 / -1; }
@media (max-width: 640px) {
  .session-edit-grid { grid-template-columns: 1fr; }
}
.session-map { height: 300px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
.map-link { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--accent); margin-top: 8px; text-decoration: none; }
.map-link:hover { text-decoration: underline; }
.map-empty { text-align: center; padding: 24px; color: var(--muted); font-size: 13px; background: var(--bg2); border-radius: 8px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.form-group input, .form-group select { width: 100%; background: var(--input); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; color: var(--text); font-size: 13px; }
.modal-actions { display: flex; gap: 8px; align-items: center; margin-top: 16px; }
.modal-actions-spacer { flex: 1; }
.input-with-action { display: flex; gap: 8px; }
.input-with-action input { flex: 1; min-width: 0; }
.btn-recalc { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; background: var(--btn-bg); border: 1px solid var(--btn-border); border-radius: 8px; padding: 0 10px; color: var(--text); cursor: pointer; }
.btn-recalc:hover:not(:disabled) { border-color: var(--text); }
.btn-recalc:disabled { opacity: 0.6; cursor: default; }
.btn-delete { display: inline-flex; align-items: center; gap: 6px; background: var(--btn-bg); border: 1px solid var(--btn-border); border-radius: 8px; padding: 8px 14px; color: var(--red); cursor: pointer; font-size: 13px; }
.btn-delete:hover:not(:disabled) { border-color: var(--red); }
.btn-delete:disabled { opacity: 0.6; cursor: default; }
.btn-cancel { background: var(--btn-bg); border: 1px solid var(--btn-border); border-radius: 8px; padding: 8px 16px; color: var(--muted); cursor: pointer; font-size: 13px; }
.btn-save { background: var(--green); border: none; border-radius: 8px; padding: 8px 16px; color: #000; font-weight: 600; cursor: pointer; font-size: 13px; }
.btn-save:disabled { opacity: 0.5; }
.field-error { color: #ff5252; font-size: 12px; margin-top: 8px; }
.form-hint { font-size: 11px; color: var(--muted); margin: 6px 0 0; line-height: 1.45; }
.check-label { display: flex !important; align-items: center; gap: 8px; font-size: 13px !important; color: var(--text) !important; cursor: pointer; }
.form-group .check-label input { width: auto; }
.bulk-summary { margin: 0 0 14px; padding-left: 18px; font-size: 13px; color: var(--text); display: flex; flex-direction: column; gap: 4px; }
.bulk-result { font-size: 13px; color: var(--text); margin: 0 0 8px; }
.bulk-skipped { list-style: none; margin: 0; padding: 0; font-size: 12px; max-height: 200px; overflow-y: auto; }
.bulk-skipped li { display: flex; justify-content: space-between; gap: 12px; padding: 5px 0; border-bottom: 1px solid var(--border); color: var(--text); }
.skip-reason { color: var(--muted); }

@media (max-width: 640px) {
  .charts-grid { grid-template-columns: 1fr; }
}
</style>
