<template>
  <div class="settings-tab">
    <!-- Section Navigation -->
    <div class="settings-nav">
      <button
        v-for="s in sections"
        :key="s.key"
        class="nav-pill"
        :class="{ active: activeSection === s.key }"
        @click="activeSection = s.key"
      >
        <component :is="s.icon" :size="14" />
        <span>{{ s.label }}</span>
      </button>
    </div>

    <!-- ═══════════════ ACCOUNT ═══════════════ -->
    <template v-if="activeSection === 'account'">
      <div class="settings-grid">
        <SectionCard title="LeapConnect Account" :icon="User">
          <div class="account-row">
            <div class="account-avatar">{{ initials }}</div>
            <div>
              <div class="account-name">{{ displayName }}</div>
              <div class="account-role">Local account</div>
            </div>
          </div>
          <button class="action-btn" @click="showUserEdit = !showUserEdit">
            {{ showUserEdit ? 'Cancel' : 'Edit Account' }}
          </button>
          <div v-if="showUserEdit" class="edit-panel">
            <div class="form-group">
              <label>Display Name</label>
              <input v-model="userForm.display_name" type="text" placeholder="Your name" />
            </div>
            <div class="form-group">
              <label>New Password</label>
              <input v-model="userForm.password" type="password" placeholder="Leave empty to keep current" />
            </div>
            <div class="form-divider">Verification</div>
            <div class="form-group">
              <label>Current Password</label>
              <input v-model="userForm.current_password" type="password" placeholder="Required to save changes" />
            </div>
            <button class="save-btn" :disabled="userSaving" @click="saveUser">
              {{ userSaving ? 'Saving…' : 'Save Changes' }}
            </button>
            <div v-if="userError" class="field-error">{{ userError }}</div>
            <div v-if="userSuccess" class="field-success">{{ userSuccess }}</div>
          </div>
        </SectionCard>

        <SectionCard title="API Rate Limit" :icon="AlertTriangle">
          <p class="rate-limit-hint" style="margin-bottom:10px">Minimum seconds between API calls to Leapmotor servers per vehicle</p>
          <div class="interval-row">
            <span class="interval-label">Rate limit</span>
            <div class="interval-control">
              <button class="interval-btn" @click="pendingRateLimit = Math.max(5, pendingRateLimit - 5)">−</button>
              <span class="interval-value">{{ pendingRateLimit }}s</span>
              <button class="interval-btn" @click="pendingRateLimit = Math.min(300, pendingRateLimit + 5)">+</button>
              <button
                class="interval-set-btn"
                :disabled="pendingRateLimit === scheduler.rate_limit_seconds || schedulerUpdating"
                @click="applyRateLimit"
              >Set</button>
            </div>
          </div>
        </SectionCard>
      </div>

      <div class="settings-grid">
        <SectionCard title="Leapmotor Credentials" :icon="KeyRound">
          <InfoRow label="Email" :value="leapmotorEmail" color="#e2e6f0" />
          <InfoRow label="Connection" :value="store.connected ? 'Connected' : 'Offline'" :color="store.connected ? '#00e676' : '#ffab40'" :dot="true" />
          <button class="save-btn" style="margin-top:12px" @click="showLeapmotorEdit = true">
            Edit Credentials
          </button>
        </SectionCard>

        <SectionCard title="Certificates" :icon="ShieldCheck">
          <InfoRow label="App Certificate" :value="certsStatus.cert_exists ? 'Installed' : 'Missing'" :color="certsStatus.cert_exists ? '#00e676' : '#ff5252'" :dot="true" />
          <InfoRow label="Private Key" :value="certsStatus.key_exists ? 'Installed' : 'Missing'" :color="certsStatus.key_exists ? '#00e676' : '#ff5252'" :dot="true" />
          <div v-if="certDownloadError" class="field-error" style="margin-top:8px">{{ certDownloadError }}</div>
          <div v-if="certDownloadSuccess" class="field-success" style="margin-top:8px">{{ certDownloadSuccess }}</div>
          <p class="cert-repo-hint">
            <Github :size="13" />
            <span>Certificates are sourced from</span>
            <a href="https://github.com/markoceri/leapmotor-certs" target="_blank" rel="noopener" class="cert-repo-link">github.com/markoceri/leapmotor-certs</a>
            <ExternalLink :size="10" />
          </p>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button class="save-btn" @click="showCertEdit = true">
              Update Certificates
            </button>
            <button class="save-btn" :disabled="certDownloading" @click="fetchCertsFromGitHub">
              <RefreshCw v-if="certDownloading" :size="13" style="animation:spin 1s linear infinite" />
              {{ certDownloading ? 'Downloading…' : 'Download from GitHub' }}
            </button>
          </div>
        </SectionCard>
      </div>
    </template>

    <!-- ═══════════════ GENERAL ═══════════════ -->
    <template v-if="activeSection === 'general'">
      <SectionCard title="Vehicle" :icon="Car">
        <InfoRow label="Model" :value="`Leapmotor ${vehicle.car_type || ''} ${vehicle.year || ''}`" color="#e2e6f0" />
        <InfoRow label="VIN" color="#e2e6f0">
          <span style="font-family:var(--mono);font-size:11px">{{ vehicle.vin || '—' }}</span>
        </InfoRow>
        <InfoRow label="Nickname" :value="vehicle.vehicle_nickname || '—'" color="#00d4ff" />
      </SectionCard>

      <SectionCard title="Preferences" :icon="SlidersHorizontal">
        <div class="pref-row">
          <div class="pref-info">
            <span class="pref-label">Theme</span>
            <span class="pref-hint">Switch between dark and light mode</span>
          </div>
          <div class="pref-input-group">
            <button
              class="theme-btn"
              :class="{ active: store.theme === 'dark' }"
              @click="store.setTheme('dark')"
            ><Moon :size="13" /> Dark</button>
            <button
              class="theme-btn"
              :class="{ active: store.theme === 'light' }"
              @click="store.setTheme('light')"
            ><Sun :size="13" /> Light</button>
          </div>
        </div>
        <InfoRow label="Distance unit" value="km" color="#e2e6f0" />
        <InfoRow label="Pressure unit" value="bar" color="#e2e6f0" />
        <InfoRow label="Language" value="English" color="#e2e6f0" />
      </SectionCard>

      <SectionCard title="Database" :icon="Database">
        <InfoRow label="Size" :value="databaseSize.size_human" color="#e2e6f0" />
        <div v-if="databaseSize.error" class="field-error">{{ databaseSize.error }}</div>
        <button
          class="save-btn"
          style="margin-top:10px"
          :disabled="databaseSize.loading"
          @click="loadDatabaseSize"
        >{{ databaseSize.loading ? 'Refreshing…' : 'Refresh' }}</button>
      </SectionCard>

      <SectionCard title="Geofences" :icon="Navigation">
        <p class="rate-limit-hint" style="margin-bottom:12px">
          Configure geographic zones to receive notifications when the vehicle enters or exits. Click on the map to set coordinates for a new zone.
        </p>

        <!-- Map -->
        <div class="geofence-map-wrapper">
          <div ref="geofenceMapEl" class="geofence-map-container"></div>
        </div>

        <div v-for="gf in geofences" :key="gf.id" class="geofence-item">
          <div class="geofence-header">
            <div class="geofence-name-row">
              <MapPin :size="13" class="geofence-pin" />
              <span class="geofence-name">{{ gf.name }}</span>
            </div>
            <button class="geofence-delete-btn" @click="deleteGeofence(gf.id)">
              <Trash2 :size="13" />
            </button>
          </div>
          <div class="geofence-details">
            <span>{{ gf.latitude.toFixed(5) }}, {{ gf.longitude.toFixed(5) }} · {{ gf.radius_m }}m</span>
          </div>
          <div class="geofence-toggles">
            <label class="geofence-toggle-label">
              <input type="checkbox" :checked="gf.notify_on_enter" @change="updateGeofenceField(gf, 'notify_on_enter', $event.target.checked)" /> Enter
            </label>
            <label class="geofence-toggle-label">
              <input type="checkbox" :checked="gf.notify_on_exit" @change="updateGeofenceField(gf, 'notify_on_exit', $event.target.checked)" /> Exit
            </label>
          </div>
        </div>

        <div class="divider" v-if="geofences.length" />

        <div class="notif-category-title" style="cursor:default">
          <div class="notif-category-left">
            <MapPin :size="13" />
            <span>Add zone</span>
          </div>
        </div>
        <div class="form-group">
          <label>Name</label>
          <input v-model="newGeofence.name" type="text" placeholder="Home, Work, ..." />
        </div>
        <div style="display:flex;gap:8px;align-items:flex-end">
          <div class="form-group" style="flex:1">
            <label>Latitude</label>
            <input v-model.number="newGeofence.latitude" type="number" step="0.00001" placeholder="45.12345" />
          </div>
          <div class="form-group" style="flex:1">
            <label>Longitude</label>
            <input v-model.number="newGeofence.longitude" type="number" step="0.00001" placeholder="9.12345" />
          </div>
          <button class="locate-btn" :disabled="geolocating" @click="useCurrentLocation" title="Use current location">
            <Locate :size="15" :class="{ spinning: geolocating }" />
          </button>
        </div>
        <div class="form-group">
          <label>Radius (m)</label>
          <input v-model.number="newGeofence.radius_m" type="number" min="10" max="5000" step="10" />
        </div>
        <button class="save-btn" :disabled="notifSaving || !newGeofence.name || !newGeofence.latitude" @click="addGeofence">
          {{ notifSaving ? 'Saving…' : 'Add geofence' }}
        </button>
      </SectionCard>

      <SectionCard title="Energy & Charging Costs" :icon="Zap">
        <!-- Solar panels toggle -->
        <div class="pref-row">
          <div class="pref-info">
            <Sun :size="15" class="pref-icon" />
            <span class="pref-label">Solar panels at home</span>
            <span class="pref-hint">Track energy charged from your solar installation separately</span>
          </div>
          <ToggleSwitch :modelValue="hasSolarPanels" @update:modelValue="toggleSolarPanels" />
        </div>

        <!-- Home pricing mode selector -->
        <div class="pref-row">
          <div class="pref-info">
            <Clock :size="15" class="pref-icon" />
            <span class="pref-label">Home pricing mode</span>
          </div>
          <div class="pricing-mode-toggle">
            <button
              class="theme-btn"
              :class="{ active: homePricingMode === 'flat' }"
              @click="setHomePricingMode('flat')"
            >Flat rate</button>
            <button
              class="theme-btn"
              :class="{ active: homePricingMode === 'time_of_use' }"
              @click="setHomePricingMode('time_of_use')"
            >Time-of-use</button>
          </div>
        </div>

        <div class="divider" />

        <!-- Price Tiers -->
        <p class="rate-limit-hint" style="margin-bottom:8px"><strong>Charging price tiers</strong></p>

        <div v-for="tier in visibleTiers" :key="tier.id" class="pref-row">
          <div class="pref-info">
            <component :is="tierIcon(tier.id)" :size="15" class="pref-icon" />
            <span class="pref-label">{{ tier.label }}</span>
          </div>
          <div class="pref-input-group">
            <input
              v-model.number="tier.price_kwh"
              type="number"
              step="0.01"
              min="0"
              class="pref-input"
              :disabled="tier.id === 'home_grid' && homePricingMode === 'time_of_use'"
            />
            <span class="pref-unit">€/kWh</span>
          </div>
        </div>

        <button
          class="interval-set-btn"
          style="margin-top:8px"
          :disabled="chargingTiersSaving"
          @click="saveChargingTiers"
        >{{ chargingTiersSaving ? '…' : 'Save prices' }}</button>
        <div v-if="tiersSuccess" class="field-success">{{ tiersSuccess }}</div>
        <div v-if="tiersError" class="field-error">{{ tiersError }}</div>

        <!-- Time-of-use bands (visible only in TOU mode) -->
        <template v-if="homePricingMode === 'time_of_use'">
          <div class="divider" />
          <p class="rate-limit-hint" style="margin-bottom:8px"><strong>Time-of-use bands</strong> — Home (grid) pricing by time slot</p>

          <div v-for="(band, idx) in timeBands" :key="band.id || idx" class="time-band-row">
            <div class="band-header">
              <Clock :size="14" class="pref-icon" :style="{ color: band.color || '#888' }" />
              <input
                v-model="band.name"
                type="text"
                class="band-name-input"
                placeholder="Band name"
              />
              <input
                v-model.number="band.price_kwh"
                type="number"
                step="0.01"
                min="0"
                class="pref-input band-price-input"
              />
              <span class="pref-unit">€/kWh</span>
              <button class="icon-btn danger" @click="removeBand(idx)" title="Remove band">
                <Trash2 :size="14" />
              </button>
            </div>
            <div class="band-schedule">
              <div v-for="(slot, si) in band.schedule" :key="si" class="schedule-slot">
                <div class="days-row">
                  <button
                    v-for="(dayLabel, dayIdx) in ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']"
                    :key="dayIdx"
                    class="day-btn"
                    :class="{ active: slot.days.includes(dayIdx) }"
                    @click="toggleDay(band, si, dayIdx)"
                  >{{ dayLabel.charAt(0) }}</button>
                </div>
                <div class="time-range">
                  <input v-model.number="slot.start_hour" type="number" min="0" max="23" class="time-input" />
                  <span>:</span>
                  <input v-model.number="slot.start_min" type="number" min="0" max="59" step="15" class="time-input" />
                  <span>–</span>
                  <input v-model.number="slot.end_hour" type="number" min="0" max="24" class="time-input" />
                  <span>:</span>
                  <input v-model.number="slot.end_min" type="number" min="0" max="59" step="15" class="time-input" />
                  <button v-if="band.schedule.length > 1" class="icon-btn" @click="band.schedule.splice(si, 1)" title="Remove slot">
                    <X :size="12" />
                  </button>
                </div>
              </div>
              <button class="add-slot-btn" @click="band.schedule.push({ days: [0,1,2,3,4], start_hour: 0, start_min: 0, end_hour: 0, end_min: 0 })">
                <Plus :size="12" /> Add time slot
              </button>
            </div>
          </div>

          <button class="add-band-btn" @click="addBand">
            <Plus :size="14" /> Add band
          </button>

          <button
            class="interval-set-btn"
            style="margin-top:8px"
            :disabled="chargingTiersSaving"
            @click="saveTimeBands"
          >{{ chargingTiersSaving ? '…' : 'Save bands' }}</button>
          <div v-if="bandsSuccess" class="field-success">{{ bandsSuccess }}</div>
          <div v-if="bandsError" class="field-error">{{ bandsError }}</div>
        </template>
      </SectionCard>
    </template>

    <!-- ═══════════════ SERVICES ═══════════════ -->
    <template v-if="activeSection === 'services'">
      <SectionCard title="Data Collection" :icon="BarChart3">
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="scheduler.is_running ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ scheduler.is_running ? 'Running' : 'Stopped' }}
              <span v-if="scheduler.is_running" class="service-interval">· every {{ scheduler.interval_minutes }} min</span>
            </span>
          </div>
          <button
            class="service-btn"
            :class="scheduler.is_running ? 'btn-stop' : 'btn-start'"
            :disabled="schedulerUpdating"
            @click="toggleScheduler(!scheduler.enabled)"
          >
            {{ scheduler.is_running ? 'Stop' : 'Start' }}
          </button>
        </div>

        <div class="interval-row">
          <span class="interval-label">Collection interval</span>
          <div class="interval-control">
            <button class="interval-btn" @click="pendingInterval = Math.max(1, pendingInterval - 5)">−</button>
            <span class="interval-value">{{ pendingInterval }} min</span>
            <button class="interval-btn" @click="pendingInterval = Math.min(1440, pendingInterval + 5)">+</button>
            <button
              class="interval-set-btn"
              :disabled="pendingInterval === scheduler.interval_minutes || schedulerUpdating"
              @click="applyInterval('interval_minutes', pendingInterval)"
            >Set</button>
          </div>
        </div>

        <div class="scheduler-status">
          <div v-if="scheduler.last_run" class="status-detail">
            Last update: {{ formatTime(scheduler.last_run) }}
          </div>
          <div class="status-detail">
            Runs: {{ scheduler.total_runs }} · Errors: {{ scheduler.total_errors }}
          </div>
          <div v-if="scheduler.last_error" class="status-error">
            {{ scheduler.last_error }}
          </div>
        </div>

        <div class="divider" />

        <p class="rate-limit-hint" style="margin-bottom:8px">
          <strong>History downsampling</strong> — limits the number of data points returned when loading large date ranges in History. Keeps transition boundaries (charge start/stop) for KPI accuracy.
        </p>
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="downsamplingEnabled ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ downsamplingEnabled ? 'Enabled' : 'Disabled' }}
              <span v-if="downsamplingEnabled" class="service-interval">· max {{ downsamplingMaxPoints }} points</span>
            </span>
          </div>
          <button
            class="service-btn"
            :class="downsamplingEnabled ? 'btn-stop' : 'btn-start'"
            :disabled="downsamplingSaving"
            @click="toggleDownsampling"
          >
            {{ downsamplingEnabled ? 'Disable' : 'Enable' }}
          </button>
        </div>
        <div v-if="downsamplingEnabled" class="interval-row">
          <span class="interval-label">Max points</span>
          <div class="interval-control">
            <button class="interval-btn" @click="pendingMaxPoints = Math.max(500, pendingMaxPoints - 500)">−</button>
            <span class="interval-value">{{ pendingMaxPoints }}</span>
            <button class="interval-btn" @click="pendingMaxPoints = Math.min(10000, pendingMaxPoints + 500)">+</button>
            <button
              class="interval-set-btn"
              :disabled="pendingMaxPoints === downsamplingMaxPoints || downsamplingSaving"
              @click="saveDownsampling"
            >Set</button>
          </div>
        </div>
        <div v-if="downsamplingSuccess" class="field-success">{{ downsamplingSuccess }}</div>
        <div v-if="downsamplingError" class="field-error">{{ downsamplingError }}</div>
      </SectionCard>

      <SectionCard title="Transition Detection" :icon="Activity">
        <p class="rate-limit-hint" style="margin-bottom:10px">Fast polling (every {{ scheduler.transition_poll_interval_seconds }}s) to detect state changes like regenerative braking, charging start/stop, and driving events. Saves an event + snapshot only when a transition occurs.</p>
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="scheduler.transition_detection_enabled ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ scheduler.transition_detection_enabled ? 'Active' : 'Disabled' }}
              <span v-if="scheduler.transition_detection_enabled" class="service-interval">· poll every {{ scheduler.transition_poll_interval_seconds }}s</span>
            </span>
          </div>
          <button
            class="service-btn"
            :class="scheduler.transition_detection_enabled ? 'btn-stop' : 'btn-start'"
            :disabled="schedulerUpdating"
            @click="updateScheduler({ transition_detection_enabled: !scheduler.transition_detection_enabled })"
          >
            {{ scheduler.transition_detection_enabled ? 'Disable' : 'Enable' }}
          </button>
        </div>

        <div class="interval-row">
          <span class="interval-label">Poll interval</span>
          <div class="interval-control">
            <button class="interval-btn" @click="pendingTransitionPoll = Math.max(5, pendingTransitionPoll - 5)">−</button>
            <span class="interval-value">{{ pendingTransitionPoll }}s</span>
            <button class="interval-btn" @click="pendingTransitionPoll = Math.min(300, pendingTransitionPoll + 5)">+</button>
            <button
              class="interval-set-btn"
              :disabled="pendingTransitionPoll === scheduler.transition_poll_interval_seconds || schedulerUpdating"
              @click="updateScheduler({ transition_poll_interval_seconds: pendingTransitionPoll })"
            >Set</button>
          </div>
        </div>

        <div class="interval-row">
          <span class="interval-label">Dedup interval</span>
          <div class="interval-control">
            <button class="interval-btn" @click="pendingTransitionDedup = Math.max(1, pendingTransitionDedup - 5)">−</button>
            <span class="interval-value">{{ pendingTransitionDedup }}s</span>
            <button class="interval-btn" @click="pendingTransitionDedup = Math.min(300, pendingTransitionDedup + 5)">+</button>
            <button
              class="interval-set-btn"
              :disabled="pendingTransitionDedup === scheduler.transition_min_event_interval_seconds || schedulerUpdating"
              @click="updateScheduler({ transition_min_event_interval_seconds: pendingTransitionDedup })"
            >Set</button>
          </div>
        </div>

        <p class="rate-limit-hint" style="margin-top:8px">Monitored: regen, charging, plug, parking, lock, ignition, speed, SOC (±5%), charge state</p>
      </SectionCard>

      <SectionCard title="Live Refresh" :icon="RefreshCw">
        <p class="rate-limit-hint" style="margin-bottom:10px">Automatically push fresh vehicle data to the dashboard via WebSocket. Only active when the page is open.</p>
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="liveRefresh.is_running ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ liveRefresh.is_running ? 'Active' : 'Disabled' }}
              <span v-if="liveRefresh.is_running" class="service-interval">· every {{ formatSeconds(liveRefresh.interval_seconds) }}</span>
            </span>
          </div>
          <button
            class="service-btn"
            :class="liveRefresh.is_running ? 'btn-stop' : 'btn-start'"
            :disabled="liveRefreshUpdating"
            @click="toggleLiveRefresh"
          >
            {{ liveRefresh.is_running ? 'Disable' : 'Enable' }}
          </button>
        </div>

        <div class="interval-row">
          <span class="interval-label">Refresh interval</span>
          <div class="interval-control">
            <button class="interval-btn" @click="pendingLiveInterval = Math.max(10, pendingLiveInterval - 10)">−</button>
            <span class="interval-value">{{ formatSeconds(pendingLiveInterval) }}</span>
            <button class="interval-btn" @click="pendingLiveInterval = Math.min(600, pendingLiveInterval + 10)">+</button>
            <button
              class="interval-set-btn"
              :disabled="pendingLiveInterval === liveRefresh.interval_seconds || liveRefreshUpdating"
              @click="applyLiveInterval"
            >Set</button>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Home Assistant" :icon="Wifi">
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="mqtt.connected ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ mqtt.connected ? 'Connected' : mqtt.enabled ? 'Disconnected' : 'Disabled' }}
              <span v-if="mqtt.connected" class="service-interval">· {{ mqtt.broker }}</span>
            </span>
          </div>
          <button
            class="service-btn"
            :class="mqtt.enabled ? 'btn-stop' : 'btn-start'"
            :disabled="mqttUpdating || (!mqtt.enabled && !mqttForm.broker)"
            @click="toggleMqtt(!mqtt.enabled)"
          >
            {{ mqtt.enabled ? 'Disable' : 'Enable' }}
          </button>
        </div>

        <div class="interval-row">
          <span class="interval-label">Polling interval</span>
          <div class="interval-control">
            <button class="interval-btn" @click="pendingMqttInterval = Math.max(10, stepDown(pendingMqttInterval))">−</button>
            <span class="interval-value">{{ formatSeconds(pendingMqttInterval) }}</span>
            <button class="interval-btn" @click="pendingMqttInterval = Math.min(3600, stepUp(pendingMqttInterval))">+</button>
            <button
              class="interval-set-btn"
              :disabled="pendingMqttInterval === scheduler.mqtt_interval_seconds || schedulerUpdating"
              @click="applyMqttInterval"
            >Set</button>
          </div>
        </div>

        <button class="save-btn" style="margin-top:12px" @click="showMqttEdit = true">
          Configure MQTT
        </button>

        <div v-if="mqtt.last_error" class="status-error" style="margin-top:8px">
          {{ mqtt.last_error }}
        </div>

        <div class="form-divider" style="margin-top:14px">Vehicle Remote Control</div>
        <p class="section-desc" style="margin-bottom:0">Save the operation PIN so HA automations can execute lock, unlock, trunk, etc.</p>

        <div class="interval-row">
          <span class="interval-label">Operation PIN</span>
          <div class="interval-control">
            <div class="pin-input-wrap">
              <input
                v-model="vehiclePin"
                :type="showPin ? 'text' : 'password'"
                class="pin-input"
                placeholder="PIN"
                maxlength="8"
              />
              <button class="pin-eye-btn" tabindex="-1" @click="showPin = !showPin" :title="showPin ? 'Hide PIN' : 'Show PIN'">
                <svg v-if="!showPin" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
            <button
              v-if="vehiclePin"
              class="interval-btn" style="font-size:11px;width:auto;padding:0 6px;color:#ff5252"
              :disabled="pinSaving"
              @click="clearVehiclePin"
              title="Clear PIN"
            >✕</button>
            <button
              class="interval-set-btn"
              :disabled="pinSaving || !vehiclePin"
              @click="saveVehiclePin"
            >{{ pinSaving ? '…' : 'Set' }}</button>
          </div>
        </div>
        <div v-if="pinSuccess" class="field-success" style="margin-top:4px;text-align:right;font-size:11px">{{ pinSuccess }}</div>
        <div v-if="pinError" class="field-error" style="margin-top:4px;text-align:right;font-size:11px">{{ pinError }}</div>
      </SectionCard>

      <SectionCard title="ABRP" :icon="Navigation">
        <p class="rate-limit-hint" style="margin-bottom:10px">Send live telemetry to <a href="https://abetterrouteplanner.com" target="_blank" rel="noopener">A Better Route Planner</a> for real-time route planning.</p>
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="abrp.is_running ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ abrp.is_running ? 'Running' : abrp.enabled ? 'Stopped' : 'Disabled' }}
              <span v-if="abrp.is_running" class="service-interval">· adaptive</span>
            </span>
          </div>
          <button
            class="service-btn"
            :class="abrp.enabled ? 'btn-stop' : 'btn-start'"
            :disabled="abrpUpdating || (!abrp.enabled && !abrpForm.user_token)"
            @click="toggleAbrp(!abrp.enabled)"
          >
            {{ abrp.enabled ? 'Disable' : 'Enable' }}
          </button>
        </div>

        <div class="form-divider" style="margin-top:12px">User Token</div>
        <p class="section-desc" style="margin-bottom:8px">
          Open your vehicle settings in ABRP, click <b>Live Data</b> and copy the generic token.
        </p>

        <div class="interval-row">
          <span class="interval-label" style="margin-right:10px">Token</span>
          <div class="interval-control" style="flex:1">
            <div class="pin-input-wrap" style="flex:1">
              <input
                v-model="abrpForm.user_token"
                :type="showAbrpToken ? 'text' : 'password'"
                class="pin-input"
                style="width:100%;letter-spacing:0"
                placeholder="Paste your ABRP live data token"
              />
              <button class="pin-eye-btn" tabindex="-1" @click="showAbrpToken = !showAbrpToken" :title="showAbrpToken ? 'Hide' : 'Show'">
                <svg v-if="!showAbrpToken" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
            <button
              class="interval-set-btn"
              :disabled="abrpUpdating || !abrpForm.user_token"
              @click="saveAbrp"
            >{{ abrpUpdating ? '…' : 'Set' }}</button>
          </div>
        </div>

        <div v-if="abrpSuccess" class="field-success" style="margin-top:6px;text-align:right;font-size:11px">{{ abrpSuccess }}</div>
        <div v-if="abrp.last_error" class="status-error" style="margin-top:6px">{{ abrp.last_error }}</div>

        <div class="scheduler-status" v-if="abrp.total_sends || abrp.total_errors">
          <div class="status-detail">
            Sends: {{ abrp.total_sends }} · Errors: {{ abrp.total_errors }}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Telegram Bot" :icon="Send">
        <p class="rate-limit-hint" style="margin-bottom:12px">Connect a Telegram bot to receive notifications and interact with your vehicle remotely.</p>

        <div class="form-divider">Connection</div>
        <div class="form-group" style="margin-top:8px">
          <label>Bot Token</label>
          <div class="secret-input-wrap">
            <input
              v-model="telegramForm.bot_token"
              :type="showTelegramSecrets ? 'text' : 'password'"
              placeholder="123456:ABC-DEF..."
            />
            <button class="secret-toggle-btn" type="button" @click="showTelegramSecrets = !showTelegramSecrets" tabindex="-1">
              <component :is="showTelegramSecrets ? EyeOff : Eye" :size="14" />
            </button>
          </div>
        </div>
        <div class="form-group">
          <label>Chat ID</label>
          <div class="secret-input-wrap">
            <input
              v-model="telegramForm.chat_id"
              :type="showTelegramSecrets ? 'text' : 'password'"
              placeholder="-100123456789"
            />
          </div>
        </div>
        <div class="channel-actions">
          <button class="save-btn" :disabled="notifSaving || !telegramForm.bot_token || !telegramForm.chat_id" @click="saveTelegramChannel">
            {{ notifSaving ? 'Saving…' : telegramChannel ? 'Save' : 'Configure' }}
          </button>
          <button v-if="telegramChannel" class="service-btn btn-start" :disabled="notifTesting" @click="testTelegram" style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap">
            <Bell :size="13" style="flex-shrink:0" /> {{ notifTesting ? 'Sending…' : 'Test' }}
          </button>
        </div>
        <div v-if="notifTestResult" :class="notifTestResult.success ? 'field-success' : 'field-error'" style="margin-top:6px">
          {{ notifTestResult.message }}
        </div>

        <div class="form-divider" style="margin-top:16px">Bot Commands</div>
        <p class="rate-limit-hint" style="margin-bottom:8px">
          Enable commands to control and query the vehicle directly from Telegram (/status, /lock, /track, etc.).
        </p>
        <div class="scheduler-service">
          <div class="service-status">
            <span class="status-dot" :class="telegramBotActive ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ !telegramChannel ? 'Not configured' : telegramBotActive ? 'Active' : 'Disabled' }}
            </span>
          </div>
          <button
            v-if="telegramChannel"
            class="service-btn"
            :class="telegramBotActive ? 'btn-stop' : 'btn-start'"
            :disabled="botToggling"
            @click="toggleTelegramBot(!telegramBotActive)"
          >
            {{ telegramBotActive ? 'Disable' : 'Enable' }}
          </button>
        </div>

        <div class="form-divider" style="margin-top:16px">Linked Users</div>
        <p class="rate-limit-hint" style="margin-bottom:8px">
          Manage who can interact with the bot. Generate a link for instant access, or approve pending requests.
        </p>

        <!-- Generate link button -->
        <div class="channel-actions" style="margin-bottom:12px">
          <button
            class="service-btn btn-start"
            :disabled="!telegramChannel || linkTokenLoading"
            @click="generateLinkToken"
            style="display:inline-flex;align-items:center;gap:4px"
          >
            <Link2 :size="13" style="flex-shrink:0" />
            {{ linkTokenLoading ? 'Generating…' : 'Generate Link' }}
          </button>
        </div>

        <!-- Generated link display -->
        <div v-if="linkTokenData" class="link-token-card">
          <div class="link-token-url">
            <input type="text" :value="linkTokenData.link" readonly class="link-input" />
            <button class="secret-toggle-btn" @click="copyLink" title="Copy link">
              <component :is="linkCopied ? Check : Copy" :size="14" />
            </button>
          </div>
          <p class="rate-limit-hint" style="margin-top:4px">
            Expires at {{ new Date(linkTokenData.expires_at).toLocaleTimeString() }}. Single use only.
          </p>
        </div>

        <!-- Users list -->
        <div v-if="telegramUsers.length" class="telegram-users-list">
          <div
            v-for="user in telegramUsers"
            :key="user.chat_id"
            class="telegram-user-row"
          >
            <div class="telegram-user-info">
              <span class="telegram-user-name">
                {{ user.first_name || '' }} {{ user.last_name || '' }}
                <span v-if="user.username" class="telegram-user-handle">@{{ user.username }}</span>
              </span>
              <span class="telegram-user-status" :class="'status-' + user.status">
                {{ user.status }}
              </span>
            </div>
            <div class="telegram-user-actions">
              <button
                v-if="user.status === 'pending'"
                class="service-btn btn-start btn-sm"
                @click="approveTelegramUser(user.chat_id)"
              >Approve</button>
              <button
                v-if="user.status === 'pending'"
                class="service-btn btn-stop btn-sm"
                @click="rejectTelegramUser(user.chat_id)"
              >Reject</button>
              <button
                v-if="user.status !== 'pending'"
                class="service-btn btn-stop btn-sm"
                @click="removeTelegramUser(user.chat_id)"
              >Remove</button>
            </div>
          </div>
        </div>
        <p v-else-if="telegramChannel" class="rate-limit-hint" style="margin-top:8px;opacity:0.6">
          No linked users yet. Generate a link or wait for /start requests.
        </p>

        <ConfirmDialog
          :visible="showRemoveConfirm"
          title="Remove user"
          message="This user will lose access to the bot and will need to be re-approved."
          confirm-label="Remove"
          cancel-label="Cancel"
          variant="danger"
          icon="trash"
          @confirm="confirmRemoveUser"
          @cancel="cancelRemoveUser"
        />
      </SectionCard>
    </template>

    <!-- ═══════════════ NOTIFICATIONS ═══════════════ -->
    <template v-if="activeSection === 'notifications'">
      <SectionCard title="Channels" :icon="Send">
        <p class="rate-limit-hint" style="margin-bottom:12px">
          Notification channels deliver vehicle alerts. Configure credentials in <b>Services → Telegram Bot</b>.
        </p>

        <!-- Telegram channel -->
        <div class="channel-card">
          <div class="channel-header">
            <div class="channel-info">
              <Send :size="14" class="channel-icon" />
              <span class="channel-name">Telegram</span>
              <span v-if="telegramChannel" class="channel-badge" :class="telegramChannel.enabled ? 'active' : 'inactive'">
                {{ telegramChannel.enabled ? 'Active' : 'Disabled' }}
              </span>
              <span v-else class="channel-badge inactive">Not configured</span>
            </div>
            <div class="channel-controls">
              <button v-if="telegramChannel" class="service-btn btn-start" :disabled="notifTesting" @click="testTelegram" style="font-size:11px;display:inline-flex;align-items:center;gap:4px;white-space:nowrap">
                <Bell :size="12" style="flex-shrink:0" /> {{ notifTesting ? '…' : 'Test' }}
              </button>
              <ToggleSwitch
                v-if="telegramChannel"
                :modelValue="telegramChannel.enabled"
                @update:modelValue="toggleTelegramEnabled"
              />
            </div>
          </div>
          <div v-if="notifTestResult" :class="notifTestResult.success ? 'field-success' : 'field-error'" style="margin-top:6px;padding-left:28px">
            {{ notifTestResult.message }}
          </div>
        </div>

        <div v-if="notifError" class="field-error" style="margin-top:6px">{{ notifError }}</div>

        <!-- Cooldown setting -->
        <div class="channel-cooldown">
          <div class="interval-row">
            <div>
              <span class="interval-label">Notification cooldown</span>
              <p class="cooldown-desc">Time to suppress repeated notifications for the same event. Set to 0 to disable.</p>
            </div>
            <div class="interval-control">
              <input
                type="number"
                class="pref-input"
                :min="0"
                :max="86400"
                v-model.number="cooldownSeconds"
                style="width:70px"
              />
              <span class="pref-unit">sec</span>
              <button class="save-btn save-btn-sm" @click="saveCooldown">Set</button>
            </div>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Events" :icon="Activity">
        <p class="rate-limit-hint" style="margin-bottom:12px">
          Select which events you want to receive as notifications.
        </p>

        <!-- Search filter -->
        <div class="event-search-wrap">
          <Search :size="14" class="event-search-icon" />
          <input v-model="eventSearch" type="text" class="event-search-input" placeholder="Search events..." />
          <button v-if="eventSearch" class="event-search-clear" @click="eventSearch = ''">
            <X :size="12" />
          </button>
        </div>

        <div v-for="category in eventCategories" :key="category.key" class="notif-category" v-show="filteredEventsByCategory[category.key].length">
          <div class="notif-category-title" @click="toggleCategory(category.key)" style="cursor:pointer">
            <div class="notif-category-left">
              <component :is="collapsedCategories.has(category.key) ? ChevronRight : ChevronDown" :size="13" />
              <component :is="categoryIcons[category.key]" :size="13" />
              <span>{{ category.label }}</span>
            </div>
            <span class="notif-category-count">{{ filteredEventsByCategory[category.key].filter(e => e.enabled).length }}/{{ filteredEventsByCategory[category.key].length }}</span>
          </div>
          <template v-if="!collapsedCategories.has(category.key)">
            <template v-for="evt in filteredEventsByCategory[category.key]" :key="evt.event_type">
              <div class="notif-event-row">
                <div class="notif-event-info">
                  <span class="notif-event-label">{{ evt.label }}</span>
                  <span class="notif-event-desc">{{ evt.description }}</span>
                </div>
                <div class="notif-event-actions">
                  <button
                    class="event-test-btn"
                    :disabled="testingEvent === evt.event_type || !telegramChannel"
                    @click="testEvent(evt)"
                    title="Send test notification"
                  >
                    <Bell :size="12" :class="{ spinning: testingEvent === evt.event_type }" />
                  </button>
                  <ToggleSwitch :modelValue="evt.enabled" @update:modelValue="toggleEvent(evt, $event)" />
                </div>
              </div>
              <!-- Event options shown directly under each event -->
              <div v-if="evt.enabled && (evt.configurable || evt.has_image)" class="notif-event-config">
                <div v-if="evt.has_image" class="interval-row" style="margin-top:4px">
                  <span class="interval-label">Dynamic image</span>
                  <div class="interval-control">
                    <ToggleSwitch
                      :modelValue="getEventImageEnabled(evt)"
                      @update:modelValue="setEventImageEnabled(evt, $event)"
                    />
                  </div>
                </div>
                <div v-for="(schema, paramKey) in evt.config_schema" :key="paramKey" class="interval-row" style="margin-top:4px">
                  <span class="interval-label">{{ schema.label || paramKey }}</span>
                  <div class="interval-control">
                    <input
                      type="number"
                      class="pref-input"
                      :min="schema.min"
                      :max="schema.max"
                      :value="getEventConfigValue(evt, paramKey, schema.default)"
                      @change="setEventConfigValue(evt, paramKey, $event.target.value)"
                      style="width:60px"
                    />
                    <span class="pref-unit">{{ schema.unit }}</span>
                  </div>
                </div>
              </div>
            </template>
          </template>
        </div>

        <div v-if="eventSearch && eventCategories.every(c => !filteredEventsByCategory[c.key].length)" class="rate-limit-hint" style="text-align:center;padding:16px 0">
          No events matching "{{ eventSearch }}"
        </div>

        <button class="save-btn" style="margin-top:12px" :disabled="notifSaving" @click="saveEventPreferences">
          {{ notifSaving ? 'Saving…' : 'Save preferences' }}
        </button>
        <div v-if="eventsSuccess" class="field-success" style="margin-top:6px">{{ eventsSuccess }}</div>
      </SectionCard>

      <SectionCard title="Location Tracking" :icon="Locate">
        <p class="rate-limit-hint" style="margin-bottom:12px">
          Send periodic location updates via Telegram. Useful for anti-theft monitoring.
        </p>

        <div class="tracking-status">
          <div class="service-status">
            <span class="status-dot" :class="tracking.active ? 'running' : 'stopped'" />
            <span class="service-text">
              {{ tracking.active ? `Active · every ${tracking.interval_seconds}s` : 'Stopped' }}
            </span>
          </div>
        </div>

        <div class="interval-row" style="margin-top:12px">
          <span class="interval-label">Interval</span>
          <div class="interval-control">
            <input
              type="number"
              class="pref-input"
              :min="10"
              :max="3600"
              v-model.number="trackingInterval"
              style="width:70px"
            />
            <span class="pref-unit">sec</span>
          </div>
        </div>

        <div class="channel-actions" style="margin-top:12px">
          <button v-if="!tracking.active" class="save-btn" :disabled="!telegramChannel || trackingLoading" @click="startTracking">
            {{ trackingLoading ? 'Starting…' : 'Start Tracking' }}
          </button>
          <button v-else class="service-btn btn-stop" :disabled="trackingLoading" @click="stopTracking">
            {{ trackingLoading ? 'Stopping…' : 'Stop Tracking' }}
          </button>
        </div>
      </SectionCard>

    </template>

    <!-- ═══════════════ ADVANCED ═══════════════ -->
    <template v-if="activeSection === 'advanced'">
      <SectionCard title="Log Levels" :icon="SlidersHorizontal">
        <p class="section-desc">Set the logging verbosity for the app and the leapmotor-api library independently.</p>
        <div class="interval-row">
          <span class="interval-label">LeapConnect App</span>
          <div class="interval-control">
            <select v-model="logLevels.app_level" class="log-level-select" @change="saveLogLevels">
              <option v-for="l in logLevelOptions" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>
        </div>
        <div class="interval-row">
          <span class="interval-label">leapmotor-api</span>
          <div class="interval-control">
            <select v-model="logLevels.library_level" class="log-level-select" @change="saveLogLevels">
              <option v-for="l in logLevelOptions" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>
        </div>
        <div v-if="logLevelSuccess" class="field-success">{{ logLevelSuccess }}</div>
      </SectionCard>

      <SectionCard title="Application Logs" :icon="Terminal">
        <p class="section-desc">Live console output for troubleshooting. Entries stream in real-time via WebSocket.</p>
        <div class="notif-row">
          <span class="notif-label">Enable live log viewer</span>
          <ToggleSwitch v-model="liveLogsEnabled" />
        </div>
      </SectionCard>
      <LogViewer v-if="liveLogsEnabled" />

      <SectionCard title="Debug" :icon="Code">
        <p class="section-desc">Inspect raw JSON data returned by the Leapmotor API for troubleshooting.</p>
        <button class="save-btn" style="margin-top:4px" @click="showRaw = true">
          Show Raw JSON
        </button>
      </SectionCard>
    </template>

    <!-- ═══════════════ ABOUT ═══════════════ -->
    <template v-if="activeSection === 'about'">
      <SectionCard title="About LeapConnect" :icon="Info">
        <div class="about-header">
          <div class="about-logo">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="#00d4ff" stroke-width="2">
              <path d="M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v9a2 2 0 01-2 2h-2" />
              <circle cx="9" cy="17" r="2" /><circle cx="17" cy="17" r="2" />
            </svg>
          </div>
          <div>
            <div class="about-app-name">LeapConnect</div>
            <div class="about-version">{{ appVersion ? `v${appVersion}` : '—' }}</div>
          </div>
        </div>
        <p class="about-desc">
          Open-source web dashboard for monitoring and controlling Leapmotor vehicles.
          Built on top of the <a href="https://github.com/markoceri/leapmotor-api" target="_blank" rel="noopener">leapmotor-api</a> Python client.
        </p>
      </SectionCard>

      <SectionCard title="GitHub" :icon="Github">
        <div class="about-links">
          <a href="https://github.com/markoceri/leapconnect" target="_blank" rel="noopener" class="about-link-card">
            <Github :size="18" />
            <div>
              <div class="about-link-title">Source Code</div>
              <div class="about-link-hint">markoceri/leapconnect</div>
            </div>
            <ExternalLink :size="14" class="about-link-arrow" />
          </a>
          <a href="https://github.com/markoceri/leapconnect/stargazers" target="_blank" rel="noopener" class="about-link-card star">
            <Star :size="18" />
            <div>
              <div class="about-link-title">Star the project</div>
              <div class="about-link-hint">If you find LeapConnect useful, a star helps the project grow!</div>
            </div>
            <ExternalLink :size="14" class="about-link-arrow" />
          </a>
          <a href="https://github.com/markoceri/leapconnect/issues" target="_blank" rel="noopener" class="about-link-card">
            <AlertTriangle :size="18" />
            <div>
              <div class="about-link-title">Report an Issue</div>
              <div class="about-link-hint">Found a bug or have a suggestion? Open an issue on GitHub.</div>
            </div>
            <ExternalLink :size="14" class="about-link-arrow" />
          </a>
        </div>
      </SectionCard>

      <SectionCard title="Disclaimer" :icon="AlertTriangle">
        <div class="about-disclaimer">
          <p><strong>This is NOT an official Leapmotor product.</strong></p>
          <p>
            LeapConnect is an independent, community-driven project with no affiliation to
            Leapmotor International or its subsidiaries. It interacts with Leapmotor's cloud
            services through unofficial, reverse-engineered APIs.
          </p>
          <p>
            By using this software you acknowledge that:
          </p>
          <ul>
            <li>You use LeapConnect <strong>entirely at your own risk</strong>.</li>
            <li>The author(s) accept <strong>no responsibility</strong> for any consequences, including but not limited to account suspension or ban by Leapmotor.</li>
            <li>Vehicle commands are sent over unofficial channels — <strong>use remote controls with caution</strong>.</li>
            <li>The project may stop working at any time if Leapmotor changes its APIs.</li>
          </ul>
        </div>
      </SectionCard>
    </template>

    <!-- ═══════════════ MODALS (always rendered) ═══════════════ -->

    <!-- Leapmotor Credentials Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showLeapmotorEdit" class="mqtt-overlay" @click.self="closeLeapmotorModal">
          <div class="mqtt-modal">
            <div class="mqtt-modal-header">
              <KeyRound :size="16" style="color:#00d4ff" />
              <span class="mqtt-modal-title">Leapmotor Credentials</span>
              <button class="mqtt-modal-close" @click="closeLeapmotorModal">&times;</button>
            </div>
            <div class="mqtt-modal-body">
              <div class="form-group">
                <label>Leapmotor Email</label>
                <input v-model="accountForm.username" type="email" placeholder="your@email.com" />
              </div>
              <div class="form-group">
                <label>Leapmotor Password</label>
                <input v-model="accountForm.password" type="password" placeholder="Leapmotor account password" />
              </div>
              <div v-if="accountError" class="field-error" style="margin-bottom:8px">{{ accountError }}</div>
              <div v-if="accountSuccess" class="field-success" style="margin-bottom:8px">{{ accountSuccess }}</div>
            </div>
            <div class="mqtt-modal-footer">
              <button class="test-btn" @click="closeLeapmotorModal">Cancel</button>
              <button class="save-btn" :disabled="testingLeapmotor || accountSaving" @click="testLeapmotorConnection">
                {{ testingLeapmotor ? 'Testing…' : 'Test Connection' }}
              </button>
              <button class="save-btn" :disabled="accountSaving || testingLeapmotor" @click="saveLeapmotorAccount">
                {{ accountSaving ? 'Saving…' : 'Save & Reconnect' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Certificates Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showCertEdit" class="mqtt-overlay" @click.self="closeCertModal">
          <div class="mqtt-modal">
            <div class="mqtt-modal-header">
              <ShieldCheck :size="16" style="color:#00d4ff" />
              <span class="mqtt-modal-title">Update Certificates</span>
              <button class="mqtt-modal-close" @click="closeCertModal">&times;</button>
            </div>
            <div class="mqtt-modal-body">
              <div class="form-group">
                <label>App Certificate (.crt / .pem)</label>
                <div class="file-upload" :class="{ filled: certFile }" @click="$refs.certInput.click()">
                  <span>{{ certFile ? certFile.name : 'Choose file…' }}</span>
                </div>
                <input ref="certInput" type="file" accept=".crt,.pem,.cer" hidden @change="e => certFile = e.target.files[0]" />
              </div>
              <div class="form-group">
                <label>Private Key (.key / .pem)</label>
                <div class="file-upload" :class="{ filled: keyFile }" @click="$refs.keyInput.click()">
                  <span>{{ keyFile ? keyFile.name : 'Choose file…' }}</span>
                </div>
                <input ref="keyInput" type="file" accept=".key,.pem" hidden @change="e => keyFile = e.target.files[0]" />
              </div>
              <div v-if="certError" class="field-error" style="margin-bottom:8px">{{ certError }}</div>
              <div v-if="certSuccess" class="field-success" style="margin-bottom:8px">{{ certSuccess }}</div>
            </div>
            <div class="mqtt-modal-footer">
              <button class="test-btn" @click="closeCertModal">Cancel</button>
              <button class="save-btn" :disabled="certSaving || !certFile || !keyFile" @click="saveCertificates">
                {{ certSaving ? 'Uploading…' : 'Upload Certificates' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- MQTT Config Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showMqttEdit" class="mqtt-overlay" @click.self="closeMqttModal">
          <div class="mqtt-modal">
            <div class="mqtt-modal-header">
              <Wifi :size="16" style="color:#00d4ff" />
              <span class="mqtt-modal-title">MQTT Configuration</span>
              <button class="mqtt-modal-close" @click="closeMqttModal">&times;</button>
            </div>
            <div class="mqtt-modal-body">
              <div class="form-group">
                <label>MQTT Broker Host</label>
                <input v-model="mqttForm.broker" type="text" placeholder="192.168.1.x or hostname" />
              </div>
              <div class="form-group">
                <label>Port</label>
                <input v-model.number="mqttForm.port" type="number" placeholder="1883" />
              </div>
              <div class="form-group">
                <label>Username</label>
                <input v-model="mqttForm.username" type="text" placeholder="MQTT username (optional)" />
              </div>
              <div class="form-group">
                <label>Password</label>
                <input v-model="mqttForm.password" type="password" placeholder="MQTT password (optional)" />
              </div>
              <div class="notif-row" style="margin:8px 0 12px">
                <span class="notif-label">Use TLS</span>
                <ToggleSwitch v-model="mqttForm.use_tls" />
              </div>
              <div class="form-group">
                <label>Discovery Prefix</label>
                <input v-model="mqttForm.discovery_prefix" type="text" placeholder="homeassistant" />
              </div>
              <div class="form-group">
                <label>Topic Prefix</label>
                <input v-model="mqttForm.topic_prefix" type="text" placeholder="leapconnect" />
              </div>

              <div v-if="mqttTestResult" :class="mqttTestResult.ok ? 'field-success' : 'field-error'" style="margin-bottom:8px">
                {{ mqttTestResult.message }}
              </div>
              <div v-if="mqttError" class="field-error" style="margin-bottom:8px">{{ mqttError }}</div>
              <div v-if="mqttSuccess" class="field-success" style="margin-bottom:8px">{{ mqttSuccess }}</div>
            </div>
            <div class="mqtt-modal-footer">
              <button class="test-btn" :disabled="mqttTesting || !mqttForm.broker" @click="testMqtt">
                {{ mqttTesting ? 'Testing…' : 'Test Connection' }}
              </button>
              <button class="save-btn" :disabled="mqttUpdating || !mqttForm.broker" @click="saveMqtt">
                {{ mqttUpdating ? 'Saving…' : 'Save & Connect' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Debug Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showRaw" class="mqtt-overlay" @click.self="showRaw = false">
          <div class="mqtt-modal" style="max-width:560px">
            <div class="mqtt-modal-header">
              <Code :size="16" style="color:#00d4ff" />
              <span class="mqtt-modal-title">Raw JSON Data</span>
              <button class="mqtt-modal-close" @click="showRaw = false">&times;</button>
            </div>
            <div class="mqtt-modal-body" style="padding:0">
              <div class="raw-tabs">
                <button class="raw-tab" :class="{ active: rawTab === 'vehicle' }" @click="rawTab = 'vehicle'">Vehicle</button>
                <button class="raw-tab" :class="{ active: rawTab === 'status' }" @click="rawTab = 'status'">Status</button>
                <button class="raw-tab" :class="{ active: rawTab === 'lastCmd' }" @click="rawTab = 'lastCmd'">Commands</button>
              </div>
              <div class="raw-panel">
                <pre v-if="rawTab === 'vehicle'">{{ JSON.stringify(rawData?.vehicle_raw, null, 2) }}</pre>
                <pre v-else-if="rawTab === 'status'">{{ JSON.stringify(rawData?.status_raw, null, 2) }}</pre>
                <pre v-else>{{ store.commandHistory.length ? JSON.stringify(store.commandHistory, null, 2) : 'No commands executed yet.' }}</pre>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import SectionCard from '../components/SectionCard.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import InfoRow from '../components/InfoRow.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import LogViewer from '../components/LogViewer.vue'
import { api } from '../composables/useApi'
import { useAppStore } from '../stores/appStore'
import { User, Car, Bell, SlidersHorizontal, BarChart3, Code, KeyRound, ShieldCheck, Wifi, Wrench, Settings, Github, Info, Star, AlertTriangle, ExternalLink, Moon, Sun, RefreshCw, Terminal, Navigation, Activity, Eye, EyeOff, Send, ChevronDown, ChevronRight, Search, MapPin, Locate, Zap, CarFront, Lock, X, Trash2, Link2, Copy, Check, Home, Plug, Clock, Plus, Database } from 'lucide-vue-next'

const store = useAppStore()

const sections = [
  { key: 'account', label: 'Account', icon: User },
  { key: 'general', label: 'General', icon: SlidersHorizontal },
  { key: 'services', label: 'Services', icon: Wrench },
  { key: 'notifications', label: 'Notifications', icon: Bell },
  { key: 'advanced', label: 'Advanced', icon: Code },
  { key: 'about', label: 'About', icon: Info },
]
const activeSection = ref('account')

const props = defineProps({
  vehicle: { type: Object, required: true },
  rawData: { type: Object, default: () => ({}) },
})

const showRaw = ref(false)
const rawTab = ref('vehicle')

// LeapConnect user edit
const showUserEdit = ref(false)
const userSaving = ref(false)
const userError = ref('')
const userSuccess = ref('')
const userForm = reactive({ display_name: '', password: '', current_password: '' })
const displayName = ref('User')
const appVersion = ref('')

// Leapmotor credentials edit
const showLeapmotorEdit = ref(false)
const accountSaving = ref(false)
const testingLeapmotor = ref(false)
const accountError = ref('')
const accountSuccess = ref('')
const leapmotorEmail = ref('—')
const accountForm = reactive({ username: '', password: '' })

function closeLeapmotorModal() {
  showLeapmotorEdit.value = false
  accountError.value = ''
  accountSuccess.value = ''
}

// Certificates edit
const showCertEdit = ref(false)
const certSaving = ref(false)
const certError = ref('')
const certSuccess = ref('')
const certFile = ref(null)
const keyFile = ref(null)
const certsStatus = reactive({ cert_exists: false, key_exists: false })
const certDownloading = ref(false)
const certDownloadError = ref('')
const certDownloadSuccess = ref('')

function closeCertModal() {
  showCertEdit.value = false
  certError.value = ''
  certSuccess.value = ''
}

const initials = computed(() => {
  const n = displayName.value
  return n.substring(0, 2).toUpperCase()
})

// -- Scheduler state --------------------------------------------------------
const scheduler = reactive({
  enabled: false,
  interval_minutes: 15,
  mqtt_interval_seconds: 60,
  rate_limit_seconds: 10,
  transition_detection_enabled: true,
  transition_poll_interval_seconds: 10,
  transition_min_event_interval_seconds: 10,
  is_running: false,
  last_run: null,
  last_error: null,
  total_runs: 0,
  total_errors: 0,
})

const pendingInterval = ref(15)
const pendingMqttInterval = ref(60)
const pendingRateLimit = ref(10)
const pendingTransitionPoll = ref(10)
const pendingTransitionDedup = ref(10)
const schedulerUpdating = ref(false)

// -- Database Size -----------------------------------------------------------
const databaseSize = reactive({
  size_human: '...',
  loading: false,
  error: '',
})

async function loadDatabaseSize() {
  databaseSize.loading = true
  databaseSize.error = ''
  try {
    const data = await api('GET', '/api/system/database-size')
    databaseSize.size_human = data.size_human
  } catch (e) {
    databaseSize.error = e.message || 'Failed to load database size'
    databaseSize.size_human = 'unknown'
  } finally {
    databaseSize.loading = false
  }
}

async function loadScheduler() {
  try {
    const data = await api('GET', '/api/scheduler')
    Object.assign(scheduler, data)
    pendingInterval.value = data.interval_minutes
    pendingMqttInterval.value = data.mqtt_interval_seconds
    pendingRateLimit.value = data.rate_limit_seconds ?? 10
    pendingTransitionPoll.value = data.transition_poll_interval_seconds ?? 10
    pendingTransitionDedup.value = data.transition_min_event_interval_seconds ?? 10
  } catch {
    // scheduler not available yet
  }
}

async function updateScheduler(patch) {
  if (schedulerUpdating.value) return
  schedulerUpdating.value = true
  try {
    const data = await api('PUT', '/api/scheduler', patch)
    Object.assign(scheduler, data)
    pendingInterval.value = data.interval_minutes
    pendingMqttInterval.value = data.mqtt_interval_seconds
    pendingRateLimit.value = data.rate_limit_seconds ?? 10
    pendingTransitionPoll.value = data.transition_poll_interval_seconds ?? 10
    pendingTransitionDedup.value = data.transition_min_event_interval_seconds ?? 10
  } catch {
    await loadScheduler()
  } finally {
    schedulerUpdating.value = false
  }
}

function toggleScheduler(val) {
  updateScheduler({ enabled: val })
}

function applyInterval(key, value) {
  if (value !== scheduler[key]) {
    updateScheduler({ [key]: value })
  }
}

function applyMqttInterval() {
  if (pendingMqttInterval.value !== scheduler.mqtt_interval_seconds) {
    updateScheduler({ mqtt_interval_seconds: pendingMqttInterval.value })
  }
}

function applyRateLimit() {
  if (pendingRateLimit.value !== scheduler.rate_limit_seconds) {
    updateScheduler({ rate_limit_seconds: pendingRateLimit.value })
  }
}

// -- Live Refresh state -----------------------------------------------------
const liveRefresh = reactive({
  interval_seconds: 0,
  is_running: false,
})
const pendingLiveInterval = ref(30)
const liveRefreshUpdating = ref(false)

async function loadLiveRefresh() {
  try {
    const data = await api('GET', '/api/live-refresh')
    Object.assign(liveRefresh, data)
    pendingLiveInterval.value = data.interval_seconds || 30
  } catch { /* ignore */ }
}

async function toggleLiveRefresh() {
  liveRefreshUpdating.value = true
  try {
    const newInterval = liveRefresh.is_running ? 0 : (pendingLiveInterval.value || 30)
    const data = await api('PUT', '/api/live-refresh', { interval_seconds: newInterval })
    Object.assign(liveRefresh, data)
    if (data.interval_seconds > 0) pendingLiveInterval.value = data.interval_seconds
  } catch { /* ignore */ }
  finally { liveRefreshUpdating.value = false }
}

async function applyLiveInterval() {
  if (pendingLiveInterval.value === liveRefresh.interval_seconds) return
  liveRefreshUpdating.value = true
  try {
    const data = await api('PUT', '/api/live-refresh', { interval_seconds: pendingLiveInterval.value })
    Object.assign(liveRefresh, data)
    pendingLiveInterval.value = data.interval_seconds
  } catch { /* ignore */ }
  finally { liveRefreshUpdating.value = false }
}

function formatSeconds(s) {
  if (s < 60) return `${s} sec`
  const m = Math.round(s / 60)
  return `${m} min`
}

function stepUp(val) {
  if (val < 60) return val + 10
  return val + 60
}

function stepDown(val) {
  if (val <= 60) return val - 10
  return val - 60
}

// -- MQTT / Home Assistant state --------------------------------------------
const mqtt = reactive({
  enabled: false,
  connected: false,
  broker: '',
  port: 1883,
  username: '',
  use_tls: false,
  discovery_prefix: 'homeassistant',
  topic_prefix: 'leapconnect',
  last_error: null,
})

const showMqttEdit = ref(false)
const mqttUpdating = ref(false)
const mqttTesting = ref(false)
const mqttError = ref('')
const mqttSuccess = ref('')
const mqttTestResult = ref(null)

function closeMqttModal() {
  showMqttEdit.value = false
  mqttError.value = ''
  mqttSuccess.value = ''
  mqttTestResult.value = null
}
const mqttForm = reactive({
  broker: '',
  port: 1883,
  username: '',
  password: '',
  use_tls: false,
  discovery_prefix: 'homeassistant',
  topic_prefix: 'leapconnect',
})

async function loadMqtt() {
  try {
    const data = await api('GET', '/api/mqtt')
    Object.assign(mqtt, data)
    mqttForm.broker = data.broker || ''
    mqttForm.port = data.port || 1883
    mqttForm.username = data.username || ''
    mqttForm.password = ''
    mqttForm.use_tls = data.use_tls || false
    mqttForm.discovery_prefix = data.discovery_prefix || 'homeassistant'
    mqttForm.topic_prefix = data.topic_prefix || 'leapconnect'
  } catch { /* ignore */ }
}

async function toggleMqtt(val) {
  mqttUpdating.value = true
  mqttError.value = ''
  try {
    const payload = { enabled: val }
    if (val && mqttForm.broker) {
      Object.assign(payload, {
        broker: mqttForm.broker,
        port: mqttForm.port,
        username: mqttForm.username,
        password: mqttForm.password || undefined,
        use_tls: mqttForm.use_tls,
        discovery_prefix: mqttForm.discovery_prefix,
        topic_prefix: mqttForm.topic_prefix,
      })
    }
    const data = await api('PUT', '/api/mqtt', payload)
    Object.assign(mqtt, data)
  } catch (err) {
    mqttError.value = err.message
  } finally {
    mqttUpdating.value = false
  }
}

async function saveMqtt() {
  mqttError.value = ''
  mqttSuccess.value = ''
  mqttUpdating.value = true
  try {
    const data = await api('PUT', '/api/mqtt', {
      enabled: true,
      broker: mqttForm.broker,
      port: mqttForm.port,
      username: mqttForm.username,
      password: mqttForm.password || undefined,
      use_tls: mqttForm.use_tls,
      discovery_prefix: mqttForm.discovery_prefix,
      topic_prefix: mqttForm.topic_prefix,
    })
    Object.assign(mqtt, data)
    mqttSuccess.value = 'Settings saved. Connecting…'
    setTimeout(() => { mqttSuccess.value = '' }, 4000)
  } catch (err) {
    mqttError.value = err.message
  } finally {
    mqttUpdating.value = false
  }
}

async function testMqtt() {
  mqttTesting.value = true
  mqttTestResult.value = null
  try {
    const data = await api('POST', '/api/mqtt/test', {
      broker: mqttForm.broker,
      port: mqttForm.port,
      username: mqttForm.username,
      password: mqttForm.password,
      use_tls: mqttForm.use_tls,
    })
    mqttTestResult.value = {
      ok: data.status === 'ok',
      message: data.message,
    }
  } catch (err) {
    mqttTestResult.value = { ok: false, message: err.message }
  } finally {
    mqttTesting.value = false
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// -- ABRP state -------------------------------------------------------------
const abrp = reactive({
  enabled: false,
  user_token: '',
  is_running: false,
  last_error: null,
  total_sends: 0,
  total_errors: 0,
})

const abrpForm = reactive({ user_token: '' })
const showAbrpToken = ref(false)
const abrpUpdating = ref(false)
const abrpSuccess = ref('')

async function loadAbrp() {
  try {
    const data = await api('GET', '/api/abrp')
    Object.assign(abrp, data)
    abrpForm.user_token = data.user_token || ''
  } catch { /* ignore */ }
}

async function toggleAbrp(val) {
  abrpUpdating.value = true
  abrpSuccess.value = ''
  try {
    const payload = { enabled: val }
    if (val) {
      payload.user_token = abrpForm.user_token
    }
    const data = await api('PUT', '/api/abrp', payload)
    Object.assign(abrp, data)
  } catch { /* ignore */ }
  finally { abrpUpdating.value = false }
}

async function saveAbrp() {
  abrpUpdating.value = true
  abrpSuccess.value = ''
  try {
    const data = await api('PUT', '/api/abrp', {
      enabled: abrp.enabled,
      user_token: abrpForm.user_token,
    })
    Object.assign(abrp, data)
    abrpSuccess.value = 'Credentials saved'
    setTimeout(() => { abrpSuccess.value = '' }, 4000)
  } catch { /* ignore */ }
  finally { abrpUpdating.value = false }
}

async function loadAccount() {
  try {
    const data = await api('GET', '/api/status')
    if (data.leapmotor_email) {
      leapmotorEmail.value = data.leapmotor_email
      accountForm.username = data.leapmotor_email
    }
    if (data.display_name) {
      displayName.value = data.display_name
      userForm.display_name = data.display_name
    }
    if (data.app_version) {
      appVersion.value = data.app_version
    }
  } catch { /* ignore */ }
}

async function loadCertsStatus() {
  try {
    const data = await api('GET', '/api/setup/certificates')
    Object.assign(certsStatus, data)
  } catch { /* ignore */ }
}

async function saveUser() {
  userError.value = ''
  userSuccess.value = ''
  if (!userForm.current_password) {
    userError.value = 'Current password is required'
    return
  }
  userSaving.value = true
  try {
    const payload = { current_password: userForm.current_password }
    if (userForm.display_name) payload.display_name = userForm.display_name
    if (userForm.password) payload.password = userForm.password
    const result = await api('PUT', '/api/setup/user', payload)
    displayName.value = result.display_name
    userForm.current_password = ''
    userForm.password = ''
    userSuccess.value = 'Account updated successfully'
  } catch (err) {
    userError.value = err.message
  } finally {
    userSaving.value = false
  }
}

async function testLeapmotorConnection() {
  accountError.value = ''
  accountSuccess.value = ''
  if (!accountForm.username || !accountForm.password) {
    accountError.value = 'Email and password are required'
    return
  }
  testingLeapmotor.value = true
  try {
    const result = await api('POST', '/api/setup/account/test', {
      username: accountForm.username,
      password: accountForm.password,
    })
    if (result.connected) {
      accountSuccess.value = 'Connection successful — ' + (result.vehicles?.length || 0) + ' vehicle(s) found.'
    } else {
      accountError.value = result.connection_error || 'Connection failed'
    }
  } catch (err) {
    accountError.value = err.message
  } finally {
    testingLeapmotor.value = false
  }
}

async function saveLeapmotorAccount() {
  accountError.value = ''
  accountSuccess.value = ''
  if (!accountForm.username || !accountForm.password) {
    accountError.value = 'Email and password are required'
    return
  }
  accountSaving.value = true
  try {
    const result = await api('POST', '/api/setup/account', {
      username: accountForm.username,
      password: accountForm.password,
    })
    if (result.connected) {
      accountSuccess.value = 'Credentials saved. Connected successfully.'
      leapmotorEmail.value = accountForm.username
      store.connected = true
      store.vehicles = result.vehicles || []
    } else {
      accountSuccess.value = 'Credentials saved. ' + (result.connection_error || 'Connection failed.')
    }
  } catch (err) {
    accountError.value = err.message
  } finally {
    accountSaving.value = false
  }
}

async function saveCertificates() {
  certError.value = ''
  certSuccess.value = ''
  if (!certFile.value || !keyFile.value) return
  certSaving.value = true
  try {
    const formData = new FormData()
    formData.append('cert_file', certFile.value)
    formData.append('key_file', keyFile.value)
    const res = await fetch('./api/setup/certificates', { method: 'POST', body: formData, credentials: 'include' })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Upload failed')
    certSuccess.value = 'Certificates updated successfully'
    certFile.value = null
    keyFile.value = null
    await loadCertsStatus()
  } catch (err) {
    certError.value = err.message
  } finally {
    certSaving.value = false
  }
}

async function fetchCertsFromGitHub() {
  certDownloadError.value = ''
  certDownloadSuccess.value = ''
  certDownloading.value = true
  try {
    const res = await fetch('./api/setup/certificates/fetch', { method: 'POST', credentials: 'include' })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Download failed')
    certDownloadSuccess.value = 'Certificates downloaded from GitHub' + (data.source ? ` (${data.source})` : '')
    await loadCertsStatus()
  } catch (err) {
    certDownloadError.value = err.message
  } finally {
    certDownloading.value = false
  }
}

// -- Charging Price Tiers ---------------------------------------------------
const electricityPrice = ref(0.25)
const savedElectricityPrice = ref(0.25)
const electricitySaving = ref(false)
const electricityError = ref('')
const electricitySuccess = ref('')

const hasSolarPanels = ref(false)
const homePricingMode = ref('flat')
const chargingTiers = ref([])
const timeBands = ref([])
const chargingTiersSaving = ref(false)
const tiersSuccess = ref('')
const tiersError = ref('')
const bandsSuccess = ref('')
const bandsError = ref('')

const visibleTiers = computed(() => {
  if (hasSolarPanels.value) return chargingTiers.value
  return chargingTiers.value.filter(t => t.id !== 'home_solar')
})

function tierIcon(tierId) {
  const map = { home_grid: Home, home_solar: Sun, public_ac: Plug, public_dc: Zap }
  return map[tierId] || Zap
}

async function loadPreferences() {
  try {
    const data = await api('GET', '/api/preferences')
    electricityPrice.value = data.electricity_price_kwh
    savedElectricityPrice.value = data.electricity_price_kwh
    hasSolarPanels.value = data.has_solar_panels || false
    homePricingMode.value = data.home_pricing_mode || 'flat'
  } catch { /* ignore */ }
}

async function loadChargingTiers() {
  try {
    const data = await api('GET', '/api/charging-tiers')
    chargingTiers.value = data.tiers || []
    timeBands.value = (data.time_bands || []).map(b => ({
      ...b,
      schedule: b.schedule || []
    }))
    homePricingMode.value = data.home_pricing_mode || 'flat'
  } catch { /* ignore */ }
}

async function toggleSolarPanels(newVal) {
  chargingTiersSaving.value = true
  try {
    if (newVal === undefined) newVal = !hasSolarPanels.value
    await api('PUT', '/api/preferences', { has_solar_panels: newVal })
    hasSolarPanels.value = newVal
    await loadChargingTiers()
  } catch { /* ignore */ }
  finally { chargingTiersSaving.value = false }
}

async function setHomePricingMode(mode) {
  chargingTiersSaving.value = true
  try {
    await api('PUT', '/api/preferences', { home_pricing_mode: mode })
    homePricingMode.value = mode
  } catch { /* ignore */ }
  finally { chargingTiersSaving.value = false }
}

async function saveChargingTiers() {
  tiersError.value = ''
  tiersSuccess.value = ''
  chargingTiersSaving.value = true
  try {
    for (const tier of chargingTiers.value) {
      await api('PUT', `/api/charging-tiers/${tier.id}`, { price_kwh: tier.price_kwh })
    }
    tiersSuccess.value = 'Prices saved'
    setTimeout(() => { tiersSuccess.value = '' }, 3000)
  } catch (err) {
    tiersError.value = err.message
  } finally {
    chargingTiersSaving.value = false
  }
}

async function saveTimeBands() {
  bandsError.value = ''
  bandsSuccess.value = ''
  chargingTiersSaving.value = true
  try {
    // Get current server bands to diff
    const serverBands = await api('GET', '/api/charging-tiers/time-bands')
    const serverIds = new Set(serverBands.map(b => b.id))
    const localIds = new Set(timeBands.value.filter(b => b.id).map(b => b.id))

    // Delete removed bands
    for (const sb of serverBands) {
      if (!localIds.has(sb.id)) {
        await api('DELETE', `/api/charging-tiers/time-bands/${sb.id}`)
      }
    }
    // Create/update bands
    for (let i = 0; i < timeBands.value.length; i++) {
      const band = timeBands.value[i]
      const payload = { name: band.name, price_kwh: band.price_kwh, schedule: band.schedule, color: band.color, position: i + 1 }
      if (band.id && serverIds.has(band.id)) {
        await api('PUT', `/api/charging-tiers/time-bands/${band.id}`, payload)
      } else {
        const created = await api('POST', '/api/charging-tiers/time-bands', payload)
        band.id = created.id
      }
    }
    bandsSuccess.value = 'Time bands saved'
    setTimeout(() => { bandsSuccess.value = '' }, 3000)
  } catch (err) {
    bandsError.value = err.message
  } finally {
    chargingTiersSaving.value = false
  }
}

function addBand() {
  timeBands.value.push({
    id: null,
    tier_id: 'home_grid',
    name: '',
    price_kwh: 0.0,
    schedule: [{ days: [0, 1, 2, 3, 4], start_hour: 0, start_min: 0, end_hour: 0, end_min: 0 }],
    color: '#888888',
    position: timeBands.value.length + 1,
  })
}

function removeBand(idx) {
  timeBands.value.splice(idx, 1)
}

function toggleDay(band, slotIdx, dayIdx) {
  const slot = band.schedule[slotIdx]
  const i = slot.days.indexOf(dayIdx)
  if (i >= 0) slot.days.splice(i, 1)
  else slot.days.push(dayIdx)
}

// -- Vehicle PIN state ------------------------------------------------------
const vehiclePin = ref('')
const showPin = ref(false)
const pinSaving = ref(false)
const pinSuccess = ref('')
const pinError = ref('')

// -- Downsampling settings --------------------------------------------------
const downsamplingEnabled = ref(true)
const downsamplingMaxPoints = ref(2000)
const pendingMaxPoints = ref(2000)
const downsamplingSaving = ref(false)
const downsamplingSuccess = ref('')
const downsamplingError = ref('')

async function loadDownsamplingSettings() {
  try {
    const data = await api('GET', '/api/preferences')
    downsamplingEnabled.value = data.downsampling_enabled ?? true
    downsamplingMaxPoints.value = data.downsampling_max_points ?? 2000
    pendingMaxPoints.value = data.downsampling_max_points ?? 2000
  } catch { /* ignore */ }
}

async function toggleDownsampling() {
  downsamplingSaving.value = true
  downsamplingError.value = ''
  try {
    const data = await api('PUT', '/api/preferences', {
      downsampling_enabled: !downsamplingEnabled.value,
    })
    downsamplingEnabled.value = data.downsampling_enabled
    downsamplingSuccess.value = downsamplingEnabled.value ? 'Enabled' : 'Disabled'
    setTimeout(() => { downsamplingSuccess.value = '' }, 3000)
  } catch (err) {
    downsamplingError.value = err.message
  } finally {
    downsamplingSaving.value = false
  }
}

async function saveDownsampling() {
  if (pendingMaxPoints.value === downsamplingMaxPoints.value) return
  downsamplingSaving.value = true
  downsamplingError.value = ''
  downsamplingSuccess.value = ''
  try {
    const data = await api('PUT', '/api/preferences', {
      downsampling_max_points: pendingMaxPoints.value,
    })
    downsamplingMaxPoints.value = data.downsampling_max_points
    pendingMaxPoints.value = data.downsampling_max_points
    downsamplingSuccess.value = 'Saved'
    setTimeout(() => { downsamplingSuccess.value = '' }, 3000)
  } catch (err) {
    downsamplingError.value = err.message
  } finally {
    downsamplingSaving.value = false
  }
}

async function loadVehiclePin() {
  try {
    const data = await api('GET', '/api/vehicle-pin')
    vehiclePin.value = data.pin || ''
  } catch { /* ignore */ }
}

async function saveVehiclePin() {
  pinSaving.value = true
  pinError.value = ''
  pinSuccess.value = ''
  try {
    await api('PUT', '/api/vehicle-pin', { pin: vehiclePin.value })
    pinSuccess.value = 'PIN saved'
    setTimeout(() => { pinSuccess.value = '' }, 3000)
  } catch (err) {
    pinError.value = err.message
  } finally {
    pinSaving.value = false
  }
}

async function clearVehiclePin() {
  vehiclePin.value = ''
  await saveVehiclePin()
}

// -- Log levels -------------------------------------------------------------
const logLevelOptions = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
const logLevels = reactive({ app_level: 'INFO', library_level: 'INFO' })
const logLevelSuccess = ref('')
const liveLogsEnabled = ref(false)

async function loadLogLevels() {
  try {
    const data = await api('GET', '/api/logs/levels')
    logLevels.app_level = data.app_level
    logLevels.library_level = data.library_level
  } catch { /* ignore */ }
}

async function saveLogLevels() {
  logLevelSuccess.value = ''
  try {
    const data = await api('PUT', '/api/logs/levels', {
      app_level: logLevels.app_level,
      library_level: logLevels.library_level,
    })
    logLevels.app_level = data.app_level
    logLevels.library_level = data.library_level
    logLevelSuccess.value = 'Log levels updated'
    setTimeout(() => { logLevelSuccess.value = '' }, 3000)
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------
const telegramChannel = ref(null)
const telegramForm = reactive({ bot_token: '', chat_id: '', bot_enabled: true })
const notifSaving = ref(false)
const notifTesting = ref(false)
const notifError = ref('')
const notifTestResult = ref(null)
const showTelegramSecrets = ref(false)
const telegramExpanded = ref(true)
const cooldownSeconds = ref(300)
const notifEvents = ref([])
const eventsSuccess = ref('')
const eventSearch = ref('')
const collapsedCategories = ref(new Set())
const geofences = ref([])
const newGeofence = reactive({ name: '', latitude: null, longitude: null, radius_m: 200 })
const geolocating = ref(false)
const botToggling = ref(false)
const geofenceMapEl = ref(null)

// Telegram linked users
const telegramUsers = ref([])
const linkTokenData = ref(null)
const linkTokenLoading = ref(false)
const linkCopied = ref(false)
let telegramUsersPollingInterval = null
// Confirm dialog for remove
const showRemoveConfirm = ref(false)
const removeTargetChatId = ref(null)
let geofenceMap = null
let geofenceMapLayers = []
let newGeofenceMarker = null
let newGeofenceCircle = null

const telegramBotActive = computed(() => {
  return telegramChannel.value?.config?.bot_enabled !== false
})

const categoryIcons = { charging: Zap, driving: CarFront, security: Lock, maintenance: Wrench }

const eventCategories = [
  { key: 'charging', label: 'Charging' },
  { key: 'driving', label: 'Driving' },
  { key: 'security', label: 'Security' },
  { key: 'maintenance', label: 'Maintenance' },
]

const defaultDynamicImageEvents = new Set([
  'charge_start',
  'charge_stop',
  'plugged_in',
  'unplugged',
])

const filteredEventsByCategory = computed(() => {
  const q = eventSearch.value.toLowerCase().trim()
  const map = {}
  for (const cat of eventCategories) {
    const events = notifEvents.value.filter(e => e.category === cat.key)
    map[cat.key] = q ? events.filter(e => e.label.toLowerCase().includes(q) || e.description?.toLowerCase().includes(q) || e.event_type.toLowerCase().includes(q)) : events
  }
  return map
})

function toggleCategory(key) {
  if (collapsedCategories.value.has(key)) {
    collapsedCategories.value.delete(key)
  } else {
    collapsedCategories.value.add(key)
  }
}

function useCurrentLocation() {
  if (!navigator.geolocation) return
  geolocating.value = true
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      newGeofence.latitude = parseFloat(pos.coords.latitude.toFixed(5))
      newGeofence.longitude = parseFloat(pos.coords.longitude.toFixed(5))
      geolocating.value = false
    },
    () => { geolocating.value = false },
    { enableHighAccuracy: true, timeout: 10000 }
  )
}

// ── Geofence Map ──
function getGeofenceTileUrl() {
  const theme = document.documentElement.getAttribute('data-theme')
  const style = theme === 'light' ? 'light_all' : 'dark_all'
  return `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png`
}

function initGeofenceMap() {
  if (geofenceMap || !geofenceMapEl.value) return
  const center = geofences.value.length
    ? [geofences.value[0].latitude, geofences.value[0].longitude]
    : [45.4642, 9.1900]
  geofenceMap = L.map(geofenceMapEl.value, {
    center,
    zoom: 13,
    zoomControl: true,
    attributionControl: false,
  })
  L.tileLayer(getGeofenceTileUrl(), { maxZoom: 19, subdomains: 'abcd' }).addTo(geofenceMap)
  geofenceMap.on('click', onGeofenceMapClick)
  renderGeofencesOnMap()
}

function onGeofenceMapClick(e) {
  newGeofence.latitude = parseFloat(e.latlng.lat.toFixed(5))
  newGeofence.longitude = parseFloat(e.latlng.lng.toFixed(5))
}

function renderGeofencesOnMap() {
  if (!geofenceMap) return
  // Remove old layers
  geofenceMapLayers.forEach(l => geofenceMap.removeLayer(l))
  geofenceMapLayers = []
  // Draw existing geofences
  geofences.value.forEach(gf => {
    const circle = L.circle([gf.latitude, gf.longitude], {
      radius: gf.radius_m,
      color: '#00d4ff',
      fillColor: '#00d4ff',
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(geofenceMap)
    const marker = L.circleMarker([gf.latitude, gf.longitude], {
      radius: 5,
      color: '#00d4ff',
      fillColor: '#00d4ff',
      fillOpacity: 1,
      weight: 2,
    }).addTo(geofenceMap)
    marker.bindTooltip(gf.name, { permanent: false, direction: 'top', offset: [0, -8] })
    geofenceMapLayers.push(circle, marker)
  })
  // Fit bounds if we have geofences
  if (geofenceMapLayers.length) {
    const group = L.featureGroup(geofenceMapLayers)
    geofenceMap.fitBounds(group.getBounds().pad(0.3))
  }
}

function updateNewGeofencePreview() {
  if (!geofenceMap) return
  // Remove previous preview
  if (newGeofenceMarker) { geofenceMap.removeLayer(newGeofenceMarker); newGeofenceMarker = null }
  if (newGeofenceCircle) { geofenceMap.removeLayer(newGeofenceCircle); newGeofenceCircle = null }
  if (newGeofence.latitude && newGeofence.longitude) {
    newGeofenceCircle = L.circle([newGeofence.latitude, newGeofence.longitude], {
      radius: newGeofence.radius_m || 200,
      color: '#ff9800',
      fillColor: '#ff9800',
      fillOpacity: 0.15,
      weight: 2,
      dashArray: '6 4',
    }).addTo(geofenceMap)
    newGeofenceMarker = L.circleMarker([newGeofence.latitude, newGeofence.longitude], {
      radius: 6,
      color: '#ff9800',
      fillColor: '#ff9800',
      fillOpacity: 1,
      weight: 2,
    }).addTo(geofenceMap)
    newGeofenceMarker.bindTooltip('New zone', { permanent: false, direction: 'top', offset: [0, -8] })
  }
}

watch(() => [newGeofence.latitude, newGeofence.longitude, newGeofence.radius_m], updateNewGeofencePreview)
watch(geofences, renderGeofencesOnMap, { deep: true })
watch(() => activeSection.value, (val) => {
  if (val === 'general') {
    geofenceMap = null
    nextTick(() => initGeofenceMap())
  }
  // Start/stop telegram users polling when on services tab
  if (val === 'services') {
    startTelegramUsersPolling()
  } else {
    stopTelegramUsersPolling()
  }
})

function getEventConfigValue(evt, paramKey, defaultVal) {
  return evt.config?.[paramKey] ?? defaultVal
}

function getEventImageEnabled(evt) {
  if (!evt?.has_image) return false
  const configured = evt.config?.send_dynamic_image
  if (typeof configured === 'boolean') return configured
  return defaultDynamicImageEvents.has(evt.event_type)
}

function setEventConfigValue(evt, paramKey, value) {
  if (!evt.config) evt.config = {}
  evt.config[paramKey] = Number(value)
}

function setEventImageEnabled(evt, enabled) {
  if (!evt.config) evt.config = {}
  evt.config.send_dynamic_image = !!enabled
}

async function loadNotifications() {
  try {
    const channels = await api('GET', '/api/notifications/channels')
    const tg = channels.find(c => c.channel_type === 'telegram')
    if (tg) {
      telegramChannel.value = tg
      telegramForm.bot_token = tg.config?.bot_token || ''
      telegramForm.chat_id = tg.config?.chat_id || ''
      telegramForm.bot_enabled = tg.config?.bot_enabled !== false
    }
    // Load events
    const events = await api('GET', '/api/notifications/events' + (tg ? `?channel_id=${tg.id}` : ''))
    notifEvents.value = events
    // Load geofences
    geofences.value = await api('GET', '/api/notifications/geofences')
    nextTick(() => initGeofenceMap())
    // Load cooldown
    const cd = await api('GET', '/api/notifications/cooldown')
    cooldownSeconds.value = cd.cooldown_seconds ?? 300
    // Load tracking status
    await loadTrackingStatus()
    // Load telegram linked users
    await loadTelegramUsers()
  } catch (e) {
    notifError.value = e.message || 'Failed to load notifications'
  }
}

async function saveCooldown() {
  try {
    await api('PUT', '/api/notifications/cooldown', { cooldown_seconds: cooldownSeconds.value })
  } catch (e) {
    notifError.value = e.message || 'Failed to save cooldown'
  }
}

async function saveTelegramChannel() {
  notifSaving.value = true
  notifError.value = ''
  try {
    const config = { bot_token: telegramForm.bot_token, chat_id: telegramForm.chat_id, bot_enabled: telegramForm.bot_enabled }
    if (telegramChannel.value) {
      const updated = await api('PUT', `/api/notifications/channels/${telegramChannel.value.id}`, { config })
      telegramChannel.value = updated
    } else {
      const created = await api('POST', '/api/notifications/channels', { channel_type: 'telegram', config, enabled: true })
      telegramChannel.value = created
      // Reload events now that we have a channel
      const events = await api('GET', `/api/notifications/events?channel_id=${created.id}`)
      notifEvents.value = events
    }
  } catch (e) {
    notifError.value = e.message || 'Save failed'
  } finally {
    notifSaving.value = false
  }
}

async function toggleTelegramEnabled() {
  if (!telegramChannel.value) return
  notifSaving.value = true
  try {
    const updated = await api('PUT', `/api/notifications/channels/${telegramChannel.value.id}`, { enabled: !telegramChannel.value.enabled })
    telegramChannel.value = updated
  } catch (e) {
    notifError.value = e.message || 'Toggle failed'
  } finally {
    notifSaving.value = false
  }
}

async function toggleTelegramBot(enable) {
  if (!telegramChannel.value) return
  botToggling.value = true
  try {
    const config = { ...telegramChannel.value.config, bot_enabled: enable }
    const updated = await api('PUT', `/api/notifications/channels/${telegramChannel.value.id}`, { config })
    telegramChannel.value = updated
    telegramForm.bot_enabled = enable
  } catch (e) {
    notifError.value = e.message || 'Bot toggle failed'
  } finally {
    botToggling.value = false
  }
}

async function testTelegram() {
  if (!telegramChannel.value) return
  notifTesting.value = true
  notifTestResult.value = null
  try {
    const result = await api('POST', `/api/notifications/channels/${telegramChannel.value.id}/test`)
    notifTestResult.value = result
  } catch (e) {
    notifTestResult.value = { success: false, message: e.message || 'Test failed' }
  } finally {
    notifTesting.value = false
  }
}

// -- Telegram Linked Users --

async function loadTelegramUsers() {
  try {
    telegramUsers.value = await api('GET', '/api/notifications/channels/telegram/users')
  } catch (e) {
    // Silently ignore if endpoint not available
  }
}

async function generateLinkToken() {
  linkTokenLoading.value = true
  linkTokenData.value = null
  linkCopied.value = false
  try {
    linkTokenData.value = await api('POST', '/api/notifications/channels/telegram/link-token')
  } catch (e) {
    notifError.value = e.message || 'Failed to generate link'
  } finally {
    linkTokenLoading.value = false
  }
}

async function copyLink() {
  if (!linkTokenData.value) return
  try {
    await navigator.clipboard.writeText(linkTokenData.value.link)
    linkCopied.value = true
    setTimeout(() => { linkCopied.value = false }, 2000)
  } catch (e) {
    // Fallback: select input
  }
}

async function approveTelegramUser(chatId) {
  try {
    await api('PUT', `/api/notifications/channels/telegram/users/${chatId}/approve`)
    await loadTelegramUsers()
  } catch (e) {
    notifError.value = e.message || 'Approve failed'
  }
}

async function rejectTelegramUser(chatId) {
  try {
    await api('PUT', `/api/notifications/channels/telegram/users/${chatId}/reject`)
    await loadTelegramUsers()
  } catch (e) {
    notifError.value = e.message || 'Reject failed'
  }
}

async function removeTelegramUser(chatId) {
  removeTargetChatId.value = chatId
  showRemoveConfirm.value = true
}

async function confirmRemoveUser() {
  const chatId = removeTargetChatId.value
  showRemoveConfirm.value = false
  removeTargetChatId.value = null
  try {
    await api('DELETE', `/api/notifications/channels/telegram/users/${chatId}`)
    await loadTelegramUsers()
  } catch (e) {
    notifError.value = e.message || 'Remove failed'
  }
}

function cancelRemoveUser() {
  showRemoveConfirm.value = false
  removeTargetChatId.value = null
}

function toggleEvent(evt, enabled) {
  evt.enabled = enabled
}

const testingEvent = ref(null)

async function testEvent(evt) {
  if (!telegramChannel.value) {
    notifError.value = 'Configure a Telegram channel first'
    return
  }
  testingEvent.value = evt.event_type
  try {
    const result = await api('POST', `/api/notifications/channels/${telegramChannel.value.id}/test-event`, { event_type: evt.event_type, vin: store.selectedVin })
    if (!result.success) {
      notifError.value = result.message || 'Test failed'
    }
  } catch (e) {
    notifError.value = e.message || 'Test failed'
  } finally {
    testingEvent.value = null
  }
}

async function saveEventPreferences() {
  if (!telegramChannel.value) {
    notifError.value = 'Configure a Telegram channel first'
    return
  }
  notifSaving.value = true
  eventsSuccess.value = ''
  try {
    const preferences = notifEvents.value.map(e => ({
      event_type: e.event_type,
      enabled: e.enabled,
      config: (() => {
        const cfg = { ...(e.config || {}) }
        if (e.has_image) {
          cfg.send_dynamic_image = getEventImageEnabled(e)
        }
        return Object.keys(cfg).length ? cfg : null
      })(),
    }))
    await api('PUT', '/api/notifications/events', { channel_id: telegramChannel.value.id, preferences })
    eventsSuccess.value = 'Preferences saved'
    setTimeout(() => { eventsSuccess.value = '' }, 3000)
  } catch (e) {
    notifError.value = e.message || 'Save failed'
  } finally {
    notifSaving.value = false
  }
}

// -- Location Tracking ------------------------------------------------------
const tracking = reactive({ active: false, interval_seconds: 60 })
const trackingInterval = ref(60)
const trackingLoading = ref(false)
let trackingPollTimer = null

function startTrackingPoll() {
  stopTrackingPoll()
  trackingPollTimer = setInterval(async () => {
    if (!store.selectedVin) return
    try {
      const data = await api('GET', `/api/tracking/${store.selectedVin}`)
      if (!data.tracking && tracking.active) {
        tracking.active = false
        stopTrackingPoll()
      }
    } catch { /* ignore */ }
  }, 5000)
}

function stopTrackingPoll() {
  if (trackingPollTimer) {
    clearInterval(trackingPollTimer)
    trackingPollTimer = null
  }
}

async function loadTrackingStatus() {
  if (!store.selectedVin) return
  try {
    const data = await api('GET', `/api/tracking/${store.selectedVin}`)
    tracking.active = data.tracking
    if (data.interval_seconds) {
      tracking.interval_seconds = data.interval_seconds
      trackingInterval.value = data.interval_seconds
    }
    if (data.tracking) startTrackingPoll()
    else stopTrackingPoll()
  } catch {
    // ignore
  }
}

async function startTracking() {
  if (!store.selectedVin) return
  trackingLoading.value = true
  try {
    const data = await api('POST', `/api/tracking/${store.selectedVin}/start`, { interval_seconds: trackingInterval.value })
    tracking.active = data.tracking
    tracking.interval_seconds = data.interval_seconds
    startTrackingPoll()
  } catch (e) {
    notifError.value = e.message || 'Failed to start tracking'
  } finally {
    trackingLoading.value = false
  }
}

async function stopTracking() {
  if (!store.selectedVin) return
  trackingLoading.value = true
  try {
    await api('POST', `/api/tracking/${store.selectedVin}/stop`)
    tracking.active = false
    stopTrackingPoll()
  } catch (e) {
    notifError.value = e.message || 'Failed to stop tracking'
  } finally {
    trackingLoading.value = false
  }
}

async function addGeofence() {
  notifSaving.value = true
  try {
    const gf = await api('POST', '/api/notifications/geofences', {
      name: newGeofence.name,
      latitude: newGeofence.latitude,
      longitude: newGeofence.longitude,
      radius_m: newGeofence.radius_m,
      notify_on_enter: true,
      notify_on_exit: true,
      enabled: true,
    })
    geofences.value.push(gf)
    newGeofence.name = ''
    newGeofence.latitude = null
    newGeofence.longitude = null
    newGeofence.radius_m = 200
  } catch (e) {
    notifError.value = e.message || 'Failed to add geofence'
  } finally {
    notifSaving.value = false
  }
}

async function deleteGeofence(id) {
  try {
    await api('DELETE', `/api/notifications/geofences/${id}`)
    geofences.value = geofences.value.filter(g => g.id !== id)
  } catch (e) {
    notifError.value = e.message || 'Failed to delete geofence'
  }
}

async function updateGeofenceField(gf, field, value) {
  try {
    await api('PUT', `/api/notifications/geofences/${gf.id}`, { [field]: value })
    gf[field] = value
  } catch (e) {
    notifError.value = e.message || 'Failed to update geofence'
  }
}

onMounted(() => {
  loadScheduler()
  loadLiveRefresh()
  loadAccount()
  loadCertsStatus()
  loadPreferences()
  loadChargingTiers()
  loadDownsamplingSettings()
  loadDatabaseSize()
  loadMqtt()
  loadAbrp()
  loadVehiclePin()
  loadLogLevels()
  loadNotifications()
})

onBeforeUnmount(() => {
  stopTrackingPoll()
  stopTelegramUsersPolling()
})

function startTelegramUsersPolling() {
  stopTelegramUsersPolling()
  telegramUsersPollingInterval = setInterval(loadTelegramUsers, 5000)
}

function stopTelegramUsersPolling() {
  if (telegramUsersPollingInterval) {
    clearInterval(telegramUsersPollingInterval)
    telegramUsersPollingInterval = null
  }
}
</script>

<style scoped>
.settings-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 100%;
}

/* Section Navigation */
.settings-nav {
  display: flex;
  gap: 6px;
  padding: 4px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.settings-nav::-webkit-scrollbar { display: none; }
.nav-pill {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.nav-pill:hover { color: var(--sub); background: #ffffff06; }
.nav-pill.active {
  background: #00d4ff12;
  color: #00d4ff;
  box-shadow: 0 0 0 1px #00d4ff22;
}

/* Grid for compact cards */
.settings-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
@media (min-width: 520px) {
  .settings-grid { grid-template-columns: 1fr 1fr; }
}

.section-desc {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 8px;
  line-height: 1.5;
}

.account-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0 16px;
}
.account-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #00d4ff22;
  border: 2px solid #00d4ff55;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #00d4ff;
}
.account-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.account-role {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.action-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 12px;
}
.action-btn:hover { color: #00d4ff; border-color: #00d4ff44; }

.edit-panel {
  padding: 12px 0;
  border-top: 1px solid var(--divider);
  margin-bottom: 12px;
}
.form-group { margin-bottom: 0.9rem; }
.form-group label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.form-group input {
  width: 100%;
  padding: 10px 14px;
  background: var(--input);
  border: 1px solid var(--btn-border);
  border-radius: 8px;
  color: var(--text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus { border-color: #00d4ff55; }
.form-group input::placeholder { color: var(--muted2); }

.form-divider {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 1rem 0 0.7rem;
  padding-top: 0.8rem;
  border-top: 1px solid var(--divider);
}

.divider {
  border: none;
  border-top: 1px solid var(--divider);
  margin: 14px 0;
}

.file-upload {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--input);
  border: 1px dashed var(--btn-border);
  border-radius: 8px;
  color: var(--muted2);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.file-upload:hover { border-color: #00d4ff55; }
.file-upload.filled { border-style: solid; border-color: #00d4ff44; color: var(--text); }

.form-hint {
  display: block;
  font-size: 11px;
  color: var(--muted2);
  margin-bottom: 0.8rem;
}

.save-btn {
  width: 100%;
  padding: 10px;
  background: linear-gradient(135deg, #00d4ff22, #00d4ff44);
  border: 1px solid #00d4ff55;
  border-radius: 8px;
  color: #00d4ff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.save-btn:hover { background: linear-gradient(135deg, #00d4ff33, #00d4ff55); }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.field-error {
  margin-top: 0.6rem;
  font-size: 12px;
  color: #ff5252;
}
.field-success {
  margin-top: 0.6rem;
  font-size: 12px;
  color: #00e676;
}

.notif-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--divider);
}
.notif-row:last-child { border-bottom: none; }
.notif-label { font-size: 13px; color: var(--sub); }

/* Channel card */
.channel-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--elevated);
  overflow: hidden;
}
.channel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.channel-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.channel-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.channel-icon { color: var(--sub); flex-shrink: 0; }
.channel-name { font-size: 13px; font-weight: 600; color: var(--text); }
.channel-badge {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
  padding: 2px 8px;
  border-radius: 10px;
}
.channel-badge.active {
  background: #00e67618;
  color: #00e676;
  border: 1px solid #00e67633;
}
.channel-badge.inactive {
  background: var(--bg);
  color: var(--muted);
  border: 1px solid var(--border);
}
.channel-body {
  padding: 14px;
}
.channel-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.channel-cooldown {
  margin-top: 14px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.cooldown-desc {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
}
.save-btn-sm {
  padding: 4px 12px;
  font-size: 12px;
  min-width: unset;
  margin-left: 8px;
}

/* Secret input with reveal toggle */
.secret-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.secret-input-wrap input {
  width: 100%;
  padding-right: 36px;
  background: var(--bg);
  border: 1px solid var(--border2);
  border-radius: 8px;
  padding: 9px 36px 9px 12px;
  font-size: 13px;
  color: var(--sub);
  font-family: var(--mono);
  transition: border 0.2s;
}
.secret-input-wrap input:focus { border-color: #00d4ff55; outline: none; }
.secret-input-wrap input::placeholder { color: var(--muted2); }
.secret-toggle-btn {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}
.secret-toggle-btn:hover { color: var(--sub); }

.raw-toggle {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--muted);
  font-size: 12px;
  font-family: var(--mono);
  cursor: pointer;
  transition: all 0.2s;
}
.raw-toggle:hover { color: var(--sub); border-color: #00d4ff44; }

.raw-panel {
  max-height: 400px;
  overflow: auto;
  background: var(--elevated);
  border-radius: 0 0 8px 8px;
  padding: 12px;
  margin-top: 0;
}
.raw-panel pre {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted3);
  white-space: pre-wrap;
  word-break: break-all;
}
.raw-tabs {
  display: flex;
  gap: 4px;
  margin-top: 12px;
}
.raw-tab {
  flex: 1;
  padding: 8px 0;
  border: none;
  border-radius: 8px 8px 0 0;
  background: #161a26;
  color: #5c6478;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.raw-tab.active {
  background: var(--elevated);
  color: #7c6aff;
}

/* Scheduler / Data Collection */
.scheduler-service {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--divider);
}
.service-status {
  display: flex;
  align-items: center;
  gap: 8px;
}
.service-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--sub);
}
.service-interval {
  font-weight: 400;
  color: var(--muted);
}
.service-btn {
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid;
}
.service-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-start {
  background: #00e67618;
  border-color: #00e67644;
  color: #00e676;
}
.btn-start:hover:not(:disabled) { background: #00e67630; }
.btn-stop {
  background: #ff525218;
  border-color: #ff525244;
  color: #ff5252;
}
.btn-stop:hover:not(:disabled) { background: #ff525230; }

.interval-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--divider);
}
.interval-label {
  font-size: 13px;
  color: var(--sub);
}
.interval-control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.interval-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--sub);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.interval-btn:hover:not(:disabled) {
  border-color: #00d4ff55;
  color: #00d4ff;
}
.interval-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.interval-value {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  min-width: 52px;
  text-align: center;
  font-family: var(--mono);
}
.interval-set-btn {
  padding: 4px 12px;
  background: var(--btn-bg);
  border: 1px solid var(--btn-border);
  border-radius: 6px;
  color: var(--sub);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  margin-left: 4px;
}
.interval-set-btn:hover:not(:disabled) { background: var(--btn-hover); color: #00d4ff; }
.interval-set-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.pin-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.pin-input {
  width: 90px;
  padding: 4px 28px 4px 8px;
  background: var(--elevated);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  font-family: var(--mono);
  letter-spacing: 1px;
  outline: none;
  transition: border-color 0.15s;
}
.pin-input:focus { border-color: #00d4ff55; }
.pin-input::placeholder { color: #444; letter-spacing: 0; }
.pin-eye-btn {
  position: absolute;
  right: 4px;
  background: none;
  border: none;
  cursor: pointer;
  line-height: 0;
  padding: 3px;
  color: var(--sub);
  opacity: 0.45;
  transition: opacity 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pin-eye-btn:hover { opacity: 0.85; }
.scheduler-status {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--elevated);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.running {
  background: #00e676;
  box-shadow: 0 0 6px #00e67688;
}
.status-dot.stopped {
  background: #5c6478;
}
.status-detail {
  font-size: 11px;
  color: var(--muted);
}
.status-error {
  font-size: 11px;
  color: #ff5252;
  font-family: var(--mono);
}

/* Preferences */
.pref-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--divider);
}
.pref-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.pref-label {
  font-size: 13px;
  color: var(--sub);
}
.pref-hint {
  font-size: 11px;
  color: var(--muted);
}
.rate-limit-hint {
  font-size: 11px;
  color: var(--muted);
  margin: -4px 0 8px 0;
}
.pref-input-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.pref-input {
  width: 70px;
  padding: 6px 10px;
  background: var(--input);
  border: 1px solid var(--btn-border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
  font-family: var(--mono);
  text-align: right;
  outline: none;
  transition: border-color 0.2s;
}
.pref-input:focus { border-color: #00d4ff55; }
.pref-unit {
  font-size: 11px;
  color: var(--muted);
}
.theme-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 6px 12px; border-radius: 8px;
  font-size: 12px; font-weight: 600;
  background: var(--input); border: 1px solid var(--border);
  color: var(--label); cursor: pointer; transition: all 0.2s;
}
.theme-btn:hover { border-color: var(--muted); color: var(--text); }
.theme-btn.active {
  background: #7c6aff22; border-color: #7c6aff66; color: #7c6aff;
}

/* MQTT Modal */
.mqtt-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}
.mqtt-modal {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  width: 100%;
  max-width: 420px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.mqtt-modal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.mqtt-modal-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--fg);
}
.mqtt-modal-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 22px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  transition: color 0.2s;
}
.mqtt-modal-close:hover { color: var(--fg); }
.mqtt-modal-body {
  padding: 16px 20px;
  overflow-y: auto;
  flex: 1;
}
.mqtt-modal-footer {
  display: flex;
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border);
}
.mqtt-modal-footer .test-btn,
.mqtt-modal-footer .save-btn {
  flex: 1;
}
/* Modal transition */
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .mqtt-modal, .modal-leave-active .mqtt-modal { transition: transform 0.2s ease; }
.modal-enter-from .mqtt-modal { transform: scale(0.95); }
.modal-leave-to .mqtt-modal { transform: scale(0.95); }

.test-btn {
  flex: 1;
  padding: 10px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.test-btn:hover:not(:disabled) { color: #00d4ff; border-color: #00d4ff44; }
.test-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── About ── */
.about-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
}
.about-logo {
  width: 48px; height: 48px;
  border-radius: 12px;
  background: rgba(0,212,255,0.08);
  display: flex; align-items: center; justify-content: center;
}
.about-app-name { font-size: 18px; font-weight: 700; color: #e2e6f0; }
.about-version { font-size: 12px; color: #5c6478; font-family: var(--mono); margin-top: 2px; }
.about-desc {
  font-size: 13px; color: #8a90a0; line-height: 1.6; margin: 0;
}
.about-desc a {
  color: #00d4ff; text-decoration: none;
}
.about-desc a:hover { text-decoration: underline; }
.about-links {
  display: flex; flex-direction: column; gap: 8px;
}
.about-link-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  color: #c8cdd8;
  text-decoration: none;
  transition: all 0.2s;
}
.about-link-card:hover {
  background: rgba(0,212,255,0.06);
  border-color: rgba(0,212,255,0.2);
}
.about-link-card.star { color: #fbbf24; }
.about-link-card.star:hover { background: rgba(251,191,36,0.06); border-color: rgba(251,191,36,0.2); }
.about-link-title { font-size: 13px; font-weight: 600; }
.about-link-hint { font-size: 11px; color: #5c6478; margin-top: 2px; }
.about-link-arrow { margin-left: auto; color: #5c6478; flex-shrink: 0; }
.about-disclaimer {
  font-size: 13px; color: #8a90a0; line-height: 1.7;
}
.about-disclaimer p { margin: 0 0 10px; }
.about-disclaimer strong { color: #ffab40; }
.about-disclaimer ul {
  margin: 8px 0 0; padding-left: 20px;
}
.about-disclaimer li { margin-bottom: 6px; }

/* Log level select */
.log-level-select {
  appearance: none;
  -webkit-appearance: none;
  padding: 6px 28px 6px 10px;
  background: var(--input) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2388909a' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") no-repeat right 10px center;
  border: 1px solid var(--btn-border);
  border-radius: 6px;
  color: var(--text);
  font-size: 12px;
  font-weight: 600;
  font-family: var(--mono);
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}
.log-level-select:focus { border-color: #00d4ff55; }
.log-level-select option {
  background: var(--card, #1a1e2e);
  color: var(--text);
}

/* Notifications */
/* Channel collapse transition */
.collapse-enter-active, .collapse-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.collapse-enter-from, .collapse-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.collapse-enter-to, .collapse-leave-from {
  opacity: 1;
  max-height: 400px;
}
.channel-chevron { color: var(--muted); flex-shrink: 0; }

/* Event search */
.event-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
  margin-bottom: 14px;
}
.event-search-icon {
  position: absolute;
  left: 10px;
  color: var(--muted);
  pointer-events: none;
}
.event-search-input {
  width: 100%;
  padding: 8px 32px 8px 32px;
  background: var(--bg);
  border: 1px solid var(--border2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--sub);
  transition: border 0.2s;
}
.event-search-input:focus { border-color: #00d4ff55; outline: none; }
.event-search-input::placeholder { color: var(--muted2); }
.event-search-clear {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}
.event-search-clear:hover { color: var(--sub); }

.notif-category { margin-bottom: 16px; }
.notif-category-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary, #8a919e);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--btn-border, #2a2e3e);
  user-select: none;
}
.notif-category-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.notif-category-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
}
.notif-event-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  gap: 12px;
}
.notif-event-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.notif-event-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.event-test-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: none;
  border: 1px solid var(--border2);
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s;
}
.event-test-btn:hover { color: var(--sub); border-color: #00d4ff44; }
.event-test-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.notif-event-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.notif-event-desc {
  font-size: 11px;
  color: var(--text-secondary, #6a7080);
}
.notif-event-config {
  padding: 4px 0 8px 16px;
  border-left: 2px solid var(--btn-border, #2a2e3e);
  margin-bottom: 4px;
}
.geofence-map-wrapper {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  height: 240px;
  margin-bottom: 14px;
  border: 1px solid var(--btn-border, #2a2e3e);
}
.geofence-map-container {
  width: 100%;
  height: 100%;
}
@media (min-width: 640px) {
  .geofence-map-wrapper { height: 300px; }
}
.geofence-item {
  padding: 10px;
  border: 1px solid var(--btn-border, #2a2e3e);
  border-radius: 8px;
  margin-bottom: 8px;
}
.geofence-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.geofence-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.geofence-pin { color: var(--sub); flex-shrink: 0; }
.geofence-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}
.geofence-delete-btn {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s, background 0.15s;
}
.geofence-delete-btn:hover { color: #f44336; background: #f4433610; }
.locate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  margin-bottom: 0.9rem;
  background: var(--elevated);
  border: 1px solid var(--border2);
  border-radius: 8px;
  color: var(--sub);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.2s, color 0.2s;
}
.locate-btn:hover { border-color: #00d4ff55; color: #00d4ff; }
.locate-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.geofence-details {
  font-size: 11px;
  color: var(--text-secondary, #6a7080);
  margin-top: 4px;
}
.geofence-toggles {
  display: flex;
  gap: 16px;
  margin-top: 6px;
}
.geofence-toggle-label {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

/* Telegram Linked Users */
.link-token-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.link-token-url {
  display: flex;
  align-items: center;
  gap: 6px;
}
.link-input {
  flex: 1;
  font-size: 12px;
  font-family: monospace;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 8px;
  color: var(--text-primary);
}
.telegram-users-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.telegram-user-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
}
.telegram-user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.telegram-user-name {
  color: var(--text-primary);
  font-weight: 500;
}
.telegram-user-handle {
  color: var(--text-secondary);
  font-weight: 400;
}
.telegram-user-status {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
}
.telegram-user-status.status-pending {
  background: rgba(255, 152, 0, 0.15);
  color: #ff9800;
}
.telegram-user-status.status-approved {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}
.telegram-user-status.status-rejected {
  background: rgba(244, 67, 54, 0.15);
  color: #f44336;
}
.telegram-user-actions {
  display: flex;
  gap: 4px;
}
.btn-sm {
  font-size: 11px !important;
  padding: 3px 8px !important;
}

/* -- Charging Price Tiers -- */
.pref-icon {
  color: var(--muted);
  flex-shrink: 0;
}
.pref-row .pref-info {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.pricing-mode-toggle {
  display: flex;
  gap: 4px;
}
.time-band-row {
  padding: 10px 0;
  border-bottom: 1px solid var(--divider);
}
.band-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.band-name-input {
  flex: 1;
  padding: 5px 8px;
  background: var(--input);
  border: 1px solid var(--btn-border);
  border-radius: 6px;
  color: var(--text);
  font-size: 12px;
  outline: none;
}
.band-name-input:focus { border-color: #00d4ff55; }
.band-price-input { width: 65px; }
.band-schedule {
  margin-left: 22px;
}
.schedule-slot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.days-row {
  display: flex;
  gap: 2px;
}
.day-btn {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  background: var(--input);
  border: 1px solid var(--btn-border);
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.day-btn.active {
  background: #00d4ff22;
  border-color: #00d4ff;
  color: #00d4ff;
}
.time-range {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: var(--muted);
}
.time-input {
  width: 36px;
  padding: 3px 4px;
  background: var(--input);
  border: 1px solid var(--btn-border);
  border-radius: 4px;
  color: var(--text);
  font-size: 11px;
  font-family: var(--mono);
  text-align: center;
  outline: none;
}
.time-input:focus { border-color: #00d4ff55; }
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid var(--btn-border);
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s;
}
.icon-btn:hover { border-color: var(--text); color: var(--text); }
.icon-btn.danger:hover { border-color: #ef4444; color: #ef4444; }
.add-slot-btn, .add-band-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  color: #00d4ff;
  background: transparent;
  border: 1px dashed #00d4ff44;
  border-radius: 6px;
  cursor: pointer;
  margin-top: 6px;
  transition: all 0.15s;
}
.add-slot-btn:hover, .add-band-btn:hover {
  background: #00d4ff11;
  border-color: #00d4ff;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.cert-repo-hint {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--muted);
}
.cert-repo-link {
  color: #00d4ff;
  text-decoration: none;
  font-family: var(--mono);
  transition: color 0.15s;
}
.cert-repo-link:hover {
  color: #4de0ff;
  text-decoration: underline;
}
</style>
