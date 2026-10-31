"""
CareLens Schema and Output Contract Tests.
Verifies strict adherence to canonical JSON contract, enums, coordinate constraints,
extra-key rejections, and audio alert word-count rules.
"""

import unittest
from pydantic import ValidationError
from app.schema.contract import (
    CareLensResponse,
    InspectionType,
    OverallStatus,
    OverlayStatus,
    VisualOverlay,
    VitalsExtracted,
)


class TestCareLensSchema(unittest.TestCase):
    def test_canonical_valid_response(self):
        """Test that a fully specified canonical response validates correctly."""
        data = {
            "inspection_type": "Equipment_Setup",
            "overall_status": "WARNING",
            "vitals_extracted": {
                "heart_rate_bpm": "N/A",
                "spo2_percent": "N/A",
                "blood_pressure_mmHg": "N/A",
                "respiration_rate": "N/A",
            },
            "visual_overlays": [
                {
                    "label": "Example component",
                    "box_2d": [100, 100, 400, 400],
                    "status": "PASS",
                    "detail": "Visible observation only; verify against the applicable protocol.",
                }
            ],
            "findings": [
                "Describe visible evidence without asserting details that cannot be confirmed."
            ],
            "audio_alert_text": "Verify the setup against the approved clinical protocol.",
        }
        resp = CareLensResponse.model_validate(data)
        self.assertEqual(resp.inspection_type, InspectionType.EQUIPMENT_SETUP)
        self.assertEqual(resp.overall_status, OverallStatus.WARNING)
        self.assertEqual(resp.vitals_extracted.heart_rate_bpm, "N/A")
        self.assertEqual(len(resp.visual_overlays), 1)
        self.assertEqual(resp.visual_overlays[0].box_2d, [100, 100, 400, 400])

    def test_forbid_extra_keys(self):
        """Contract rule: strictly forbid extra keys not in canonical schema."""
        data = {
            "inspection_type": "Equipment_Setup",
            "overall_status": "PASS",
            "vitals_extracted": {
                "heart_rate_bpm": "N/A",
                "spo2_percent": "N/A",
                "blood_pressure_mmHg": "N/A",
                "respiration_rate": "N/A",
            },
            "visual_overlays": [],
            "findings": ["Test"],
            "audio_alert_text": "Verify setup.",
            "unauthorized_extra_key": "should_fail",
        }
        with self.assertRaises(ValidationError):
            CareLensResponse.model_validate(data)

    def test_forbid_extra_keys_in_nested_models(self):
        """Strictly forbid extra keys in vitals and visual overlays."""
        # Extra key in vitals_extracted
        with self.assertRaises(ValidationError):
            VitalsExtracted.model_validate({
                "heart_rate_bpm": "70",
                "spo2_percent": "98",
                "blood_pressure_mmHg": "120/80",
                "respiration_rate": "16",
                "extra_vital": "123",
            })

        # Extra key in visual_overlays
        with self.assertRaises(ValidationError):
            VisualOverlay.model_validate({
                "label": "Dial",
                "box_2d": [0, 0, 100, 100],
                "status": "PASS",
                "detail": "Ok",
                "confidence_score": 0.99,
            })

    def test_invalid_enums_rejected(self):
        """Enums must be strictly Equipment_Setup, Patient_Monitor, or Unknown."""
        data = {
            "inspection_type": "Ventilator_Screen",  # Invalid enum
            "overall_status": "PASS",
            "vitals_extracted": {
                "heart_rate_bpm": "N/A",
                "spo2_percent": "N/A",
                "blood_pressure_mmHg": "N/A",
                "respiration_rate": "N/A",
            },
            "visual_overlays": [],
            "findings": [],
            "audio_alert_text": "Verify setup.",
        }
        with self.assertRaises(ValidationError):
            CareLensResponse.model_validate(data)

    def test_box_2d_coordinate_constraints(self):
        """Coordinates must be 4 integers in [0..1000] with ymin <= ymax and xmin <= xmax."""
        # Valid boundary coordinates
        ov_min = VisualOverlay(label="Min", box_2d=[0, 0, 0, 0], status=OverlayStatus.PASS, detail="Min")
        self.assertEqual(ov_min.box_2d, [0, 0, 0, 0])

        ov_max = VisualOverlay(label="Max", box_2d=[0, 0, 1000, 1000], status=OverlayStatus.PASS, detail="Max")
        self.assertEqual(ov_max.box_2d, [0, 0, 1000, 1000])

        # Test out of range > 1000
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, 100, 1001, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )

        # Test negative coordinates
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[-1, 100, 500, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, -5, 500, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )

        # Test inverted ymin > ymax
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[600, 100, 500, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )

        # Test inverted xmin > xmax
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, 600, 500, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )

        # Test wrong length (3 elements or 5 elements)
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, 100, 500],
                status=OverlayStatus.PASS,
                detail="Test",
            )
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, 100, 500, 500, 600],
                status=OverlayStatus.PASS,
                detail="Test",
            )

    def test_audio_alert_word_count_limit(self):
        """audio_alert_text must be strictly fewer than 15 words."""
        # 14 words: should pass
        fourteen_words = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen."
        resp = CareLensResponse(
            inspection_type=InspectionType.EQUIPMENT_SETUP,
            overall_status=OverallStatus.PASS,
            vitals_extracted=VitalsExtracted(),
            visual_overlays=[],
            findings=[],
            audio_alert_text=fourteen_words,
        )
        self.assertEqual(resp.audio_alert_text, fourteen_words)

        # 15 words: must fail validation
        fifteen_words = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen."
        with self.assertRaises(ValidationError):
            CareLensResponse(
                inspection_type=InspectionType.EQUIPMENT_SETUP,
                overall_status=OverallStatus.PASS,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=[],
                findings=[],
                audio_alert_text=fifteen_words,
            )

        # Empty string: must fail
        with self.assertRaises(ValidationError):
            CareLensResponse(
                inspection_type=InspectionType.EQUIPMENT_SETUP,
                overall_status=OverallStatus.PASS,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=[],
                findings=[],
                audio_alert_text="",
            )


if __name__ == "__main__":
    unittest.main()
