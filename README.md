# CareLens — Edge-Native Clinical Visual Safety Auditor [PROTOTYPE]

> [!CAUTION]
> ### Prototype & Clinical Decision-Support Advisory Notice
> **CareLens is a research and development prototype and clinical decision-support aid, NOT a certified medical device.**
> **Do NOT use to guide real patient care without appropriate clinical, regulatory (e.g. FDA / CE-MDR), and safety validation.**
> It must **never** autonomously change equipment settings, control drug delivery, modify mechanical ventilation, or make definitive clinical decisions. All findings require qualification and confirmation by a licensed clinician before any clinical action is taken.

CareLens is a clinical visual safety auditing prototype engineered to analyze imagery and video frames of medical equipment and ICU patient monitors. Running edge-first with **Gemma 4 Vision** and deterministic safety rules, CareLens identifies equipment setup details, extracts readable monitor vital signs, flags potential safety concerns, and produces strictly structured canonical JSON for visual overlays and voice alerts.

---

## Safety Core & Architectural Priorities

1. **Explicit Uncertainty Handling & Abstention**: When image quality is degraded, specular glare obscures displays, vital signs are unreadable or missing, or ambiguous equipment is presented, CareLens **explicitly abstains** with `WARNING` and requires manual clinical review. It **never** outputs a confident but unsupported `PASS` safety status.
2. **Clinician-Reviewed De-identified Evaluation**: Evaluated across clinician-reviewed, de-identified scenarios specifically testing poor image quality, specular glare, unreadable numeric displays, and ambiguous non-protocol equipment.
3. **Automated Safety Boundary Verification**: Fully tested with 47 automated unit and safety tests covering bounding box coordinate ranges `[0..1000]`, extra-key schema rejection, protocol versions, and vital threshold boundaries.
4. **Application Startup Model Loading & Readiness Check**: Model engine initialization is decoupled from import time and executed during application startup lifecycle, exposing `/api/ready` to reflect runtime model availability.
5. **CORS Restrictions & Endpoint Protection**: Restricts CORS to approved origins (no wildcard `*` with credentials), validates file upload MIME types and size limits (10MB), bounds base64 payload sizes (15MB), and protects inspection endpoints and audit data.
6. **Tamper-Evident Cryptographic Audit Ledger**: Audit records form an append-only SHA-256 cryptographic hash chain where each entry links to the prior record hash. Includes automated integrity verification (`verify_integrity()`) exposed via CLI (`--verify-integrity`) and API (`/api/audit/verify`).

---

## Canonical JSON Contract

Every CareLens response satisfies the following exact schema with strictly zero extraneous keys:

```json
{
  "inspection_type": "Equipment_Setup",
  "overall_status": "WARNING",
  "vitals_extracted": {
    "heart_rate_bpm": "N/A",
    "spo2_percent": "N/A",
    "blood_pressure_mmHg": "N/A",
    "respiration_rate": "N/A"
  },
  "visual_overlays": [
    {
      "label": "Example component",
      "box_2d": [100, 100, 400, 400],
      "status": "PASS",
      "detail": "Visible observation only; verify against the applicable protocol."
    }
  ],
  "findings": [
    "Describe visible evidence without asserting details that cannot be confirmed."
  ],
  "audio_alert_text": "Verify the setup against the approved clinical protocol."
}
```

### Schema Rules
- `inspection_type`: Exactly `Equipment_Setup`, `Patient_Monitor`, or `Unknown`.
- `overall_status`: Exactly `PASS`, `WARNING`, or `CRITICAL`.
- `vitals_extracted`: Always includes `heart_rate_bpm`, `spo2_percent`, `blood_pressure_mmHg`, and `respiration_rate` as strings (or `"N/A"`).
- `visual_overlays`: Array of detected components. Each item must have `label`, `box_2d` (`[ymin, xmin, ymax, xmax]` in range $0 \dots 1000$ where $ymin \le ymax$ and $xmin \le xmax$), `status` (`PASS` | `FAIL`), and `detail`.
- `findings`: Evidence-based descriptive strings. When uncertain or ambiguous, explicitly notes abstention and requests manual clinical review.
- `audio_alert_text`: One imperative sentence, strictly fewer than 15 words.
- Extra keys are strictly forbidden.

---

## Project Structure

