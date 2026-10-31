"""
CareLens Clinical Safety Uncertainty Policy and Explicit Abstention Tests.
Ensures uncertainty, degraded image quality, severe glare, unreadable displays,
and ambiguous equipment produce an explicit abstention or manual-review result,
NOT a confident but unsupported safety status.
"""

import unittest
import base64
import io
from PIL import Image, ImageDraw

from app.schema.contract import OverallStatus, OverlayStatus, VisualOverlay, VitalsExtracted, InspectionType
from app.protocol_engine.protocols import get_protocol
from app.protocol_engine.engine import ProtocolEngine
from app.inference.edge_engine import EdgeClinicalEngine


class TestUncertaintyAndAbstention(unittest.TestCase):
    def setUp(self):
        self.proto = get_protocol("adult_icu_v1.0")
        self.engine = ProtocolEngine(self.proto)
        self.edge_engine = EdgeClinicalEngine()

    def _create_high_contrast_image_b64(self) -> str:
        img = Image.new("RGB", (200, 200), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 180, 180], fill=(240, 240, 240))
        draw.text((30, 50), "TEST FEED", fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def test_all_na_vitals_produce_explicit_abstention_warning(self):
        """
        When all vital signs are N/A (unreadable or absent), the engine must produce
        an explicit abstention / manual-review result (WARNING), NEVER a confident PASS.
        """
        vitals = VitalsExtracted(
            heart_rate_bpm="N/A",
            spo2_percent="N/A",
            blood_pressure_mmHg="N/A",
            respiration_rate="N/A",
        )
        status, findings, crits = self.engine.evaluate_vitals(vitals)
        self.assertEqual(status, OverallStatus.WARNING)
        self.assertTrue(any("abstaining" in f.lower() or "manual clinical verification" in f.lower() for f in findings))
        self.assertEqual(len(crits), 0)

    def test_corrupted_vital_strings_produce_warning_and_manual_review(self):
        """Unparseable or corrupted vital strings must produce WARNING and demand manual review."""
        vitals = VitalsExtracted(
            heart_rate_bpm="ERR_CORRUPT",
            spo2_percent="--",
            blood_pressure_mmHg="XXX/YY",
            respiration_rate="NAN",
        )
        status, findings, crits = self.engine.evaluate_vitals(vitals)
        self.assertEqual(status, OverallStatus.WARNING)
        self.assertTrue(any("manual review required" in f.lower() for f in findings))

    def test_empty_equipment_overlays_produce_abstention_warning(self):
        """When no equipment components are detected, engine must abstain and flag WARNING."""
        status, findings, crits = self.engine.evaluate_equipment([], "adult")
        self.assertEqual(status, OverallStatus.WARNING)
        self.assertTrue(any("abstaining" in f.lower() or "manual clinical inspection" in f.lower() for f in findings))

    def test_ambiguous_equipment_produces_abstention_and_fail_overlay(self):
        """Ambiguous non-protocol equipment must produce WARNING and overlay FAIL, never PASS."""
        overlays = [
            VisualOverlay(
                label="Ambiguous Equipment Box",
                box_2d=[100, 100, 500, 500],
                status=OverlayStatus.PASS,
                detail="Unrecognized dial apparatus without clinical markings.",
            )
        ]
        status, findings, crits = self.engine.evaluate_equipment(overlays, "adult")
        self.assertEqual(status, OverallStatus.WARNING)
        self.assertEqual(overlays[0].status, OverlayStatus.FAIL)
        self.assertTrue(any("abstaining" in f.lower() or "ambiguous" in f.lower() for f in findings))

    def test_preprocessor_low_contrast_produces_abstention(self):
        """Pre-processor detects unreadable low-contrast image and explicitly abstains."""
        # Flat blank image has 0 contrast stddev
        img = Image.new("RGB", (200, 200), color=(50, 50, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        resp, meta = self.edge_engine.audit(image_b64=b64)
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertEqual(resp.visual_overlays[0].status, OverlayStatus.FAIL)
        self.assertTrue(any("abstaining" in f.lower() for f in resp.findings))

    def test_clinician_preset_poor_image_quality_blur(self):
        """Clinician-reviewed example: poor image quality / motion blur produces abstention."""
        b64 = self._create_high_contrast_image_b64()
        resp, meta = self.edge_engine.audit(
            image_b64=b64,
            preset_hint="poor_image_quality_blur",
        )
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertTrue(any("abstaining" in f.lower() for f in resp.findings))
        self.assertEqual(resp.visual_overlays[0].status, OverlayStatus.FAIL)
        self.assertIn("Manual clinical review required", resp.audio_alert_text)

    def test_clinician_preset_severe_optical_glare(self):
        """Clinician-reviewed example: severe optical glare produces abstention."""
        b64 = self._create_high_contrast_image_b64()
        resp, meta = self.edge_engine.audit(
            image_b64=b64,
            preset_hint="severe_optical_glare",
        )
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertTrue(any("glare" in f.lower() and "abstaining" in f.lower() for f in resp.findings))
        self.assertEqual(resp.visual_overlays[0].status, OverlayStatus.FAIL)
        self.assertIn("Manual clinical review required", resp.audio_alert_text)

    def test_clinician_preset_unreadable_display_noise(self):
        """Clinician-reviewed example: unreadable monitor display noise produces abstention."""
        b64 = self._create_high_contrast_image_b64()
        resp, meta = self.edge_engine.audit(
            image_b64=b64,
            preset_hint="unreadable_display_noise",
        )
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertTrue(any("unreadable" in f.lower() and "abstaining" in f.lower() for f in resp.findings))
        self.assertEqual(resp.visual_overlays[0].status, OverlayStatus.FAIL)
        self.assertIn("Manual clinical review required", resp.audio_alert_text)

    def test_clinician_preset_ambiguous_equipment(self):
        """Clinician-reviewed example: ambiguous equipment produces abstention."""
        b64 = self._create_high_contrast_image_b64()
        resp, meta = self.edge_engine.audit(
            image_b64=b64,
            preset_hint="ambiguous_equipment",
        )
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertTrue(any("ambiguous" in f.lower() and "abstaining" in f.lower() for f in resp.findings))
        self.assertEqual(resp.visual_overlays[0].status, OverlayStatus.FAIL)

    def test_unrecognized_default_input_abstains_never_defaults_to_pass(self):
        """
        CRITICAL SAFETY TEST: If an image is presented with no preset hint and no matched patterns,
        CareLens must NOT return PASS. It must abstain with WARNING and manual-review finding.
        """
        b64 = self._create_high_contrast_image_b64()
        resp, meta = self.edge_engine.audit(
            image_b64=b64,
            preferred_backend="edge",
            preset_hint=None,  # No hint
        )
        self.assertNotEqual(resp.overall_status, OverallStatus.PASS)
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertTrue(any("abstaining" in f.lower() for f in resp.findings))
        self.assertIn("Manual clinical review required", resp.audio_alert_text)


if __name__ == "__main__":
    unittest.main()
