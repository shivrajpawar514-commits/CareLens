"""
CareLens Schema and Output Contract Tests.
Verifies strict adherence to canonical JSON contract, enums, coordinate constraints, and key rules.
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
        # Test out of range > 1000
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, 100, 1050, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )

        # Test inverted ymin > ymax
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[500, 100, 200, 400],
                status=OverlayStatus.PASS,
                detail="Test",
            )

        # Test inverted xmin > xmax
        with self.assertRaises(ValidationError):
            VisualOverlay(
                label="Dial",
                box_2d=[100, 600, 400, 200],
                status=OverlayStatus.PASS,
                detail="Test",
            )

    def test_audio_alert_word_count_limit(self):
        """audio_alert_text must be strictly fewer than 15 words."""
        # 16 words -> must fail validation
        long_alert = "This is a very long alert that definitely exceeds fifteen words in length and should be rejected immediately by the schema validator."
        with self.assertRaises(ValidationError):
            CareLensResponse(
                inspection_type=InspectionType.UNKNOWN,
                overall_status=OverallStatus.WARNING,
                vitals_extracted=VitalsExtracted(),
                visual_overlays=[],
                findings=[],
                audio_alert_text=long_alert,
            )

        # 9 words -> must pass
        valid_alert = "Verify the equipment setup against the approved clinical protocol."
        resp = CareLensResponse(
            inspection_type=InspectionType.UNKNOWN,
            overall_status=OverallStatus.WARNING,
            vitals_extracted=VitalsExtracted(),
            visual_overlays=[],
            findings=[],
            audio_alert_text=valid_alert,
        )
        self.assertEqual(resp.audio_alert_text, valid_alert)


if __name__ == "__main__":
    unittest.main()
