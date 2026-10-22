"""
CareLens Protocol Tests.
Validates reference thresholds, adult vs pediatric oxygen limits, and vital signs evaluation.
"""

import unittest
from app.schema.contract import VitalsExtracted, OverallStatus, VisualOverlay, OverlayStatus
from app.protocol_engine.protocols import get_protocol
from app.protocol_engine.engine import ProtocolEngine


class TestProtocolEngine(unittest.TestCase):
    def test_adult_nominal_vitals(self):
        """Adult vitals in normal range return PASS."""
        proto = get_protocol("adult_icu_v1.0")
        engine = ProtocolEngine(proto)
        vitals = VitalsExtracted(
            heart_rate_bpm="75",
            spo2_percent="98",
            blood_pressure_mmHg="120/80",
            respiration_rate="16",
        )
        status, findings, crits = engine.evaluate_vitals(vitals)
        self.assertEqual(status, OverallStatus.PASS)
        self.assertEqual(len(crits), 0)

    def test_pediatric_critical_oxygen_flow(self):
        """Pediatric flow meter reading > 2.0 L/min escalates to CRITICAL."""
        proto = get_protocol("pediatric_icu_v1.0")
        engine = ProtocolEngine(proto)
        overlays = [
            VisualOverlay(
                label="Oxygen Flow Meter",
                box_2d=[100, 100, 400, 400],
                status=OverlayStatus.PASS,
                detail="Observed flow rate: 8.0 L/min via nasal cannula.",
            )
        ]
        status, findings, crits = engine.evaluate_equipment(overlays, patient_context="pediatric")
        self.assertEqual(status, OverallStatus.CRITICAL)
        self.assertTrue(any("exceeds pediatric threshold" in f for f in findings))
        self.assertEqual(overlays[0].status, OverlayStatus.FAIL)

    def test_pediatric_nominal_oxygen_flow(self):
        """Pediatric flow meter reading 1.0 L/min (<= 2.0) returns PASS."""
        proto = get_protocol("pediatric_icu_v1.0")
        engine = ProtocolEngine(proto)
        overlays = [
            VisualOverlay(
                label="Oxygen Flow Meter",
                box_2d=[100, 100, 400, 400],
                status=OverlayStatus.PASS,
                detail="Observed flow rate: 1.0 L/min via nasal cannula.",
            )
        ]
        status, findings, crits = engine.evaluate_equipment(overlays, patient_context="pediatric")
        self.assertEqual(status, OverallStatus.PASS)
        self.assertEqual(overlays[0].status, OverlayStatus.PASS)

    def test_critical_hypoxia_escalation(self):
        """SpO2 <= 88% in adult ICU protocol triggers CRITICAL status."""
        proto = get_protocol("adult_icu_v1.0")
        engine = ProtocolEngine(proto)
        vitals = VitalsExtracted(
            heart_rate_bpm="95",
            spo2_percent="84",  # Critical desaturation
            blood_pressure_mmHg="115/75",
            respiration_rate="22",
        )
        status, findings, crits = engine.evaluate_vitals(vitals)
        self.assertEqual(status, OverallStatus.CRITICAL)
        self.assertTrue(any("desaturation" in c.lower() for c in crits))

    def test_neonatal_hyperoxia_warning(self):
        """SpO2 > 97% in neonatal preterm protocol triggers WARNING."""
        proto = get_protocol("neonatal_icu_v1.0")
        engine = ProtocolEngine(proto)
        vitals = VitalsExtracted(
            heart_rate_bpm="135",
            spo2_percent="99",  # Hyperoxia concern in neonates
            blood_pressure_mmHg="70/45",
            respiration_rate="40",
        )
        status, findings, crits = engine.evaluate_vitals(vitals)
        self.assertEqual(status, OverallStatus.WARNING)
        self.assertTrue(any("hyperoxia" in f.lower() for f in findings))


if __name__ == "__main__":
    unittest.main()
