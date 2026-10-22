# CareLens — Edge-Native Clinical Visual Safety Auditor

CareLens is a clinical visual safety auditing prototype engineered to analyze imagery and video frames of medical equipment and ICU patient monitors. Running edge-first with **Gemma 4 Vision** and deterministic safety rules, CareLens identifies equipment setup details, extracts readable monitor vital signs, flags potential safety concerns, and produces strictly structured JSON for visual overlays and voice alerts.

---

> [!CAUTION]
> ### Clinical Governance and Decision-Support Notice
> **CareLens is an advisory decision-support aid, not a medical device or a substitute for trained clinical judgment.**
> It must **never** autonomously change equipment settings, control drug delivery, modify mechanical ventilation, or make definitive clinical decisions. All findings require qualification and confirmation by a licensed clinician before any clinical action is taken.

---

## Key Features

- **Multi-Parameter Monitor Extraction**: Reads heart rate (bpm), pulse oximetry (SpO2 %), non-invasive/arterial blood pressure (mmHg), and respiration rate (br/min).
- **Equipment Safety Inspection**: Detects oxygen rotameter ball levels, infusion pump run states, manual roller clamp positions, and IV tubing integrity.
- **Versioned Clinical Protocols**: Separates safety thresholds from model reasoning. Out-of-the-box support for:
  - `adult_icu_v1.0`: Standard adult ICU ranges and equipment guidelines.
  - `pediatric_icu_v1.0`: Pediatric ranges with strict oxygen flow limits ($\le 2.0\text{ L/min}$).
  - `neonatal_icu_v1.0`: Neonatal vital bounds with hyperoxia protection.
- **Edge-First Architecture**: Runs on-device (macOS Metal / local Gemma 4) with sub-25ms deterministic evaluation to eliminate latency and protect patient privacy.
- **Strict Canonical JSON Contract**: Emits exact, schema-validated JSON with zero extraneous keys.
- **Normalized Bounding Boxes**: Generates `[ymin, xmin, ymax, xmax]` coordinates ($0 \dots 1000$) grounded in image pixels.
- **Concise Imperative Voice Alerts**: Web Speech API audio synthesis limited to one imperative sentence of fewer than 15 words.
- **Clinician Verification & Sign-Off**: Mandatory human-in-the-loop acknowledgement workflow with tamper-evident audit logging (`audit_trail.jsonl`).

---

## Canonical JSON Contract

Every CareLens response satisfies the following exact schema with no surrounding Markdown code fence:

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
- `findings`: Evidence-based descriptive strings.
- `audio_alert_text`: One imperative sentence, strictly fewer than 15 words.
- Extra keys are strictly forbidden.

---

## Project Structure

```
carelens/
├── README.md
├── audit_cli.py               # CLI tool for headless audits and testing
├── app/
│   ├── capture/               # Ingestion, validation, and aspect-preserving resizing
│   ├── inference/             # Gemma 4 Vision Ollama adapter & Edge CV safety engine
│   ├── protocol_engine/       # Versioned clinical protocols & safety threshold rules
│   ├── schema/                # Strict Pydantic v2 canonical contract models
│   ├── overlays/              # Coordinate transforms and canvas visual overlay rendering
│   ├── alerts/                # Voice alert adapter and TTS payload generator
│   ├── audit/                 # Tamper-evident logger with clinician sign-off
│   ├── presets.py             # Pre-configured clinical scenarios and ground truth
│   └── main.py                # FastAPI server hosting REST API and Web Cockpit
├── tests/
│   ├── schema/                # Schema contract and extra-key rejection tests
│   ├── protocols/             # Reference range and threshold evaluation tests
│   ├── safety/                # Risk escalation and uncertainty policy tests
│   ├── images/                # Preprocessing and quality heuristic tests
│   └── run_all_tests.py       # Master test suite runner
├── configs/
│   └── protocols.example.yaml # Declarative versioned protocols configuration
├── docs/
│   ├── architecture.md        # Comprehensive architecture & data flow diagrams
│   └── validation_plan.md     # 12-point clinical and technical validation plan
└── frontend/
    ├── index.html             # High-tech medical dark UI cockpit
    ├── styles.css             # Glassmorphism styling and responsive design system
    ├── app.js                 # Canvas overlay controller and voice alert synthesis
    └── assets/                # High-fidelity SVG equipment illustrations
```

---

## Quickstart

### 1. Run Automated Test Suite
Ensure the environment passes all 18 unit and safety tests:
```bash
PYTHONPATH=. .venv/bin/python3 tests/run_all_tests.py
```

### 2. Start CareLens Cockpit & API Server
Launch the FastAPI edge server:
```bash
.venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to access the CareLens Visual Safety Cockpit.

### 3. CLI Audit Tool
Run instant headless audits on preset clinical scenarios or custom files:
```bash
# Audit pediatric oxygen overflow scenario (escalates to CRITICAL)
.venv/bin/python3 audit_cli.py --preset pediatric_o2_critical

# Output pure canonical JSON
.venv/bin/python3 audit_cli.py --preset pediatric_o2_critical --json

# Run audit on a custom image file with adult ICU protocol
.venv/bin/python3 audit_cli.py --image path/to/equipment.jpg --protocol adult_icu_v1.0
```

---

## Interactive Presets in the Web Cockpit

1. **🚨 Pediatric O2 Over-delivery (Critical)**: Thorpe tube flow meter visibly set to $8.0\text{ L/min}$ for a pediatric patient (exceeding the $2.0\text{ L/min}$ safe threshold).
2. **🚨 ICU Monitor Desaturation & Shock (Critical)**: Patient monitor showing heart rate 142 bpm (tachycardia), SpO2 84% (critical desaturation), blood pressure 78/45 mmHg (hypotensive shock), and respiration 32 br/min (tachypnea).
3. **⚠️ Infusion Line Clamp Closed (Warning)**: Volumetric infusion pump actively running while manual IV line roller clamp is closed.
4. **✅ Nominal Adult ICU Monitor (Pass)**: Patient monitor displaying resting vitals (HR 72, SpO2 98%, BP 120/80, RR 16).
5. **🔍 Severe Optical Glare (Warning)**: Tests uncertainty handling when glare prevents reliable optical reading. CareLens safely requests manual inspection.
