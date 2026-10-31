"""
CareLens Protocol Threshold Boundaries and Protocol Versions Automated Test Suite.
Verifies all clinical reference threshold boundaries (heart rate, SpO2, blood pressure,
respiration rate, and oxygen flow meter titration limits) and validates protocol versioning.
"""

import unittest
from app.schema.contract import VitalsExtracted, OverallStatus, VisualOverlay, OverlayStatus
from app.protocol_engine.protocols import CLINICAL_PROTOCOLS, get_protocol
from app.protocol_engine.engine import ProtocolEngine


class TestProtocolThresholdBoundaries(unittest.TestCase):
    def setUp(self):
        self.adult_proto = get_protocol("adult_icu_v1.0")
        self.adult_engine = ProtocolEngine(self.adult_proto)
        self.pediatric_proto = get_protocol("pediatric_icu_v1.0")
        self.pediatric_engine = ProtocolEngine(self.pediatric_proto)
        self.neonatal_proto = get_protocol("neonatal_icu_v1.0")
        self.neonatal_engine = ProtocolEngine(self.neonatal_proto)

    def test_protocol_versions_integrity(self):
        """Verify all registered protocols have valid identifiers, versions, and populations."""
        expected_protocols = ["adult_icu_v1.0", "pediatric_icu_v1.0", "neonatal_icu_v1.0"]
        for proto_id in expected_protocols:
            self.assertIn(proto_id, CLINICAL_PROTOCOLS)
            proto = CLINICAL_PROTOCOLS[proto_id]
            self.assertEqual(proto.protocol_id, proto_id)
            self.assertEqual(proto.version, "1.0.0")
            self.assertTrue(len(proto.population) > 0)
            self.assertTrue(len(proto.description) > 0)

        # Test unknown protocol falls back safely to default protocol
        fallback = get_protocol("non_existent_protocol_v99")
        self.assertEqual(fallback.protocol_id, "adult_icu_v1.0")

    def test_adult_heart_rate_threshold_boundaries(self):
        """
        Adult HR: nominal 60-100 bpm.
        Critical Low <= 45 bpm.
        Critical High >= 130 bpm.
        """
        # Critical Bradycardia boundary: HR 45 (CRITICAL) vs HR 46 (WARNING)
        v45 = VitalsExtracted(heart_rate_bpm="45")
        st, _, crits = self.adult_engine.evaluate_vitals(v45)
        self.assertEqual(st, OverallStatus.CRITICAL)
        self.assertTrue(any("bradycardia" in c.lower() for c in crits))

        v46 = VitalsExtracted(heart_rate_bpm="46")
        st, _, crits = self.adult_engine.evaluate_vitals(v46)
        self.assertEqual(st, OverallStatus.WARNING)
        self.assertEqual(len(crits), 0)

        # Lower nominal boundary: HR 59 (WARNING) vs HR 60 (PASS)
        v59 = VitalsExtracted(heart_rate_bpm="59")
        st, _, crits = self.adult_engine.evaluate_vitals(v59)
        self.assertEqual(st, OverallStatus.WARNING)

        v60 = VitalsExtracted(heart_rate_bpm="60")
        st, _, crits = self.adult_engine.evaluate_vitals(v60)
        self.assertEqual(st, OverallStatus.PASS)

        # Upper nominal boundary: HR 100 (PASS) vs HR 101 (WARNING)
        v100 = VitalsExtracted(heart_rate_bpm="100")
        st, _, crits = self.adult_engine.evaluate_vitals(v100)
        self.assertEqual(st, OverallStatus.PASS)

        v101 = VitalsExtracted(heart_rate_bpm="101")
        st, _, crits = self.adult_engine.evaluate_vitals(v101)
        self.assertEqual(st, OverallStatus.WARNING)

        # Critical Tachycardia boundary: HR 129 (WARNING) vs HR 130 (CRITICAL)
        v129 = VitalsExtracted(heart_rate_bpm="129")
        st, _, crits = self.adult_engine.evaluate_vitals(v129)
        self.assertEqual(st, OverallStatus.WARNING)

        v130 = VitalsExtracted(heart_rate_bpm="130")
        st, _, crits = self.adult_engine.evaluate_vitals(v130)
        self.assertEqual(st, OverallStatus.CRITICAL)
        self.assertTrue(any("tachycardia" in c.lower() for c in crits))

    def test_adult_spo2_threshold_boundaries(self):
        """
        Adult SpO2: nominal >= 94%.
        Warning <= 93%.
        Critical Desaturation <= 88%.
        """
        # Critical Desaturation: SpO2 88% (CRITICAL) vs SpO2 89% (WARNING)
        v88 = VitalsExtracted(spo2_percent="88")
        st, _, crits = self.adult_engine.evaluate_vitals(v88)
        self.assertEqual(st, OverallStatus.CRITICAL)

        v89 = VitalsExtracted(spo2_percent="89")
        st, _, crits = self.adult_engine.evaluate_vitals(v89)
        self.assertEqual(st, OverallStatus.WARNING)

        # Warning vs Nominal: SpO2 93% (WARNING) vs SpO2 94% (PASS)
        v93 = VitalsExtracted(spo2_percent="93")
        st, _, crits = self.adult_engine.evaluate_vitals(v93)
        self.assertEqual(st, OverallStatus.WARNING)

        v94 = VitalsExtracted(spo2_percent="94")
        st, _, crits = self.adult_engine.evaluate_vitals(v94)
        self.assertEqual(st, OverallStatus.PASS)

    def test_adult_blood_pressure_threshold_boundaries(self):
        """
        Adult Systolic BP: nominal 90-140 mmHg.
        Critical Low <= 80 mmHg.
        Critical High >= 180 mmHg.
        """
        # Critical Hypotension: Systolic 80 (CRITICAL) vs 81 (WARNING)
        v80 = VitalsExtracted(blood_pressure_mmHg="80/50")
        st, _, crits = self.adult_engine.evaluate_vitals(v80)
        self.assertEqual(st, OverallStatus.CRITICAL)

        v81 = VitalsExtracted(blood_pressure_mmHg="81/50")
        st, _, crits = self.adult_engine.evaluate_vitals(v81)
        self.assertEqual(st, OverallStatus.WARNING)

        # Nominal lower boundary: 89 (WARNING) vs 90 (PASS)
        v89 = VitalsExtracted(blood_pressure_mmHg="89/55")
        st, _, crits = self.adult_engine.evaluate_vitals(v89)
        self.assertEqual(st, OverallStatus.WARNING)

        v90 = VitalsExtracted(blood_pressure_mmHg="90/60")
        st, _, crits = self.adult_engine.evaluate_vitals(v90)
        self.assertEqual(st, OverallStatus.PASS)

        # Nominal upper boundary: 140 (PASS) vs 141 (WARNING)
        v140 = VitalsExtracted(blood_pressure_mmHg="140/90")
        st, _, crits = self.adult_engine.evaluate_vitals(v140)
        self.assertEqual(st, OverallStatus.PASS)

        v141 = VitalsExtracted(blood_pressure_mmHg="141/90")
        st, _, crits = self.adult_engine.evaluate_vitals(v141)
        self.assertEqual(st, OverallStatus.WARNING)

        # Critical Hypertension: 179 (WARNING) vs 180 (CRITICAL)
        v179 = VitalsExtracted(blood_pressure_mmHg="179/110")
        st, _, crits = self.adult_engine.evaluate_vitals(v179)
        self.assertEqual(st, OverallStatus.WARNING)

        v180 = VitalsExtracted(blood_pressure_mmHg="180/115")
        st, _, crits = self.adult_engine.evaluate_vitals(v180)
        self.assertEqual(st, OverallStatus.CRITICAL)

    def test_adult_respiration_rate_threshold_boundaries(self):
        """
        Adult RR: nominal 12-20 breaths/min.
        Critical Low <= 8.
        Critical High >= 30.
        """
        # Critical Bradypnea: RR 8 (CRITICAL) vs RR 9 (WARNING)
        v8 = VitalsExtracted(respiration_rate="8")
        st, _, crits = self.adult_engine.evaluate_vitals(v8)
        self.assertEqual(st, OverallStatus.CRITICAL)

        v9 = VitalsExtracted(respiration_rate="9")
        st, _, crits = self.adult_engine.evaluate_vitals(v9)
        self.assertEqual(st, OverallStatus.WARNING)

        # Nominal lower boundary: 11 (WARNING) vs 12 (PASS)
        v11 = VitalsExtracted(respiration_rate="11")
        st, _, crits = self.adult_engine.evaluate_vitals(v11)
        self.assertEqual(st, OverallStatus.WARNING)

        v12 = VitalsExtracted(respiration_rate="12")
        st, _, crits = self.adult_engine.evaluate_vitals(v12)
        self.assertEqual(st, OverallStatus.PASS)

        # Nominal upper boundary: 20 (PASS) vs 21 (WARNING)
        v20 = VitalsExtracted(respiration_rate="20")
        st, _, crits = self.adult_engine.evaluate_vitals(v20)
        self.assertEqual(st, OverallStatus.PASS)

        v21 = VitalsExtracted(respiration_rate="21")
        st, _, crits = self.adult_engine.evaluate_vitals(v21)
        self.assertEqual(st, OverallStatus.WARNING)

        # Critical Tachypnea: 29 (WARNING) vs 30 (CRITICAL)
        v29 = VitalsExtracted(respiration_rate="29")
        st, _, crits = self.adult_engine.evaluate_vitals(v29)
        self.assertEqual(st, OverallStatus.WARNING)

        v30 = VitalsExtracted(respiration_rate="30")
        st, _, crits = self.adult_engine.evaluate_vitals(v30)
        self.assertEqual(st, OverallStatus.CRITICAL)

    def test_oxygen_flow_meter_threshold_boundaries(self):
        """
        Pediatric O2: max 2.0 L/min.
        Adult nasal cannula: max 6.0 L/min.
        """
        # Pediatric: 2.0 L/min is PASS; 2.1 L/min is CRITICAL
        ov_ped_safe = [
            VisualOverlay(
                label="Oxygen Flow Meter",
                box_2d=[100, 100, 400, 400],
                status=OverlayStatus.PASS,
                detail="Observed flow rate: 2.0 L/min via pediatric cannula.",
            )
        ]
        st, _, crits = self.pediatric_engine.evaluate_equipment(ov_ped_safe, "pediatric")
        self.assertEqual(st, OverallStatus.PASS)

        ov_ped_crit = [
            VisualOverlay(
                label="Oxygen Flow Meter",
                box_2d=[100, 100, 400, 400],
                status=OverlayStatus.PASS,
                detail="Observed flow rate: 2.1 L/min via pediatric cannula.",
            )
        ]
        st, _, crits = self.pediatric_engine.evaluate_equipment(ov_ped_crit, "pediatric")
        self.assertEqual(st, OverallStatus.CRITICAL)
        self.assertEqual(ov_ped_crit[0].status, OverlayStatus.FAIL)

        # Adult nasal cannula: 6.0 L/min is PASS; 6.1 L/min is WARNING
        ov_adult_safe = [
            VisualOverlay(
                label="Oxygen Flow Meter",
                box_2d=[100, 100, 400, 400],
                status=OverlayStatus.PASS,
                detail="Observed flow rate: 6.0 L/min via nasal cannula.",
            )
        ]
        st, _, crits = self.adult_engine.evaluate_equipment(ov_adult_safe, "adult")
        self.assertEqual(st, OverallStatus.PASS)

        ov_adult_warn = [
            VisualOverlay(
                label="Oxygen Flow Meter",
                box_2d=[100, 100, 400, 400],
                status=OverlayStatus.PASS,
                detail="Observed flow rate: 6.5 L/min via nasal cannula.",
            )
        ]
        st, _, crits = self.adult_engine.evaluate_equipment(ov_adult_warn, "adult")
        self.assertEqual(st, OverallStatus.WARNING)


if __name__ == "__main__":
    unittest.main()
