/**
 * Webcam Controller - Frontend Application Logic
 * Real-time controls, WebSocket telemetry, pan/tilt joystick, and preset management.
 */

class WebcamApp {
  constructor() {
    this.ws = null;
    this.telemetry = {
      zoom: 1.0,
      pan_x: 0.0,
      pan_y: 0.0,
      auto_zoom: false,
      fps: 30.0,
      virtual_cam_active: false
    };

    this.isDraggingPad = false;
    this.isDraggingVideo = false;
    this.dragStart = { x: 0, y: 0 };
    this.panStart = { x: 0, y: 0 };

    this.initElements();
    this.initTabs();
    this.initEventListeners();
    this.initWebSocket();
    this.loadDevices();
    this.loadControls();
    this.loadProfiles();
    this.checkVirtualCamStatus();
  }

  initElements() {
    // Navigation & Header
    this.deviceSelect = document.getElementById('deviceSelect');
    this.profileSelect = document.getElementById('profileSelect');
    this.saveProfileBtn = document.getElementById('saveProfileBtn');
    this.virtualCamToggleBtn = document.getElementById('virtualCamToggleBtn');
    this.vcamIndicator = document.getElementById('vcamIndicator');
    this.vcamBtnText = document.getElementById('vcamBtnText');
    this.vcamStatusPill = document.getElementById('vcamStatusPill');

    // Viewport HUD
    this.videoFeed = document.getElementById('videoFeed');
    this.viewportWrapper = document.getElementById('viewportWrapper');
    this.telemetryFps = document.getElementById('telemetryFps');
    this.telemetryResolution = document.getElementById('telemetryResolution');
    this.telemetryZoom = document.getElementById('telemetryZoom');
    this.mirrorBtn = document.getElementById('mirrorBtn');
    this.centerPanBtn = document.getElementById('centerPanBtn');
    this.chipButtons = document.querySelectorAll('.chip-btn');

    // Zoom Tab Controls
    this.zoomSlider = document.getElementById('zoomSlider');
    this.zoomValDisplay = document.getElementById('zoomValDisplay');
    this.zoomMinusBtn = document.getElementById('zoomMinusBtn');
    this.zoomPlusBtn = document.getElementById('zoomPlusBtn');
    this.autoZoomToggle = document.getElementById('autoZoomToggle');
    this.autoZoomOptions = document.getElementById('autoZoomOptions');
    this.smoothSlider = document.getElementById('smoothSlider');
    this.smoothVal = document.getElementById('smoothVal');
    this.panTiltPad = document.getElementById('panTiltPad');
    this.padPuck = document.getElementById('padPuck');
    this.panValDisplay = document.getElementById('panValDisplay');
    this.tiltValDisplay = document.getElementById('tiltValDisplay');
    this.resetPanTiltBtn = document.getElementById('resetPanTiltBtn');

    // Focus Tab Controls
    this.autoFocusToggle = document.getElementById('autoFocusToggle');
    this.manualFocusGroup = document.getElementById('manualFocusGroup');
    this.focusSlider = document.getElementById('focusSlider');
    this.focusValDisplay = document.getElementById('focusValDisplay');

    // Lighting Tab Controls
    this.autoExposureToggle = document.getElementById('autoExposureToggle');
    this.manualExposureGroup = document.getElementById('manualExposureGroup');
    this.exposureSlider = document.getElementById('exposureSlider');
    this.exposureValDisplay = document.getElementById('exposureValDisplay');
    this.backlightSlider = document.getElementById('backlightSlider');
    this.backlightValDisplay = document.getElementById('backlightValDisplay');
    this.gainSlider = document.getElementById('gainSlider');
    this.gainValDisplay = document.getElementById('gainValDisplay');

    // Color Tab Controls
    this.autoWbToggle = document.getElementById('autoWbToggle');
    this.manualWbGroup = document.getElementById('manualWbGroup');
    this.wbTempSlider = document.getElementById('wbTempSlider');
    this.wbTempValDisplay = document.getElementById('wbTempValDisplay');
    this.brightSlider = document.getElementById('brightSlider');
    this.brightValDisplay = document.getElementById('brightValDisplay');
    this.contrastSlider = document.getElementById('contrastSlider');
    this.contrastValDisplay = document.getElementById('contrastValDisplay');
    this.satSlider = document.getElementById('satSlider');
    this.satValDisplay = document.getElementById('satValDisplay');
    this.sharpSlider = document.getElementById('sharpSlider');
    this.sharpValDisplay = document.getElementById('sharpValDisplay');
    this.gammaSlider = document.getElementById('gammaSlider');
    this.gammaValDisplay = document.getElementById('gammaValDisplay');
    this.hueSlider = document.getElementById('hueSlider');
    this.hueValDisplay = document.getElementById('hueValDisplay');
    this.resetDefaultsBtn = document.getElementById('resetDefaultsBtn');

    // Virtual Camera Tab
    this.vcamNodeDisplay = document.getElementById('vcamNodeDisplay');
    this.setupCodeText = document.getElementById('setupCodeText');
    this.copySetupBtn = document.getElementById('copySetupBtn');

    // Profile Modal
    this.saveProfileModal = document.getElementById('saveProfileModal');
    this.profileNameInput = document.getElementById('profileNameInput');
    this.closeModalBtn = document.getElementById('closeModalBtn');
    this.cancelProfileBtn = document.getElementById('cancelProfileBtn');
    this.confirmSaveProfileBtn = document.getElementById('confirmSaveProfileBtn');
  }

  initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    const activateTab = (targetId) => {
      tabButtons.forEach(b => b.classList.toggle('active', b.getAttribute('data-tab') === targetId));
      tabPanes.forEach(p => p.classList.toggle('active', p.id === targetId));
    };

    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        activateTab(targetId);
        window.location.hash = targetId;
      });
    });

    // Check hash on load
    if (window.location.hash) {
      const hashId = window.location.hash.substring(1);
      if (document.getElementById(hashId)) {
        activateTab(hashId);
      }
    }
  }

  initEventListeners() {
    // Zoom Slider
    this.zoomSlider.addEventListener('input', (e) => {
      const zoom = parseFloat(e.target.value);
      this.updateZoom(zoom);
    });

    this.zoomMinusBtn.addEventListener('click', () => {
      let zoom = Math.max(1.0, parseFloat(this.zoomSlider.value) - 0.25);
      this.zoomSlider.value = zoom.toFixed(2);
      this.updateZoom(zoom);
    });

    this.zoomPlusBtn.addEventListener('click', () => {
      let zoom = Math.min(5.0, parseFloat(this.zoomSlider.value) + 0.25);
      this.zoomSlider.value = zoom.toFixed(2);
      this.updateZoom(zoom);
    });

    // Quick Zoom Chips
    this.chipButtons.forEach(chip => {
      chip.addEventListener('click', () => {
        const zoom = parseFloat(chip.getAttribute('data-zoom'));
        this.zoomSlider.value = zoom.toFixed(2);
        this.updateZoom(zoom);
        this.highlightChip(zoom);
      });
    });

    // Auto-Zoom Toggle
    this.autoZoomToggle.addEventListener('change', (e) => {
      const enabled = e.target.checked;
      this.autoZoomOptions.style.display = enabled ? 'flex' : 'none';
      this.sendPost('/api/auto-zoom', { enabled, smoothing: parseFloat(this.smoothSlider.value) });
    });

    this.smoothSlider.addEventListener('input', (e) => {
      const smoothing = parseFloat(e.target.value);
      this.smoothVal.innerText = `Smoothing (${smoothing.toFixed(2)})`;
      if (this.autoZoomToggle.checked) {
        this.sendPost('/api/auto-zoom', { enabled: true, smoothing });
      }
    });

    // 2D Pan/Tilt Pad dragging
    this.initPanTiltPad();

    // Direct Video Viewport dragging
    this.initVideoViewportDrag();

    this.resetPanTiltBtn.addEventListener('click', () => this.resetPanTilt());
    this.centerPanBtn.addEventListener('click', () => this.resetPanTilt());

    // Mirror Toggle
    let isMirrored = false;
    this.mirrorBtn.addEventListener('click', () => {
      isMirrored = !isMirrored;
      this.mirrorBtn.classList.toggle('active', isMirrored);
      this.sendPost('/api/mirror', { flip: isMirrored });
    });

    // Device Switcher
    this.deviceSelect.addEventListener('change', (e) => {
      this.sendPost('/api/devices/select', { device: e.target.value }).then(() => {
        this.loadControls();
      });
    });

    // Virtual Camera Toggle
    this.virtualCamToggleBtn.addEventListener('click', () => {
      const newState = !this.telemetry.virtual_cam_active;
      this.sendPost('/api/virtual-cam/toggle', { enabled: newState }).then(res => {
        if (!res.success && res.error) {
          alert(`Virtual Camera Notice:\n${res.error}\n\nHint: ${res.setup_hint || ''}`);
        }
        this.checkVirtualCamStatus();
      });
    });

    // Copy Setup Command
    this.copySetupBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(this.setupCodeText.innerText);
      this.copySetupBtn.style.color = 'var(--accent-green)';
      setTimeout(() => { this.copySetupBtn.style.color = ''; }, 1500);
    });

    // Focus Controls
    this.autoFocusToggle.addEventListener('change', (e) => {
      const isAuto = e.target.checked;
      this.manualFocusGroup.style.opacity = isAuto ? '0.4' : '1';
      this.manualFocusGroup.style.pointerEvents = isAuto ? 'none' : 'auto';
      this.sendControl('focus_automatic_continuous', isAuto ? 1 : 0);
    });

    this.focusSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.focusValDisplay.innerText = val;
      this.sendControl('focus_absolute', val);
    });

    // Lighting Controls
    this.autoExposureToggle.addEventListener('change', (e) => {
      const isAuto = e.target.checked;
      this.manualExposureGroup.style.opacity = isAuto ? '0.4' : '1';
      this.manualExposureGroup.style.pointerEvents = isAuto ? 'none' : 'auto';
      this.sendControl('auto_exposure', isAuto ? 3 : 1);
    });

    this.exposureSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.exposureValDisplay.innerText = val;
      this.sendControl('exposure_time_absolute', val);
    });

    this.backlightSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.backlightValDisplay.innerText = val;
      this.sendControl('backlight_compensation', val);
    });

    this.gainSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.gainValDisplay.innerText = val;
      this.sendControl('gain', val);
    });

    // Color Controls
    this.autoWbToggle.addEventListener('change', (e) => {
      const isAuto = e.target.checked;
      this.manualWbGroup.style.opacity = isAuto ? '0.4' : '1';
      this.manualWbGroup.style.pointerEvents = isAuto ? 'none' : 'auto';
      this.sendControl('white_balance_automatic', isAuto ? 1 : 0);
    });

    this.wbTempSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.wbTempValDisplay.innerText = `${val}K`;
      this.sendControl('white_balance_temperature', val);
    });

    this.brightSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.brightValDisplay.innerText = val;
      this.sendControl('brightness', val);
    });

    this.contrastSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.contrastValDisplay.innerText = val;
      this.sendControl('contrast', val);
    });

    this.satSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.satValDisplay.innerText = val;
      this.sendControl('saturation', val);
    });

    this.sharpSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.sharpValDisplay.innerText = val;
      this.sendControl('sharpness', val);
    });

    this.gammaSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.gammaValDisplay.innerText = val;
      this.sendControl('gamma', val);
    });

    this.hueSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.hueValDisplay.innerText = val;
      this.sendControl('hue', val);
    });

    this.resetDefaultsBtn.addEventListener('click', () => {
      this.sendPost('/api/controls/reset', {}).then(() => {
        this.loadControls();
      });
    });

    // Profile Presets
    this.profileSelect.addEventListener('change', (e) => {
      if (e.target.value) {
        this.applyProfile(e.target.value);
      }
    });

    this.saveProfileBtn.addEventListener('click', () => {
      this.saveProfileModal.classList.add('active');
      this.profileNameInput.focus();
    });

    this.closeModalBtn.addEventListener('click', () => this.saveProfileModal.classList.remove('active'));
    this.cancelProfileBtn.addEventListener('click', () => this.saveProfileModal.classList.remove('active'));

    this.confirmSaveProfileBtn.addEventListener('click', () => {
      const name = this.profileNameInput.value.trim();
      if (!name) return;
      this.saveCurrentProfile(name);
      this.saveProfileModal.classList.remove('active');
      this.profileNameInput.value = '';
    });
  }

  initPanTiltPad() {
    const pad = this.panTiltPad;

    const handlePadMove = (e) => {
      if (!this.isDraggingPad) return;
      const rect = pad.getBoundingClientRect();
      const clientX = e.clientX || (e.touches && e.touches[0].clientX);
      const clientY = e.clientY || (e.touches && e.touches[0].clientY);

      let x = (clientX - rect.left) / rect.width; // 0 to 1
      let y = (clientY - rect.top) / rect.height; // 0 to 1

      x = Math.max(0, Math.min(1, x));
      y = Math.max(0, Math.min(1, y));

      const panX = (x - 0.5) * 2;   // -1.0 to 1.0
      const panY = (y - 0.5) * 2;   // -1.0 to 1.0

      this.updatePanTilt(panX, panY);
    };

    pad.addEventListener('mousedown', (e) => {
      this.isDraggingPad = true;
      handlePadMove(e);
    });

    window.addEventListener('mousemove', handlePadMove);
    window.addEventListener('mouseup', () => { this.isDraggingPad = false; });

    pad.addEventListener('touchstart', (e) => {
      this.isDraggingPad = true;
      handlePadMove(e);
    });
    window.addEventListener('touchmove', handlePadMove);
    window.addEventListener('touchend', () => { this.isDraggingPad = false; });
  }

  initVideoViewportDrag() {
    const wrapper = this.viewportWrapper;

    wrapper.addEventListener('mousedown', (e) => {
      this.isDraggingVideo = true;
      this.dragStart = { x: e.clientX, y: e.clientY };
      this.panStart = { x: this.telemetry.pan_x, y: this.telemetry.pan_y };
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDraggingVideo) return;
      const dx = (e.clientX - this.dragStart.x) / (wrapper.clientWidth / 2);
      const dy = (e.clientY - this.dragStart.y) / (wrapper.clientHeight / 2);

      const newPanX = Math.max(-1.0, Math.min(1.0, this.panStart.x - dx));
      const newPanY = Math.max(-1.0, Math.min(1.0, this.panStart.y - dy));

      this.updatePanTilt(newPanX, newPanY);
    });

    window.addEventListener('mouseup', () => {
      this.isDraggingVideo = false;
    });

    // Scroll wheel zoom on video viewport
    wrapper.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      let newZoom = Math.max(1.0, Math.min(5.0, parseFloat(this.zoomSlider.value) + delta));
      this.zoomSlider.value = newZoom.toFixed(2);
      this.updateZoom(newZoom);
    }, { passive: false });
  }

  updateZoom(zoom) {
    this.zoomValDisplay.innerText = `${zoom.toFixed(2)}x`;
    this.telemetryZoom.innerText = `${zoom.toFixed(2)}x`;
    this.highlightChip(zoom);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'set_zoom', zoom }));
    } else {
      this.sendPost('/api/zoom', { zoom });
    }
  }

  updatePanTilt(panX, panY) {
    this.telemetry.pan_x = panX;
    this.telemetry.pan_y = panY;

    this.panValDisplay.innerText = panX.toFixed(2);
    this.tiltValDisplay.innerText = panY.toFixed(2);

    // Update Puck position in 2D Pad
    const padXPercent = 50 + (panX * 50);
    const padYPercent = 50 + (panY * 50);
    this.padPuck.style.left = `${padXPercent}%`;
    this.padPuck.style.top = `${padYPercent}%`;

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'set_pan_tilt', pan_x: panX, pan_y: panY }));
    } else {
      this.sendPost('/api/pan-tilt', { pan_x: panX, pan_y: panY });
    }
  }

  resetPanTilt() {
    this.updatePanTilt(0.0, 0.0);
  }

  highlightChip(zoom) {
    this.chipButtons.forEach(chip => {
      const chipZ = parseFloat(chip.getAttribute('data-zoom'));
      chip.classList.toggle('active', Math.abs(chipZ - zoom) < 0.05);
    });
  }

  sendControl(name, value) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'set_control', name, value }));
    } else {
      this.sendPost('/api/controls', { name, value });
    }
  }

  initWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry') {
          this.handleTelemetry(msg.data);
        }
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    this.ws.onclose = () => {
      setTimeout(() => this.initWebSocket(), 2000);
    };
  }

  handleTelemetry(data) {
    this.telemetry = { ...this.telemetry, ...data };

    // Update Telemetry HUD
    this.telemetryFps.innerHTML = `<span class="live-dot"></span> ${data.fps || 30.0} FPS`;
    if (data.resolution) this.telemetryResolution.innerText = data.resolution;
    this.telemetryZoom.innerText = `${(data.curr_zoom || data.zoom || 1.0).toFixed(2)}x`;

    // Update Virtual Cam Button status
    const isVcamActive = data.virtual_cam_active;
    this.virtualCamToggleBtn.classList.toggle('active', isVcamActive);
    this.vcamBtnText.innerText = isVcamActive ? 'Virtual Cam: Live' : 'Virtual Cam: Off';
    this.vcamStatusPill.innerText = isVcamActive 
      ? `Virtual Cam: Active (${data.virtual_device})` 
      : 'Virtual Cam: Inactive';
    this.vcamStatusPill.style.color = isVcamActive ? 'var(--accent-green)' : 'var(--text-secondary)';

    // Update puck if not manually dragging
    if (!this.isDraggingPad && !this.isDraggingVideo) {
      const panX = data.pan_x || 0.0;
      const panY = data.pan_y || 0.0;
      this.panValDisplay.innerText = panX.toFixed(2);
      this.tiltValDisplay.innerText = panY.toFixed(2);
      this.padPuck.style.left = `${50 + (panX * 50)}%`;
      this.padPuck.style.top = `${50 + (panY * 50)}%`;
    }

    // Auto-zoom indicator
    const faceReticle = document.getElementById('faceReticle');
    if (faceReticle) {
      faceReticle.style.display = (data.auto_zoom && data.faces_detected > 0) ? 'flex' : 'none';
    }
  }

  async loadDevices() {
    try {
      const res = await this.sendGet('/api/devices');
      this.deviceSelect.innerHTML = '';
      if (res.devices) {
        res.devices.forEach(dev => {
          const opt = document.createElement('option');
          opt.value = dev.primary_node;
          opt.innerText = `${dev.card} (${dev.primary_node})`;
          if (dev.primary_node === res.active_device) opt.selected = true;
          this.deviceSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Error loading devices:', e);
    }
  }

  async loadControls() {
    try {
      const res = await this.sendGet('/api/controls');
      const ctrls = res.controls || {};

      // Sync focus
      if (ctrls.focus_automatic_continuous) {
        this.autoFocusToggle.checked = ctrls.focus_automatic_continuous.value === 1;
        this.manualFocusGroup.style.opacity = this.autoFocusToggle.checked ? '0.4' : '1';
        this.manualFocusGroup.style.pointerEvents = this.autoFocusToggle.checked ? 'none' : 'auto';
      }
      if (ctrls.focus_absolute) {
        this.focusSlider.min = ctrls.focus_absolute.min || 1;
        this.focusSlider.max = ctrls.focus_absolute.max || 1023;
        this.focusSlider.value = ctrls.focus_absolute.value || 320;
        this.focusValDisplay.innerText = this.focusSlider.value;
      }

      // Sync lighting
      if (ctrls.auto_exposure) {
        this.autoExposureToggle.checked = ctrls.auto_exposure.value === 3;
        this.manualExposureGroup.style.opacity = this.autoExposureToggle.checked ? '0.4' : '1';
        this.manualExposureGroup.style.pointerEvents = this.autoExposureToggle.checked ? 'none' : 'auto';
      }
      if (ctrls.exposure_time_absolute) {
        this.exposureSlider.min = ctrls.exposure_time_absolute.min || 1;
        this.exposureSlider.max = ctrls.exposure_time_absolute.max || 5000;
        this.exposureSlider.value = ctrls.exposure_time_absolute.value || 156;
        this.exposureValDisplay.innerText = this.exposureSlider.value;
      }
      if (ctrls.backlight_compensation) {
        this.backlightSlider.value = ctrls.backlight_compensation.value || 85;
        this.backlightValDisplay.innerText = this.backlightSlider.value;
      }
      if (ctrls.gain) {
        this.gainSlider.value = ctrls.gain.value || 0;
        this.gainValDisplay.innerText = this.gainSlider.value;
      }

      // Sync color
      if (ctrls.white_balance_automatic) {
        this.autoWbToggle.checked = ctrls.white_balance_automatic.value === 1;
        this.manualWbGroup.style.opacity = this.autoWbToggle.checked ? '0.4' : '1';
        this.manualWbGroup.style.pointerEvents = this.autoWbToggle.checked ? 'none' : 'auto';
      }
      if (ctrls.white_balance_temperature) {
        this.wbTempSlider.value = ctrls.white_balance_temperature.value || 4600;
        this.wbTempValDisplay.innerText = `${this.wbTempSlider.value}K`;
      }
      if (ctrls.brightness) {
        this.brightSlider.value = ctrls.brightness.value || 0;
        this.brightValDisplay.innerText = this.brightSlider.value;
      }
      if (ctrls.contrast) {
        this.contrastSlider.value = ctrls.contrast.value || 35;
        this.contrastValDisplay.innerText = this.contrastSlider.value;
      }
      if (ctrls.saturation) {
        this.satSlider.value = ctrls.saturation.value || 68;
        this.satValDisplay.innerText = this.satSlider.value;
      }
      if (ctrls.sharpness) {
        this.sharpSlider.value = ctrls.sharpness.value || 4;
        this.sharpValDisplay.innerText = this.sharpSlider.value;
      }
      if (ctrls.gamma) {
        this.gammaSlider.value = ctrls.gamma.value || 100;
        this.gammaValDisplay.innerText = this.gammaSlider.value;
      }
      if (ctrls.hue) {
        this.hueSlider.value = ctrls.hue.value || 0;
        this.hueValDisplay.innerText = this.hueSlider.value;
      }
    } catch (e) {
      console.error('Error loading controls:', e);
    }
  }

  async checkVirtualCamStatus() {
    try {
      const res = await this.sendGet('/api/virtual-cam/status');
      if (res.recommended_device) {
        this.vcamNodeDisplay.innerText = res.recommended_device;
      }
      if (res.setup_command) {
        this.setupCodeText.innerText = res.setup_command;
      }
    } catch (e) {
      console.error('Error checking virtual cam status:', e);
    }
  }

  async loadProfiles() {
    try {
      const profiles = await this.sendGet('/api/profiles');
      this.profileSelect.innerHTML = '<option value="">Preset Profiles...</option>';
      Object.keys(profiles).forEach(pName => {
        const opt = document.createElement('option');
        opt.value = pName;
        opt.innerText = pName;
        this.profileSelect.appendChild(opt);
      });
    } catch (e) {
      console.error('Error loading profiles:', e);
    }
  }

  async applyProfile(name) {
    try {
      await this.sendPost('/api/profiles/apply', { name });
      this.loadControls();
    } catch (e) {
      console.error('Error applying profile:', e);
    }
  }

  async saveCurrentProfile(name) {
    const settings = {
      zoom: parseFloat(this.zoomSlider.value),
      pan_x: this.telemetry.pan_x,
      pan_y: this.telemetry.pan_y,
      auto_zoom: this.autoZoomToggle.checked,
      v4l2: {
        brightness: parseInt(this.brightSlider.value),
        contrast: parseInt(this.contrastSlider.value),
        saturation: parseInt(this.satSlider.value),
        gain: parseInt(this.gainSlider.value),
        gamma: parseInt(this.gammaSlider.value),
        sharpness: parseInt(this.sharpSlider.value),
        focus_automatic_continuous: this.autoFocusToggle.checked ? 1 : 0,
        focus_absolute: parseInt(this.focusSlider.value),
        white_balance_automatic: this.autoWbToggle.checked ? 1 : 0,
        white_balance_temperature: parseInt(this.wbTempSlider.value)
      }
    };
    await this.sendPost('/api/profiles/save', { name, settings });
    this.loadProfiles();
  }

  // Helpers
  async sendGet(url) {
    const res = await fetch(url);
    return res.json();
  }

  async sendPost(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  window.app = new WebcamApp();
});
