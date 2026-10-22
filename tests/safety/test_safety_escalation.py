"""
CareLens Clinical Safety and Risk Escalation Tests.
Ensures confirmed high-risk cases escalate to CRITICAL, uncertain cases remain WARNING,
and audio alerts never exceed 14 words.
"""

import unittest
from app.schema.contract import OverallStatus, VisualOverlay, OverlayStatus, VitalsExtracted
from app.protocol_engine.protocols import get_protocol
from app.protocol_engine.engine import ProtocolEngine
from app.alerts.voice_alert import VoiceAlertAdapter


class TestSafetyEscalation(unittest.TestCase):
    def setUp(self):
        self.proto = get_protocol("adult_icu_v1.0")
        self.engine = ProtocolEngine(self.proto)

    def test_air_in_line_critical_escalation(self):
        """Visible air bubble in IV line must immediately escalate to CRITICAL."""
        overlays = [
            VisualOverlay(
                label="Primary IV Tubing",
                box_2d=[200, 300, 600, 500],
                status=OverlayStatus.PASS,
                detail="Visible 1.5 cm air bubble in intravenous line segment.",
            )
        ]
        status, findings, crits = self.engine.evaluate_equipment(overlays, "adult")
        self.assertEqual(status, OverallStatus.CRITICAL)
        self.assertEqual(overlays[0].status, OverlayStatus.FAIL)
        self.assertTrue(any("air bubble" in c.lower() for c in crits))

    def test_uncertain_readings_yield_warning_not_failure(self):
        """Unreadable or N/A vital signs must result in WARNING or human verification, not false certainty."""
        vitals = VitalsExtracted(
            heart_rate_bpm="N/A",
            spo2_percent="N/A",
            blood_pressure_mmHg="N/A",
            respiration_rate="N/A",
        )
        status, findings, crits = self.engine.evaluate_vitals(vitals)
        # N/A vitals should never create a false CRITICAL alarm
        self.assertNotEqual(status, OverallStatus.CRITICAL)
        self.assertEqual(len(crits), 0)

    def test_audio_alert_safety_constraints(self):
        """All synthesized audio alerts must be imperative, under 15 words, and end with a period."""
        for status in [OverallStatus.CRITICAL, OverallStatus.WARNING, OverallStatus.PASS]:
            alert = self.engine.generate_audio_alert(status, ["Hypoxia"], "Patient_Monitor")
            sanitized = VoiceAlertAdapter.sanitize_alert_text(alert, status)
            word_count = len(sanitized.split())
            self.assertLess(word_count, 15, f"Alert exceeded word limit: '{sanitized}' ({word_count} words)")
            self.assertTrue(sanitized.endswith("."), f"Alert must end with period: '{sanitized}'")

    def test_closed_roller_clamp_during_infusion_flags_fail(self):
        """Infusion pump with closed roller clamp flags overlay as FAIL with WARNING status."""
        overlays = [
            VisualOverlay(
                label="Roller Clamp",
                box_2d=[400, 350, 700, 600],
                status=OverlayStatus.PASS,
                detail="Manual roller clamp is visibly closed while pump run state is active.",
            )
        ]
        status, findings, crits = self.engine.evaluate_equipment(overlays, "adult")
        self.assertEqual(status, OverallStatus.WARNING)
        self.assertEqual(overlays[0].status, OverlayStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
