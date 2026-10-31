# CareLens Validation and Testing Plan [PROTOTYPE]

> [!CAUTION]
> ### Prototype Governance Notice
> **CareLens is a research and development prototype and clinical decision-support aid, NOT a medical device.**
> **Do NOT use to guide real patient care without appropriate clinical, regulatory (FDA / CE-MDR), and safety validation.**

This validation plan outlines the verification stages and testing protocols required for CareLens.

---

## 1. Schema Contract & Coordinate Tests
- **Objective**: Ensure that every response returned by CareLens strictly satisfies the canonical contract.
- **Verification**:
  - Exact keys present: `inspection_type`, `overall_status`, `vitals_extracted`, `visual_overlays`, `findings`, `audio_alert_text`.
  - Forbid extra keys (`extra="forbid"`) on root model and nested models (`VitalsExtracted`, `VisualOverlay`).
  - Validate allowed enum values (`Equipment_Setup`, `Patient_Monitor`, `Unknown`; `PASS`, `WARNING`, `CRITICAL`; `PASS`, `FAIL`).
  - Validate coordinate bounds: `0 <= ymin <= ymax <= 1000` and `0 <= xmin <= xmax <= 1000`, rejecting negative, out-of-range, non-integer, or inverted bounds.
- **Automated Suite**: `tests/schema/test_schema.py`

## 2. Threshold Boundaries & Protocol Versions
- **Objective**: Verify exact boundary conditions for all clinical vitals (heart rate, SpO2, blood pressure, respiration rate) and equipment flow meter limits.
- **Verification**:
  - Heart rate boundary transitions: Adult 45 (CRIT) vs 46 (WARN); 59 (WARN) vs 60 (PASS); 100 (PASS) vs 101 (WARN); 129 (WARN) vs 130 (CRIT).
  - SpO2 desaturation boundary: 88% (CRIT) vs 89% (WARN); 93% (WARN) vs 94% (PASS).
  - Blood pressure boundary: 80 mmHg systolic (CRIT) vs 81 (WARN); 89 (WARN) vs 90 (PASS); 140 (PASS) vs 141 (WARN); 179 (WARN) vs 180 (CRIT).
  - Respiration rate boundary: 8 br/min (CRIT) vs 9 (WARN); 11 (WARN) vs 12 (PASS); 20 (PASS) vs 21 (WARN); 29 (WARN) vs 30 (CRIT).
  - Pediatric O2 flow limit: 2.0 L/min (PASS) vs 2.1 L/min (CRITICAL).
  - Adult cannula flow limit: 6.0 L/min (PASS) vs 6.1 L/min (WARN).
  - Protocol versions: `adult_icu_v1.0`, `pediatric_icu_v1.0`, `neonatal_icu_v1.0`.
- **Automated Suite**: `tests/protocols/test_threshold_boundaries.py`

## 3. Explicit Uncertainty Policy & Abstention Tests
- **Objective**: Ensure uncertainty produces an explicit abstention or manual-review result, never a confident but unsupported safety status.
- **Verification**:
  - All N/A vital signs produce `WARNING` with explicit abstention findings (never defaulting to `PASS`).
  - Corrupted or unparseable readings produce `WARNING` requesting manual verification.
  - Empty equipment overlays produce `WARNING` requesting manual review.
  - Ambiguous equipment produces `WARNING` with overlay marked `FAIL`.
  - Poor image quality, blur, and severe optical glare produce `WARNING` with explicit abstention.
  - Unrecognized default images abstain with `WARNING` and never default to `PASS`.
- **Automated Suite**: `tests/safety/test_uncertainty_and_abstention.py` and `tests/safety/test_safety_escalation.py`

## 4. Tamper-Evident Cryptographic Audit Integrity
- **Objective**: Implement and test cryptographic hash-chain verification for clinical audit records.
- **Verification**:
  - Each record is chained via SHA-256 hash to its predecessor (`previous_hash`).
  - Genesis record has 64 zeros as `previous_hash`.
  - Tampering with any record field (e.g. altering status from `CRITICAL` to `PASS`) causes verification to FAIL.
  - Deletion of records or sequence breaks cause verification to FAIL.
  - Append-only clinician acknowledgements preserve hash-chain validity.
  - CLI `--verify-integrity` and API `/api/audit/verify` verification.
- **Automated Suite**: `tests/audit/test_audit_integrity.py`

## 5. Application Startup Lifecycle, Readiness & API Protection
- **Objective**: Move model initialization into application startup lifecycle and protect endpoints.
- **Verification**:
  - Application startup lifespan initializes model engine; `/api/ready` reflects runtime readiness.
  - CORS is restricted to approved origins (no wildcard `*` with credentials).
  - File uploads enforce 10MB size limit and valid image MIME types.
  - Base64 inspections enforce 15MB payload size limits.
  - Audit log pagination limits are bounded (1..500).
- **Automated Suite**: `tests/api/test_api_security_readiness.py`