```
carelens/
├── README.md
├── audit_cli.py               # CLI tool for headless audits, testing, and integrity checks
├── app/
│   ├── capture/               # Ingestion, validation, and aspect-preserving resizing
│   ├── inference/             # Gemma 4 Vision Ollama adapter & Edge CV safety engine
│   ├── protocol_engine/       # Versioned clinical protocols & safety threshold rules
│   ├── schema/                # Strict Pydantic v2 canonical contract models
│   ├── overlays/              # Coordinate transforms and canvas visual overlay rendering
│   ├── alerts/                # Voice alert adapter and TTS payload generator
│   ├── audit/                 # Tamper-evident cryptographic logger with hash-chain verification
│   ├── presets.py             # Clinician-reviewed de-identified scenarios and ground truth
│   └── main.py                # FastAPI server hosting REST API, readiness checks & UI
├── tests/
│   ├── schema/                # Schema contract and bounding box coordinate constraint tests
│   ├── protocols/             # Threshold boundary edge-testing and protocol version tests
│   ├── safety/                # Risk escalation and uncertainty policy / abstention tests
│   ├── images/                # Preprocessing and quality heuristic tests
│   ├── audit/                 # Cryptographic hash chain and tampering detection tests
│   ├── api/                   # API readiness, security, upload protections, and CORS tests
│   └── run_all_tests.py       # Master test suite runner (47 automated tests)
├── configs/
│   └── protocols.example.yaml # Declarative versioned protocols configuration
├── docs/
│   ├── architecture.md        # Comprehensive architecture & data flow diagrams
│   └── validation_plan.md     # 12-point clinical and technical validation plan
└── frontend/
    ├── index.html             # High-tech medical dark UI cockpit with prototype notices
    ├── styles.css             # Glassmorphism styling and responsive design system
    ├── app.js                 # Canvas overlay controller and voice alert synthesis
    └── assets/                # De-identified clinical equipment SVG illustrations
```

---

## Quickstart

### 1. Run Automated Test Suite
Ensure the environment passes all 47 automated tests:
```bash
python3 tests/run_all_tests.py
```

### 2. Verify Audit Trail Cryptographic Integrity
Verify the tamper-evident hash chain:
```bash
python3 audit_cli.py --verify-integrity
```

### 3. Start CareLens Cockpit & API Server
Launch the FastAPI edge server with startup lifecycle model initialization:
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Open **[http://localhost:8000](http://localhost:8000)** to access the CareLens Visual Safety Cockpit.
- Check model readiness: **[http://localhost:8000/api/ready](http://localhost:8000/api/ready)**.
- Verify audit ledger: **[http://localhost:8000/api/audit/verify](http://localhost:8000/api/audit/verify)**.

### 4. CLI Headless Audits
Run instant headless audits on clinician-reviewed presets or custom files:
```bash
# Audit pediatric oxygen overflow scenario (escalates to CRITICAL)
python3 audit_cli.py --preset pediatric_o2_critical

# Audit severe optical glare (explicitly abstains with WARNING)
python3 audit_cli.py --preset severe_optical_glare

# Output pure canonical JSON
python3 audit_cli.py --preset pediatric_o2_critical --json

# Run audit on a custom image file with adult ICU protocol
python3 audit_cli.py --image path/to/equipment.jpg --protocol adult_icu_v1.0
```

---

## Clinician-Reviewed De-identified Presets in the Cockpit

1. **🚨 Pediatric O2 Over-delivery (Critical)**: Thorpe tube flow meter set to $8.0\text{ L/min}$ for a pediatric patient (exceeding the $2.0\text{ L/min}$ protocol threshold).
2. **🚨 ICU Monitor Desaturation & Shock (Critical)**: Multi-parameter monitor showing heart rate 142 bpm (tachycardia), SpO2 84% (critical desaturation), blood pressure 78/45 mmHg (hypotensive shock), and respiration 32 br/min (tachypnea).
3. **⚠️ Infusion Line Clamp Closed (Warning)**: Volumetric infusion pump actively running while manual IV line roller clamp is closed.
4. **✅ Nominal Adult ICU Monitor (Pass)**: Patient monitor displaying resting vitals (HR 72, SpO2 98%, BP 120/80, RR 16).
5. **🔍 Severe Optical Glare (Abstain / Warning)**: High-intensity specular reflection washes out monitor numbers. CareLens explicitly abstains and requests manual verification.
6. **🔍 Poor Image Quality / Motion Blur (Abstain / Warning)**: Extreme camera motion blur and low contrast prevent reliable OCR. Explicit abstention with manual review request.
7. **🔍 Unreadable Monitor Display (Abstain / Warning)**: Segmented LCD display with partial burn-out / broken digits. Prevents hallucinated readings by explicitly abstaining.
8. **🔍 Ambiguous Non-Protocol Equipment (Abstain / Warning)**: Hardware device lacking recognizable clinical markings. System abstains and flags for direct clinician inspection.
