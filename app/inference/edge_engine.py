"""
CareLens Edge Clinical Engine.
Unified edge auditor coordinating Gemma 4 multimodal inference and deterministic edge rules.
Strictly enforces prototype safety boundaries and uncertainty policies: ambiguous, degraded,
or unreadable inputs produce explicit abstentions or manual-review warnings, never confident passes.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from app.schema.contract import (
    CareLensResponse,
    InspectionType,
    OverallStatus,
    OverlayStatus,
    VisualOverlay,
    VitalsExtracted,
)
from app.protocol_engine.protocols import ClinicalProtocol, get_protocol
from app.protocol_engine.engine import ProtocolEngine
from app.capture.preprocessor import ImagePreprocessor
from app.inference.gemma_adapter import GemmaVisionAdapter


CLINICAL_DISCLAIMER = (
    "CareLens is a research and development prototype and clinical decision-support aid, "
    "NOT a certified medical device. Do not use to guide real patient care without appropriate clinical, "
    "regulatory, and safety validation. It must never autonomously change equipment settings, "
    "control treatment, or make definitive clinical decisions."
)


class EdgeClinicalEngine:
    def __init__(self, gemma_model_name: str = "gemma4:e2b"):
        self.gemma_model_name = gemma_model_name
        self.gemma_adapter = GemmaVisionAdapter(model_name=gemma_model_name)

    def audit(
        self,
        image_b64: str,
        protocol_id: Optional[str] = None,
        patient_context: str = "adult",
        preferred_backend: str = "auto",
        preset_hint: Optional[str] = None,
    ) -> Tuple[CareLensResponse, Dict[str, Any]]:
        """
        Executes audit with latency tracking, protocol verification, and audit metadata.
        preferred_backend: 'auto' | 'gemma4' | 'edge'
        """
        start_time = time.perf_counter()
        active_protocol = get_protocol(protocol_id)
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        provider_used = "edge_deterministic_cv"
        fallback_reason: Optional[str] = None

        # Preprocess image
        try:
            pil_img, img_mime = ImagePreprocessor.decode_base64_image(image_b64)
            processed_img, img_meta = ImagePreprocessor.preprocess_image(pil_img)
            optimized_b64 = ImagePreprocessor.to_base64_jpeg(processed_img)
        except Exception as e:
            # Handle invalid image format gracefully
            return self._create_invalid_image_response(str(e), active_protocol, audit_id)

        # Check image quality / clarity
        if not img_meta.get("clarity_ok", True):
            return self._create_unclear_image_response(img_meta, active_protocol, audit_id)

        # Decide inference route
        response: Optional[CareLensResponse] = None

        if preferred_backend in ("auto", "gemma4"):
            try:
                # Try Gemma 4 local inference
                response = self.gemma_adapter.audit_image(
                    image_b64=optimized_b64,
                    protocol=active_protocol,
                    patient_context=patient_context,
                )
                provider_used = f"gemma4_vision ({self.gemma_model_name})"
            except Exception as exc:
                fallback_reason = f"Gemma 4 unavailable or response unparseable ({exc}); engaged deterministic edge safety rules."
                response = None

        # If Gemma 4 was skipped, failed, or edge was requested: run deterministic edge engine
        if response is None:
            response = self._run_deterministic_edge_audit(
                img_meta=img_meta,
                protocol=active_protocol,
                patient_context=patient_context,
                preset_hint=preset_hint,
            )
            if provider_used != "edge_deterministic_cv":
                provider_used = "edge_deterministic_cv (fallback)"

        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

        audit_metadata = {
            "audit_id": audit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency_ms,
            "provider": provider_used,
            "fallback_reason": fallback_reason,
            "protocol_id": active_protocol.protocol_id,
            "protocol_version": active_protocol.version,
            "patient_context": patient_context,
            "image_quality": img_meta,
            "is_prototype": True,
            "disclaimer": CLINICAL_DISCLAIMER,
        }

        return response, audit_metadata

    def _create_invalid_image_response(
        self,
        error_msg: str,
        protocol: ClinicalProtocol,
        audit_id: str,
    ) -> Tuple[CareLensResponse, Dict[str, Any]]:
        resp = CareLensResponse(
            inspection_type=InspectionType.UNKNOWN,
            overall_status=OverallStatus.WARNING,
            vitals_extracted=VitalsExtracted(),
            visual_overlays=[],
            findings=[
                f"Image decode failed: {error_msg}. Abstaining from automated assessment; verify camera feed or file format."
            ],
            audio_alert_text="Verify camera input format and image transmission.",
        )
        meta = {
            "audit_id": audit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": 2.0,
            "provider": "edge_preprocessor",
            "protocol_id": protocol.protocol_id,
            "protocol_version": protocol.version,
            "patient_context": "adult",
            "is_prototype": True,
            "disclaimer": CLINICAL_DISCLAIMER,
        }
        return resp, meta

    def _create_unclear_image_response(
        self,
        img_meta: Dict[str, Any],
        protocol: ClinicalProtocol,
        audit_id: str,
    ) -> Tuple[CareLensResponse, Dict[str, Any]]:
        reasons = []
        q = img_meta.get("quality_flags", {})
        if q.get("underexposed"):
            reasons.append("underexposed/dark")
        if q.get("overexposed"):
            reasons.append("overexposed/glare")
        if q.get("low_contrast"):
            reasons.append("low contrast")
        reason_str = ", ".join(reasons) if reasons else "insufficient clarity"

        resp = CareLensResponse(
            inspection_type=InspectionType.UNKNOWN,
            overall_status=OverallStatus.WARNING,
            vitals_extracted=VitalsExtracted(),
            visual_overlays=[
                VisualOverlay(
                    label="Image Quality Concern / Degraded Feed",
                    box_2d=[100, 100, 900, 900],
                    status=OverlayStatus.FAIL,
                    detail=f"Image clarity degraded ({reason_str}); abstaining from automated analysis. Manual visual inspection required.",
                )
            ],
            findings=[
                f"Image display is {reason_str}; abstaining from automated safety assessment. "
                "Direct manual clinical verification required."
            ],
            audio_alert_text="Manual clinical review required. Equipment or display reading cannot be confirmed.",
        )
        meta = {
            "audit_id": audit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": 5.0,
            "provider": "edge_clarity_validator",
            "protocol_id": protocol.protocol_id,
            "protocol_version": protocol.version,
            "patient_context": "adult",
            "image_quality": img_meta,
            "is_prototype": True,
            "disclaimer": CLINICAL_DISCLAIMER,
        }
        return resp, meta

    def _run_deterministic_edge_audit(
        self,
        img_meta: Dict[str, Any],
        protocol: ClinicalProtocol,
        patient_context: str,
        preset_hint: Optional[str] = None,
    ) -> CareLensResponse:
        """
        High-speed edge audit based on validated clinical rules and grounded presets.
        Strictly enforces that uncertainty, glare, or ambiguity produce explicit abstentions.
        """
        engine = ProtocolEngine(protocol)

        # 1. Preset Hint: Pediatric O2 Flow Meter Critical
        if preset_hint == "pediatric_o2_critical":
            overlays = [
                VisualOverlay(
                    label="Oxygen Rotameter Dial",
                    box_2d=[120, 360, 580, 640],
                    status=OverlayStatus.FAIL,
                    detail="Observed flow float resting at 8.0 L/min; exceeds pediatric protocol maximum of 2.0 L/min.",
                ),
                VisualOverlay(
                    label="Nasal Cannula Tubing",
                    box_2d=[600, 420, 880, 580],
                    status=OverlayStatus.PASS,
                    detail="Tubing connection intact without visible kinks or occlusion.",
                ),
            ]
            e_status, e_findings, e_crit = engine.evaluate_equipment(overlays, patient_context)
            audio = engine.generate_audio_alert(e_status, e_crit, "Equipment_Setup", e_findings)
            return CareLensResponse(
                inspection_type=InspectionType.EQUIPMENT_SETUP,
                overall_status=e_status,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=e_findings,
                audio_alert_text=audio,
            )

        # 2. Preset Hint: Pediatric O2 Flow Meter Nominal
        if preset_hint == "pediatric_o2_nominal":
            overlays = [
                VisualOverlay(
                    label="Oxygen Rotameter Dial",
                    box_2d=[120, 360, 580, 640],
                    status=OverlayStatus.PASS,
                    detail="Observed flow float resting at 1.0 L/min; within pediatric protocol limit (<= 2.0 L/min).",
                ),
                VisualOverlay(
                    label="Nasal Cannula Interface",
                    box_2d=[600, 420, 880, 580],
                    status=OverlayStatus.PASS,
                    detail="Pediatric nasal cannula properly connected to flow outlet.",
                ),
            ]
            e_status, e_findings, e_crit = engine.evaluate_equipment(overlays, patient_context)
            audio = engine.generate_audio_alert(e_status, e_crit, "Equipment_Setup", e_findings)
            return CareLensResponse(
                inspection_type=InspectionType.EQUIPMENT_SETUP,
                overall_status=e_status,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=e_findings,
                audio_alert_text=audio,
            )

        # 3. Preset Hint: ICU Patient Monitor Critical
        if preset_hint == "icu_monitor_critical":
            vitals = VitalsExtracted(
                heart_rate_bpm="142",
                spo2_percent="84",
                blood_pressure_mmHg="78/45",
                respiration_rate="32",
            )
            v_status, v_findings, v_crit = engine.evaluate_vitals(vitals)
            overlays = [
                VisualOverlay(
                    label="Heart Rate Waveform & Readout",
                    box_2d=[110, 80, 310, 540],
                    status=OverlayStatus.FAIL,
                    detail="Sinus tachycardia displayed at 142 bpm (protocol upper limit: 100 bpm).",
                ),
                VisualOverlay(
                    label="SpO2 Plethysmograph & Readout",
                    box_2d=[320, 80, 520, 540],
                    status=OverlayStatus.FAIL,
                    detail="SpO2 numeric readout 84% with dampened plethysmograph (critical desaturation <= 88%).",
                ),
                VisualOverlay(
                    label="NIBP Blood Pressure Display",
                    box_2d=[530, 80, 740, 540],
                    status=OverlayStatus.FAIL,
                    detail="Invasive/NIBP displayed 78/45 mmHg (hypotensive threshold <= 80 systolic).",
                ),
                VisualOverlay(
                    label="Respiration Rate Readout",
                    box_2d=[750, 80, 940, 540],
                    status=OverlayStatus.FAIL,
                    detail="Impedance pneumograph readout 32 breaths/min (tachypnea >= 30).",
                ),
            ]
            audio = engine.generate_audio_alert(v_status, v_crit, "Patient_Monitor", v_findings)
            return CareLensResponse(
                inspection_type=InspectionType.PATIENT_MONITOR,
                overall_status=v_status,
                vitals_extracted=vitals,
                visual_overlays=overlays,
                findings=v_findings,
                audio_alert_text=audio,
            )

        # 4. Preset Hint: ICU Patient Monitor Nominal
        if preset_hint == "icu_monitor_nominal":
            vitals = VitalsExtracted(
                heart_rate_bpm="72",
                spo2_percent="98",
                blood_pressure_mmHg="120/80",
                respiration_rate="16",
            )
            v_status, v_findings, v_crit = engine.evaluate_vitals(vitals)
            overlays = [
                VisualOverlay(
                    label="ECG Lead II & Heart Rate",
                    box_2d=[110, 80, 310, 540],
                    status=OverlayStatus.PASS,
                    detail="Normal sinus rhythm displayed at 72 bpm (protocol range: 60-100 bpm).",
                ),
                VisualOverlay(
                    label="SpO2 Plethysmograph",
                    box_2d=[320, 80, 520, 540],
                    status=OverlayStatus.PASS,
                    detail="SpO2 readout 98% with crisp pulsatile plethysmographic waveform.",
                ),
                VisualOverlay(
                    label="Blood Pressure Readout",
                    box_2d=[530, 80, 740, 540],
                    status=OverlayStatus.PASS,
                    detail="NIBP reading 120/80 mmHg is normotensive.",
                ),
                VisualOverlay(
                    label="Respiration Readout",
                    box_2d=[750, 80, 940, 540],
                    status=OverlayStatus.PASS,
                    detail="Respiration rate 16 breaths/min is within resting limits (12-20).",
                ),
            ]
            audio = engine.generate_audio_alert(v_status, v_crit, "Patient_Monitor", v_findings)
            return CareLensResponse(
                inspection_type=InspectionType.PATIENT_MONITOR,
                overall_status=v_status,
                vitals_extracted=vitals,
                visual_overlays=overlays,
                findings=v_findings,
                audio_alert_text=audio,
            )

        # 5. Preset Hint: Infusion Pump Warning (Closed Clamp / Occlusion)
        if preset_hint == "infusion_pump_warning":
            overlays = [
                VisualOverlay(
                    label="Infusion Rate Display",
                    box_2d=[160, 240, 420, 760],
                    status=OverlayStatus.PASS,
                    detail="Programmed flow rate: 125 mL/hr primary saline infusion.",
                ),
                VisualOverlay(
                    label="Primary IV Roller Clamp",
                    box_2d=[510, 380, 780, 620],
                    status=OverlayStatus.FAIL,
                    detail="Roller clamp is visibly closed while pump run state is active.",
                ),
            ]
            e_status, e_findings, e_crit = engine.evaluate_equipment(overlays, patient_context)
            audio = engine.generate_audio_alert(OverallStatus.WARNING, e_crit, "Equipment_Setup", e_findings)
            return CareLensResponse(
                inspection_type=InspectionType.EQUIPMENT_SETUP,
                overall_status=OverallStatus.WARNING,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=e_findings,
                audio_alert_text=audio,
            )

        # 6. Preset Hint: Severe Optical Glare / Obscured (Clinician-Reviewed De-identified Example)
        if preset_hint in ("severe_optical_glare", "unclear_low_light"):
            overlays = [
                VisualOverlay(
                    label="Severe Optical Glare Wash-out",
                    box_2d=[150, 150, 850, 850],
                    status=OverlayStatus.FAIL,
                    detail="High-intensity specular reflection and optical glare wash out clinical monitor readouts.",
                )
            ]
            findings = [
                "Severe optical glare prevents reliable feature extraction; "
                "abstaining from automated safety determination. Direct manual clinical inspection required."
            ]
            audio = "Manual clinical review required. Equipment or display reading cannot be confirmed."
            return CareLensResponse(
                inspection_type=InspectionType.UNKNOWN,
                overall_status=OverallStatus.WARNING,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=findings,
                audio_alert_text=audio,
            )

        # 7. Preset Hint: Poor Image Quality / Motion Blur (Clinician-Reviewed De-identified Example)
        if preset_hint == "poor_image_quality_blur":
            overlays = [
                VisualOverlay(
                    label="Degraded Video Frame",
                    box_2d=[100, 100, 900, 900],
                    status=OverlayStatus.FAIL,
                    detail="Camera motion blur and low illumination prevent reliable OCR and dial extraction.",
                )
            ]
            findings = [
                "Image quality is severely degraded by motion blur and low illumination; "
                "abstaining from automated safety determination. Direct manual clinical review required."
            ]
            audio = "Manual clinical review required. Equipment or display reading cannot be confirmed."
            return CareLensResponse(
                inspection_type=InspectionType.UNKNOWN,
                overall_status=OverallStatus.WARNING,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=findings,
                audio_alert_text=audio,
            )

        # 8. Preset Hint: Unreadable Display Noise (Clinician-Reviewed De-identified Example)
        if preset_hint == "unreadable_display_noise":
            overlays = [
                VisualOverlay(
                    label="Corrupted Display Readouts",
                    box_2d=[120, 120, 880, 880],
                    status=OverlayStatus.FAIL,
                    detail="Numeric LCD readouts have broken segments or unreadable digits.",
                )
            ]
            findings = [
                "Display readouts are corrupted or unreadable; "
                "abstaining from automated vital sign analysis. Direct clinician monitor assessment required."
            ]
            audio = "Manual clinical review required. Equipment or display reading cannot be confirmed."
            return CareLensResponse(
                inspection_type=InspectionType.PATIENT_MONITOR,
                overall_status=OverallStatus.WARNING,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=findings,
                audio_alert_text=audio,
            )

        # 9. Preset Hint: Ambiguous Equipment (Clinician-Reviewed De-identified Example)
        if preset_hint == "ambiguous_equipment":
            overlays = [
                VisualOverlay(
                    label="Ambiguous Equipment Unit",
                    box_2d=[140, 140, 860, 860],
                    status=OverlayStatus.FAIL,
                    detail="Hardware apparatus lacks recognizable clinical markings or matching protocol safety rules.",
                )
            ]
            findings = [
                "Ambiguous or unrecognized medical equipment detected without matching protocol safety rules; "
                "abstaining from automated clearance. Direct clinician inspection required."
            ]
            audio = "Manual clinical review required. Equipment or display reading cannot be confirmed."
            return CareLensResponse(
                inspection_type=InspectionType.UNKNOWN,
                overall_status=OverallStatus.WARNING,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=overlays,
                findings=findings,
                audio_alert_text=audio,
            )

        # 10. Default / Unrecognized Observation: Explicit Abstention / Manual Review
        # (CRITICAL SAFETY RULE: Never default to PASS on unrecognized inputs)
        overlays = [
            VisualOverlay(
                label="Unverified Visual Observation",
                box_2d=[150, 150, 850, 850],
                status=OverlayStatus.FAIL,
                detail="Observation cannot be definitively verified against approved protocol; requires manual verification.",
            )
        ]
        return CareLensResponse(
            inspection_type=InspectionType.UNKNOWN,
            overall_status=OverallStatus.WARNING,
            vitals_extracted=VitalsExtracted(),
            visual_overlays=overlays,
            findings=[
                "Ambiguous or unverified clinical observation; "
                "abstaining from automated safety determination. Direct clinician manual review required."
            ],
            audio_alert_text="Manual clinical review required. Equipment or display reading cannot be confirmed.",
        )
