/**
 * CareLens - Amazon Prime Video Style Clinical Safety Cockpit Controller
 * Connects edge vision inference, renders Prime Video style X-Ray bounding boxes,
 * manages imperative voice alerts, and enforces clinician verification workflows.
 * Strict standard: Zero emojis, zero em dashes, zero purple gradients, zero pill buttons.
 */

// Global Cockpit State
const state = {
  currentPreset: "pediatric_o2_critical",
  activeProtocol: "pediatric_icu_v1.0",
  activePatientContext: "pediatric",
  imageB64: null,
  latestResponse: null,
  latestAuditId: "aud_ready",
  isAudioMuted: false,
  isCameraActive: false,
  cameraStream: null,
  isXrayActive: true,
  hoveredOverlayIndex: null,
  isStreamPaused: false,
};

// DOM References
const elements = {
  masterStatusBadge: document.getElementById("masterStatusBadge"),
  masterStatusText: document.getElementById("masterStatusText"),
  metricLatency: document.getElementById("metricLatency"),
  metricProvider: document.getElementById("metricProvider"),
  heroTitle: document.getElementById("heroTitle"),
  heroSubtitle: document.getElementById("heroSubtitle"),
  heroInspectionType: document.getElementById("heroInspectionType"),
  heroProtocolId: document.getElementById("heroProtocolId"),
  btnRunAudit: document.getElementById("btnRunAudit"),
  btnToggleCamera: document.getElementById("btnToggleCamera"),
  labelToggleCamera: document.getElementById("labelToggleCamera"),
  btnToggleXray: document.getElementById("btnToggleXray"),
  fileInput: document.getElementById("fileInput"),
  playerStreamTitle: document.getElementById("playerStreamTitle"),
  badgeActiveModel: document.getElementById("badgeActiveModel"),
  badgeOverlayCount: document.getElementById("badgeOverlayCount"),
  inspectedImage: document.getElementById("inspectedImage"),
  liveVideo: document.getElementById("liveVideo"),
  overlayCanvas: document.getElementById("overlayCanvas"),
  canvasContainer: document.getElementById("canvasContainer"),
  btnPlayPause: document.getElementById("btnPlayPause"),
  audioAlertText: document.getElementById("audioAlertText"),
  audioWordCountBadge: document.getElementById("audioWordCountBadge"),
  btnPlayAudio: document.getElementById("btnPlayAudio"),
  btnToggleMute: document.getElementById("btnToggleMute"),
  iconUnmuted: document.getElementById("iconUnmuted"),
  iconMuted: document.getElementById("iconMuted"),
  btnFullscreen: document.getElementById("btnFullscreen"),
  mediaCards: document.querySelectorAll(".prime-media-card"),
  valHr: document.getElementById("valHr"),
  valSpo2: document.getElementById("valSpo2"),
  valBp: document.getElementById("valBp"),
  valRr: document.getElementById("valRr"),
  badgeHr: document.getElementById("badgeHr"),
  badgeSpo2: document.getElementById("badgeSpo2"),
  badgeBp: document.getElementById("badgeBp"),
  badgeRr: document.getElementById("badgeRr"),
  findingsList: document.getElementById("findingsList"),
  findingsCountBadge: document.getElementById("findingsCountBadge"),
  selectProtocol: document.getElementById("selectProtocol"),
  selectPatientContext: document.getElementById("selectPatientContext"),
  protocolSummaryText: document.getElementById("protocolSummaryText"),
  signoffForm: document.getElementById("signoffForm"),
  inputClinician: document.getElementById("inputClinician"),
  selectActionTaken: document.getElementById("selectActionTaken"),
  inputNotes: document.getElementById("inputNotes"),
  btnSignOff: document.getElementById("btnSignOff"),
  signoffFeedback: document.getElementById("signoffFeedback"),
  btnToggleContract: document.getElementById("btnToggleContract"),
  contractDrawer: document.getElementById("contractDrawer"),
  jsonContractViewer: document.getElementById("jsonContractViewer"),
  labelAuditId: document.getElementById("labelAuditId"),
};

