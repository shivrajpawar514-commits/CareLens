"""
CareLens Preset Scenarios for clinical evaluation, live demonstrations, and automated test suites.
"""

from typing import Dict, Any, List

PRESET_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "pediatric_o2_critical": {
        "id": "pediatric_o2_critical",
        "title": "Pediatric Oxygen Over-delivery (Critical)",
        "category": "Equipment_Setup",
        "protocol_id": "pediatric_icu_v1.0",
        "patient_context": "pediatric",
        "expected_status": "CRITICAL",
        "asset_url": "/assets/pediatric_oxygen_flow.svg",
        "description": "Nasal cannula flow meter visibly set to 8.0 L/min for a pediatric patient, exceeding the 2.0 L/min safe threshold.",
        "clinical_significance": "Risk of pulmonary oxygen toxicity, barotrauma, and mucosal drying in infants.",
    },
    "pediatric_o2_nominal": {
        "id": "pediatric_o2_nominal",
        "title": "Pediatric Oxygen Nominal Flow (Pass)",
        "category": "Equipment_Setup",
        "protocol_id": "pediatric_icu_v1.0",
        "patient_context": "pediatric",
        "expected_status": "PASS",
        "asset_url": "/assets/pediatric_oxygen_flow.svg",
        "description": "Pediatric oxygen flow meter verified at 1.0 L/min, within approved protocol limit.",
        "clinical_significance": "Safe titration under pediatric clinical care.",
    },
    "icu_monitor_critical": {
        "id": "icu_monitor_critical",
        "title": "ICU Monitor: Critical Desaturation & Shock (Critical)",
        "category": "Patient_Monitor",
        "protocol_id": "adult_icu_v1.0",
        "patient_context": "adult",
        "expected_status": "CRITICAL",
        "asset_url": "/assets/icu_patient_monitor.svg",
        "description": "ICU multi-parameter screen displaying HR 142 bpm (tachycardia), SpO2 84% (severe hypoxia), BP 78/45 mmHg (hypotensive shock), RR 32 (tachypnea).",
        "clinical_significance": "Acute patient deterioration requiring immediate clinical assessment.",
    },
    "icu_monitor_nominal": {
        "id": "icu_monitor_nominal",
        "title": "Adult ICU Monitor Nominal (Pass)",
        "category": "Patient_Monitor",
        "protocol_id": "adult_icu_v1.0",
        "patient_context": "adult",
        "expected_status": "PASS",
        "asset_url": "/assets/icu_monitor_nominal.svg",
        "description": "Adult ICU monitor displaying resting vitals: HR 72, SpO2 98%, BP 120/80, RR 16.",
        "clinical_significance": "All visible vital signs within approved reference ranges.",
    },
    "infusion_pump_warning": {
        "id": "infusion_pump_warning",
        "title": "Infusion Pump: Line Clamp Closed (Warning)",
        "category": "Equipment_Setup",
        "protocol_id": "adult_icu_v1.0",
        "patient_context": "adult",
        "expected_status": "WARNING",
        "asset_url": "/assets/infusion_pump.svg",
        "description": "Volumetric infusion pump is running at 125 mL/hr while the manual primary line roller clamp is closed.",
        "clinical_significance": "Impending downstream occlusion alarm, medication delay, or line extravasation.",
    },
    "unclear_low_light": {
        "id": "unclear_low_light",
        "title": "Severe Optical Glare / Obscured (Warning)",
        "category": "Unknown",
        "protocol_id": "adult_icu_v1.0",
        "patient_context": "adult",
        "expected_status": "WARNING",
        "asset_url": "/assets/unclear_low_light.svg",
        "description": "Excessive glare and camera blur obscure clinical monitor readouts. CareLens assigns WARNING and requests manual verification.",
        "clinical_significance": "Adheres to safety policy: uncertain high-risk inputs never default to unverified pass or failure.",
    },
}
