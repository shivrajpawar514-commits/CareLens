"""
CareLens Clinical Protocol Engine.
Evaluates visual observations against versioned protocol rules and assigns risk tiers.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from app.schema.contract import (
    OverallStatus,
    OverlayStatus,
    VisualOverlay,
    VitalsExtracted,
)
from app.protocol_engine.protocols import ClinicalProtocol, get_protocol


class ProtocolEngine:
    def __init__(self, protocol: Optional[ClinicalProtocol] = None):
        self.protocol = protocol or get_protocol()

    def evaluate_vitals(
        self,
        vitals: VitalsExtracted,
    ) -> Tuple[OverallStatus, List[str], List[str]]:
        """
        Evaluate extracted vitals against protocol thresholds.
        Returns: (status, findings, critical_issues)
        """
        findings: List[str] = []
        critical_issues: List[str] = []
        warning_issues: List[str] = []
        t = self.protocol.vitals

        # 1. Heart Rate
        if vitals.heart_rate_bpm != "N/A":
            try:
                hr = int(re.sub(r"[^\d]", "", vitals.heart_rate_bpm))
                if hr <= t.hr_critical_low:
                    msg = f"Critical bradycardia detected: HR {hr} bpm (threshold <= {t.hr_critical_low})."
                    critical_issues.append(msg)
                    findings.append(msg)
                elif hr >= t.hr_critical_high:
                    msg = f"Critical tachycardia detected: HR {hr} bpm (threshold >= {t.hr_critical_high})."
                    critical_issues.append(msg)
                    findings.append(msg)
                elif hr < t.hr_min or hr > t.hr_max:
                    msg = f"Heart rate {hr} bpm is outside nominal protocol range ({t.hr_min}-{t.hr_max} bpm)."
                    warning_issues.append(msg)
                    findings.append(msg)
                else:
                    findings.append(f"Heart rate {hr} bpm is within nominal range ({t.hr_min}-{t.hr_max} bpm).")
            except (ValueError, TypeError):
                findings.append(f"Heart rate value '{vitals.heart_rate_bpm}' could not be parsed numerically.")
                warning_issues.append("Unparseable HR")

        # 2. SpO2
        if vitals.spo2_percent != "N/A":
            try:
                spo2 = int(re.sub(r"[^\d]", "", vitals.spo2_percent))
                if spo2 <= t.spo2_critical_threshold:
                    msg = f"Critical oxygen desaturation detected: SpO2 {spo2}% (threshold <= {t.spo2_critical_threshold}%)."
                    critical_issues.append(msg)
                    findings.append(msg)
                elif spo2 <= t.spo2_warning_threshold:
                    msg = f"Sub-nominal SpO2 {spo2}% detected (nominal >= {t.spo2_min_nominal}%)."
                    warning_issues.append(msg)
                    findings.append(msg)
                elif t.spo2_hyperoxia_warning and spo2 >= t.spo2_hyperoxia_warning:
                    msg = f"Potential hyperoxia detected in {self.protocol.population}: SpO2 {spo2}% (target 90-95%)."
                    warning_issues.append(msg)
                    findings.append(msg)
                else:
                    findings.append(f"SpO2 {spo2}% is nominal under {self.protocol.name}.")
            except (ValueError, TypeError):
                findings.append(f"SpO2 value '{vitals.spo2_percent}' could not be parsed numerically.")
                warning_issues.append("Unparseable SpO2")

        # 3. Blood Pressure
        if vitals.blood_pressure_mmHg != "N/A":
            try:
                # Look for systolic/diastolic e.g. 120/80 or 78/45
                parts = re.findall(r"\d+", vitals.blood_pressure_mmHg)
                if parts:
                    systolic = int(parts[0])
                    diastolic = int(parts[1]) if len(parts) > 1 else None
                    if systolic <= t.bp_systolic_critical_low:
                        msg = f"Critical hypotension detected: Systolic BP {systolic} mmHg (threshold <= {t.bp_systolic_critical_low})."
                        critical_issues.append(msg)
                        findings.append(msg)
                    elif systolic >= t.bp_systolic_critical_high:
                        msg = f"Critical hypertension detected: Systolic BP {systolic} mmHg (threshold >= {t.bp_systolic_critical_high})."
                        critical_issues.append(msg)
                        findings.append(msg)
                    elif systolic < t.bp_systolic_min or systolic > t.bp_systolic_max:
                        msg = f"Blood pressure {vitals.blood_pressure_mmHg} mmHg outside nominal range ({t.bp_systolic_min}-{t.bp_systolic_max})."
                        warning_issues.append(msg)
                        findings.append(msg)
                    else:
                        findings.append(f"Blood pressure {vitals.blood_pressure_mmHg} mmHg is nominal.")
            except (ValueError, TypeError):
                findings.append(f"Blood pressure '{vitals.blood_pressure_mmHg}' could not be parsed.")
                warning_issues.append("Unparseable BP")

        # 4. Respiration Rate
        if vitals.respiration_rate != "N/A":
            try:
                rr = int(re.sub(r"[^\d]", "", vitals.respiration_rate))
                if rr <= t.rr_critical_low:
                    msg = f"Critical hypoventilation/bradypnea: RR {rr} (threshold <= {t.rr_critical_low})."
                    critical_issues.append(msg)
                    findings.append(msg)
                elif rr >= t.rr_critical_high:
                    msg = f"Critical tachypnea detected: RR {rr} (threshold >= {t.rr_critical_high})."
                    critical_issues.append(msg)
                    findings.append(msg)
                elif rr < t.rr_min or rr > t.rr_max:
                    msg = f"Respiration rate {rr} breaths/min outside protocol range ({t.rr_min}-{t.rr_max})."
                    warning_issues.append(msg)
                    findings.append(msg)
                else:
                    findings.append(f"Respiration rate {rr} breaths/min is nominal.")
            except (ValueError, TypeError):
                findings.append(f"Respiration rate '{vitals.respiration_rate}' could not be parsed.")
                warning_issues.append("Unparseable RR")

        # Check overall vitals status
        if critical_issues:
            status = OverallStatus.CRITICAL
        elif warning_issues:
            status = OverallStatus.WARNING
        else:
            status = OverallStatus.PASS

        return status, findings, critical_issues

    def evaluate_equipment(
        self,
        overlays: List[VisualOverlay],
        patient_context: str = "adult",
    ) -> Tuple[OverallStatus, List[str], List[str]]:
        """
        Evaluate equipment visual overlays against protocol rules.
        """
        findings: List[str] = []
        critical_issues: List[str] = []
        warning_issues: List[str] = []

        is_pediatric = "pediatric" in self.protocol.protocol_id or patient_context.lower() in ["pediatric", "child", "infant"]

        for overlay in overlays:
            label_lower = overlay.label.lower()
            detail_lower = overlay.detail.lower()

            # Rule 1: Pediatric oxygen flow meter threshold
            if "oxygen" in label_lower or "flow" in label_lower or "rotameter" in label_lower:
                flow_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:l/min|lpm|liters)", detail_lower)
                if flow_match:
                    flow_val = float(flow_match.group(1))
                    if is_pediatric and flow_val > self.protocol.equipment.max_pediatric_o2_lpm:
                        msg = f"High oxygen flow of {flow_val} L/min exceeds pediatric threshold ({self.protocol.equipment.max_pediatric_o2_lpm} L/min)."
                        critical_issues.append(msg)
                        findings.append(msg)
                        overlay.status = OverlayStatus.FAIL
                        overlay.detail = f"Observed {flow_val} L/min exceeds pediatric limit ({self.protocol.equipment.max_pediatric_o2_lpm} L/min); verify immediately."
                    elif flow_val > self.protocol.equipment.max_nasal_cannula_o2_lpm:
                        msg = f"Oxygen flow of {flow_val} L/min exceeds nasal cannula guideline ({self.protocol.equipment.max_nasal_cannula_o2_lpm} L/min)."
                        warning_issues.append(msg)
                        findings.append(msg)
                    else:
                        findings.append(f"Oxygen flow rate {flow_val} L/min verified within {self.protocol.name} limits.")

            # Rule 2: Roller clamp / occlusion
            if "clamp" in label_lower:
                if "closed" in detail_lower or "occluded" in detail_lower:
                    msg = "Infusion line roller clamp is closed during active infusion."
                    warning_issues.append(msg)
                    findings.append(msg)
                    overlay.status = OverlayStatus.FAIL

            # Rule 3: Air bubble in IV line
            if "air" in detail_lower and "line" in detail_lower:
                msg = "Air bubble detected in intravenous infusion line."
                critical_issues.append(msg)
                findings.append(msg)
                overlay.status = OverlayStatus.FAIL

            # Rule 4: Overlay marked as FAIL by vision model
            if overlay.status == OverlayStatus.FAIL and overlay.detail not in findings:
                findings.append(f"Component '{overlay.label}' flagged: {overlay.detail}")
                warning_issues.append(overlay.label)

        if critical_issues:
            status = OverallStatus.CRITICAL
        elif warning_issues:
            status = OverallStatus.WARNING
        else:
            status = OverallStatus.PASS

        return status, findings, critical_issues

    def generate_audio_alert(
        self,
        overall_status: OverallStatus,
        critical_issues: List[str],
        inspection_type: str,
    ) -> str:
        """
        Generates exactly one imperative sentence under 15 words.
        """
        if overall_status == OverallStatus.CRITICAL:
            if any("oxygen" in issue.lower() for issue in critical_issues):
                return "Verify pediatric oxygen flow rate immediately against patient prescription."
            if any("desaturation" in issue.lower() or "spo2" in issue.lower() for issue in critical_issues):
                return "Verify patient monitor readings and oxygen saturation immediately."
            if any("bradycardia" in issue.lower() or "tachycardia" in issue.lower() for issue in critical_issues):
                return "Verify patient heart rate and clinical status immediately."
            if any("hypotension" in issue.lower() or "hypertension" in issue.lower() for issue in critical_issues):
                return "Verify patient blood pressure and cardiovascular status immediately."
            return "Critical observation detected; verify patient and equipment setup immediately."

        if overall_status == OverallStatus.WARNING:
            if inspection_type == "Equipment_Setup":
                return "Verify equipment connections and settings against the approved clinical protocol."
            return "Verify patient monitor readings against the approved clinical protocol."

        # PASS
        return "All visible parameters match the approved clinical protocol."