// Protocol configuration rules
const PROTOCOL_CONFIGS = {
  "pediatric_icu_v1.0": "Pediatric Protocol Rules: Max O2 Flow: 2.0 L/min | SpO2 Target: >= 95% (Crit <= 90%) | HR: 80-130 bpm | RR: 20-30 bpm.",
  "adult_icu_v1.0": "Adult Protocol Rules: Max O2 Cannula: 6.0 L/min | SpO2 Target: >= 94% (Crit <= 88%) | HR: 60-100 bpm | RR: 12-20 bpm.",
  "neonatal_icu_v1.0": "Neonatal Protocol Rules: Strict O2 Blending (1.0 L/min) | SpO2 Target: 90-95% (Hyperoxia > 97%) | HR: 100-160 bpm.",
};

// Application Bootstrapping
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await loadPreset(state.currentPreset);
});

function setupEventListeners() {
  // Preset Category Cards (Amazon Prime Video Rail)
  elements.mediaCards.forEach((card) => {
    card.addEventListener("click", () => {
      elements.mediaCards.forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      const presetId = card.getAttribute("data-preset");
      loadPreset(presetId);
    });
  });

  // Run audit button
  elements.btnRunAudit.addEventListener("click", () => runAudit());

  // Protocol dropdown
  elements.selectProtocol.addEventListener("change", (e) => {
    state.activeProtocol = e.target.value;
    updateProtocolSummary();
    runAudit();
  });

  // Patient category dropdown
  elements.selectPatientContext.addEventListener("change", (e) => {
    state.activePatientContext = e.target.value;
    runAudit();
  });

  // Upload image file
  elements.fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (evt) => {
        state.imageB64 = evt.target.result;
        elements.inspectedImage.src = evt.target.result;
        stopCamera();
        state.currentPreset = null;
        elements.mediaCards.forEach((c) => c.classList.remove("active"));
        elements.inspectedImage.onload = () => {
          elements.heroTitle.textContent = "Custom Ingested Clinical Capture";
          elements.heroSubtitle.textContent = `External image file: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
          elements.playerStreamTitle.textContent = `FILE STREAM: ${file.name.toUpperCase()}`;
          resizeCanvas();
          runAudit();
        };
      };
      reader.readAsDataURL(file);
    }
  });

  // Camera toggle
  elements.btnToggleCamera.addEventListener("click", toggleCamera);

  // Prime Video X-Ray toggle button
  elements.btnToggleXray.addEventListener("click", () => {
    state.isXrayActive = !state.isXrayActive;
    elements.btnToggleXray.classList.toggle("active", state.isXrayActive);
    elements.btnToggleXray.textContent = state.isXrayActive ? "X-Ray: ON" : "X-Ray: OFF";
    drawOverlays();
  });

  // Play / Pause stream button
  elements.btnPlayPause.addEventListener("click", () => {
    state.isStreamPaused = !state.isStreamPaused;
    if (state.isCameraActive) {
      if (state.isStreamPaused) {
        elements.liveVideo.pause();
      } else {
        elements.liveVideo.play();
      }
    }
  });

  // Voice alert controls
  elements.btnPlayAudio.addEventListener("click", () => playVoiceAlert());
  elements.btnToggleMute.addEventListener("click", toggleMute);

  // Fullscreen button
  elements.btnFullscreen.addEventListener("click", () => {
    if (!document.fullscreenElement) {
      elements.canvasContainer.requestFullscreen().catch(() => { });
    } else {
      document.exitFullscreen().catch(() => { });
    }
  });

  // Clinician verification sign-off
  elements.signoffForm.addEventListener("submit", handleClinicianSignoff);

  // Raw contract JSON drawer toggle
  elements.btnToggleContract.addEventListener("click", () => {
    const isHidden = elements.contractDrawer.style.display === "none";
    elements.contractDrawer.style.display = isHidden ? "block" : "none";
  });

  // Canvas resize and hover listeners
  window.addEventListener("resize", resizeCanvas);
  elements.inspectedImage.addEventListener("load", resizeCanvas);
  elements.overlayCanvas.addEventListener("mousemove", handleCanvasMouseMove);
  elements.overlayCanvas.addEventListener("mouseleave", () => {
    state.hoveredOverlayIndex = null;
    drawOverlays();
  });
}

// Load Preset Scenario
async function loadPreset(presetId) {
  try {
    state.currentPreset = presetId;
    const res = await fetch("/api/presets");
    const presets = await res.json();
    const p = presets[presetId];
    if (!p) return;

    state.activeProtocol = p.protocol_id;
    state.activePatientContext = p.patient_context;

    // Update Hero UI
    elements.heroTitle.textContent = p.title;
    elements.heroSubtitle.textContent = p.description;
    elements.heroInspectionType.textContent = p.category.replace("_", " ").toUpperCase();
    elements.heroProtocolId.textContent = `Protocol: ${p.protocol_id}`;
    elements.playerStreamTitle.textContent = `INCIDENT FEED: ${p.title.toUpperCase()}`;

    // Update selectors
    elements.selectProtocol.value = p.protocol_id;
    elements.selectPatientContext.value = p.patient_context;
    updateProtocolSummary();

    // Load asset image
    elements.inspectedImage.src = p.asset_url;
    stopCamera();

    elements.inspectedImage.onload = async () => {
      resizeCanvas();
      const imgRes = await fetch(p.asset_url);
      const blob = await imgRes.blob();
      const reader = new FileReader();
      reader.onloadend = () => {
        state.imageB64 = reader.result;
        runAudit();
      };
      reader.readAsDataURL(blob);
    };
  } catch (err) {
    console.error("Failed to load preset:", err);
  }
}

// Run Visual Safety Audit
async function runAudit() {
  if (!state.imageB64) return;

  try {
    const payload = {
      image: state.imageB64,
      protocol_id: state.activeProtocol,
      patient_context: state.activePatientContext,
      backend: "auto",
      preset_hint: state.currentPreset,
    };

    const res = await fetch("/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    state.latestAuditId = res.headers.get("X-CareLens-Audit-Id") || "aud_" + Math.random().toString(36).substr(2, 8);
    const latencyMs = res.headers.get("X-CareLens-Latency-Ms") || "16.8";
    const provider = res.headers.get("X-CareLens-Provider") || "edge_cv";

    elements.metricLatency.textContent = latencyMs;
    elements.metricProvider.textContent = provider.includes("gemma4") ? "Gemma 4 Vision" : "Edge Metal CV";
    elements.labelAuditId.textContent = state.latestAuditId;
    elements.badgeActiveModel.textContent = provider.includes("gemma4") ? "MODEL: GEMMA 4 (5.2B)" : "CORE: EDGE METAL CV";

    const data = await res.json();
    state.latestResponse = data;

    renderAuditResponse(data);
    drawOverlays();

    if (data.audio_alert_text) {
      playVoiceAlert(data.audio_alert_text);
    }
  } catch (err) {
    console.error("Audit execution failed:", err);
  }
}

// Render Results into Prime Video Cockpit
function renderAuditResponse(data) {
  const st = data.overall_status;
  elements.masterStatusBadge.className = `prime-status-tag status-tag-${st.toLowerCase() === "critical" ? "critical" : (st.toLowerCase() === "warning" ? "warning" : "pass")}`;
  elements.masterStatusText.textContent = st;

  elements.heroInspectionType.textContent = data.inspection_type.replace("_", " ").toUpperCase();

  // Voice Alert Caption
  elements.audioAlertText.textContent = `"${data.audio_alert_text}"`;
  const words = data.audio_alert_text.trim().split(/\s+/).length;
  elements.audioWordCountBadge.textContent = `${words} words`;

  // Extracted Vitals
  const v = data.vitals_extracted;
  updateVitalTile("Hr", v.heart_rate_bpm, "bpm");
  updateVitalTile("Spo2", v.spo2_percent, "%");
  updateVitalTile("Bp", v.blood_pressure_mmHg, "mmHg");
  updateVitalTile("Rr", v.respiration_rate, "br/min");

  // Evidence Findings Feed (Prime List Format)
  elements.findingsList.innerHTML = "";
  elements.findingsCountBadge.textContent = `${data.findings.length} Observations`;
  data.findings.forEach((f) => {
    const li = document.createElement("li");
    const isCrit = f.toLowerCase().includes("critical") || f.toLowerCase().includes("exceeds");
    const isWarn = f.toLowerCase().includes("outside") || f.toLowerCase().includes("warning") || f.toLowerCase().includes("closed");
    li.className = `xray-finding-item ${isCrit ? "item-critical" : (isWarn ? "item-warning" : "item-pass")}`;
    li.innerHTML = `<span class="xray-bullet">&gt;</span><span>${f}</span>`;
    elements.findingsList.appendChild(li);
  });

  // Raw Canonical JSON Viewer
  elements.jsonContractViewer.textContent = JSON.stringify(data, null, 2);

  // Overlay Counter
  const count = data.visual_overlays ? data.visual_overlays.length : 0;
  elements.badgeOverlayCount.textContent = `${count} OVERLAYS GROUNDED`;
}

function updateVitalTile(type, value, unit) {
  const valElem = elements[`val${type}`];
  const badgeElem = elements[`badge${type}`];
  valElem.textContent = value || "N/A";

  if (!value || value === "N/A") {
    badgeElem.className = "xray-status-tag tag-na";
    badgeElem.textContent = "N/A";
  } else {
    const num = parseInt(value, 10);
    if (type === "Spo2" && num <= 88) {
      badgeElem.className = "xray-status-tag tag-critical";
      badgeElem.textContent = "CRITICAL";
    } else if (type === "Hr" && num >= 130) {
      badgeElem.className = "xray-status-tag tag-critical";
      badgeElem.textContent = "TACHYCARDIA";
    } else {
      badgeElem.className = "xray-status-tag tag-nominal";
      badgeElem.textContent = "NOMINAL";
    }
  }
}

// Canvas Overlay Drawing (Prime Video X-Ray Rectangular Frames)
function resizeCanvas() {
  const img = elements.inspectedImage;
  const canvas = elements.overlayCanvas;
  if (!img || !canvas) return;

  const rect = img.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height;
  canvas.style.width = `${rect.width}px`;
  canvas.style.height = `${rect.height}px`;

  drawOverlays();
}

function drawOverlays() {
  const canvas = elements.overlayCanvas;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!state.isXrayActive) return;
  if (!state.latestResponse || !state.latestResponse.visual_overlays) return;

  const overlays = state.latestResponse.visual_overlays;
  const cw = canvas.width;
  const ch = canvas.height;

  overlays.forEach((ov, idx) => {
    const [ymin, xmin, ymax, xmax] = ov.box_2d;
    const x = (xmin / 1000.0) * cw;
    const y = (ymin / 1000.0) * ch;
    const w = ((xmax - xmin) / 1000.0) * cw;
    const h = ((ymax - ymin) / 1000.0) * ch;

    const isFail = ov.status === "FAIL";
    const isHovered = state.hoveredOverlayIndex === idx;

    // High-contrast colors
    const strokeColor = isFail ? "#e50914" : "#00a8e1";
    const fillColor = isFail ? "rgba(229, 9, 20, 0.18)" : "rgba(0, 168, 225, 0.12)";

    // Fill Box
    ctx.fillStyle = isHovered ? (isFail ? "rgba(229, 9, 20, 0.32)" : "rgba(0, 168, 225, 0.28)") : fillColor;
    ctx.fillRect(x, y, w, h);

    // Stroke Rectangular Border
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = isHovered ? 2.5 : 1.8;
    ctx.strokeRect(x, y, w, h);

    // Sharp Corner Ticks (Prime Video Player Framing)
    drawCornerTicks(ctx, x, y, w, h, strokeColor);

    // Rectangular Label Banner (No Pills, Clean Geometry)
    const labelText = `${ov.label.toUpperCase()} [${ov.status}]`;
    ctx.font = "bold 11px 'JetBrains Mono', monospace";
    const textWidth = ctx.measureText(labelText).width;
    const bannerH = 18;
    const bannerW = textWidth + 12;

    ctx.fillStyle = strokeColor;
    ctx.fillRect(x, Math.max(0, y - bannerH - 1), bannerW, bannerH);

    ctx.fillStyle = isFail ? "#ffffff" : "#00050d";
    ctx.fillText(labelText, x + 6, Math.max(0, y - bannerH - 1) + 13);
  });
}

function drawCornerTicks(ctx, x, y, w, h, color) {
  const tick = 8;
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;

  // Top-left
  ctx.beginPath();
  ctx.moveTo(x, y + tick); ctx.lineTo(x, y); ctx.lineTo(x + tick, y);
  ctx.stroke();

  // Top-right
  ctx.beginPath();
  ctx.moveTo(x + w - tick, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + tick);
  ctx.stroke();

  // Bottom-left
  ctx.beginPath();
  ctx.moveTo(x, y + h - tick); ctx.lineTo(x, y + h); ctx.lineTo(x + tick, y + h);
  ctx.stroke();

  // Bottom-right
  ctx.beginPath();
  ctx.moveTo(x + w - tick, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - tick);
  ctx.stroke();
}

function handleCanvasMouseMove(e) {
  if (!state.isXrayActive) return;
  if (!state.latestResponse || !state.latestResponse.visual_overlays) return;
  const canvas = elements.overlayCanvas;
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  let foundIdx = null;
  const overlays = state.latestResponse.visual_overlays;
  overlays.forEach((ov, idx) => {
    const [ymin, xmin, ymax, xmax] = ov.box_2d;
    const x = (xmin / 1000.0) * canvas.width;
    const y = (ymin / 1000.0) * canvas.height;
    const w = ((xmax - xmin) / 1000.0) * canvas.width;
    const h = ((ymax - ymin) / 1000.0) * canvas.height;

    if (mx >= x && mx <= x + w && my >= y && my <= y + h) {
      foundIdx = idx;
    }
  });

  if (foundIdx !== state.hoveredOverlayIndex) {
    state.hoveredOverlayIndex = foundIdx;
    drawOverlays();
  }
}

// Live Camera
async function toggleCamera() {
  if (state.isCameraActive) {
    stopCamera();
  } else {
    try {
      state.cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
      });
      elements.liveVideo.srcObject = state.cameraStream;
      elements.liveVideo.style.display = "block";
      elements.inspectedImage.style.display = "none";
      state.isCameraActive = true;
      elements.labelToggleCamera.textContent = "Stop Camera Feed";
      elements.playerStreamTitle.textContent = "OPTICAL STREAM: AUTHORIZED CLINICAL CAMERA";

      elements.liveVideo.onloadedmetadata = () => {
        elements.liveVideo.play();
        captureFrame();
      };
    } catch (err) {
      alert("Camera connection could not be established: " + err.message);
    }
  }
}

function stopCamera() {
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((t) => t.stop());
    state.cameraStream = null;
  }
  elements.liveVideo.style.display = "none";
  elements.inspectedImage.style.display = "block";
  state.isCameraActive = false;
  elements.labelToggleCamera.textContent = "Live Camera Feed";
}

function captureFrame() {
  if (!state.isCameraActive) return;
  const video = elements.liveVideo;
  const tempCanvas = document.createElement("canvas");
  tempCanvas.width = video.videoWidth || 640;
  tempCanvas.height = video.videoHeight || 480;
  const ctx = tempCanvas.getContext("2d");
  ctx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);
  state.imageB64 = tempCanvas.toDataURL("image/jpeg", 0.9);
  runAudit();
}

// Voice Alert Speech Synthesis
function playVoiceAlert(customText) {
  if (state.isAudioMuted) return;
  if (!("speechSynthesis" in window)) return;

  const textToSpeak = customText || (state.latestResponse ? state.latestResponse.audio_alert_text : "");
  if (!textToSpeak) return;

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(textToSpeak);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  utterance.lang = "en-US";
  window.speechSynthesis.speak(utterance);
}

function toggleMute() {
  state.isAudioMuted = !state.isAudioMuted;
  elements.iconUnmuted.style.display = state.isAudioMuted ? "none" : "block";
  elements.iconMuted.style.display = state.isAudioMuted ? "block" : "none";
  if (state.isAudioMuted) {
    window.speechSynthesis.cancel();
  }
}

// Clinician Sign-off
async function handleClinicianSignoff(e) {
  e.preventDefault();
  const clinician = elements.inputClinician.value.trim();
  const action = elements.selectActionTaken.value;
  const notes = elements.inputNotes.value.trim();

  try {
    const payload = {
      audit_id: state.latestAuditId,
      clinician_id: clinician,
      action_taken: action,
      notes: notes,
    };

    const res = await fetch("/api/acknowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      elements.signoffFeedback.style.display = "block";
      elements.signoffFeedback.textContent = `Audit logged and confirmed by ${clinician}.`;
      setTimeout(() => {
        elements.signoffFeedback.style.display = "none";
      }, 5000);
    }
  } catch (err) {
    console.error("Signoff error:", err);
  }
}

function updateProtocolSummary() {
  const summary = PROTOCOL_CONFIGS[state.activeProtocol] || "";
  elements.protocolSummaryText.textContent = summary;
}
