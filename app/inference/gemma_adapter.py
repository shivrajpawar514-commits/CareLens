"""
CareLens Gemma 4 Vision Inference Adapter.
Executes edge-native multimodal clinical inspection via Ollama with strict JSON contract compliance.
"""

import json
import re
import time
from typing import Optional, Dict, Any
import ollama

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
from app.inference.base import BaseInferenceAdapter


GEMMA_SYSTEM_INSTRUCTION = (
    "You analyze a provided medical-equipment image or patient-monitor frame for visible evidence only. "
    "Return exactly one JSON object matching the CareLens schema. Do not include Markdown or prose outside JSON. "
    "Never invent readings, equipment settings, connections, patient category, or bounding boxes. "
    "Use \"N/A\" for missing or unreadable vital signs. "
    "Use normalized integer boxes in [ymin, xmin, ymax, xmax] order, from 0 to 1000. "
    "Use only allowed enum values. "
    "Compare observations only against an explicitly supplied, applicable, versioned protocol. "
    "If the image or protocol context is insufficient, choose WARNING and request human verification in findings. "
    "Use CRITICAL only for a clearly visible condition that matches a validated high-risk rule. "
    "Keep audio_alert_text to one imperative sentence of fewer than 15 words. "
    "This output is advisory; never instruct the model or application to change clinical equipment settings automatically."
)


class GemmaVisionAdapter(BaseInferenceAdapter):
    def __init__(self, model_name: str = "gemma4:e2b", timeout_seconds: int = 45):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.client = ollama.Client()

    def audit_image(
        self,
        image_b64: str,
        protocol: Optional[ClinicalProtocol] = None,
        patient_context: str = "adult",
        inspection_type_hint: Optional[str] = None,
    ) -> CareLensResponse:
        """
        Runs Gemma 4 Vision multimodal audit on image_b64.
        Validates against protocol rules and returns canonical CareLensResponse.
        """
        active_protocol = protocol or get_protocol()
        engine = ProtocolEngine(active_protocol)

        # Construct protocol guidance for prompt
        protocol_guidance = (
            f"Active Protocol: {active_protocol.protocol_id} ({active_protocol.name})\n"
            f"Patient Context: {patient_context} ({active_protocol.population})\n"
            f"Reference Ranges: HR {active_protocol.vitals.hr_min}-{active_protocol.vitals.hr_max} bpm, "
            f"SpO2 >= {active_protocol.vitals.spo2_min_nominal}% (Critical <= {active_protocol.vitals.spo2_critical_threshold}%), "
            f"BP Systolic {active_protocol.vitals.bp_systolic_min}-{active_protocol.vitals.bp_systolic_max} mmHg, "
            f"RR {active_protocol.vitals.rr_min}-{active_protocol.vitals.rr_max} bpm.\n"
            f"Equipment Limit: Max O2 Flow = {active_protocol.equipment.max_pediatric_o2_lpm if 'pediatric' in patient_context.lower() else active_protocol.equipment.max_nasal_cannula_o2_lpm} L/min.\n"
        )
        if inspection_type_hint:
            protocol_guidance += f"Suggested Inspection Type: {inspection_type_hint}\n"

        user_prompt = (
            f"{GEMMA_SYSTEM_INSTRUCTION}\n\n"
            f"{protocol_guidance}\n"
            "Return ONLY the raw JSON object adhering strictly to the schema without any surrounding markdown code block:\n"
            "{\n"
            '  "inspection_type": "Equipment_Setup" | "Patient_Monitor" | "Unknown",\n'
            '  "overall_status": "PASS" | "WARNING" | "CRITICAL",\n'
            '  "vitals_extracted": {\n'
            '    "heart_rate_bpm": "string or N/A",\n'
            '    "spo2_percent": "string or N/A",\n'
            '    "blood_pressure_mmHg": "string or N/A",\n'
            '    "respiration_rate": "string or N/A"\n'
            "  },\n"
            '  "visual_overlays": [\n'
            "    {\n"
            '      "label": "string",\n'
            '      "box_2d": [ymin, xmin, ymax, xmax],\n'
            '      "status": "PASS" | "FAIL",\n'
            '      "detail": "string"\n'
            "    }\n"
            "  ],\n"
            '  "findings": ["string", ...],\n'
            '  "audio_alert_text": "One imperative sentence under 15 words."\n'
            "}"
        )

        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=user_prompt,
                images=[image_b64],
                format="json",
            )
            raw_text = response.response.strip()
            parsed_json = self._extract_json(raw_text)

            # Re-check via protocol engine to guarantee deterministic safety rules
            carelens_resp = CareLensResponse.model_validate(parsed_json)
            return self._post_process_with_protocol(carelens_resp, engine, patient_context)

        except Exception as e:
            # Propagate error so calling engine can decide to fallback to deterministic edge CV
            raise RuntimeError(f"Gemma 4 inference failed: {e}") from e

    def _extract_json(self, raw_text: str) -> Dict[str, Any]:
        """Strips markdown code blocks and locates the JSON dictionary."""
        cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(cleaned)

    def _post_process_with_protocol(
        self,
        resp: CareLensResponse,
        engine: ProtocolEngine,
        patient_context: str,
    ) -> CareLensResponse:
        """
        Clinical safety layer: Evaluates model observations deterministically
        against the versioned protocol rules to ensure no critical violation is missed.
        """
        # Evaluate vitals if present
        v_status, v_findings, v_crit = engine.evaluate_vitals(resp.vitals_extracted)
        # Evaluate equipment overlays
        e_status, e_findings, e_crit = engine.evaluate_equipment(resp.visual_overlays, patient_context)

        # Merge statuses (escalate to highest severity)
        final_status = resp.overall_status
        if v_status == OverallStatus.CRITICAL or e_status == OverallStatus.CRITICAL:
            final_status = OverallStatus.CRITICAL
        elif (v_status == OverallStatus.WARNING or e_status == OverallStatus.WARNING) and final_status == OverallStatus.PASS:
            final_status = OverallStatus.WARNING

        # Combine unique findings
        combined_findings = list(dict.fromkeys(resp.findings + v_findings + e_findings))
        if not combined_findings:
            combined_findings = ["Visible observations inspected against active clinical protocol."]

        # Ensure audio alert matches status and is under 15 words
        audio = resp.audio_alert_text
        if len(audio.split()) >= 15 or final_status != resp.overall_status:
            audio = engine.generate_audio_alert(final_status, v_crit + e_crit, resp.inspection_type.value)

        return CareLensResponse(
            inspection_type=resp.inspection_type,
            overall_status=final_status,
            vitals_extracted=resp.vitals_extracted,
            visual_overlays=resp.visual_overlays,
            findings=combined_findings,
            audio_alert_text=audio,
        )
