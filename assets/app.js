// ==================== APPLICATION STATE ====================
    let isSimMode = false;
    let isConnected = false;
    const socket = io();

    // Rover + Live GPS coordinates
    let roverState = {
      dir: 'STOP',
      vx: 0,
      vy: 0,
      rpmL: 0,
      rpmR: 0,
      lat: 17.05420,
      lon: 74.26380
    };

    // 3-DOF Arm Joint State
    let armCur = { base: 90, shoulder: 115, elbow: 75 };
    let armTgt = { base: 90, shoulder: 115, elbow: 75 };
    let isAutoSpraying = false;
    let sprayParticles = [];

    // Plant Leaf CNN State
    let currentLeafSample = 'early_blight';
    let uploadedLeafImg = null;
    let scanLaserY = -1;
    let detectedBBox = null;
    let detectedTitle = '';
    const SIM_ORDER = ['early_blight', 'powdery_mildew', 'healthy'];
    let simIdx = 0;

    const LEAF_SAMPLES = {
      early_blight: {
        title: 'Early Blight',
        conf: 94.6,
        probs: { eb: 94.6, lb: 3.1, pm: 1.4, hl: 0.9 },
        sprayMs: 2600,
        bbox: { x: 135, y: 42, w: 145, h: 82, color: '#EF4444' },
        lesions: [
          { x: 185, y: 75, r: 16, c: '#5C3A21' },
          { x: 230, y: 92, r: 13, c: '#4A2C18' },
          { x: 165, y: 98, r: 10, c: '#6E472B' }
        ]
      },
      powdery_mildew: {
        title: 'Powdery Mildew',
        conf: 91.8,
        probs: { eb: 4.2, lb: 2.5, pm: 91.8, hl: 1.5 },
        sprayMs: 2200,
        bbox: { x: 140, y: 38, w: 150, h: 86, color: '#F59E0B' },
        lesions: [
          { x: 190, y: 68, r: 18, c: '#CBD5E1' },
          { x: 235, y: 88, r: 15, c: '#E2E8F0' },
          { x: 165, y: 95, r: 12, c: '#94A3B8' }
        ]
      },
      healthy: {
        title: 'Healthy Leaf',
        conf: 98.4,
        probs: { eb: 0.6, lb: 0.4, pm: 0.6, hl: 98.4 },
        sprayMs: 0,
        bbox: { x: 115, y: 28, w: 190, h: 105, color: '#10B981' },
        lesions: []
      }
    };

    // ==================== LOGGING & HARDWARE GATING ====================
    function logSerial(msg) {
      document.getElementById('serialLogTxt').textContent = `>_ ${msg}`;
    }

    let toastTimer = null;
    function requireActiveHardware() {
      if (isConnected || isSimMode) return true;
      const t = document.getElementById('toastAlert');
      t.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
      return false;
    }

    document.getElementById('toastCloseBtn').addEventListener('click', () => {
      document.getElementById('toastAlert').classList.remove('show');
    });

    // Send one event to the board. `type` is the Socket.IO event name.
    function sendWS(payload, quiet = false) {
      const { type, ...data } = payload;
      if (isConnected) socket.emit(type, data);
      if (!quiet) logSerial(`TX -> UNO Q: ${type}`);
    }

    // ==================== TOP-RIGHT SIM MODE & THEME SWITCHER ====================
    const simToggle = document.getElementById('simToggle');
    const simLabel = document.getElementById('simLabel');

    simToggle.addEventListener('click', () => {
      isSimMode = !isSimMode;
      simToggle.classList.toggle('active', isSimMode);
      simLabel.textContent = isSimMode ? 'Sim Mode: ON' : 'Sim Mode: OFF';

      if (isSimMode) {
        document.getElementById('toastAlert').classList.remove('show');
        logSerial('Sim Mode: ON — 60FPS Rover, 3-DOF Arm & CNN Auto-Sprinkler enabled');
      } else if (!isConnected) {
        roverState.dir = 'STOP';
        roverState.rpmL = 0;
        roverState.rpmR = 0;
        isAutoSpraying = false;
        detectedBBox = null;
        logSerial('Sim Mode: OFF — Hardware standby');
      }
    });

    document.getElementById('themeBtn').addEventListener('click', () => {
      const html = document.documentElement;
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      document.getElementById('themeIcon').textContent = next === 'dark' ? '☀️' : '🌙';
      document.getElementById('themeTxt').textContent = next === 'dark' ? 'Light Mode' : 'Dark Mode';
    });

    // ==================== SOCKET.IO CONNECTION ====================
    const linkPill = document.getElementById('linkPill');
    const linkTxt = document.getElementById('linkTxt');
    const connectBtn = document.getElementById('connectBtn');

    function setLink(up, text) {
      isConnected = up;
      linkPill.classList.toggle('up', up);
      linkTxt.textContent = text;
      connectBtn.textContent = up ? 'Reconnect' : 'Connect UNO Q';
    }

    socket.on('connect', () => { setLink(true, 'UNO Q linked'); logSerial('Connected to UNO Q'); });
    socket.on('disconnect', () => {
      setLink(false, 'Link lost');
      stopDriveLocal();
      logSerial('Link lost - rover stops after 0.5 s without commands');
    });
    socket.on('connect_error', () => setLink(false, 'Connecting…'));

    connectBtn.addEventListener('click', () => {
      if (socket.connected) socket.disconnect();
      setTimeout(() => socket.connect(), 150);
    });

    socket.on('telemetry', t => {
      if (t.gps && t.gps.fix) {
        roverState.lat = +t.gps.lat; roverState.lon = +t.gps.lon;
        document.getElementById('gpsLatTxt').textContent = `LAT: ${roverState.lat.toFixed(4)}° N`;
        document.getElementById('gpsLonTxt').textContent = `LON: ${roverState.lon.toFixed(4)}° E`;
      }
      if (!isSimMode && t.rpm) {
        roverState.rpmL = t.rpm[0]; roverState.rpmR = t.rpm[1];
        document.getElementById('rpmLeftTxt').textContent = `L: ${Math.round(t.rpm[0])} RPM`;
        document.getElementById('rpmRightTxt').textContent = `R: ${Math.round(t.rpm[1])} RPM`;
      }
    });
    socket.on('log', m => logSerial(m));
    socket.on('cnn_result', data => applyCNNResult(data));

    // ==================== CONTROL MODE TOGGLE (JOYSTICK vs D-PAD) ====================
    const tabJoy = document.getElementById('tabJoy');
    const tabDpad = document.getElementById('tabDpad');
    const joyContainer = document.getElementById('joyContainer');
    const dpadContainer = document.getElementById('dpadContainer');

    tabJoy.addEventListener('click', () => {
      tabJoy.classList.add('active');
      tabDpad.classList.remove('active');
      joyContainer.classList.add('active-control');
      dpadContainer.classList.remove('active-control');
    });

    tabDpad.addEventListener('click', () => {
      tabDpad.classList.add('active');
      tabJoy.classList.remove('active');
      dpadContainer.classList.add('active-control');
      joyContainer.classList.remove('active-control');
    });

    // ==================== LOCOMOTION: D-PAD & JOYSTICK ====================
    // Board watchdog stops the rover if no "drive" arrives for 0.5 s,
    // so the current command is re-sent at 10 Hz while it is non-zero.
    let driveCmd = { linear: 0, angular: 0 };
    let driveTimer = null;

    function pushDrive() { if (isConnected) socket.emit('drive', driveCmd); }
    function setDriveCmd(linear, angular) {
      driveCmd = { linear, angular };
      pushDrive();
      const moving = linear !== 0 || angular !== 0;
      if (moving && !driveTimer) driveTimer = setInterval(pushDrive, 100);
      if (!moving && driveTimer) { clearInterval(driveTimer); driveTimer = null; }
    }
    function stopDriveLocal() {
      setDriveCmd(0, 0);
      roverState.dir = 'STOP'; roverState.vx = 0; roverState.vy = 0;
      roverState.rpmL = 0; roverState.rpmR = 0;
      document.getElementById('roverStateTxt').textContent = 'Standby';
      document.getElementById('rpmLeftTxt').textContent = 'L: 0 RPM';
      document.getElementById('rpmRightTxt').textContent = 'R: 0 RPM';
      document.getElementById('roverVecTxt').textContent = 'Idle';
    }

    function setRoverDrive(dir) {
      if (!requireActiveHardware()) return;
      roverState.dir = dir;
      // linear: +forward, angular: +left (matches main.py)
      let lin = 0, ang = 0;
      if (dir === 'FORWARD')       { roverState.rpmL = 120;  roverState.rpmR = 120;  roverState.vx = 0;  roverState.vy = 1;  lin = 0.6; }
      else if (dir === 'BACKWARD') { roverState.rpmL = -120; roverState.rpmR = -120; roverState.vx = 0;  roverState.vy = -1; lin = -0.6; }
      else if (dir === 'LEFT')     { roverState.rpmL = -95;  roverState.rpmR = 95;   roverState.vx = -1; roverState.vy = 0;  ang = 0.6; }
      else if (dir === 'RIGHT')    { roverState.rpmL = 95;   roverState.rpmR = -95;  roverState.vx = 1;  roverState.vy = 0;  ang = -0.6; }
      else                         { roverState.rpmL = 0; roverState.rpmR = 0; roverState.vx = 0; roverState.vy = 0; }

      document.getElementById('roverStateTxt').textContent = dir === 'STOP' ? 'Standby' : dir;
      document.getElementById('rpmLeftTxt').textContent = `L: ${roverState.rpmL} RPM`;
      document.getElementById('rpmRightTxt').textContent = `R: ${roverState.rpmR} RPM`;
      document.getElementById('roverVecTxt').textContent = dir === 'STOP' ? 'Idle' : dir;
      setDriveCmd(lin, ang);
    }

    function emergencyStop() {
      stopDriveLocal();
      isAutoSpraying = false;
      if (isConnected) socket.emit('estop', {});
      logSerial('EMERGENCY STOP — All motors & nozzle halted');
    }

    // D-pad (pointer events: mouse + touch, pointer captured so sliding off the button still releases)
    document.querySelectorAll('.dpad-btn').forEach(btn => {
      const dir = btn.dataset.dir;
      btn.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        if (btn.setPointerCapture) btn.setPointerCapture(e.pointerId);
        btn.classList.add('active');
        if (dir === 'STOP') emergencyStop(); else setRoverDrive(dir);
      });
      const up = () => {
        btn.classList.remove('active');
        if (dir !== 'STOP') setRoverDrive('STOP');
      };
      btn.addEventListener('pointerup', up);
      btn.addEventListener('pointercancel', up);
    });

    // Emergency stop works even when offline
    document.getElementById('emergencyStopBtn').addEventListener('click', emergencyStop);

    // Keyboard WASD / arrows, Space = stop
    const heldKeys = new Set();
    const KEYDIR = { w:'FORWARD', arrowup:'FORWARD', s:'BACKWARD', arrowdown:'BACKWARD',
                     a:'LEFT', arrowleft:'LEFT', d:'RIGHT', arrowright:'RIGHT' };
    window.addEventListener('keydown', (e) => {
      if (document.activeElement.tagName === 'INPUT') return;
      const k = e.key.toLowerCase();
      if (k === ' ') { e.preventDefault(); emergencyStop(); return; }
      if (KEYDIR[k] && !e.repeat) { heldKeys.add(k); setRoverDrive(KEYDIR[k]); }
    });
    window.addEventListener('keyup', (e) => {
      const k = e.key.toLowerCase();
      if (!KEYDIR[k]) return;
      heldKeys.delete(k);
      if (heldKeys.size) setRoverDrive(KEYDIR[[...heldKeys].pop()]);
      else setRoverDrive('STOP');
    });
    // Never keep driving if the tab/app loses focus or is hidden (phone lock, app switch)
    window.addEventListener('blur', () => { heldKeys.clear(); if (driveTimer) emergencyStop(); });
    document.addEventListener('visibilitychange', () => { if (document.hidden && driveTimer) emergencyStop(); });

    // 360 Virtual Joystick
    const joyBase = document.getElementById('joyBase');
    const joyStick = document.getElementById('joyStick');
    let joyDragging = false;

    function handleJoyMove(clientX, clientY) {
      if (!joyDragging) return;
      if (!requireActiveHardware()) { joyDragging = false; return; }
      const rect = joyBase.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const maxR = rect.width * 0.32;          // travel radius scales with the pad size
      let dx = clientX - cx;
      let dy = clientY - cy;
      const dist = Math.hypot(dx, dy);
      if (dist > maxR) {
        dx = (dx / dist) * maxR;
        dy = (dy / dist) * maxR;
      }
      joyStick.style.transform = `translate(${dx}px, ${dy}px)`;

      const nx = +(dx / maxR).toFixed(2);
      const ny = +(-dy / maxR).toFixed(2);
      const deg = Math.round((Math.atan2(ny, nx) * 180) / Math.PI);

      document.getElementById('joyX').textContent = `X-Axis: ${nx.toFixed(2)}`;
      document.getElementById('joyY').textContent = `Y-Axis: ${ny.toFixed(2)}`;
      document.getElementById('joyDeg').textContent = `Heading: ${deg}°`;

      roverState.vx = nx;
      roverState.vy = ny;
      roverState.rpmL = Math.round((ny + nx * 0.7) * 130);
      roverState.rpmR = Math.round((ny - nx * 0.7) * 130);
      roverState.dir = Math.hypot(nx, ny) > 0.1 ? 'JOYSTICK' : 'STOP';

      document.getElementById('roverStateTxt').textContent = roverState.dir;
      document.getElementById('rpmLeftTxt').textContent = `L: ${roverState.rpmL} RPM`;
      document.getElementById('rpmRightTxt').textContent = `R: ${roverState.rpmR} RPM`;
      document.getElementById('roverVecTxt').textContent = `VEC: ${nx}, ${ny}`;
      setDriveCmd(ny, -nx);   // linear = forward, angular = left
    }

    function resetJoystick() {
      if (!joyDragging) return;
      joyDragging = false;
      joyStick.style.transform = `translate(0px, 0px)`;
      document.getElementById('joyX').textContent = `X-Axis: 0.00`;
      document.getElementById('joyY').textContent = `Y-Axis: 0.00`;
      document.getElementById('joyDeg').textContent = `Heading: 0°`;
      if (isConnected || isSimMode) setRoverDrive('STOP');
    }

    joyBase.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      if (joyBase.setPointerCapture) joyBase.setPointerCapture(e.pointerId);
      joyDragging = true;
      handleJoyMove(e.clientX, e.clientY);
    });
    window.addEventListener('pointermove', (e) => handleJoyMove(e.clientX, e.clientY));
    window.addEventListener('pointerup', resetJoystick);
    window.addEventListener('pointercancel', resetJoystick);

    // ==================== PANEL 2: 3-DOF ARM KINEMATICS ====================
    const sBase = document.getElementById('sliderBase');
    const sShoulder = document.getElementById('sliderShoulder');
    const sElbow = document.getElementById('sliderElbow');

    let armSendTimer = null;
    function sendArmThrottled() {
      if (armSendTimer) return;
      armSendTimer = setTimeout(() => {
        armSendTimer = null;
        sendWS({ type: 'arm', joints: [armTgt.base, armTgt.shoulder, armTgt.elbow] }, true);
      }, 50);
    }

    function updateArmTarget(base, shoulder, elbow, label = 'Custom') {
      if (!requireActiveHardware()) {
        sBase.value = armTgt.base;
        sShoulder.value = armTgt.shoulder;
        sElbow.value = armTgt.elbow;
        return;
      }
      armTgt = { base: +base, shoulder: +shoulder, elbow: +elbow };
      sBase.value = armTgt.base;
      sShoulder.value = armTgt.shoulder;
      sElbow.value = armTgt.elbow;
      document.getElementById('valBase').textContent = `${armTgt.base}°`;
      document.getElementById('valShoulder').textContent = `${armTgt.shoulder}°`;
      document.getElementById('valElbow').textContent = `${armTgt.elbow}°`;
      document.getElementById('armPoseTxt').textContent = `Pose: ${label}`;
      document.getElementById('armPoseChip').textContent = `POSE: ${label.toUpperCase()}`;
      document.getElementById('yawChip').textContent = `BASE YAW: ${armTgt.base}°`;
      sendArmThrottled();
    }

    [sBase, sShoulder, sElbow].forEach(el => {
      el.addEventListener('input', () => updateArmTarget(sBase.value, sShoulder.value, sElbow.value, 'Manual'));
    });

    const POSES = {
      HOME:  { base: 90, shoulder: 115, elbow: 75 },
      SCAN:  { base: 90, shoulder: 85,  elbow: 110 },
      SPRAY: { base: 90, shoulder: 68,  elbow: 95 },
      STOW:  { base: 90, shoulder: 148, elbow: 35 }
    };

    document.querySelectorAll('[data-pose]').forEach(btn => {
      btn.addEventListener('click', () => {
        const p = POSES[btn.dataset.pose];
        updateArmTarget(p.base, p.shoulder, p.elbow, btn.dataset.pose);
      });
    });

    // ==================== PANEL 3: PLANT LEAF CNN & AUTO-SPRAY ====================
    // ---- Live camera feed (MJPEG from the ROS 2 node, see ros/mjpeg_server.py) ----
    const FEED_PORT = 8081;
    const FEED_BASE = window.FEED_BASE || `http://${location.hostname}:${FEED_PORT}`;
    const feedImg = document.getElementById('liveFeedImg');
    const feedStatus = document.getElementById('feedStatus');
    const feedBtn = document.getElementById('liveFeedBtn');
    const leafCanvasEl = document.getElementById('leafCanvas');
    let liveOn = false, feedRetry = null;

    function showFeedStatus(txt) { feedStatus.textContent = txt; feedStatus.hidden = !txt; }

    function startFeed() {
      clearTimeout(feedRetry);
      showFeedStatus('Connecting to camera…');
      feedImg.src = `${FEED_BASE}/stream.mjpg?t=${Date.now()}`;
    }

    function setLiveFeed(on) {
      if (on === liveOn) return;
      liveOn = on;
      feedBtn.classList.toggle('active', on);
      feedBtn.textContent = on ? '⏹ Stop Feed' : '📹 Live Feed';
      leafCanvasEl.hidden = on;
      feedImg.hidden = !on;
      if (on) {
        uploadedLeafImg = null; detectedBBox = null;
        startFeed();
        logSerial('Live feed: ON');
      } else {
        clearTimeout(feedRetry);
        feedImg.removeAttribute('src');      // closes the HTTP stream so the board stops encoding
        showFeedStatus('');
        logSerial('Live feed: OFF');
      }
    }

    feedImg.addEventListener('load', () => showFeedStatus(''));
    feedImg.addEventListener('error', () => {
      if (!liveOn) return;
      showFeedStatus('No signal — is the camera stream node running?');
      feedRetry = setTimeout(() => { if (liveOn) startFeed(); }, 3000);
    });
    feedBtn.addEventListener('click', () => setLiveFeed(!liveOn));

    // Save CPU/bandwidth on the board while the tab is hidden
    document.addEventListener('visibilitychange', () => {
      if (!liveOn) return;
      if (document.hidden) { clearTimeout(feedRetry); feedImg.removeAttribute('src'); }
      else startFeed();
    });

    document.getElementById('leafUpload').addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const img = new Image();
      img.onload = () => { setLiveFeed(false); uploadedLeafImg = img; detectedBBox = null; };
      img.src = URL.createObjectURL(file);
    });

    function setPipelineStep(step) {
      [1, 2, 3, 4].forEach(n => {
        document.getElementById(`step${n}`).classList.toggle('active', n <= step);
      });
    }

    // Applies a CNN result (from the board, or from the local sim samples)
    function applyCNNResult(res) {
      if (res.sprayMs == null) res.sprayMs = res.spray_ms || 0;
      if (res.sample && LEAF_SAMPLES[res.sample]) currentLeafSample = res.sample;
      if (!res.bbox) res.bbox = LEAF_SAMPLES[currentLeafSample].bbox;
      setPipelineStep(3);
      detectedBBox = res.bbox;
      detectedTitle = res.title || '';
      scanLaserY = -1;
      if (!isConnected) document.getElementById('cpuTxt').textContent = '7%';

      document.getElementById('confPctTxt').textContent = `${Math.round(res.conf)}%`;
      const offset = 201 - (201 * res.conf) / 100;
      const arc = document.getElementById('confArc');
      arc.style.strokeDashoffset = offset;
      arc.style.stroke = res.sprayMs > 0 ? '#F59E0B' : '#10B981';

      document.getElementById('diseaseNameTxt').textContent = res.title.toUpperCase();

      setTimeout(() => {
        setPipelineStep(4);
        const banner = document.getElementById('nozzleBanner');
        const stateTxt = document.getElementById('nozzleStateTxt');

        if (res.sprayMs > 0) {
          updateArmTarget(90, 68, 95, 'Auto-Spray');
          isAutoSpraying = true;
          banner.className = 'nozzle-auto-banner spraying';
          stateTxt.textContent = `AUTO-SPRAYING (${(res.sprayMs / 1000).toFixed(1)}s)`;
          logSerial(`CNN: ${res.title} (${res.conf}%) -> Auto-Spraying for ${res.sprayMs}ms`);

          setTimeout(() => {
            isAutoSpraying = false;
            banner.className = 'nozzle-auto-banner';
            stateTxt.textContent = 'SPRAY COMPLETE • STANDBY';
          }, res.sprayMs);
        } else {
          isAutoSpraying = false;
          banner.className = 'nozzle-auto-banner bypassed';
          stateTxt.textContent = 'BYPASSED • HEALTHY LEAF';
          logSerial(`CNN: Healthy Leaf (${res.conf}%) -> Sprinkler bypassed`);
        }
      }, 350);
    }

    document.getElementById('scanLeafBtn').addEventListener('click', () => {
      if (!requireActiveHardware()) return;
      detectedBBox = null;
      scanLaserY = 0;
      setPipelineStep(1);
      if (!isConnected) document.getElementById('cpuTxt').textContent = '44%';
      updateArmTarget(90, 85, 110, 'Scanning');

      setTimeout(() => setPipelineStep(2), 400);
      if (isConnected && !isSimMode) {
        // Real inference on the board: send the live frame (or an uploaded image) if there is one.
        let image = null, source = 'arm_camera';
        const frameSrc = (liveOn && feedImg.naturalWidth) ? feedImg : uploadedLeafImg;
        if (frameSrc) {
          const c = document.createElement('canvas');
          c.width = 224; c.height = 224;
          try {
            c.getContext('2d').drawImage(frameSrc, 0, 0, 224, 224);
            image = c.toDataURL('image/jpeg', 0.8);
            source = frameSrc === feedImg ? 'live_feed' : 'upload';
          } catch (e) { image = null; }
        }
        socket.emit('cnn_predict', { source, sample: null, image });
      } else {
        currentLeafSample = SIM_ORDER[simIdx++ % SIM_ORDER.length];
        setTimeout(() => applyCNNResult(LEAF_SAMPLES[currentLeafSample]), 1150);
      }
    });

    // ==================== 60FPS CANVAS RENDERING & LIVE GPS UPDATE ====================
    const roverCanvas = document.getElementById('roverCanvas');
    const rCtx = roverCanvas.getContext('2d');
    const armCanvas = document.getElementById('armCanvas');
    const aCtx = armCanvas.getContext('2d');
    const leafCanvas = document.getElementById('leafCanvas');
    const lCtx = leafCanvas.getContext('2d');

    function updateLiveGPS() {
      if ((isSimMode && !isConnected) && (Math.abs(roverState.rpmL) > 0 || Math.abs(roverState.rpmR) > 0)) {
        roverState.lat += roverState.vy * 0.000004;
        roverState.lon += roverState.vx * 0.000004;
        document.getElementById('gpsLatTxt').textContent = `LAT: ${roverState.lat.toFixed(4)}° N`;
        document.getElementById('gpsLonTxt').textContent = `LON: ${roverState.lon.toFixed(4)}° E`;
      }
    }

    function drawRoverCanvas() {
      const W = roverCanvas.width, H = roverCanvas.height;
      rCtx.clearRect(0, 0, W, H);

      rCtx.strokeStyle = 'rgba(16, 185, 129, 0.25)';
      rCtx.setLineDash([8, 8]);
      rCtx.beginPath();
      rCtx.moveTo(95, 0); rCtx.lineTo(95, H);
      rCtx.moveTo(W - 95, 0); rCtx.lineTo(W - 95, H);
      rCtx.stroke();
      rCtx.setLineDash([]);

      const cx = W / 2, cy = H / 2 + 6;
      rCtx.save();
      rCtx.translate(cx, cy);

      [-56, 38].forEach((tx, idx) => {
        rCtx.fillStyle = '#1E293B';
        rCtx.strokeStyle = '#475569';
        rCtx.lineWidth = 1.5;
        rCtx.beginPath();
        rCtx.roundRect(tx, -46, 18, 92, 5);
        rCtx.fill();
        rCtx.stroke();

        rCtx.strokeStyle = '#00B5BC';
        rCtx.lineWidth = 2;
        const rpm = (isConnected || isSimMode) ? (idx === 0 ? roverState.rpmL : roverState.rpmR) : 0;
        const off = ((Date.now() * rpm * 0.004) % 12 + 12) % 12;
        for (let y = -40 + off; y < 42; y += 12) {
          rCtx.beginPath();
          rCtx.moveTo(tx + 3, y);
          rCtx.lineTo(tx + 15, y);
          rCtx.stroke();
        }
      });

      rCtx.fillStyle = '#0F172A';
      rCtx.strokeStyle = '#00979D';
      rCtx.lineWidth = 2;
      rCtx.beginPath();
      rCtx.roundRect(-38, -40, 76, 80, 8);
      rCtx.fill();
      rCtx.stroke();

      rCtx.fillStyle = 'rgba(0, 151, 157, 0.22)';
      rCtx.fillRect(-26, -24, 52, 48);

      rCtx.strokeStyle = '#38BDF8';
      rCtx.beginPath();
      rCtx.arc(0, 0, 13, 0, Math.PI * 2);
      rCtx.stroke();

      if ((isConnected || isSimMode) && (Math.abs(roverState.rpmL) > 0 || Math.abs(roverState.rpmR) > 0)) {
        rCtx.strokeStyle = 'rgba(56, 189, 248, 0.6)';
        for (let r = 14; r <= 34; r += 10) {
          rCtx.beginPath();
          rCtx.arc(0, -44, r, -Math.PI * 0.75, -Math.PI * 0.25);
          rCtx.stroke();
        }
      }
      rCtx.restore();
    }

    function drawArmCanvas() {
      const W = armCanvas.width, H = armCanvas.height;
      aCtx.clearRect(0, 0, W, H);

      if (isConnected || isSimMode) {
        armCur.base += (armTgt.base - armCur.base) * 0.12;
        armCur.shoulder += (armTgt.shoulder - armCur.shoulder) * 0.12;
        armCur.elbow += (armTgt.elbow - armCur.elbow) * 0.12;
      }

      const light = document.documentElement.getAttribute('data-theme') === 'light';

      // Ground line
      aCtx.strokeStyle = light ? '#CBD5E1' : '#222D36';
      aCtx.lineWidth = 2;
      aCtx.beginPath();
      aCtx.moveTo(20, H - 16);
      aCtx.lineTo(W - 20, H - 16);
      aCtx.stroke();

      // Target Plant on Right Side in front of the arm
      const plantX = 335, plantY = H - 16;
      aCtx.strokeStyle = '#15803D';
      aCtx.lineWidth = 3;
      aCtx.beginPath();
      aCtx.moveTo(plantX, plantY);
      aCtx.lineTo(plantX, plantY - 95);
      aCtx.stroke();
      [{dx: -18, dy: -72, r: -0.35}, {dx: 16, dy: -54, r: 0.35}].forEach(lf => {
        aCtx.save();
        aCtx.translate(plantX + lf.dx, plantY + lf.dy);
        aCtx.rotate(lf.r);
        aCtx.fillStyle = isAutoSpraying ? '#10B981' : '#16A34A';
        aCtx.beginPath();
        aCtx.ellipse(0, 0, 16, 8, 0, 0, Math.PI * 2);
        aCtx.fill();
        aCtx.restore();
      });

      const baseX = 165, baseY = H - 22;
      aCtx.fillStyle = '#1E293B';
      aCtx.strokeStyle = '#00979D';
      aCtx.lineWidth = 2;
      aCtx.beginPath();
      aCtx.roundRect(baseX - 48, baseY, 96, 16, 4);
      aCtx.fill();
      aCtx.stroke();

      aCtx.fillStyle = '#00979D';
      aCtx.fillRect(baseX - 18, baseY - 10, 36, 10);

      const L1 = 64, L2 = 56;
      const shRad = (-armCur.shoulder * Math.PI) / 180;
      const j1x = baseX + Math.cos(shRad) * L1;
      const j1y = (baseY - 10) + Math.sin(shRad) * L1;

      const elRad = shRad + ((90 - armCur.elbow) * Math.PI) / 180;
      const j2x = j1x + Math.cos(elRad) * L2;
      const j2y = j1y + Math.sin(elRad) * L2;

      aCtx.strokeStyle = '#00B5BC';
      aCtx.lineWidth = 9;
      aCtx.lineCap = 'round';
      aCtx.beginPath();
      aCtx.moveTo(baseX, baseY - 10);
      aCtx.lineTo(j1x, j1y);
      aCtx.stroke();

      aCtx.strokeStyle = '#38BDF8';
      aCtx.lineWidth = 7;
      aCtx.beginPath();
      aCtx.moveTo(j1x, j1y);
      aCtx.lineTo(j2x, j2y);
      aCtx.stroke();

      [[baseX, baseY - 10], [j1x, j1y]].forEach(([jx, jy]) => {
        aCtx.fillStyle = '#0F172A';
        aCtx.strokeStyle = '#F8FAFC';
        aCtx.lineWidth = 2;
        aCtx.beginPath();
        aCtx.arc(jx, jy, 6, 0, Math.PI * 2);
        aCtx.fill();
        aCtx.stroke();
      });

      aCtx.save();
      aCtx.translate(j2x, j2y);
      aCtx.rotate(elRad);

      aCtx.fillStyle = 'rgba(56, 189, 248, 0.18)';
      aCtx.beginPath();
      aCtx.moveTo(12, -3);
      aCtx.lineTo(72, -26);
      aCtx.lineTo(72, 20);
      aCtx.closePath();
      aCtx.fill();

      aCtx.fillStyle = '#0F172A';
      aCtx.strokeStyle = '#00B5BC';
      aCtx.lineWidth = 2;
      aCtx.beginPath();
      aCtx.roundRect(-6, -9, 22, 18, 4);
      aCtx.fill();
      aCtx.stroke();

      aCtx.fillStyle = '#F59E0B';
      aCtx.fillRect(16, 2, 6, 5);
      aCtx.restore();

      if (isAutoSpraying && (isConnected || isSimMode)) {
        for (let i = 0; i < 3; i++) {
          sprayParticles.push({
            x: j2x + Math.cos(elRad) * 20,
            y: j2y + Math.sin(elRad) * 20,
            vx: Math.cos(elRad + (Math.random() - 0.5) * 0.45) * (3.5 + Math.random() * 2),
            vy: Math.sin(elRad + (Math.random() - 0.5) * 0.45) * (3.5 + Math.random() * 2),
            alpha: 1
          });
        }
      }

      for (let i = sprayParticles.length - 1; i >= 0; i--) {
        const p = sprayParticles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.08;
        p.alpha -= 0.03;
        if (p.alpha <= 0) {
          sprayParticles.splice(i, 1);
          continue;
        }
        aCtx.fillStyle = `rgba(16, 185, 129, ${p.alpha})`;
        aCtx.beginPath();
        aCtx.arc(p.x, p.y, 2.6, 0, Math.PI * 2);
        aCtx.fill();
      }
    }

    function drawLeafCanvas() {
      const W = leafCanvas.width, H = leafCanvas.height;
      lCtx.clearRect(0, 0, W, H);

      if (uploadedLeafImg) {
        lCtx.drawImage(uploadedLeafImg, 0, 0, W, H);
      } else {
        const sample = LEAF_SAMPLES[currentLeafSample];
        lCtx.save();
        const grad = lCtx.createLinearGradient(110, 25, 310, 135);
        grad.addColorStop(0, '#15803D');
        grad.addColorStop(0.6, '#166534');
        grad.addColorStop(1, '#14532D');
        lCtx.fillStyle = grad;
        lCtx.beginPath();
        lCtx.moveTo(110, 86);
        lCtx.quadraticCurveTo(190, 14, 310, 82);
        lCtx.quadraticCurveTo(190, 152, 110, 86);
        lCtx.fill();

        lCtx.strokeStyle = 'rgba(187, 247, 208, 0.5)';
        lCtx.lineWidth = 2;
        lCtx.beginPath();
        lCtx.moveTo(95, 86);
        lCtx.lineTo(295, 83);
        lCtx.stroke();

        sample.lesions.forEach(ls => {
          lCtx.fillStyle = ls.c;
          lCtx.beginPath();
          lCtx.arc(ls.x, ls.y, ls.r, 0, Math.PI * 2);
          lCtx.fill();
          lCtx.strokeStyle = '#F59E0B';
          lCtx.lineWidth = 1;
          lCtx.stroke();
        });
        lCtx.restore();
      }

      if (scanLaserY >= 0) {
        scanLaserY = (scanLaserY + 3.4) % H;
        lCtx.strokeStyle = '#00B5BC';
        lCtx.lineWidth = 2.5;
        lCtx.beginPath();
        lCtx.moveTo(0, scanLaserY);
        lCtx.lineTo(W, scanLaserY);
        lCtx.stroke();
      }

      if (detectedBBox) {
        lCtx.strokeStyle = detectedBBox.color;
        lCtx.lineWidth = 2;
        lCtx.strokeRect(detectedBBox.x, detectedBBox.y, detectedBBox.w, detectedBBox.h);
        lCtx.fillStyle = detectedBBox.color;
        lCtx.font = 'bold 10.5px IBM Plex Mono';
        lCtx.fillText(detectedTitle.toUpperCase(), detectedBBox.x + 4, detectedBBox.y - 5);
      }
    }

    function animateLoop() {
      updateLiveGPS();
      drawRoverCanvas();
      drawArmCanvas();
      drawLeafCanvas();
      requestAnimationFrame(animateLoop);
    }
    animateLoop();
