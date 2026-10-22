# CareLens Edge-Native Architecture

## System Overview

**CareLens** is an edge-native clinical visual safety auditor designed to inspect medical equipment and ICU patient monitors in real time. Running directly on edge hardware (such as Apple Silicon Mac with local MLX/Metal execution), CareLens provides millisecond-latency decision-support without transmitting sensitive patient imagery to external cloud servers.

> [!IMPORTANT]
> **Clinical Governance & Regulatory Disclaimer**:
> CareLens is an advisory decision-support tool, not a medical device or a substitute for trained clinical judgment. It must never autonomously change equipment settings, control drug infusion, adjust oxygen delivery, or make definitive clinical diagnoses. All findings require qualification and confirmation by a licensed clinician.

---

## Architecture Diagram

```mermaid
graph TD
    A[Image / Video Frame Capture] --> B[Capture Adapter & Preprocessor]
    B -->|Aspect-Preserving Resize & Quality Check| C[Inference Router]
    
    subgraph "Edge Inference Tier"
        C -->|Primary: Local Multimodal| D[Gemma 4 Vision via Ollama / MLX]
        C -->|Deterministic Fallback| E[Edge CV Safety Engine]
    end
    
    D --> F[Extracted Visual Observations]
    E --> F
    
    subgraph "Clinical Governance Tier"
        F --> G[Protocol Engine]
        H[(Versioned Protocol Store)] --> G
        G -->|Enforce Validated Safety Rules| I[Risk Escalation Evaluator]
    end
    
    I --> J[Schema Validator - Strict Pydantic Contract]
    
    subgraph "Output & Presentation Tier"
        J --> K[Canonical JSON Response]
        K --> L[Overlay Renderer - [ymin, xmin, ymax, xmax]]
        K --> M[Voice Alert Adapter - Imperative < 15 Words]
        K --> N[Tamper-Evident Audit Logger]
    end
    
    N --> O[Clinician Verification & Acknowledgement Workflow]
```

---

## Core Components

### 1. Capture Adapter & Preprocessor (`app/capture/`)
- Ingests still images, video frames, or base64 streams from authorized clinical cameras.
- Validates resolution (minimum 64×64, maximum 2048×2048) and orientation (EXIF transpose).
- Applies Lanczos aspect-preserving downscaling to protect fine text readability on equipment dials and monitor numerals.
- Evaluates clarity heuristics (underexposure, glare, low contrast). Degraded imagery triggers a safe `WARNING` status rather than guessing.

### 2. Multi-Adapter Inference Tier (`app/inference/`)
- **Gemma 4 Vision Adapter (`GemmaVisionAdapter`)**:
  - Connects to local `gemma4:e2b` running via Ollama / Metal.
  - Formats clinical prompts with explicit system instructions prohibiting ungrounded speculation.
  - Extracts and cleans JSON outputs.
- **Edge Clinical Engine (`EdgeClinicalEngine`)**:
  - Sub-millisecond deterministic safety fallback.
  - Immediately available if local model is busy, offline, or produces malformed JSON.
  - Provides ground-truth benchmark evaluation for standard clinical presets.

### 3. Protocol Engine (`app/protocol_engine/`)
- Separates deterministic clinical reference ranges from free-form model reasoning.
- Supports versioned protocols:
  - `adult_icu_v1.0`: Standard adult ICU ranges (HR 60-100 bpm, SpO2 ≥ 94%, BP 90-140 systolic).
  - `pediatric_icu_v1.0`: Pediatric ranges (HR 80-130 bpm, SpO2 ≥ 95%, max O2 flow ≤ 2.0 L/min).
  - `neonatal_icu_v1.0`: Neonatal precision ranges (HR 100-160 bpm, SpO2 90-95% target, hyperoxia protection).
- Evaluates equipment setup rules (e.g. roller clamp state, air-in-line detection, flow meter calibration).

### 4. Canonical Schema Contract (`app/schema/`)
Enforces the exact required CareLens JSON schema:
- `inspection_type`: `Equipment_Setup` | `Patient_Monitor` | `Unknown`
- `overall_status`: `PASS` | `WARNING` | `CRITICAL`
- `vitals_extracted`: `heart_rate_bpm`, `spo2_percent`, `blood_pressure_mmHg`, `respiration_rate` (values are strings or `"N/A"`)
- `visual_overlays`: Array of detected items with `label`, `box_2d` (`[ymin, xmin, ymax, xmax]` in range `0..1000`), `status` (`PASS` | `FAIL`), and `detail`.
- `findings`: Evidence-based descriptive strings.
- `audio_alert_text`: One imperative sentence of fewer than 15 words.
- Extra keys are strictly forbidden (`extra="forbid"`).

### 5. Overlay Renderer (`app/overlays/`)
- Translates normalized `[ymin, xmin, ymax, xmax]` coordinates (0-1000) into physical canvas pixels `(x, y, width, height)`.
- Renders high-contrast clinical overlays (Emerald for `PASS`, Crimson for `FAIL`, Amber for `WARNING`).
- Provides interactive hover and click inspection for clinical staff.

### 6. Voice Alert Adapter (`app/alerts/`)
- Generates speech synthesis payloads for browser Web Speech API.
- Enforces strict constraints: exactly one imperative sentence, fewer than 15 words, clinically calm phrasing.
- Provides mute, volume control, and audio replay capabilities.

### 7. Clinical Audit Logger (`app/audit/`)
- Maintains tamper-evident audit records (`audit_trail.jsonl`):
  - Audit UUID
  - UTC ISO8601 timestamp
  - Model and runtime environment
  - Protocol ID and version
  - Patient context
  - Overall status and findings count
  - Latency in milliseconds
- **Human Verification Loop**: Captures clinician name/ID, action taken, and notes upon acknowledgement.
- **Privacy by Design**: Never retains raw image pixels without explicit institutional consent.

---

## Status Policy & Escalation Rules

| Status | Condition | Example |
| :--- | :--- | :--- |
| **PASS** | All inspected items are readable, grounded, and within reference protocol. | Resting HR 72, SpO2 98%, BP 120/80; or pediatric O2 flow set at 1.0 L/min. |
| **WARNING** | Unclear image, glare, missing protocol context, closed clamp, or uncertain observation. | Glare obscuring monitor numerals; roller clamp closed on active infusion line. |
| **CRITICAL** | High-risk, clearly visible condition matching validated escalation rule. | Pediatric oxygen flow at 8.0 L/min (> 2.0 limit); SpO2 ≤ 88%; air bubble in IV line. |
