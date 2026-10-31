"""
CareLens Cryptographic Audit Log Integrity Tests.
Verifies that audit records form a tamper-evident cryptographic hash chain,
and that any modification, reordering, deletion, or insertion is detected.
"""

import os
import json
import tempfile
import unittest
from datetime import datetime, timezone

from app.audit.logger import ClinicalAuditLogger, compute_record_hash, AuditRecord


class TestAuditIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.temp_dir.name, "test_audit_trail.jsonl")
        self.logger = ClinicalAuditLogger(log_file_path=self.log_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_log_integrity(self):
        """Newly created audit chain passes integrity verification."""
        # Add 3 records
        for i in range(3):
            meta = {
                "audit_id": f"aud_test_{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": "edge_cv",
                "protocol_id": "adult_icu_v1.0",
                "protocol_version": "1.0.0",
                "patient_context": "adult",
                "latency_ms": 12.0,
            }
            resp = {
                "inspection_type": "Equipment_Setup",
                "overall_status": "WARNING",
                "vitals_extracted": {},
                "findings": [f"Finding {i}"],
                "audio_alert_text": "Verify setup.",
            }
            self.logger.record_audit(meta, resp)

        result = self.logger.verify_integrity()
        self.assertTrue(result["valid"])
        self.assertEqual(result["record_count"], 3)
        self.assertEqual(len(result["errors"]), 0)
        self.assertIsNotNone(result["head_hash"])

    def test_genesis_hash_and_linkage(self):
        """First record must have 64 zeros as previous_hash; subsequent records link to prior hash."""
        meta1 = {"audit_id": "aud_1", "provider": "edge_cv", "protocol_id": "adult_icu_v1.0"}
        resp1 = {"inspection_type": "Equipment_Setup", "overall_status": "PASS"}
        rec1 = self.logger.record_audit(meta1, resp1)
        self.assertEqual(rec1.sequence_number, 0)
        self.assertEqual(rec1.previous_hash, "0" * 64)

        meta2 = {"audit_id": "aud_2", "provider": "edge_cv", "protocol_id": "adult_icu_v1.0"}
        resp2 = {"inspection_type": "Equipment_Setup", "overall_status": "CRITICAL"}
        rec2 = self.logger.record_audit(meta2, resp2)
        self.assertEqual(rec2.sequence_number, 1)
        self.assertEqual(rec2.previous_hash, rec1.record_hash)

    def test_detect_data_tampering(self):
        """Altering a field (e.g. changing status from CRITICAL to PASS) breaks integrity."""
        # Record 2 audits
        meta1 = {"audit_id": "aud_1", "provider": "edge_cv", "protocol_id": "adult_icu_v1.0"}
        resp1 = {"inspection_type": "Equipment_Setup", "overall_status": "CRITICAL", "findings": ["High risk"]}
        self.logger.record_audit(meta1, resp1)

        meta2 = {"audit_id": "aud_2", "provider": "edge_cv", "protocol_id": "adult_icu_v1.0"}
        resp2 = {"inspection_type": "Equipment_Setup", "overall_status": "WARNING", "findings": ["Warning"]}
        self.logger.record_audit(meta2, resp2)

        # Confirm clean log passes
        self.assertTrue(self.logger.verify_integrity()["valid"])

        # Tamper: Read file, modify record 0 overall_status from CRITICAL to PASS, write back
        lines = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                lines.append(json.loads(line))

        # Tamper record 0
        lines[0]["overall_status"] = "PASS"

        with open(self.log_path, "w", encoding="utf-8") as f:
            for l in lines:
                f.write(json.dumps(l) + "\n")

        # Verification must now FAIL
        tampered_result = self.logger.verify_integrity()
        self.assertFalse(tampered_result["valid"])
        self.assertTrue(any("tampering detected" in err.lower() or "mismatch" in err.lower() for err in tampered_result["errors"]))

    def test_detect_record_deletion(self):
        """Deleting a record breaks sequence continuity and hash linkage."""
        for i in range(3):
            meta = {"audit_id": f"aud_{i}", "provider": "edge_cv", "protocol_id": "adult_icu_v1.0"}
            resp = {"inspection_type": "Equipment_Setup", "overall_status": "PASS"}
            self.logger.record_audit(meta, resp)

        # Read records and delete the middle one (index 1)
        lines = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                lines.append(json.loads(line))

        del lines[1]  # Delete middle record

        with open(self.log_path, "w", encoding="utf-8") as f:
            for l in lines:
                f.write(json.dumps(l) + "\n")

        tampered_result = self.logger.verify_integrity()
        self.assertFalse(tampered_result["valid"])
        self.assertTrue(any("sequence break" in err.lower() or "mismatch" in err.lower() for err in tampered_result["errors"]))

    def test_clinician_acknowledgement_preserves_hash_chain(self):
        """Clinician acknowledgement is recorded as an append-only block and preserves chain validity."""
        meta = {"audit_id": "aud_urgent_101", "provider": "edge_cv", "protocol_id": "pediatric_icu_v1.0"}
        resp = {"inspection_type": "Equipment_Setup", "overall_status": "CRITICAL", "findings": ["O2 overflow"]}
        self.logger.record_audit(meta, resp)

        ack_rec = self.logger.acknowledge_audit(
            audit_id="aud_urgent_101",
            clinician_id="Dr. Miller",
            action_taken="Down-titrated pediatric flow to 1.5 L/min.",
            notes="Patient breathing comfortably.",
        )
        self.assertIsNotNone(ack_rec)

        # Integrity verification must pass on the extended chain
        result = self.logger.verify_integrity()
        self.assertTrue(result["valid"])
        self.assertEqual(result["record_count"], 2)


if __name__ == "__main__":
    unittest.main()