// ==================== SYSTEM RESOURCES LOGGER ====================
(function () {
  const LIVE_MAX = 60;                 // 60 samples x 5 s = 5 min
  const modal = document.getElementById('resModal');
  const hint = document.getElementById('resHint');
  const liveDot = document.getElementById('resLiveDot');
  const charts = {
    cpu: { canvas: document.getElementById('resCpuCanvas'), no: document.getElementById('resCpuNo'),
           color: '#38BDF8', live: [], hist: { '1h': [], '1d': [] }, hover: -1, key: 'cpu' },
    mem: { canvas: document.getElementById('resMemCanvas'), no: document.getElementById('resMemNo'),
           color: '#10B981', live: [], hist: { '1h': [], '1d': [] }, hover: -1, key: 'mem' },
  };
  let tab = 'live', dotTimer = null;

  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function fmt(ts, mode) {
    const d = new Date(ts);
    if (mode === 'live') return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (mode === '1h') return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleTimeString([], { hour: '2-digit' });
  }
  const pts = c => tab === 'live' ? c.live : c.hist[tab];

  function draw(c) {
    const cv = c.canvas, data = pts(c);
    const dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    c.no.style.display = data.length ? 'none' : 'flex';
    if (!data.length) return;

    const L = 32, R = 10, T = 8, B = 26, pw = W - L - R, ph = H - T - B;
    const muted = cssVar('--text-muted'), grid = cssVar('--border-subtle');
    g.font = '10px "IBM Plex Mono", monospace';
    g.textBaseline = 'middle'; g.textAlign = 'right';
    for (let v = 0; v <= 100; v += 25) {
      const y = T + ph - (v / 100) * ph;
      g.strokeStyle = grid; g.lineWidth = 1;
      g.beginPath(); g.moveTo(L, y); g.lineTo(W - R, y); g.stroke();
      g.fillStyle = muted; g.fillText(String(v), L - 6, y);
    }
    const n = data.length;
    const xAt = i => n === 1 ? L + pw / 2 : L + (i / (n - 1)) * pw;
    const yAt = v => T + ph - (Math.max(0, Math.min(100, v)) / 100) * ph;

    // fill + line
    const grad = g.createLinearGradient(0, T, 0, T + ph);
    grad.addColorStop(0, c.color + '55'); grad.addColorStop(1, c.color + '05');
    g.beginPath();
    data.forEach((p, i) => i ? g.lineTo(xAt(i), yAt(p.value)) : g.moveTo(xAt(i), yAt(p.value)));
    g.strokeStyle = c.color; g.lineWidth = 2; g.stroke();
    g.lineTo(xAt(n - 1), T + ph); g.lineTo(xAt(0), T + ph); g.closePath();
    g.fillStyle = grad; g.fill();
    if (n === 1) { g.beginPath(); g.arc(xAt(0), yAt(data[0].value), 3, 0, 7); g.fillStyle = c.color; g.fill(); }

    // x labels (about 6)
    g.fillStyle = muted; g.textAlign = 'center'; g.textBaseline = 'top';
    const step = Math.max(1, Math.ceil(n / 6));
    for (let i = 0; i < n; i += step) g.fillText(fmt(data[i].ts, tab), xAt(i), T + ph + 8);

    // hover tooltip
    if (c.hover >= 0 && c.hover < n) {
      const p = data[c.hover], x = xAt(c.hover), y = yAt(p.value);
      g.strokeStyle = muted; g.setLineDash([3, 3]);
      g.beginPath(); g.moveTo(x, T); g.lineTo(x, T + ph); g.stroke(); g.setLineDash([]);
      g.beginPath(); g.arc(x, y, 4, 0, 7); g.fillStyle = c.color; g.fill();
      const txt = `${fmt(p.ts, tab)} - ${Number(p.value).toFixed(1)} %`;
      g.font = '11px "IBM Plex Mono", monospace';
      const tw = g.measureText(txt).width + 14;
      const bx = Math.min(Math.max(x - tw / 2, L), W - R - tw), by = Math.max(y - 30, T);
      g.fillStyle = cssVar('--bg-control'); g.strokeStyle = cssVar('--border-color');
      g.beginPath(); g.roundRect(bx, by, tw, 20, 4); g.fill(); g.stroke();
      g.fillStyle = cssVar('--text-main'); g.textAlign = 'left'; g.textBaseline = 'middle';
      g.fillText(txt, bx + 7, by + 10);
    }
  }
  const drawAll = () => { if (modal.classList.contains('show')) Object.values(charts).forEach(draw); };

  Object.values(charts).forEach(c => {
    c.canvas.addEventListener('mousemove', e => {
      const data = pts(c); if (!data.length) return;
      const r = c.canvas.getBoundingClientRect(), L = 32, R = 10, pw = r.width - L - R;
      const f = (e.clientX - r.left - L) / pw;
      c.hover = data.length === 1 ? 0 : Math.max(0, Math.min(data.length - 1, Math.round(f * (data.length - 1))));
      draw(c);
    });
    c.canvas.addEventListener('mouseleave', () => { c.hover = -1; draw(c); });
  });

  // ---- live data (board pushes every 5 s) ----
  function pushLive(c, msg) {
    if (!msg || msg.ts == null || msg.value == null) return;
    c.live.push({ ts: msg.ts, value: +msg.value });
    if (c.live.length > LIVE_MAX) c.live.shift();
  }
  function liveTick() {
    liveDot.classList.add('flash');
    clearTimeout(dotTimer);
    dotTimer = setTimeout(() => liveDot.classList.remove('flash'), 10000);
    if (tab === 'live') drawAll();
  }
  socket.on('cpu_usage', m => {
    pushLive(charts.cpu, m);
    if (m && m.value != null) document.getElementById('cpuTxt').textContent = `${Math.round(m.value)}%`;
    liveTick();
  });
  socket.on('memory_usage', m => {
    pushLive(charts.mem, m);
    if (m && m.used_gb != null) document.getElementById('ramTxt').textContent = `${m.used_gb.toFixed(2)}/${m.total_gb.toFixed(2)} GB`;
    liveTick();
  });

  // Sim mode: synthetic live data so the panel can be demoed without the board
  let simCpu = 12, simMem = 41;
  setInterval(() => {
    if (!isSimMode || isConnected) return;
    simCpu = Math.max(2, Math.min(95, simCpu + (Math.random() - 0.5) * 12));
    simMem = Math.max(20, Math.min(90, simMem + (Math.random() - 0.5) * 3));
    const ts = Date.now();
    pushLive(charts.cpu, { ts, value: simCpu });
    pushLive(charts.mem, { ts, value: simMem });
    if (tab === 'live') drawAll();
  }, 2000);

  // ---- history (REST on the board) ----
  async function fetchSamples(resource, start, win, keep) {
    try {
      const r = await fetch(`/get_samples/${resource}/${start}/${win}`);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      return Array.isArray(d) ? d.slice(-keep) : [];
    } catch (e) { return []; }
  }
  async function loadHistory(which) {
    const [start, win, keep] = which === '1h' ? ['-1h', '5m', 12] : ['-1d', '1h', 24];
    hint.textContent = 'Loading…';
    const [cpu, mem] = await Promise.all([
      fetchSamples('cpu', start, win, keep), fetchSamples('mem', start, win, keep)]);
    charts.cpu.hist[which] = cpu; charts.mem.hist[which] = mem;
    hint.textContent = which === '1h' ? 'Last hour, 5 minute averages.' : 'Last 24 hours, 1 hour averages.';
    if (tab === which) drawAll();
  }

  // ---- tabs / open / close ----
  document.querySelectorAll('.res-tab').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.res-tab').forEach(x => x.classList.toggle('active', x === b));
    tab = b.dataset.rtab;
    Object.values(charts).forEach(c => c.hover = -1);
    if (tab === 'live') hint.textContent = 'Live: sampled every 5 s from the UNO Q.';
    drawAll();
    if (tab !== 'live') loadHistory(tab);
  }));
  const open = () => { modal.classList.add('show'); modal.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => { drawAll(); if (tab !== 'live') loadHistory(tab); }); };
  const close = () => { modal.classList.remove('show'); modal.setAttribute('aria-hidden', 'true'); };
  document.getElementById('resBtn').addEventListener('click', open);
  document.getElementById('resClose').addEventListener('click', close);
  modal.addEventListener('click', e => { if (e.target === modal) close(); });
  window.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  window.addEventListener('resize', drawAll);
  new MutationObserver(drawAll).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
})();