# CareLens Validation and Testing Plan

This validation plan outlines the twelve verification stages required before CareLens may be deployed in any clinical pilot or simulation environment.

---

## 1. Schema Contract Tests
- **Objective**: Ensure that every response returned by CareLens strictly satisfies the canonical contract.
- **Verification**:
  - Keys present: `inspection_type`, `overall_status`, `vitals_extracted`, `visual_overlays`, `findings`, `audio_alert_text`.
  - Forbid extra keys (`extra="forbid"`).
  - Validate allowed enum values (`Equipment_Setup`, `Patient_Monitor`, `Unknown`; `PASS`, `WARNING`, `CRITICAL`; `PASS`, `FAIL`).
  - Validate coordinate bounds: `0 <= ymin <= ymax <= 1000` and `0 <= xmin <= xmax <= 1000`.
- **Automated Suite**: `tests/schema/test_schema.py`

## 2. Image Quality & Optical Degradation Tests
- **Objective**: Verify that low-light, underexposed, overexposed, blurred, or glare-compromised imagery triggers a safe `WARNING` status rather than producing hallucinated readings.
- **Verification**:
  - Threshold checks for brightness (< 20.0 or > 235.0) and contrast (< 12.0 stddev).
  - Verify that uncertain observations do not become false passes or false critical alarms.
- **Automated Suite**: `tests/images/test_preprocessor.py` and `frontend/assets/unclear_low_light.svg`.

## 3. Supported Device & Layout Tests
- **Objective**: Verify visual analysis across supported device categories:
  - Thoracic / Thorpe tube rotameters (graduated 0-15 L/min).
  - Smart infusion pumps (flow rate LCD, door latch, manual roller clamp).
  - Multi-parameter ICU patient monitors (ECG waveform, SpO2 plethysmograph, NIBP cuff readouts, impedance respiration).

## 4. Clinical Protocol Authoring & Governance
- **Objective**: Verify that reference ranges and equipment limits are approved, versioned, and isolated from model reasoning.
- **Verification**:
  - Versioned protocol registries: `adult_icu_v1.0`, `pediatric_icu_v1.0`, `neonatal_icu_v1.0`.
  - Protocol tests in `tests/protocols/test_protocols.py`.

## 5. Risk Assessment & Safety Escalation Tests
- **Objective**: Ensure high-risk observations escalate to `CRITICAL` while ambiguous observations escalate to `WARNING` for human verification.
- **Verification**:
  - Confirmed pediatric oxygen flow > 2.0 L/min -> `CRITICAL`.
  - SpO2 ≤ 88% -> `CRITICAL`.
  - Air bubble in IV line -> `CRITICAL`.
  - Closed roller clamp on active pump line -> `WARNING` / `FAIL`.
  - Missing or `"N/A"` monitor readings -> `WARNING` (request clinician verification).
- **Automated Suite**: `tests/safety/test_safety_escalation.py`.

## 6. Localization & Bounding Box Accuracy
- **Objective**: Measure bounding-box grounding in image pixel space.
- **Verification**:
  - Overlay renderer transforms normalized 0-1000 coordinates to display pixels without overflow or negative coordinates.
  - Box grounding tests in `app/overlays/renderer.py`.

## 7. Vital Sign Extraction & OCR Precision
- **Objective**: Measure numeric extraction accuracy for HR, SpO2, BP, and RR.
- **Verification**:
  - Extraction formats: `heart_rate_bpm` (integer string), `spo2_percent` (integer string), `blood_pressure_mmHg` (systolic/diastolic string), `respiration_rate` (integer string).
  - Unreadable or non-visible channels return `"N/A"`.

## 8. Voice Alert Safety Constraints
- **Objective**: Verify voice alerts adhere strictly to clinical safety communications.
- **Verification**:
  - Single imperative sentence.
  - Fewer than 15 words.
  - Advisory tone; never commands automated equipment modifications.
- **Automated Suite**: `tests/safety/test_safety_escalation.py` and `app/alerts/voice_alert.py`.

## 9. Edge Performance & Hardware Telemetry
- **Objective**: Benchmark inference latency, memory footprint, and frame processing rates.
- **Target Metrics**:
  - Edge Deterministic Safety Rules: < 25 ms.
  - Gemma 4 Local Vision (5.2B on Metal): < 25 seconds for comprehensive visual audit.
  - Video stream rendering: 30 FPS canvas rendering.

## 10. Human Factors & Clinician Acknowledgement
- **Objective**: Ensure decision support workflow requires qualified clinician qualification.
- **Verification**:
  - Clinician acknowledgement modal with staff ID, action taken, and notes.
  - Alarm fatigue mitigation via non-alarming voice alerts, mute toggle, and volume sliders.
  - Clear visual distinction between advisory findings and confirmed clinical actions.

## 11. Security, Privacy, and Access Control
- **Objective**: Prevent transmission of protected health information (PHI).
- **Verification**:
  - Local edge processing (on-device Ollama/Metal).
  - Zero raw image retention in `audit_trail.jsonl`.
  - Role-based clinician sign-off logs.

## 12. Release Gate & Clinical Sign-off
- **Release Condition**: System must not be used for live clinical decisions until institutional clinical safety, legal, privacy, and regulatory reviews are fully completed.
